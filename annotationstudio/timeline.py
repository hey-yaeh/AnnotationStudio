"""Dynamic overlapping tracks with transactional edge/center dragging."""
from __future__ import annotations
import math
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QEvent, QSignalBlocker
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QScrollArea, QScrollBar, QMenu, QFrame, QCheckBox
from .theme import category_color, PALETTE
from .models import track_temporal_kind
from .ontology import ACTIVITY_EPISODE, LABEL_PRESETS, LEGACY_MOTION_RELATION, category_workspace
from .affect_display import annotation_caption


def workspace_for_track(track):
    """Present the current taxonomy without rewriting an imported track."""
    if track.category in LABEL_PRESETS or track.category == LEGACY_MOTION_RELATION:
        return category_workspace(track.category)
    return track.workspace

LABEL_W = 222
HEADER_H = 0
RULER_H = 28
GROUP_H = 25
LANE_H = 28
ROW_H = 46
REFERENCE_LANE_H = 16
GESTURE_REFERENCE_CHANNELS = ('Left Arm', 'Right Arm', 'Left Hand', 'Right Hand', 'Hands')


def is_gesture_motion_reference(annotation):
    return (annotation.category == 'Motion Primitive' and annotation.role in ('R01', 'R02')
            and annotation.channel in GESTURE_REFERENCE_CHANNELS and str(annotation.source).startswith('auto:')
            and annotation.status != 'rejected' and annotation.temporal_kind == 'interval')


def assign_lanes(annotations, point_span_s=1e-6):
    """Stable interval partition: overlapping events remain independently editable."""
    ends, assigned = [], {}
    for a in sorted(annotations, key=lambda a: (a.start_s, a.end_s, a.id)):
        point = getattr(a, 'temporal_kind', 'interval') == 'point'
        start = a.start_s - point_span_s / 2 if point else a.start_s
        finish = a.end_s + point_span_s / 2 if point else a.end_s
        lane = next((i for i, end in enumerate(ends) if end <= start + 1e-9), len(ends))
        if lane == len(ends): ends.append(finish)
        else: ends[lane] = finish
        assigned[a.id] = lane
    return assigned, max(1, len(ends))


