"""Rotatable, software-rendered 3D skeleton, prop and gaze scene for Qt.

The viewer changes only its camera/display basis. It never rewrites imported
coordinates or asserts that separately captured people share a world frame.
"""
from __future__ import annotations
import math
import numpy as np
from PySide6.QtCore import Qt, QPointF, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QLinearGradient
from PySide6.QtWidgets import QWidget

ROLE_COLORS = {'R01': '#A54B32', 'R02': '#6D7954'}


class SkeletonCanvas(QWidget):
    selectedTime = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 230)
        self.setMouseTracking(True)
        self.motion, self.gaze, self.offsets = {}, {}, {}
        self.props = []
        self.time_s = 0.
        self.show_floor = True
        self.show_gaze = True
        self.show_props = True
        self.show_arm_labels = True
        self.world_verified = False
        self.up_axis = 'Z'
        self.az, self.el = math.radians(40), math.radians(24)
        self.zoom = 1.
        self.target = np.array([0., 0., 0.])
        self.base_span = 100.
        self.ground_z = 0.
        self._last = None
        self.colors = dict(ROLE_COLORS)
        self.highlight_role = None
        self.highlight_channels = ()

    def clear_assets(self):
        self.motion.clear()
        self.gaze.clear()
        self.props.clear()
        self.offsets.clear()
        self.highlight_role = None
        self.update()

    def add_motion(self, role, motion, offset=0):
        if not np.isfinite(float(offset)):
            raise ValueError('Motion offset must be finite')
        self.motion[role] = motion
        self.offsets[role] = float(offset)
        self.reset_camera()

    def set_gaze(self, role, track):
        self.gaze[role] = track
        self.update()

    def set_props(self, track):
        self.props.append(track)
        self.update()

    def set_time(self, t):
        if not np.isfinite(float(t)):
            return
        self.time_s = float(t)
        self.update()

    def set_up_axis(self, axis):
        axis = str(axis).upper()
        if axis not in ('Y', 'Z'):
            raise ValueError('Display up axis must be Y or Z')
        if self.up_axis != axis:
            self.up_axis = axis
            self.reset_camera()

    def set_view(self, view):
        angles = {'perspective': (40, 24), 'front': (0, 0), 'side': (90, 0), 'top': (0, 80)}
        if view not in angles:
            raise ValueError('Unknown camera view')
        self.az, self.el = map(math.radians, angles[view])
        self.update()

    def set_highlight(self, role=None, channels=()):
        self.highlight_role = role
        self.highlight_channels = (channels,) if isinstance(channels, str) else tuple(channels)
        self.update()

    def set_arm_labels_visible(self, visible):
        self.show_arm_labels = visible
        self.update()

    def _display(self, points):
        value = np.asarray(points, dtype=float)
        if self.up_axis == 'Y':
            # Proper rotation, preserving handedness: (x, y, z)->(x, -z, y).
            return np.stack((value[..., 0], -value[..., 2], value[..., 1]), axis=-1)
        return value

    def active_roles(self, time_s=None):
        t = self.time_s if time_s is None else float(time_s)
        return [role for role, motion in self.motion.items()
                if 0 <= t - self.offsets.get(role, 0.) <= motion.duration_s]

    def reset_camera(self):
        positions, feet, scales = [], [], []
        for role, motion in self.motion.items():
            try:
                local = max(0., min(motion.duration_s, self.time_s - self.offsets.get(role, 0.)))
                pose = self._display(motion.pose_at(local))
                positions.append(pose)
                scales.append(motion.scale_hint())
                for name in ('LeftFoot', 'RightFoot', 'LeftToeBase', 'RightToeBase'):
                    index = motion.joint(name)
                    if index is not None:
                        feet.append(pose[index, 2])
            except (ValueError, IndexError):
                continue
        if positions:
            joined = np.concatenate(positions)
            mins, maxs = joined.min(axis=0), joined.max(axis=0)
            self.target = (mins + maxs) * .5
            self.base_span = max(.05, float(np.max(maxs - mins)) * 1.38, max(scales, default=.1) * 2.25)
            self.ground_z = float(np.median(feet)) if feet else float(mins[2])
        self.zoom = 1.
        self.update()

    def _basis(self):
        right = np.array([-math.sin(self.az), math.cos(self.az), 0.])
        up = np.array([-math.sin(self.el) * math.cos(self.az), -math.sin(self.el) * math.sin(self.az), math.cos(self.el)])
        return right, up

    def _project_display(self, point):
        delta = np.asarray(point, dtype=float) - self.target
        right, up = self._basis()
        factor = min(self.width(), self.height()) * 1.03 / max(self.base_span, .001) * self.zoom
        return QPointF(self.width() * .52 + float(np.dot(delta, right)) * factor,
                       self.height() * .54 - float(np.dot(delta, up)) * factor)

    def project(self, point):
        return self._project_display(self._display(point))

    def _highlight_indices(self, role, motion):
        if role != self.highlight_role:
            return set()
        selected = set()
        for channel in self.highlight_channels:
            if channel in ('Full Body', 'Whole Body'):
                return set(range(len(motion.names)))
            tokens = {
                'Head': ('head', 'neck'), 'Torso': ('spine', 'chest'), 'Root': ('hips', 'pelvis', 'root'),
                'Left Arm': ('leftshoulder', 'leftarm', 'leftforearm', 'lefthand'),
                'Right Arm': ('rightshoulder', 'rightarm', 'rightforearm', 'righthand'),
                'Left Leg': ('leftupleg', 'leftleg', 'leftfoot', 'lefttoe'),
                'Right Leg': ('rightupleg', 'rightleg', 'rightfoot', 'righttoe'),
                'Left Hand': ('lefthand',), 'Right Hand': ('righthand',), 'Hands': ('lefthand', 'righthand'),
            }.get(channel, ())
            selected.update(i for i, name in enumerate(motion.names) if any(token in name.lower() for token in tokens))
        return selected

    def _arm_label_anchors(self, motion, positions):
        torso = motion.joint('Spine3', 'Chest', 'Spine2', 'Spine1', 'Spine', 'Hips', 'Pelvis', 'Root')
        center_x = self._project_display(positions[torso]).x() if torso is not None else self.width() * .5
        for side in ('Left', 'Right'):
            prefix = side.lower()
            shoulder = motion.joint(f'{side}Arm', f'{side}UpperArm', f'{side}Shoulder', f'{prefix}_shoulder')
            elbow = motion.joint(f'{side}ForeArm', f'{side}Elbow', f'{prefix}_elbow')
            if shoulder is None or elbow is None:
                continue
            point = positions[elbow]
            if motion.parents[elbow] == shoulder:
                point = (positions[shoulder] + point) * .5
            anchor = self._project_display(point)
            yield f'{side} Arm', anchor, -1 if anchor.x() < center_x else 1

    def _paint_arm_labels(self, painter, labels):
        viewport = QRectF(self.rect())
        bounds = viewport.adjusted(5, 48, -5, -36)
        painter.setFont(QFont('Segoe UI', 8, QFont.DemiBold))
        metrics = painter.fontMetrics()
        height = metrics.height() + 4
        occupied = []
        for label, anchor, direction, color in labels:
            width = metrics.horizontalAdvance(label) + 12
            if not viewport.contains(anchor) or width > bounds.width() or height > bounds.height():
                continue
            to_right, to_left = anchor.x() + 13, anchor.x() - width - 13
            x_options = (to_right, to_left) if direction > 0 else (to_left, to_right)
            preferred_top = anchor.y() - height * .5
            y_options = [preferred_top]
            for other in occupied:
                y_options.extend((other.top() - height, other.bottom()))
            tops = sorted({max(bounds.top(), min(y, bounds.bottom() - height)) for y in y_options},
                          key=lambda y: abs(y - preferred_top))
            choices = (
                QRectF(max(bounds.left(), min(x, bounds.right() - width)), y, width, height)
                for x in x_options for y in tops
            )
            rect = next((choice for choice in choices if not any(choice.intersects(other) for other in occupied)), None)
            if rect is None:
                continue
            occupied.append(rect.adjusted(-2, -2, 2, 2))
            side_x = rect.left() if anchor.x() < rect.center().x() else rect.right()
            painter.setPen(QPen(color, 1.25))
            painter.setBrush(color)
            painter.drawEllipse(anchor, 2.7, 2.7)
            painter.drawLine(anchor, QPointF(side_x, rect.center().y()))
            painter.setBrush(QColor('#FFFCF7'))
            painter.drawRoundedRect(rect, 4, 4)
            painter.drawText(rect, Qt.AlignCenter, label)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor('#FBFAF7'))
        gradient.setColorAt(1, QColor('#F0EDE6'))
        painter.fillRect(self.rect(), gradient)
        if self.show_floor:
            self._floor(painter)
        if not self.motion:
            painter.setPen(QColor('#82776D'))
            painter.setFont(QFont('Segoe UI', 11))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             '3D MOTION VIEW\n\nImport a BVH or joint-position NPZ\nOrbit, zoom and inspect each body part.')
            painter.end()
            return
        active = self.active_roles()
        arm_labels = []
        _, camera_up = self._basis()
        depth_axis = np.cross(*self._basis())
        for role in active:
            motion = self.motion[role]
            try:
                positions = self._display(motion.pose_at(self.time_s - self.offsets.get(role, 0.)))
            except (ValueError, IndexError):
                continue
            color = QColor(self.colors.get(role, '#9B7351'))
            highlighted = self._highlight_indices(role, motion)
            segments = []
            for index, parent in enumerate(motion.parents):
                if parent < 0 or parent >= len(positions):
                    continue
                first, last = positions[parent], positions[index]
                depth = float(np.dot((first + last) * .5, depth_axis))
                segments.append((depth, self._project_display(first), self._project_display(last), index in highlighted or parent in highlighted))
            segments.sort(key=lambda item: item[0], reverse=True)
            for _, first, last, selected in segments:
                line = QColor('#D87B43') if selected else color
                painter.setPen(QPen(line, 4.2 if selected else 2.8, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(first, last)
            # Joint-only NPZ files are valid point previews; absent parents
            # do not fabricate a star skeleton.
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            for point in positions:
                painter.drawEllipse(self._project_display(point), 1.7, 1.7)
            for name, radius in (('Head', 4.3), ('Hips', 3.5), ('LeftHand', 3.0), ('RightHand', 3.0)):
                index = motion.joint(name)
                if index is not None:
                    painter.drawEllipse(self._project_display(positions[index]), radius, radius)
            root = motion.joint('Hips', 'Pelvis', 'Root') or 0
            anchor = self._project_display(positions[root]) + QPointF(12, -12)
            painter.setFont(QFont('Segoe UI', 9, QFont.DemiBold))
            painter.setPen(color)
            painter.drawText(anchor, role)
            if self.show_arm_labels:
                arm_labels.extend((f'{role} {name}' if len(active) > 1 else name, point, direction, color)
                                  for name, point, direction in self._arm_label_anchors(motion, positions))
        if not active:
            painter.setPen(QColor('#82776D'))
            painter.setFont(QFont('Segoe UI', 10))
            painter.drawText(self.rect(), Qt.AlignCenter, 'No motion sample at this master time')
        if self.show_gaze:
            for role, track in self.gaze.items():
                ray = track.ray_at(self.time_s)
                if ray is None:
                    continue
                first, last = ray
                if not np.isfinite(first).all() or not np.isfinite(last).all():
                    continue
                delta = last - first
                length = float(np.linalg.norm(delta))
                if length < 1e-9:
                    continue
                end = first + delta * min(1., self.base_span * .60 / length)
                color = QColor(self.colors.get(role, '#9B7351'))
                painter.setPen(QPen(color, 1.8, Qt.DashLine))
                painter.drawLine(self.project(first), self.project(end))
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(self.project(end), 3., 3.)
        if self.show_props:
            for track in self.props:
                points = track.at(self.time_s)
                if points is None:
                    continue
                for point, name in zip(points, track.names):
                    if not np.isfinite(point).all():
                        continue
                    position = self.project(point)
                    painter.setPen(QPen(QColor('#8E7348'), 1.5))
                    painter.setBrush(QColor('#C5AB71'))
                    painter.drawEllipse(position, 4.5, 4.5)
                    painter.setPen(QColor('#705C39'))
                    painter.drawText(position + QPointF(8, -7), name)
        if arm_labels:
            self._paint_arm_labels(painter, arm_labels)
        self._hud(painter, active)
        painter.end()

    def _floor(self, painter):
        unit = max(.005, self.base_span / 10.)
        origin = self.target.copy()
        origin[2] = self.ground_z
        painter.setPen(QPen(QColor('#DDD8CF'), 1))
        for index in range(-5, 6):
            x, y = origin[0] + index * unit, origin[1] + index * unit
            painter.drawLine(self._project_display((x, origin[1] - 5 * unit, self.ground_z)),
                             self._project_display((x, origin[1] + 5 * unit, self.ground_z)))
            painter.drawLine(self._project_display((origin[0] - 5 * unit, y, self.ground_z)),
                             self._project_display((origin[0] + 5 * unit, y, self.ground_z)))
        painter.setPen(QPen(QColor('#C6BDB0'), 1.2))
        painter.drawLine(self._project_display((origin[0] - 5 * unit, origin[1], self.ground_z)),
                         self._project_display((origin[0] + 5 * unit, origin[1], self.ground_z)))
        painter.drawLine(self._project_display((origin[0], origin[1] - 5 * unit, self.ground_z)),
                         self._project_display((origin[0], origin[1] + 5 * unit, self.ground_z)))

    def _hud(self, painter, active):
        painter.setPen(QColor('#5E5248'))
        painter.setFont(QFont('Segoe UI', 9, QFont.DemiBold))
        painter.drawText(15, 24, '3D MOTION  /  ' + ' + '.join(self.motion))
        painter.setFont(QFont('Segoe UI', 8))
        painter.setPen(QColor('#877B6F'))
        painter.drawText(15, 42, f'{self.up_axis}-up  ·  native units  ·  {self.time_s:06.2f} s')
        painter.drawText(15, self.height() - 14, 'Drag to orbit   ·   Scroll to zoom   ·   Shift + drag to pan')
        if not self.world_verified and len(self.motion) > 1:
            painter.setPen(QColor('#9A6D43'))
            painter.drawText(15, self.height() - 31, 'World alignment unverified')

    def wheelEvent(self, event):
        self.zoom = max(.12, min(12., self.zoom * math.exp(event.angleDelta().y() / 750)))
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._last, self._mods = event.position(), event.modifiers()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._last is None:
            return
        delta = event.position() - self._last
        if self._mods & Qt.ShiftModifier or event.buttons() & Qt.MiddleButton:
            factor = self.base_span / max(100., min(self.width(), self.height())) / self.zoom
            right, up = self._basis()
            self.target -= right * delta.x() * factor - up * delta.y() * factor
        else:
            self.az += delta.x() * .009
            self.el = max(math.radians(-75), min(math.radians(80), self.el - delta.y() * .009))
        self._last = event.position()
        self.update()

    def mouseReleaseEvent(self, event):
        self._last = None
        self.unsetCursor()