class TimelineCanvas(QWidget):
    annotationSelected = Signal(str)
    newRange = Signal(float, float, str)
    newPoint = Signal(float, str)
    seekRequested = Signal(float)
    contextAction = Signal(str, str)
    trackAction = Signal(str, str)
    laneChanged = Signal(str)
    spanChanged = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(500)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.tracks, self.annotations = [], []
        self.editing = None
        self.selected_id = None
        self.active_track_id = None
        self.duration_s, self.visible_start, self.px_per_s, self.time_s = 120., 0., 18., 0.
        self.filter_role, self.workspace, self.category_filter = 'All', 'Motion', 'All'
        self.pending_only = False
        self.hide_legacy_tracks = False
        self.show_motion_references = True
        self.collapsed = set()
        self.snap = True
        self.frame_step = 1 / 120
        self.snap_offset = 0.
        self.audio, self.aoi = {}, {}
        self.rows, self._lane_map = [], {}
        self._drag, self._new, self._preview = None, None, None
        self._rebuild()

    def visible_tracks(self):
        return sorted([t for t in self.tracks if t.visible
                       and not (self.hide_legacy_tracks and t.category == LEGACY_MOTION_RELATION)
                       and (self.filter_role == 'All' or t.role in (self.filter_role, 'Both', 'Scene'))
                       and (self.workspace in ('Overview', 'Review') or workspace_for_track(t) == self.workspace)
                       and (self.category_filter == 'All' or t.category == self.category_filter)], key=lambda t: t.order)

    def effective_annotations(self):
        values = [a for a in self.annotations if not self.editing or a.id != self.editing.id]
        if self.editing: values.append(self.editing)
        if self.pending_only:
            values = [a for a in values if a.status == 'pending' or (self.editing and a.id == self.editing.id)]
        return values

    def _motion_references_by_actor(self):
        if self.workspace != 'Gesture' or not self.show_motion_references:
            return {}
        tracks = {track.id: track for track in self.tracks if track.visible and track.category == 'Motion Primitive'
                  and self.filter_role in ('All', track.role)}
        references = {}
        for annotation in self.annotations:
            track = tracks.get(annotation.track_id)
            if track and track.role == annotation.role and is_gesture_motion_reference(annotation):
                references.setdefault(annotation.role, []).append(annotation)
        return references

    def _rebuild(self):
        self.rows, self._lane_map = [], {}
        tracks = self.visible_tracks()
        references = self._motion_references_by_actor()
        roles = list(dict.fromkeys([t.role for t in tracks] + list(references)))
        y = HEADER_H
        events = self.effective_annotations()
        for role in roles:
            own = [t for t in tracks if t.role == role]
            self.rows.append({'kind': 'group', 'role': role, 'y': y, 'height': GROUP_H, 'count': len(own)})
            y += GROUP_H
            if role in self.collapsed: continue
            items = references.get(role)
            if items:
                lanes, n = assign_lanes(items)
                self._lane_map.update(lanes)
                h = max(28, n * REFERENCE_LANE_H + 6)
                self.rows.append({'kind': 'reference', 'role': role, 'items': items, 'y': y, 'height': h})
                y += h
            for track in own:
                items = [a for a in events if a.track_id == track.id and a.status != 'rejected']
                lanes, n = assign_lanes(items, 18 / self.px_per_s)
                self._lane_map.update(lanes)
                h = max(ROW_H, n * LANE_H + 12)
                self.rows.append({'kind': 'track', 'track': track, 'y': y, 'height': h})
                y += h
        self.setMinimumHeight(max(110, y + 6))
        self.update()

    def set_data(self, tracks, annotations, editing=None):
        self.tracks, self.annotations, self.editing = tracks, annotations, editing
        self._rebuild()

    def set_annot(self, annotations):
        self.annotations = annotations; self._rebuild()

    def set_workspace(self, workspace, category='All'):
        self.workspace, self.category_filter = workspace, category
        self.pending_only = workspace == 'Review'
        self._rebuild()

    def set_role_filter(self, role):
        self.filter_role = role; self._rebuild()

    def set_hide_legacy_tracks(self, hidden):
        self.hide_legacy_tracks = hidden
        self._rebuild()

    def set_show_motion_references(self, show):
        self.show_motion_references = show
        self._rebuild()

    def set_time(self, t): self.time_s = t; self.update()
    def set_audio(self, role, times, values): self.audio[role] = (times, values); self.update()
    def set_aoi(self, role, events): self.aoi[role] = events; self.update()
    def time_x(self, t): return LABEL_W + (t-self.visible_start)*self.px_per_s
    def x_time(self, x): return max(0., min(self.duration_s, self.visible_start+(x-LABEL_W)/self.px_per_s))
    def time_visible_span(self): return max(.05, (self.width()-LABEL_W)/self.px_per_s)
    def snapped(self, value, mods=Qt.NoModifier):
        if self.snap and not mods & Qt.ShiftModifier and self.frame_step > 0:
            value = self.snap_offset + round((value-self.snap_offset) / self.frame_step) * self.frame_step
        return max(0., min(self.duration_s, value))
    def row_at(self, y): return next((r for r in self.rows if r['y'] <= y < r['y']+r['height']), None)
    def lane_at(self, y):
        row = self.row_at(y)
        return row['track'] if row and row['kind'] == 'track' else None

    def annotation_rect(self, a):
        if self.workspace == 'Gesture' and is_gesture_motion_reference(a):
            row = next((r for r in self.rows if r['kind'] == 'reference' and r['role'] == a.role), None)
            if row is None or a.id not in self._lane_map:
                return None
            y = row['y'] + 4 + self._lane_map[a.id] * REFERENCE_LANE_H
            return QRectF(self.time_x(a.start_s), y, max(3., (a.end_s-a.start_s)*self.px_per_s), REFERENCE_LANE_H-3)
        row = next((r for r in self.rows if r['kind'] == 'track' and r['track'].id == a.track_id), None)
        if not row: return None
        y = row['y'] + 7 + self._lane_map.get(a.id, 0) * LANE_H
        if getattr(a, 'temporal_kind', 'interval') == 'point':
            return QRectF(self.time_x(a.start_s)-8, y, 16, LANE_H-5)
        return QRectF(self.time_x(a.start_s), y, max(3., (a.end_s-a.start_s)*self.px_per_s), LANE_H-5)

    def _annotation_at(self, x, y, *, reference=False):
        row = self.row_at(y)
        if x < LABEL_W or not row or row['kind'] != ('reference' if reference else 'track'):
            return None
        items = row['items'] if reference else self.effective_annotations()
        for a in reversed(items):
            if a.status == 'rejected' or (not reference and a.track_id != row['track'].id): continue
            r = self.annotation_rect(a)
            if r and r.adjusted(-2, 0, 2, 0).contains(QPointF(x, y)): return a
        return None

    def _draw_wave(self, p, role, row, end):
        if role not in self.audio: return
        times, values = self.audio[role]
        mask = (times >= self.visible_start) & (times <= end)
        ts, vs = times[mask], values[mask]
        stride = max(1, len(ts) // max(1, self.width()-LABEL_W))
        cy = row['y'] + row['height']/2
        p.setPen(QPen(QColor('#DDD5C6'), 1))
        for tm, value in zip(ts[::stride], vs[::stride]):
            x, h = self.time_x(float(tm)), min(1., float(value)) * min(17., row['height']*.35)
            p.drawLine(QPointF(x, cy-h), QPointF(x, cy+h))

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor('#FEFDFB'))
        end = min(self.duration_s, self.visible_start+self.time_visible_span())
        for row in self.rows:
            y, rh = row['y'], row['height']
            if row['kind'] == 'group':
                p.fillRect(QRectF(0, y, w, rh), QColor('#EFEAE1'))
                p.setPen(QColor('#857461')); p.setFont(QFont('Segoe UI', 8, QFont.DemiBold))
                arrow = '▸' if row['role'] in self.collapsed else '▾'
                p.drawText(QRectF(12, y, LABEL_W-15, rh), Qt.AlignVCenter,
                           f"{arrow}  {row['role']}   /   {row['count']} TRACKS")
                continue
            if row['kind'] == 'reference':
                p.fillRect(QRectF(0, y, w, rh), QColor('#F3F8F6'))
                p.setPen(QColor('#496C60')); p.setFont(QFont('Segoe UI', 8, QFont.DemiBold))
                p.drawText(QRectF(24, y, LABEL_W-40, rh), Qt.AlignVCenter, 'Motion refs · arms / hands')
                continue
            track = row['track']
            p.fillRect(QRectF(0, y, LABEL_W, rh), QColor('#F6F0E6' if track.id == self.active_track_id else '#FAF8F3'))
            p.setPen(QPen(QColor('#ECE7DF'), 1)); p.drawLine(QPointF(0, y+rh), QPointF(w, y+rh))
            p.setPen(Qt.NoPen); p.setBrush(QColor(track.color or PALETTE.get(track.category, '#8E7E63')))
            p.drawRoundedRect(QRectF(12, y+11, 4, rh-22), 2, 2)
            p.setPen(QColor('#4B3D32')); p.setFont(QFont('Segoe UI', 9, QFont.DemiBold))
            title = p.fontMetrics().elidedText(track.name, Qt.ElideRight, LABEL_W-44)
            p.drawText(QRectF(24, y+6, LABEL_W-40, 19), Qt.AlignVCenter, title)
            p.setPen(QColor('#9B8C7B')); p.setFont(QFont('Segoe UI', 7))
            kind_hint = ' · point' if track_temporal_kind(track) == 'point' else ''
            subtitle = p.fontMetrics().elidedText(track.category + kind_hint, Qt.ElideRight, LABEL_W-40)
            p.drawText(QRectF(24, y+25, LABEL_W-40, 15), Qt.AlignVCenter, subtitle)
            if track.workspace == 'Speech': self._draw_wave(p, track.role, row, end)
            if track.workspace == 'Gaze':
                p.setPen(Qt.NoPen); p.setBrush(QColor('#DCE7D9'))
                for a, b, label in self.aoi.get(track.role, []):
                    x0, x1 = max(LABEL_W, self.time_x(a)), min(w, self.time_x(b))
                    if x1 > x0: p.drawRoundedRect(QRectF(x0, y+8, x1-x0, 20), 3, 3)
        p.save(); p.setClipRect(QRectF(LABEL_W, HEADER_H, max(0, w-LABEL_W), h))
        # Grid behind candidates. Aim for readable ~80 px labels.
        target = 80 / self.px_per_s
        step = next((v for v in (.05,.1,.2,.5,1,2,5,10,20,30,60,120,300,600) if v >= target), 1200)
        ticks = []
        tick = math.floor(self.visible_start/step)*step
        while tick <= end+step:
            x = self.time_x(tick); ticks.append((x, tick))
            p.setPen(QPen(QColor('#E9E2D8'), .6)); p.drawLine(QPointF(x, HEADER_H), QPointF(x, h))
            tick += step
        for a in self.effective_annotations():
            if a.status == 'rejected' or a.end_s < self.visible_start or a.start_s > end: continue
            r = self.annotation_rect(a)
            if not r: continue
            track = next((t for t in self.tracks if t.id == a.track_id), None)
            editing = bool(self.editing and self.editing.id == a.id)
            reference = self.workspace == 'Gesture' and is_gesture_motion_reference(a)
            if reference:
                fill, edge = QColor('#DDEAE5'), QColor('#638578')
            else:
                fill = category_color(a.category, a.status, editing, track.color if track else '')
                edge = QColor('#713C26') if editing else fill.darker(125 if a.status == 'approved' else 103)
            p.setBrush(fill); p.setPen(QPen(edge, 1.8 if editing else .8, Qt.DashLine if reference else Qt.SolidLine))
            if getattr(a, 'temporal_kind', 'interval') == 'point':
                p.drawPolygon(QPolygonF([QPointF(r.center().x(), r.top()),
                    QPointF(r.right(), r.center().y()), QPointF(r.center().x(), r.bottom()),
                    QPointF(r.left(), r.center().y())]))
                if editing:
                    p.setPen(QColor('#653823')); p.setFont(QFont('Segoe UI', 8))
                    p.drawText(QPointF(r.right()+5, r.center().y()+4), f'{a.start_s:.3f}s')
                continue
            p.drawRoundedRect(r, 4, 4)
            visible = r.intersected(QRectF(LABEL_W, 0, w-LABEL_W, h))
            if visible.width() > 24:
                lum = .2126*fill.red()+.7152*fill.green()+.0722*fill.blue()
                p.setPen(QColor('#443226') if lum > 145 else QColor('#FFF9EB'))
                p.setFont(QFont('Segoe UI', 7 if reference else 8, QFont.Medium if editing else QFont.Normal))
                icon = '✓ ' if a.status == 'approved' and not editing else ('✎ ' if editing else '')
                caption = a.channel if reference else icon+annotation_caption(a)
                text = p.fontMetrics().elidedText(caption, Qt.ElideRight, int(max(0, visible.width()-14)))
                p.drawText(visible.adjusted(7, 0, -6, 0), Qt.AlignVCenter, text)
            if editing:
                p.setPen(QPen(QColor('#653823'), 1.5))
                for x in (r.left()+3, r.right()-3):
                    p.drawLine(QPointF(x, r.top()+5), QPointF(x, r.bottom()-5))
        if self._preview:
            a, b, track_id = self._preview
            row = next((r for r in self.rows if r['kind'] == 'track' and r['track'].id == track_id), None)
            if row:
                p.setPen(QPen(QColor('#B6683E'), 1.5, Qt.DashLine)); p.setBrush(QColor(182, 104, 62, 55))
                p.drawRoundedRect(QRectF(self.time_x(min(a,b)), row['y']+6, abs(b-a)*self.px_per_s, 26), 3, 3)
        p.restore()
        px = self.time_x(self.time_s)
        if LABEL_W <= px <= w:
            p.setPen(QPen(QColor('#B34E2F'), 1.4)); p.drawLine(QPointF(px, 7), QPointF(px, h))
            p.setPen(Qt.NoPen); p.setBrush(QColor('#B34E2F'))
            p.drawPolygon(QPolygonF([QPointF(px-5, 0), QPointF(px+5, 0), QPointF(px+5, 8), QPointF(px, 13), QPointF(px-5, 8)]))
        p.setPen(QPen(QColor('#DDD2C4'), 1)); p.drawLine(QPointF(LABEL_W, 0), QPointF(LABEL_W, h))
        if not self.rows:
            p.setPen(QColor('#A0907E')); p.setFont(QFont('Segoe UI', 10))
            p.drawText(QRectF(LABEL_W+20, HEADER_H+22, max(50,w-LABEL_W-40), 50), Qt.AlignCenter,
                       'Add a track for this workspace, then drag an interval to label.')
        p.end()

    def mousePressEvent(self, event):
        self.setFocus(Qt.MouseFocusReason)
        x,y = event.position().x(),event.position().y()
        row = self.row_at(y)
        if row and row['kind'] == 'reference':
            if event.button() == Qt.LeftButton and x >= LABEL_W:
                hit = self._annotation_at(x, y, reference=True)
                self.seekRequested.emit(hit.start_s if hit else self.x_time(x))
            return
        if event.button() == Qt.RightButton:
            hit = self._annotation_at(x,y)
            menu = QMenu(self)
            if hit:
                for title, action in [('Edit segment','edit'),('Accept segment','approve'),('Split at playhead','split'),('Duplicate','duplicate'),('Reject candidate','reject'),('Delete segment','delete')]:
                    if action == 'split' and getattr(hit, 'temporal_kind', 'interval') == 'point':
                        continue
                    q = menu.addAction(title); q.setData(action)
                selected = menu.exec(event.globalPosition().toPoint())
                if selected: self.contextAction.emit(hit.id, selected.data())
            elif row and row['kind'] == 'track':
                for title, action in [('Track label list…','labels'),('Rename track…','rename'),('Move up','up'),('Move down','down'),('Hide track','hide'),('Delete track…','delete')]:
                    q = menu.addAction(title); q.setData(action)
                selected = menu.exec(event.globalPosition().toPoint())
                if selected: self.trackAction.emit(row['track'].id, selected.data())
            return
        if event.button() != Qt.LeftButton: return
        if row and row['kind'] == 'group':
            role = row['role']
            if role in self.collapsed: self.collapsed.remove(role)
            else: self.collapsed.add(role)
            self._rebuild(); return
        if x < LABEL_W:
            if row and row['kind'] == 'track':
                self.active_track_id = row['track'].id; self.laneChanged.emit(self.active_track_id); self.update()
            return
        if y < HEADER_H:
            self.seekRequested.emit(self.x_time(x)); self._drag = ('seek',); return
        hit = self._annotation_at(x,y)
        if hit:
            self.annotationSelected.emit(hit.id)
            r = self.annotation_rect(hit)
            left_distance, right_distance = abs(x-r.left()), abs(x-r.right())
            mode = 'point' if getattr(hit, 'temporal_kind', 'interval') == 'point' else (('left' if left_distance <= right_distance else 'right') if min(left_distance, right_distance) <= 7 else 'move')
            self._drag = (mode, hit.id, self.x_time(x), hit.start_s, hit.end_s)
            return
        track = self.lane_at(y)
        if track:
            self.active_track_id = track.id; self.laneChanged.emit(track.id)
            t = self.snapped(self.x_time(x), event.modifiers())
            self._new = (t, track.id); self._preview = (t,t,track.id); self.update()

    def mouseMoveEvent(self, event):
        x,y = event.position().x(),event.position().y()
        if self._new:
            start, track_id = self._new
            track = next((t for t in self.tracks if t.id == track_id), None)
            if track is not None and track_temporal_kind(track) == 'point':
                self.setCursor(Qt.CrossCursor); return
            self._preview = (start, self.snapped(self.x_time(x), event.modifiers()), track_id); self.update(); return
        if self._drag:
            if self._drag[0] == 'seek': self.seekRequested.emit(self.x_time(x)); return
            mode, ident, anchor, start, end = self._drag
            raw_delta = self.x_time(x)-anchor
            minimum = max(.001, self.frame_step if self.snap else .001)
            if mode == 'point': start = end = self.snapped(start+raw_delta, event.modifiers())
            elif mode == 'left': start = min(end-minimum, self.snapped(start+raw_delta, event.modifiers()))
            elif mode == 'right': end = max(start+minimum, self.snapped(end+raw_delta, event.modifiers()))
            else:
                length = end-start
                start = min(max(0., self.duration_s-length), self.snapped(start+raw_delta, event.modifiers()))
                end = start+length
            self.spanChanged.emit(ident, max(0., start), min(self.duration_s, end)); return
        reference = self._annotation_at(x, y, reference=True)
        if reference:
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip(f'{reference.channel} · {reference.label}\n{reference.start_s:.3f}–{reference.end_s:.3f}s · Motion reference\nClick to seek')
            return
        hit = self._annotation_at(x,y)
        if hit:
            r = self.annotation_rect(hit)
            caption = annotation_caption(hit)
            heading = caption if caption == hit.label else f'{caption}\nLabel: {hit.label}'
            if hit.category == ACTIVITY_EPISODE and hit.notes:
                heading += f'\n{hit.notes}'
            if getattr(hit, 'temporal_kind', 'interval') == 'point':
                self.setCursor(Qt.OpenHandCursor)
                self.setToolTip(f'{heading}\nPoint at {hit.start_s:.3f}s · {hit.source}\nDrag to move the time point; no artificial duration.')
                return
            edge = min(abs(x-r.left()),abs(x-r.right())) <= 7
            self.setCursor(Qt.SizeHorCursor if edge else Qt.OpenHandCursor)
            self.setToolTip(f'{heading}\n{hit.start_s:.3f}–{hit.end_s:.3f}s · {hit.source}\nClick to edit · Drag edges to trim · Drag center to move')
        else:
            self.setCursor(Qt.CrossCursor if x >= LABEL_W and self.lane_at(y) else Qt.ArrowCursor)
            self.setToolTip('')

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton: return
        if self._new:
            start, track_id = self._new
            end = self.snapped(self.x_time(event.position().x()), event.modifiers())
            self._new, self._preview = None, None
            track = next((t for t in self.tracks if t.id == track_id), None)
            if track is not None and track_temporal_kind(track) == 'point': self.newPoint.emit(start, track_id)
            elif abs(end-start) >= max(.01, self.frame_step): self.newRange.emit(min(start,end), max(start,end), track_id)
            else: self.seekRequested.emit(start)
        self._drag = None; self.update()

    def mouseDoubleClickEvent(self, event):
        if event.position().x() >= LABEL_W and not self._annotation_at(event.position().x(), event.position().y()):
            self.seekRequested.emit(self.x_time(event.position().x()))


class TimelineRuler(QWidget):
    """Fixed ruler: remains visible while vertically scrolling body-part lanes."""
    def __init__(self, canvas, parent=None):
        super().__init__(parent); self.canvas=canvas; self.setFixedHeight(RULER_H)
        self.setMouseTracking(True); self._seeking=False
    def paintEvent(self,event):
        c=self.canvas; p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor('#F5F0E7')); p.fillRect(QRectF(0,0,LABEL_W,RULER_H),QColor('#F1EBE1'))
        p.setPen(QColor('#766351')); p.setFont(QFont('Segoe UI',8,QFont.DemiBold))
        p.drawText(QRectF(12,0,LABEL_W-20,RULER_H),Qt.AlignVCenter,'TRACK  /  ANNOTATION TYPE')
        target=80/c.px_per_s
        step=next((v for v in (.05,.1,.2,.5,1,2,5,10,20,30,60,120,300,600) if v>=target),1200)
        tick=math.floor(c.visible_start/step)*step; end=min(c.duration_s,c.visible_start+c.time_visible_span())
        p.setFont(QFont('Segoe UI',8)); p.setPen(QColor('#8D7964'))
        while tick<=end+step:
            x=c.time_x(tick)
            if LABEL_W<=x<self.width()-25:
                label=f'{tick:.2f}s' if step<1 else f'{int(tick//60):02}:{tick%60:04.1f}' if step<2 else f'{int(tick//60):02}:{int(tick%60):02}'
                p.drawText(QPointF(x+4,18),label)
            tick+=step
        x=c.time_x(c.time_s)
        if LABEL_W<=x<=self.width():
            p.setPen(QPen(QColor('#B34E2F'),1.4)); p.drawLine(QPointF(x,0),QPointF(x,RULER_H))
            p.setPen(Qt.NoPen); p.setBrush(QColor('#B34E2F'))
            p.drawPolygon(QPolygonF([QPointF(x-5,0),QPointF(x+5,0),QPointF(x+5,8),QPointF(x,13),QPointF(x-5,8)]))
        p.end()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and event.position().x()>=LABEL_W:
            self._seeking=True; self.canvas.seekRequested.emit(self.canvas.x_time(event.position().x()))
    def mouseMoveEvent(self,event):
        if self._seeking:self.canvas.seekRequested.emit(self.canvas.x_time(event.position().x()))
    def mouseReleaseEvent(self,event):self._seeking=False


class TimelinePane(QFrame):
    annotationSelected=Signal(str)
    newRange=Signal(float,float,str)
    newPoint=Signal(float,str)
    seekRequested=Signal(float)
    contextAction=Signal(str,str)
    trackAction=Signal(str,str)
    spanChanged=Signal(str,float,float)
    addTrack=Signal()
    manageTracks=Signal()

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName('TimelinePane')
        layout=QVBoxLayout(self); layout.setContentsMargins(10,7,10,7); layout.setSpacing(4)
        row=QHBoxLayout(); layout.addLayout(row)
        title=QLabel('ANNOTATION TIMELINE'); title.setObjectName('Subhead'); row.addWidget(title)
        row.addSpacing(12)
        for text,status,editing in [('Candidate','pending',False),('Editing','pending',True),('Accepted','approved',False)]:
            dot=QLabel('  '); dot.setFixedSize(12,12); dot.setStyleSheet(f'background:{category_color("Motion Primitive",status,editing).name()};border-radius:3px;')
            row.addWidget(dot); label=QLabel(text); label.setStyleSheet('font-size:8pt;color:#8C7B68;'); row.addWidget(label)
        row.addStretch()
        self.motion_refs=QCheckBox('Motion refs'); self.motion_refs.setChecked(True); self.motion_refs.hide()
        self.motion_refs.setToolTip('Show arm and hand Motion candidates as read-only timing references in Gesture.')
        row.addWidget(self.motion_refs)
        self.snap=QCheckBox('Snap'); self.snap.setChecked(True); self.snap.setToolTip('Snap to the active BVH frame rate; hold Shift for free adjustment.'); row.addWidget(self.snap)
        self.role_filter=QComboBox(); self.role_filter.addItems(['All','R01','R02','Both','Scene']); self.role_filter.setMinimumWidth(70); row.addWidget(self.role_filter)
        for text,slot in [('−',lambda:self.change_zoom(.75)),('+',lambda:self.change_zoom(1.33)),('Fit',self.fit_all)]:
            b=QPushButton(text); b.setMaximumWidth(44); b.clicked.connect(slot); row.addWidget(b)
        manage=QPushButton('Tracks'); manage.clicked.connect(self.manageTracks); row.addWidget(manage)
        add=QPushButton('+ Add track'); add.setObjectName('PrimaryButton'); add.clicked.connect(self.addTrack); row.addWidget(add)
        self.canvas=TimelineCanvas()
        self.ruler=TimelineRuler(self.canvas); layout.addWidget(self.ruler)
        self.area=QScrollArea(); self.area.setWidgetResizable(True); self.area.setWidget(self.canvas)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); layout.addWidget(self.area,1)
        hr=QHBoxLayout(); layout.addLayout(hr)
        self.scroll=QScrollBar(Qt.Horizontal); hr.addWidget(self.scroll,1)
        self.range_label=QLabel(''); self.range_label.setMinimumWidth(110); self.range_label.setStyleSheet('font-size:8pt;color:#8C7B68;'); hr.addWidget(self.range_label)
        for name in ('annotationSelected','newRange','newPoint','seekRequested','contextAction','trackAction','spanChanged'):
            getattr(self.canvas,name).connect(getattr(self,name))
        self.snap.toggled.connect(lambda x:setattr(self.canvas,'snap',x))
        self.role_filter.currentTextChanged.connect(self.canvas.set_role_filter)
        self.motion_refs.toggled.connect(self.canvas.set_show_motion_references)
        self.scroll.valueChanged.connect(self._scrolled)
        self.canvas.installEventFilter(self)
        self.setMinimumHeight(155)

    def eventFilter(self, watched, event):
        if watched is self.canvas and event.type() == QEvent.Resize: self._refresh_scroll()
        return super().eventFilter(watched,event)
    def _refresh_scroll(self):
        c=self.canvas; span=c.time_visible_span()
        self.scroll.setRange(0, round(max(0,c.duration_s-span)*1000))
        self.scroll.setPageStep(max(1,round(span*1000)))
        self._scrolled(self.scroll.value())
    def _scrolled(self,n):
        self.canvas.visible_start=n/1000.; self.canvas.update(); self.ruler.update()
        self.range_label.setText(f'{n/1000.:.1f} – {min(self.canvas.duration_s,n/1000.+self.canvas.time_visible_span()):.1f} s')
    def set_workspace(self, workspace, category='All'):
        self.motion_refs.setVisible(workspace == 'Gesture')
        self.setMinimumHeight(255 if workspace == 'Gesture' else 155)
        self.canvas.set_workspace(workspace, category)
    def set_duration(self,d): self.canvas.duration_s=max(.05,float(d)); self._refresh_scroll()
    def set_time(self,t,follow=False):
        self.canvas.set_time(t); self.ruler.update()
        if follow:
            span=self.canvas.time_visible_span()
            if t>self.canvas.visible_start+span*.94 or t<self.canvas.visible_start:
                self.scroll.setValue(max(0,round((t-span*.15)*1000)))
    def change_zoom(self,factor):
        center=self.canvas.visible_start+self.canvas.time_visible_span()/2
        self.canvas.px_per_s=max(.2,min(1600.,self.canvas.px_per_s*factor))
        self.canvas._rebuild()
        self._refresh_scroll(); self.scroll.setValue(round(max(0,center-self.canvas.time_visible_span()/2)*1000))
    def fit_all(self):
        self.canvas.px_per_s=max(.2,(self.canvas.width()-LABEL_W-12)/max(.05,self.canvas.duration_s))
        self.canvas._rebuild()
        self._refresh_scroll(); self.scroll.setValue(0)
    def select(self,ident): self.canvas.selected_id=ident; self.canvas.update()
    def reveal(self,annotation):
        rect = self.canvas.annotation_rect(annotation)
        if rect is not None:
            self.area.ensureVisible(0, round(rect.center().y()), 0, 35)
        if annotation.start_s<self.canvas.visible_start or annotation.start_s>self.canvas.visible_start+self.canvas.time_visible_span():
            self.scroll.setValue(round(max(0,annotation.start_s-1)*1000))
