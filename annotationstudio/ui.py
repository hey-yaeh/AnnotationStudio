"""Annotation Studio: a local, transactional multimodal annotation desktop."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import json
import os
import sys
import time
import threading
import uuid

from PySide6.QtCore import Qt,QTimer,QThread,QObject,Signal,QUrl,QSignalBlocker,QStandardPaths
from PySide6.QtGui import QAction,QKeySequence,QColor,QBrush,QFont,QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QSplitter,QVBoxLayout,QHBoxLayout,
    QGridLayout,QLabel,QPushButton,QComboBox,QTreeWidget,QTreeWidgetItem,QLineEdit,QPlainTextEdit,
    QAbstractSpinBox,QMessageBox,QFileDialog,QInputDialog,QSlider,QTabWidget,QScrollArea,QDialog,QCheckBox)
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput

from .models import Project,Annotation,import_annotation_csv,export_eaf,track_temporal_kind,PRIMITIVE_CHANNELS
from .annotation_export import (select_annotations,export_annotation_csv,export_annotation_bundle,
                                suggested_export_stem,category_export_stem)
from . import __version__
from .ontology import LEGACY_MOTION_RELATION, RETIRED_PRIMITIVE_LABELS, WORKSPACES,WORKSPACE_CATEGORIES,WORKFLOWS
from .editing import ProjectHistory,EditSession
from .bvh import open_motion
from .modalities import read_gaze_csv,read_props,read_aoi_csv,wav_envelope
from .theme import STYLE
from .timeline import TimelinePane, is_gesture_motion_reference, workspace_for_track
from .editor import SegmentEditor
from .label_palette import LabelPalette
from .dialogs import TrackDialog,TrackLabelDialog,TracksDialog,LabelDialog,AssetDialog,ExportDialog
from .media import MediaWorkspace
from .panels import AutoPanel,ReviewPanel
from .jobs import run_motion_job,merge_auto_results,JobCancelled
from .audio_models import detect_audio,AudioCancelled
from .object_registry import ObjectRegistryDialog

VERSION=__version__
BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))


def button(text,slot,style=None):
    b=QPushButton(text)
    if style:b.setObjectName(style)
    b.clicked.connect(slot)
    return b


class AnalysisWorker(QObject):
    done=Signal(object,object)
    failed=Signal(str)
    cancelled=Signal()
    progress=Signal(str)
    finished=Signal()
    def __init__(self,job,cancel):
        super().__init__(); self.job=job; self.cancel=cancel
    def run(self):
        try:
            output,detail=self.job(self.progress.emit,self.cancel)
            if self.cancel.is_set():self.cancelled.emit()
            else:self.done.emit(output,detail)
        except (JobCancelled,AudioCancelled):self.cancelled.emit()
        except Exception as exc:self.failed.emit(f'{type(exc).__name__}: {exc}')
        finally:self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self,example=False,recover=True):
        super().__init__(); self.setObjectName('AnnotationStudio')
        self.resize(1680,1060); self.setMinimumSize(1220,800); self.setAcceptDrops(True)
        self.project=Project(); self.history=ProjectHistory(); self.session=EditSession(self.project,self.history)
        self.motion={}; self.extra_audio={}; self._asset_duration={}; self._asset_errors={}
        self._time=0.; self._playing=False; self._clock0=0.; self._t0=0.; self._last_sync=0.; self._rate=1.
        self.selected_id=None; self._quick_track=None; self._workflow='Motion'; self._category='All'
        self._mark_in=None; self._mark_out=None; self._updating=False; self._worker=None; self._thread=None; self._cancel_token=None; self._job_scope=None; self._job_replace=False; self._job_assets_signature={}
        self._close_after_job=False; self._initializing=True; self._preview_invalid=False
        self._return_to_review=False
        self._build_ui(); self._build_menus()
        self.timer=QTimer(self); self.timer.setInterval(30); self.timer.timeout.connect(self._tick); self.timer.start()
        self.autosave_timer=QTimer(self); self.autosave_timer.setInterval(30000); self.autosave_timer.timeout.connect(self.save_recovery); self.autosave_timer.start()
        self.history.mark_saved(self.project); self._initializing=False
        self._refresh_all(); self.set_workflow('Motion',force=True)
        if example:self.load_example(force=True)
        elif recover:QTimer.singleShot(400,self.check_recovery)
        self.statusBar().showMessage('Ready · Add sources, open a project or try the synthetic demo.')

    def _build_ui(self):
        root=QWidget(); root.setObjectName('Root'); layout=QVBoxLayout(root); layout.setContentsMargins(10,0,10,6); layout.setSpacing(7)
        bar=QWidget(); bar.setObjectName('TopBar'); top=QHBoxLayout(bar); top.setContentsMargins(15,12,15,12); top.setSpacing(12)
        icon=QLabel('AS'); icon.setObjectName('Monogram'); icon.setAlignment(Qt.AlignCenter); icon.setFixedSize(36,36); top.addWidget(icon)
        brand=QVBoxLayout(); brand.setSpacing(0); top.addLayout(brand)
        title=QLabel('Annotation Studio'); title.setObjectName('Brand'); brand.addWidget(title)
        subtitle=QLabel('MULTIMODAL ANNOTATION  /  MOTION • VIDEO • AUDIO'); subtitle.setObjectName('Subtitle'); brand.addWidget(subtitle)
        top.addStretch()
        self.project_label=QLabel(); top.addWidget(self.project_label)
        self.saved_label=QLabel('SAVED'); self.saved_label.setObjectName('Subtitle'); top.addWidget(self.saved_label)
        if (BASE/'examples/S004_I02_manual.studio.json').is_file():
            top.addWidget(button('BVH example',self.load_manual_example,'TopButton'))
        elif (BASE/'examples/annotation_schema_demo.studio.json').is_file():
            top.addWidget(button('Synthetic demo',self.load_schema_demo,'TopButton'))
        top.addWidget(button('Open project',self.open_project,'TopButton'))
        self.auto_detect_button=button('Auto-detect…',lambda:self.open_auto_detection(),'TopAccent')
        self.auto_detect_button.setToolTip('Open motion, audio and speech-turn proposal tools.')
        top.addWidget(self.auto_detect_button)
        top.addWidget(button('Save project',self.save_project,'TopAccent')); layout.addWidget(bar)
        nav=QHBoxLayout(); nav.setContentsMargins(0,0,0,0); nav.setSpacing(0); layout.addLayout(nav)
        self.nav={}
        for name in WORKSPACES:
            b=button(name,lambda checked=False,n=name:self.set_workflow(n),'Nav'); b.setCheckable(True); nav.addWidget(b); self.nav[name]=b
        nav.addStretch()
        nav.addWidget(button('Vocabulary',self.manage_labels)); nav.addSpacing(5); nav.addWidget(button('Export',self.export_annotations))
        self.main_split=QSplitter(Qt.Vertical); layout.addWidget(self.main_split,1)
        self.upper=QSplitter(Qt.Horizontal); self.main_split.addWidget(self.upper)
        self.sidebar=self._build_sidebar(); self.sidebar_area=QScrollArea(); self.sidebar_area.setWidgetResizable(True); self.sidebar_area.setWidget(self.sidebar); self.sidebar_area.setMinimumWidth(205); self.sidebar_area.setMaximumWidth(285); self.upper.addWidget(self.sidebar_area)
        self.media=MediaWorkspace(); self.media.importVideo.connect(lambda:self.add_asset_dialog('video')); self.media.durationReady.connect(self._media_duration_update); self.media.failed.connect(self._media_error)
        self.media.axis.currentTextChanged.connect(self._axis_changed)
        # Native Windows title bars/fonts leave less vertical room than the
        # offscreen platform. Allow the preview to scroll when expanded editor
        # rows need that room, instead of pushing Accept/evidence below Root.
        self.media_area=QScrollArea(); self.media_area.setWidgetResizable(True)
        self.media_area.setWidget(self.media); self.upper.addWidget(self.media_area)
        self.right_tabs=QTabWidget()
        self.label_palette=LabelPalette()
        self.auto=AutoPanel(); self.review=ReviewPanel(); self.properties=self._build_properties()
        self.right_tabs.addTab(self.label_palette,'Labels'); self.right_tabs.addTab(self.auto,'Automatic'); self.right_tabs.addTab(self.review,'Review'); self.right_tabs.addTab(self.properties,'Details')
        self.label_palette.labelChosen.connect(self.choose_palette_label)
        self.label_palette.configureTrackRequested.connect(self.configure_track_labels)
        self.label_palette.addLabelRequested.connect(self.add_custom_label)
        # The tab content has a larger minimum height than the media pane.
        # Keep it scroll-accessible on short displays so the lower editor can
        # retain its readable row heights instead of clipping either region.
        self.right_tabs_area=QScrollArea(); self.right_tabs_area.setWidgetResizable(True)
        self.right_tabs_area.setWidget(self.right_tabs)
        self.right_tabs_area.setMinimumWidth(315); self.right_tabs_area.setMaximumWidth(440)
        self.upper.addWidget(self.right_tabs_area); self.upper.setSizes([215,1070,330])
        self.auto.runMotion.connect(self.run_segmentation); self.auto.runAudio.connect(self.run_audio); self.auto.cancelJob.connect(self.cancel_job); self.auto.importResults.connect(self.import_annotations)
        self.auto.runSpeechStructure.connect(self.run_speech_structure)
        self.auto.world.toggled.connect(self.set_world_frame_verified)
        self.auto.reviewLatest.connect(self.open_latest_review)
        self.review.selected.connect(self._select_review_annotation)
        lower=QWidget(); lv=QVBoxLayout(lower); lv.setContentsMargins(0,2,0,0); lv.setSpacing(6)
        transport=QHBoxLayout(); lv.addLayout(transport)
        self.play=button('▶  Play',self.toggle_play,'PrimaryButton'); self.play.setMinimumWidth(95); transport.addWidget(self.play)
        transport.addWidget(button('‹',lambda:self.step_frame(-1))); transport.addWidget(button('›',lambda:self.step_frame(1)))
        self.time_label=QLabel('00:00.000'); self.time_label.setObjectName('TimeCode'); self.time_label.setMinimumWidth(125); transport.addWidget(self.time_label)
        self.scrub=QSlider(Qt.Horizontal); self.scrub.setRange(0,120000); self.scrub.sliderMoved.connect(lambda v:self.seek(v/1000)); transport.addWidget(self.scrub,1)
        self.speed=QComboBox()
        for value in (.25,.5,1.,1.5,2.):self.speed.addItem(f'{value:g}×',value)
        self.speed.setCurrentIndex(2); self.speed.currentIndexChanged.connect(self._set_speed); transport.addWidget(self.speed)
        self.loop=QCheckBox('Loop selection'); transport.addWidget(self.loop)
        self.loop.setToolTip('Intervals loop their span. Points preview 0.75 seconds on each side without changing their duration.')
        transport.addWidget(QLabel('Listen'))
        self.listen=QComboBox(); self.listen.setMinimumWidth(110); self.listen.setMaximumWidth(180); self.listen.addItem('Mute',('mute','')); self.listen.currentIndexChanged.connect(self._apply_audio_selection); transport.addWidget(self.listen)
        self.volume=QSlider(Qt.Horizontal); self.volume.setRange(0,100); self.volume.setValue(70); self.volume.setMaximumWidth(65); self.volume.setToolTip('Playback volume'); self.volume.valueChanged.connect(self._apply_audio_selection); transport.addWidget(self.volume)
        self.timeline=TimelinePane(); lv.addWidget(self.timeline,1)
        self.timeline.annotationSelected.connect(self.select_annotation); self.timeline.newRange.connect(self.add_range); self.timeline.seekRequested.connect(self.seek); self.timeline.contextAction.connect(self.annotation_context); self.timeline.trackAction.connect(self.track_context); self.timeline.spanChanged.connect(self.change_span); self.timeline.addTrack.connect(self.add_track); self.timeline.manageTracks.connect(self.manage_tracks); self.timeline.canvas.laneChanged.connect(self._track_selected)
        self.timeline.newPoint.connect(self.add_point)
        self.editor=SegmentEditor(); lv.addWidget(self.editor)
        self.editor.changed.connect(self.update_draft); self.editor.acceptClicked.connect(self.accept_edit); self.editor.cancelClicked.connect(self.cancel_edit); self.editor.candidateClicked.connect(self.keep_candidate); self.editor.addLabelClicked.connect(self.add_custom_label); self.editor.splitClicked.connect(self.split_selected); self.editor.mergeClicked.connect(self.merge_selected)
        self.editor.objectsRequested.connect(self.manage_objects)
        self.main_split.addWidget(lower); self.main_split.setSizes([500,380]); self.setCentralWidget(root)

    def _build_sidebar(self):
        card=QFrame(); card.setObjectName('Card'); card.setMinimumWidth(190); card.setMinimumHeight(505)
        v=QVBoxLayout(card); v.setContentsMargins(12,12,12,10); v.setSpacing(8)
        self.workspace_title=QLabel('Motion'); self.workspace_title.setObjectName('WorkspaceTitle'); v.addWidget(self.workspace_title)
        self.workspace_hint=QLabel('Body-part primitives, posture and hand behavior.'); self.workspace_hint.setWordWrap(True); self.workspace_hint.setStyleSheet('color:#9B8873;font-size:8pt;'); v.addWidget(self.workspace_hint)
        self.submodule=QComboBox(); self.submodule.currentIndexChanged.connect(self._filter_category); v.addWidget(self.submodule)
        self.summary=QLabel(''); self.summary.setWordWrap(True); self.summary.setStyleSheet('background:#F5EEE2;padding:9px;border-radius:5px;color:#86674E;font-size:8pt;'); v.addWidget(self.summary)
        h=QHBoxLayout(); v.addLayout(h)
        sub=QLabel('SOURCES'); sub.setObjectName('Subhead'); h.addWidget(sub); h.addStretch(); h.addWidget(button('＋',self.add_source_menu))
        self.assets=QTreeWidget(); self.assets.setHeaderHidden(True); self.assets.setIndentation(9); self.assets.setMinimumHeight(85); self.assets.itemDoubleClicked.connect(self.edit_asset); v.addWidget(self.assets,1)
        small=QHBoxLayout(); v.addLayout(small); small.addWidget(button('Timing / relink',self.edit_asset)); small.addWidget(button('Remove',self.remove_asset))
        actions=QGridLayout(); v.addLayout(actions)
        for i,(name,kind) in enumerate([('BVH / pose','motion'),('Video','video'),('Audio','audio'),('Gaze ref.','gaze'),('Props','props')]):
            actions.addWidget(button('+ '+name,lambda checked=False,k=kind:self.add_asset_dialog(k)),i//2,i%2)
        tools=QHBoxLayout(); v.addLayout(tools)
        tools.addWidget(button('Objects…',self.manage_objects)); tools.addWidget(button('Context query…',self.open_context_query))
        self.track_hint=QLabel('Generate proposals, or select a track.\nChoose a label and edit its timing.\nAccept with Ctrl+Enter.\n\nIntervals: drag edges.\nPoint tracks: click a time, then drag the marker.'); self.track_hint.setWordWrap(True); self.track_hint.setStyleSheet('color:#8B745F;font-size:8pt;'); v.addWidget(self.track_hint)
        return card

    def _build_properties(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(12,12,12,10)
        label=QLabel('SEGMENT PROVENANCE'); label.setObjectName('Subhead'); v.addWidget(label)
        self.detail_text=QPlainTextEdit(); self.detail_text.setReadOnly(True); self.detail_text.setPlaceholderText('Select a segment to see original boundaries, model settings and review history.'); v.addWidget(self.detail_text,1)
        note=QLabel('Candidate scores are model outputs or relative salience, not measured accuracy. Accepted means reviewed in this project.'); note.setWordWrap(True); note.setStyleSheet('font-size:8pt;color:#9A826B;'); v.addWidget(note)
        return w

    def _build_menus(self):
        self.actions={}
        def action(menu,name,slot,key=None):
            a=QAction(name,self); a.triggered.connect(slot)
            if key:a.setShortcut(QKeySequence(key))
            menu.addAction(a); self.actions[name]=a; return a
        f=self.menuBar().addMenu('File')
        for n,s,k in [('New project',self.new_project,'Ctrl+Shift+N'),('Open project…',self.open_project,'Ctrl+O'),('Save project',self.save_project,'Ctrl+S'),('Save as…',self.save_as,'Ctrl+Shift+S'),('Import annotations…',self.import_annotations,'Ctrl+I'),('Export annotations…',self.export_annotations,'Ctrl+E')]:action(f,n,s,k)
        if (BASE/'examples/S004_I02_manual.studio.json').is_file():
            action(f,'Open manual example',self.load_manual_example)
        if (BASE/'examples/S004_I02_example.ocumo.json').is_file():
            action(f,'Open included automatic example',self.load_example)
        if (BASE/'examples/annotation_schema_demo.studio.json').is_file():
            action(f,'Open synthetic annotation demo',self.load_schema_demo)
        edit=self.menuBar().addMenu('Edit')
        action(edit,'Undo',self.undo,'Ctrl+Z'); action(edit,'Redo',self.redo,'Ctrl+Y'); action(edit,'Add segment',self.quick_add,'Ctrl+N'); action(edit,'Accept segment',self.accept_edit,'Ctrl+Return'); action(edit,'Cancel edit',self.cancel_edit,'Escape'); action(edit,'Duplicate segment',self.duplicate_selected,'Ctrl+D'); action(edit,'Split at playhead',self.split_selected,'Ctrl+Shift+K')
        action(edit,'Add point at playhead',self.quick_add_point,'Ctrl+M')
        view=self.menuBar().addMenu('View'); action(view,'Fit timeline',self.timeline.fit_all,'Ctrl+0'); action(view,'Restore video panels',self.media.restore_panels); action(view,'Reset 3D camera',self.media.canvas.reset_camera)
        legacy_tracks=QAction('Hide legacy tracks',self)
        legacy_tracks.setCheckable(True)
        legacy_tracks.setToolTip('Hide historical Motion Activity Relation lanes from the timeline.')
        legacy_tracks.toggled.connect(self._set_hide_legacy_tracks)
        view.addAction(legacy_tracks); self.actions[legacy_tracks.text()]=legacy_tracks
        self.floor_action=QAction('Floor grid',self); self.floor_action.setCheckable(True); self.floor_action.setChecked(True); self.floor_action.toggled.connect(lambda x:(setattr(self.media.canvas,'show_floor',x),self.media.canvas.update())); view.addAction(self.floor_action)
        self.gaze_action=QAction('Gaze rays',self); self.gaze_action.setCheckable(True); self.gaze_action.setChecked(True); self.gaze_action.toggled.connect(lambda x:(setattr(self.media.canvas,'show_gaze',x),self.media.canvas.update())); view.addAction(self.gaze_action)
        self.props_action=QAction('Props',self); self.props_action.setCheckable(True); self.props_action.setChecked(True); self.props_action.toggled.connect(lambda x:(setattr(self.media.canvas,'show_props',x),self.media.canvas.update())); view.addAction(self.props_action)
        project=self.menuBar().addMenu('Project'); action(project,'Add track…',self.add_track); action(project,'Track label list…',self.configure_track_labels); action(project,'Track manager…',self.manage_tracks); action(project,'Label vocabulary…',self.manage_labels); action(project,'Rename project…',self.rename_project); action(project,'Set timeline duration…',self.set_duration_dialog)
        action(project,'Scene objects…',self.manage_objects)
        action(project,'Add missing primitive tracks…',self.add_missing_primitive_tracks)
        action(project,'Add missing annotation tracks…',self.add_missing_annotation_tracks)
        analysis=self.menuBar().addMenu('Analysis')
        action(analysis,'Motion proposals…',lambda:self.open_auto_detection(tab=0))
        action(analysis,'Build speech turns…',self.run_speech_structure)
        action(analysis,'Context / overlap query…',self.open_context_query)
        action(analysis,'Recheck derived results…',self.open_derived_review)
        helpmenu=self.menuBar().addMenu('Help'); action(helpmenu,'Keyboard shortcuts',self.shortcuts); action(helpmenu,'Open recovery copy',self.open_recovery); action(helpmenu,'About / model support',self.about)

    def _set_hide_legacy_tracks(self, hidden):
        self.timeline.canvas.set_hide_legacy_tracks(hidden)
        self._filter_category()

    def open_auto_detection(self, tab=None):
        if tab is None and self._thread is None:
            audio_only = not {'R01','R02'}.intersection(self.motion) and self.auto.audio_asset.currentData() is not None
            tab = 1 if self._workflow == 'Speech' or audio_only else 0
        if tab is not None:
            self.auto.tabs.setCurrentIndex(tab)
        self.right_tabs.setCurrentWidget(self.auto)
        self.right_tabs_area.verticalScrollBar().setValue(0)

    def open_latest_review(self):
        self.review.show_latest_pending()
        if self.session.draft is None:
            canvas = self.timeline.canvas
            latest = self.review.latest_pending()
            gesture_motion = self._workflow == 'Gesture' and any(a.category == 'Motion Primitive' for a in latest)
            if gesture_motion:
                latest = [a for a in latest if canvas.show_motion_references and is_gesture_motion_reference(a)]
            tracks = {track.id: track for track in self.project.tracks if track.visible
                      and not (canvas.hide_legacy_tracks and track.category == LEGACY_MOTION_RELATION)}
            candidate = min(
                (item for item in latest if item.track_id in tracks
                 and (not gesture_motion or (tracks[item.track_id].category == 'Motion Primitive'
                                             and tracks[item.track_id].role == item.role))),
                key=lambda item: (max(0., item.start_s - self._time, self._time - item.end_s), item.start_s),
                default=None,
            )
            if candidate is not None:
                if gesture_motion:
                    self._show_role_in_timeline(candidate.role)
                else:
                    self._show_track_in_timeline(tracks[candidate.track_id])
                self.timeline.reveal(candidate)
        self.right_tabs.setCurrentWidget(self.review)
        self.right_tabs_area.verticalScrollBar().setValue(0)

    def _offer_candidate_review(self, ids):
        self.review.set_latest_batch(ids)
        self.auto.set_latest_review_available(bool(ids))
        if (ids and self.session.draft is None and not self._close_after_job
                and self.right_tabs.currentWidget() is self.auto):
            self.open_latest_review()

    def _message(self,text,ms=6500):self.statusBar().showMessage(text,ms)
    def _checkpoint(self):self.history.checkpoint(self.project)
    def _dirty(self):return self.history.is_dirty(self.project) or self.session.dirty or self._preview_invalid
    def _update_name(self):
        dirty=self._dirty()
        self.project_label.setText(self.project.name); self.saved_label.setText('UNSAVED' if dirty else 'SAVED')
        self.setWindowTitle(f'{"* " if dirty else ""}{self.project.name} — Annotation Studio {VERSION}')
        self.actions['Undo'].setEnabled(self.history.can_undo); self.actions['Redo'].setEnabled(self.history.can_redo)
    def _refresh_all(self):
        self.project.ensure_tracks(); self._update_assets(); self._refresh_annotations(); self._update_duration(); self._refresh_audio_sources()
        self.auto.set_assets(self.project.assets,self.motion)
        self._update_name()
    def _refresh_annotations(self,rebind_editor=True):
        self.project.ensure_tracks()
        self.timeline.canvas.set_data(self.project.tracks,self.project.annotations,self.session.draft)
        self.timeline.select(self.selected_id)
        self.review.populate(self.project.annotations)
        counts={s:sum(a.status==s for a in self.project.annotations) for s in ('approved','pending','rejected')}
        self.summary.setText(f'{counts["approved"]} accepted   ·   {counts["pending"]} candidates\n{len(self.project.tracks)} tracks   ·   {len(self.project.assets)} sources')
        if rebind_editor:self.editor.bind(self.session.draft,self.project)
        self._refresh_label_palette()
        self._show_properties(); self._update_name()
    def _refresh_label_palette(self):
        draft=self.session.draft
        track=self.project.get_track(draft.track_id if draft else self._quick_track)
        self.label_palette.bind(self.project,track,draft)
    def choose_palette_label(self,name):
        if not self.session.draft:
            self._message('Drag a time interval on the selected track, then choose its label.'); return
        self.editor.choose_label(name)
        self._message(f'Label selected: {name} · adjust the boundaries, then Accept (Ctrl+Enter).')
    def _show_properties(self):
        a=self.session.draft or self._selected()
        if not a:self.detail_text.clear(); return
        text={'id':a.id,'status':'editing (uncommitted)' if self.session.draft else a.status,'source':a.source,'label_id':a.label_id or 'Unmapped','original_prediction':a.original or {'start_s':a.start_s,'end_s':a.end_s,'label':a.label},'attributes':a.attributes,'history':a.history}
        if a.attributes.get('dependency_snapshots'):
            from .speech_structure import dependency_issues
            text['upstream_records_needing_recheck']=dependency_issues(self.project,a)
        self.detail_text.setPlainText(json.dumps(text,ensure_ascii=False,indent=2))
    def _selected(self):return next((a for a in self.project.annotations if a.id==self.selected_id),None)

    def _settle_edit(self):
        if not self.session.draft:return True
        if not self.session.dirty and not self._preview_invalid:self.cancel_edit(); return True
        box=QMessageBox(self); box.setWindowTitle('Uncommitted segment'); box.setText('Keep your segment changes before switching?')
        keep=box.addButton('Keep as candidate',QMessageBox.AcceptRole); discard=box.addButton('Discard changes',QMessageBox.DestructiveRole); box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is keep:return self.keep_candidate()
        if box.clickedButton() is discard:self.cancel_edit(); return True
        return False
    def _can_replace_project(self):
        if self._thread and self._thread.isRunning():
            self._message('Cancel or finish the running analysis before changing projects.'); return False
        if not self._settle_edit():return False
        if not self.history.is_dirty(self.project):return True
        result=QMessageBox.question(self,'Unsaved project','Save this project before closing it?',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        if result==QMessageBox.Cancel:return False
        if result==QMessageBox.Save:return bool(self.save_project())
        return True

    def set_workflow(self,mode,force=False):
        if mode not in WORKSPACES:return
        if not force and mode!=self._workflow and not self._settle_edit():
            self.nav[mode].setChecked(False); self.nav[self._workflow].setChecked(True); return
        self._workflow=mode; self._category='All'
        for name,b in self.nav.items():b.setChecked(name==mode)
        self.workspace_title.setText(mode)
        hints = {
            'Overview': 'All annotation tracks on one clock. Oculo Studio gaze remains an external reference.',
            'Activity': 'Describe what each person does over an interval. Add an object or a short description as needed.',
            'Motion': 'Body-part primitives, posture, hand behavior, locomotion, whole-body actions and gait.',
            'Gesture': 'Gesture form, optional phase and speech relation.',
            'HOI': 'Object actions and sustained contact / support states, linked by stable object IDs.',
            'Affect': 'Choose Adjective + intensity or Valence / Arousal for R01 or R02.',
            'Speech': 'Speaking, turns, timing, vocal events and observable speech disfluencies.',
            'Spatial': 'Person and object positions, directions and movement. Register object names; 3D models are optional.',
            'Social': 'Communicative events, directed physical interaction and expressed cognitive states.',
            'Review': 'Review candidates across all workspaces.',
        }
        self.workspace_hint.setText(hints[mode])
        with QSignalBlocker(self.submodule):
            self.submodule.clear(); self.submodule.addItem('All annotation types','All')
            for category in WORKSPACE_CATEGORIES.get(mode,()):self.submodule.addItem(category,category)
        self.timeline.set_workspace(mode)
        tracks=self.timeline.canvas.visible_tracks()
        self._quick_track=tracks[0].id if tracks else None; self.timeline.canvas.active_track_id=self._quick_track
        if mode=='Review':self.right_tabs.setCurrentWidget(self.review)
        elif mode in ('Motion','Speech'):self.right_tabs.setCurrentWidget(self.auto)
        else:self.right_tabs.setCurrentWidget(self.label_palette)
        if mode in ('Motion','Speech'):self.auto.tabs.setCurrentIndex(1 if mode=='Speech' else 0)
        self._refresh_label_palette()
        self._message(f'{mode} · Add a track or select a segment to annotate.')
    def _filter_category(self,*_):
        value=self.submodule.currentData() or 'All'
        self._category=value; self.timeline.set_workspace(self._workflow,value)
        tracks=self.timeline.canvas.visible_tracks()
        if self._quick_track not in [t.id for t in tracks]:self._quick_track=tracks[0].id if tracks else None
        self.timeline.canvas.active_track_id=self._quick_track; self._refresh_label_palette()
    def _track_selected(self,track_id):
        self._quick_track=track_id; self._set_frame_grid(track_id); track=self.project.get_track(track_id)
        if track and hasattr(self.media.canvas,'set_highlight'):self.media.canvas.set_highlight(track.role,track.body_parts)
        self._refresh_label_palette(); self.right_tabs.setCurrentWidget(self.label_palette)

    def _show_track_in_timeline(self, track):
        workspace = workspace_for_track(track)
        if self._workflow not in (workspace, 'Overview', 'Review'):
            self.set_workflow(workspace if workspace in WORKSPACES else 'Overview', force=True)
        canvas = self.timeline.canvas
        if canvas.category_filter not in ('All', track.category):
            self.submodule.setCurrentIndex(0)
        self._show_role_in_timeline(track.role)

    def _show_role_in_timeline(self, role):
        canvas = self.timeline.canvas
        if canvas.filter_role not in ('All', role) and role not in ('Both', 'Scene'):
            self.timeline.role_filter.setCurrentText('All')
        if role in canvas.collapsed:
            canvas.collapsed.remove(role)
            canvas._rebuild()

    def _select_review_annotation(self, ident):
        if self._workflow == 'Gesture' and self.timeline.canvas.show_motion_references:
            annotation = next((a for a in self.project.annotations if a.id == ident), None)
            track = self.project.get_track(annotation.track_id) if annotation else None
            if (track and track.visible and track.category == 'Motion Primitive'
                    and track.role == annotation.role and is_gesture_motion_reference(annotation)):
                self._show_role_in_timeline(annotation.role)
                self.timeline.reveal(annotation)
                self.pause()
                self.seek(annotation.start_s)
                return
        self.select_annotation(ident, from_review=True)

    def select_annotation(self,ident,*,from_review=False):
        if self.session.draft and self.session.draft.id==ident:
            if from_review:
                self._return_to_review=True
                self.right_tabs.setCurrentWidget(self.label_palette)
            return
        if not self._settle_edit():return
        a=next((x for x in self.project.annotations if x.id==ident),None)
        if not a:return
        track=self.project.get_track(a.track_id)
        if track and not track.visible:
            self._checkpoint(); track.visible=True
        if track:
            self._show_track_in_timeline(track)
            self._quick_track=track.id; self.timeline.canvas.active_track_id=track.id
        self._set_frame_grid(a.track_id)
        self.selected_id=ident; self.session.begin(ident); self._preview_invalid=False
        self._return_to_review=from_review
        self.pause(); self._refresh_annotations(); self.timeline.reveal(a); self.seek(a.start_s,follow=False)
        self.right_tabs.setCurrentWidget(self.label_palette)
        if hasattr(self.media.canvas,'set_highlight'):self.media.canvas.set_highlight(a.role,track.body_parts if track else [a.channel])
    def add_range(self,start,end,track_id):
        if not self._settle_edit():return
        try:
            draft=self.session.create(start,end,track_id); self.selected_id=draft.id; self._quick_track=track_id; self._preview_invalid=False
            self.timeline.canvas.active_track_id=track_id
            self.pause(); self._refresh_annotations(); self.right_tabs.setCurrentWidget(self.label_palette)
            self._message('Interval selected · choose a label in the list, then Accept (Ctrl+Enter).')
        except ValueError as exc:self._message(str(exc))
    def add_point(self,time_s,track_id):
        if not self._settle_edit():return
        try:
            draft=self.session.create_point(time_s,track_id)
            self.selected_id=draft.id; self._quick_track=track_id; self._preview_invalid=False
            self.timeline.canvas.active_track_id=track_id
            self.pause(); self._refresh_annotations(); self.right_tabs.setCurrentWidget(self.label_palette)
            self._message('Point selected · choose a label. Drag the diamond to adjust its time.')
        except ValueError as exc:self._message(str(exc))
    def update_draft(self,values):
        if not self.session.draft:return
        try:
            self.session.update(**values); self.editor.current=self.session.draft; self._preview_invalid=False
            self.timeline.canvas.set_data(self.project.tracks,self.project.annotations,self.session.draft); self._update_name()
            self._quick_track=self.session.draft.track_id; self._refresh_label_palette()
        except ValueError as exc:
            self._preview_invalid=True; self._message(str(exc))
    def change_span(self,ident,start,end):
        if not self.session.draft or self.session.draft.id!=ident:return
        try:
            self.session.update(start_s=start,end_s=end); self.editor.current=self.session.draft; self.editor.update_span(start,end); self._preview_invalid=False
            self.timeline.canvas.set_data(self.project.tracks,self.project.annotations,self.session.draft); self._update_name()
        except ValueError as exc:self._message(str(exc))
    def _read_editor(self):
        if not self.session.draft:return False
        self.session.update(**self.editor.values()); self._preview_invalid=False; return True
    def accept_edit(self):
        if not self.session.draft:return False
        try:
            self._read_editor(); a=self.session.accept(self.editor.reviewer.text().strip()); self.selected_id=a.id
            self._refresh_annotations(); self._finish_review_edit(); self._message('Segment accepted · original prediction and edit history retained.'); return True
        except ValueError as exc:QMessageBox.warning(self,'Cannot accept',str(exc)); return False
    def keep_candidate(self):
        if not self.session.draft:return True
        try:
            self._read_editor(); a=self.session.save_candidate(); self.selected_id=a.id
            self._refresh_annotations(); self._finish_review_edit(); self._message('Segment saved as a candidate.'); return True
        except ValueError as exc:QMessageBox.warning(self,'Cannot save segment',str(exc)); return False
    def cancel_edit(self):
        if not self.session.draft:return
        was_new=self.session.is_new; self.session.cancel(); self._preview_invalid=False
        if was_new:self.selected_id=None
        self._refresh_annotations(); self._finish_review_edit(); self._message('Edit cancelled; saved annotation unchanged.')

    def _finish_review_edit(self):
        if self._return_to_review and self.right_tabs.currentWidget() is self.label_palette:
            self.right_tabs.setCurrentWidget(self.review)
        self._return_to_review=False
    def add_custom_label(self,name):
        draft=self.session.draft
        track=self.project.get_track(draft.track_id if draft else self._quick_track)
        name=name.strip()
        if not track or name in ('','Unlabeled'):return
        if track.category == LEGACY_MOTION_RELATION or (
                track.category == 'Motion Primitive' and name.casefold() in RETIRED_PRIMITIVE_LABELS):
            self._message('Use a specific movement form on an active track.'); return
        existing=self.project.resolve_label(name,track.category)
        if existing and existing in self.project.labels_for_track(track):
            if draft:self.editor.label.setEditText(existing.name)
            self._message('This label is already available on this track.'); return
        scopes={0:('core','project'),1:('project',),2:('temporary',)}.get(track.extra.get('label_scope',0),('core','project','temporary'))
        if existing and existing.scope not in scopes:
            self._message('That label belongs to a different label source. Use a distinct project label or a track with the matching source.'); return
        self._checkpoint()
        scope='temporary' if track.extra.get('label_scope')==2 else 'project'
        label=existing or self.project.add_label(name,track.category,scope)
        self.project.allow_label_on_track(track,label)
        if draft:self.session.update(label=label.name)
        self._refresh_annotations()
        self._message('Label added to this track. Select an interval and Accept to save an annotation.')

    def annotation_context(self,ident,action):
        self.select_annotation(ident)
        if self.selected_id!=ident:return
        actions={'approve':self.accept_edit,'delete':self.delete_selected,'reject':self.reject_selected,'split':self.split_selected,'duplicate':self.duplicate_selected}
        if action in actions:actions[action]()
    def reject_selected(self):
        a=self._selected()
        if not a:return
        self.session.cancel(); self._checkpoint(); before=a.snapshot(); a.status='rejected'; a.record_change(before,'reject'); self._refresh_annotations(); self._finish_review_edit(); self._message('Candidate rejected. It remains available in the review table and exports.')
    def delete_selected(self):
        if self.session.draft and self.session.is_new:self.cancel_edit(); return
        a=self._selected()
        if not a:return
        self.session.cancel(); self._checkpoint(); self.project.annotations.remove(a); self.selected_id=None; self._refresh_annotations(); self._message('Segment deleted · Undo is available.')
    def duplicate_selected(self):
        a=self.session.draft or self._selected()
        if not a:return
        copy=deepcopy(a)
        if not self._settle_edit():return
        try:
            if copy.is_point:self.session.create_point(copy.start_s,copy.track_id)
            else:self.session.create(copy.start_s,copy.end_s,copy.track_id)
        except ValueError as exc:
            self._message(str(exc)); return
        self.session.update(label=copy.label,notes=copy.notes,attributes={**copy.attributes,'duplicated_from':copy.id})
        self.selected_id=self.session.draft.id; self._refresh_annotations()
    def split_selected(self):
        a=self.session.draft or self._selected()
        if not a:return
        if a.is_point:self._message('A point has no duration to split. Drag it to change its time.'); return
        if not a.start_s+1e-6<self._time<a.end_s-1e-6:self._message('Place the playhead inside the selected segment to split it.'); return
        if self.session.draft and self.session.dirty:
            if not self.keep_candidate():return
        else:self.session.cancel()
        a=self._selected()
        if not a:return
        self._checkpoint(); before=a.snapshot(); new=deepcopy(a); new.id=str(uuid.uuid4()); split=self._time
        a.end_s=split; a.status='pending'; a.record_change(before,'split left')
        new.start_s=split; new.status='pending'; new.parent_id=a.id; new.attributes={**new.attributes,'split_from':a.id}; new.record_change(before,'split right'); self.project.annotations.append(new)
        self._refresh_annotations(); self._message('Split into two candidates; review each boundary and accept.')
    def merge_selected(self):
        active=self.session.draft or self._selected()
        if active and active.is_point:self._message('Point events are separate observations and cannot be merged as intervals.'); return
        if self.session.draft and self.session.dirty:
            if not self.keep_candidate():return
        else:self.session.cancel()
        a=self._selected()
        if not a:return
        group=sorted([x for x in self.project.annotations if x.track_id==a.track_id and x.id!=a.id and not x.is_point and x.start_s>=a.start_s and x.status!='rejected'],key=lambda x:x.start_s)
        if not group or group[0].label!=a.label:self._message('The next segment on this track must have the same label to merge.'); self._refresh_annotations(); return
        b=group[0]; gap=b.start_s-a.end_s
        if gap>.5 and QMessageBox.question(self,'Merge across a gap',f'The segments have a {gap:.2f}s gap. Include this gap in the merged candidate?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self._checkpoint(); before=a.snapshot(); a.end_s=max(a.end_s,b.end_s); a.status='pending'; a.attributes={**a.attributes,'merged_annotations':[*a.attributes.get('merged_annotations',[]),asdict(b)]}; a.record_change(before,'merge next'); self.project.annotations.remove(b)
        self._refresh_annotations(); self._message('Merged candidate created; both original records are retained in provenance.')

    def add_track(self):
        if not self._settle_edit():return
        dialog=TrackDialog(self._workflow,self,project=self.project)
        if dialog.exec()!=QDialog.Accepted:return
        self._checkpoint(); track=self.project.add_track(**dialog.values()); self.set_workflow(track.workspace,force=True); self._quick_track=track.id; self.timeline.canvas.active_track_id=track.id
        self._refresh_annotations(); self._message(f'Track added: {track.name}')
    def configure_track_labels(self,checked=False,track_id=None):
        track=self.project.get_track(track_id or (self.session.draft.track_id if self.session.draft else self._quick_track))
        if not track:self._message('Select a track or add one before configuring its labels.'); return
        dialog=TrackLabelDialog(self.project,track,self)
        if dialog.exec()!=QDialog.Accepted:return
        ids=dialog.allowed_ids()
        if track.extra.get('allowed_label_ids')==ids:return
        self._checkpoint(); self.project.set_track_label_ids(track,ids); self._refresh_annotations()
        self._message('Track label list updated. Existing annotation labels and times are preserved.')
    def manage_tracks(self):
        if not self._settle_edit():return
        dialog=TracksDialog(self.project,self)
        if dialog.exec()!=QDialog.Accepted:return
        self._checkpoint(); self.project.tracks=dialog.result_tracks(); self.project.annotations=[a for a in self.project.annotations if a.track_id not in dialog.removed]
        self.selected_id=None; self._refresh_annotations()
    def add_missing_primitive_tracks(self):
        if not self._settle_edit():return
        existing={(t.role,t.channel) for t in self.project.tracks if t.category=='Motion Primitive'}
        missing=[(role,part) for role in ('R01','R02') for part in PRIMITIVE_CHANNELS if (role,part) not in existing]
        if not missing:
            self._message('Primitive tracks already cover the major body parts for R01 and R02.'); return
        self._checkpoint()
        added=self.project.ensure_primitive_tracks()
        self.set_workflow('Motion',force=True); self._refresh_annotations()
        preferred=next((t for t in added if t.channel=='Left Leg'),added[0])
        self._track_selected(preferred.id)
        self.timeline.canvas.collapsed.discard(preferred.role)
        self.timeline.canvas._rebuild()
        row=next((r for r in self.timeline.canvas.rows if r.get('track') and r['track'].id==preferred.id),None)
        if row:self.timeline.area.ensureVisible(0,round(row['y']+row['height']/2),0,20)
        self._message(f'Added {len(added)} body-part primitive tracks. Existing tracks and annotations are preserved; Undo is available.')
    def add_missing_annotation_tracks(self):
        if not self._settle_edit():return
        # Check on a detached project before recording history: invoking the
        # action again must not consume an Undo step or modify authored tracks.
        preview=deepcopy(self.project)
        if not preview.ensure_annotation_tracks():
            self._message('Annotation tracks already cover the active types for R01 and R02.'); return
        self._checkpoint()
        added=self.project.ensure_annotation_tracks()
        preferred=next((t for t in added if t.category=='Physical Interaction'),added[0])
        self.set_workflow(preferred.workspace,force=True); self._refresh_annotations()
        self._track_selected(preferred.id)
        self.timeline.canvas.collapsed.discard(preferred.role)
        self.timeline.canvas._rebuild()
        row=next((r for r in self.timeline.canvas.rows if r.get('track') and r['track'].id==preferred.id),None)
        if row:self.timeline.area.ensureVisible(0,round(row['y']+row['height']/2),0,20)
        self._message(f'Added {len(added)} annotation tracks. Existing records and custom lists are preserved; Undo is available.',10000)
    def track_context(self,track_id,action):
        if action=='labels':self.configure_track_labels(track_id=track_id); return
        if not self._settle_edit():return
        track=self.project.get_track(track_id)
        if not track:return
        if action=='rename':
            name,ok=QInputDialog.getText(self,'Rename track','Name',text=track.name)
            if ok and name.strip():self._checkpoint(); track.name=name.strip()
        elif action in ('up','down'):
            group=sorted([t for t in self.project.tracks if t.role==track.role],key=lambda t:t.order); i=group.index(track); j=i+(-1 if action=='up' else 1)
            if 0<=j<len(group):self._checkpoint(); track.order,group[j].order=group[j].order,track.order
        elif action=='hide':self._checkpoint(); track.visible=False
        elif action=='delete':
            count=sum(a.track_id==track_id for a in self.project.annotations)
            if count and QMessageBox.question(self,'Delete track',f'Delete this track and {count} annotations?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self._checkpoint(); self.project.tracks.remove(track); self.project.annotations=[a for a in self.project.annotations if a.track_id!=track_id]
        self._refresh_annotations()
    def manage_labels(self):
        if not self._settle_edit():return
        track=self.project.get_track(self._quick_track)
        dialog=LabelDialog(self.project,track.category if track else None,self)
        if dialog.exec()==QDialog.Accepted:
            self._checkpoint(); self.project.labels=dialog.project.labels; self.project.annotations=dialog.project.annotations; self._refresh_annotations()
    def manage_objects(self):
        dialog=ObjectRegistryDialog(self.project,self)
        if dialog.exec()!=QDialog.Accepted:return
        objects=dialog.result_objects()
        if objects==self.project.objects:return
        self._checkpoint(); self.project.objects=objects
        self._refresh_annotations(rebind_editor=False)
        self.editor.refresh_objects(self.project)
        self._message('Object registry updated. Existing references and IDs are retained; Undo is available.')
    def run_speech_structure(self):
        if self._thread and self._thread.isRunning():
            self._message('Finish or cancel the current analysis before building speech turns.'); return
        if not self._settle_edit():return
        from .speech_tools import SpeechStructureDialog
        from .speech_structure import apply_speech_structure
        dialog=SpeechStructureDialog(self.project,self)
        if dialog.exec()!=QDialog.Accepted:return
        try:
            self._checkpoint()
            previous_ids={a.id for a in self.project.annotations}
            counts=apply_speech_structure(self.project,dialog.annotations,dialog.report,replace=dialog.replace)
            self._refresh_annotations(); self._update_duration(); self.set_workflow('Speech',force=True)
            self._offer_candidate_review({a.id for a in self.project.annotations
                                          if a.status=='pending' and a.id not in previous_ids})
            message=f"Speech structure: {counts.get('added',0)} added · {counts.get('protected',0)} reviewed/edited results retained."
            if counts.get('stale_protected',0) or counts.get('blocked_dependencies',0):
                message+=' Some results need checking: Analysis → Recheck derived results.'
            self._message(message,16000)
        except ValueError as exc:QMessageBox.warning(self,'Speech structure',str(exc))
    def open_context_query(self):
        if not self._settle_edit():return
        from .context_dialog import ContextQueryDialog
        ContextQueryDialog(self.project,self).exec()
    def open_derived_review(self):
        if not self._settle_edit():return
        from .derived_review import DerivedReviewDialog
        dialog=DerivedReviewDialog(self.project,self)
        if dialog.exec()==QDialog.Accepted and dialog.annotation_id:self.select_annotation(dialog.annotation_id)
    def rename_project(self):
        name,ok=QInputDialog.getText(self,'Project name','Name',text=self.project.name)
        if ok and name.strip():self._checkpoint(); self.project.name=name.strip(); self._update_name()
    def set_duration_dialog(self):
        value,ok=QInputDialog.getDouble(self,'Master timeline','Minimum timeline duration (seconds)',self.project.settings.get('manual_duration_s',120.),.05,1e7,3)
        if ok:self._checkpoint(); self.project.settings['manual_duration_s']=value; self._update_duration(); self._update_name()

    def undo(self):
        if self.session.draft:self.cancel_edit(); return
        old=[asdict(a) for a in self.project.assets]
        if self.history.undo(self.project):
            self.selected_id=None
            if old!=[asdict(a) for a in self.project.assets]:self.rebind_assets()
            self._refresh_all(); self._apply_project_settings(); self._message('Undid last project change.')
    def redo(self):
        if self.session.draft:self.cancel_edit(); return
        old=[asdict(a) for a in self.project.assets]
        if self.history.redo(self.project):
            self.selected_id=None
            if old!=[asdict(a) for a in self.project.assets]:self.rebind_assets()
            self._refresh_all(); self._apply_project_settings(); self._message('Redid project change.')

    def _clear_media(self):
        self.pause(); self.media.clear(); self.motion.clear(); self._asset_duration.clear(); self._asset_errors.clear()
        for player,out,asset in self.extra_audio.values():player.stop(); player.setSource(QUrl()); player.deleteLater(); out.deleteLater()
        self.extra_audio.clear(); self.timeline.canvas.audio.clear(); self.timeline.canvas.aoi.clear()
    def _install_project(self,project):
        self._clear_media(); self.project=project; self.history=ProjectHistory(); self.session=EditSession(project,self.history)
        self.selected_id=None; self._mark_in=None; self._mark_out=None; self._time=0.; self._preview_invalid=False
        self._return_to_review=False
        self.review.set_latest_batch(())
        self.auto.set_latest_review_available(False)
        self.auto.set_progress('Ready. Run a detector, then review its proposals.')
        self.project.ensure_tracks()
        for asset in self.project.assets:
            if asset.enabled:
                try:self._activate_asset(asset)
                except Exception as exc:self._asset_errors[asset.id]=str(exc)
        self._apply_project_settings(); self._refresh_all(); self.seek(0.); self.history.mark_saved(self.project); self._update_name()
        self.set_workflow('Motion',force=True); QTimer.singleShot(50,self.timeline.fit_all)
        if self._asset_errors:self._message(f'{len(self._asset_errors)} source(s) need relinking or have an error. Double-click them in Sources.',12000)
    def _apply_project_settings(self):
        with QSignalBlocker(self.auto.world):self.auto.world.setChecked(bool(self.project.settings.get('world_frame_verified',False)))
        self.media.canvas.world_verified=bool(self.project.settings.get('world_frame_verified',False))
        axis=self.project.settings.get('up_axis','Z')
        with QSignalBlocker(self.media.axis):self.media.axis.setCurrentText(axis+' up')
        with QSignalBlocker(self.auto.up_axis):self.auto.up_axis.setCurrentText(axis)
        if hasattr(self.media.canvas,'set_up_axis'):self.media.canvas.set_up_axis(axis)
    def new_project(self,checked=False,force=False):
        if not force and not self._can_replace_project():return
        self._install_project(Project()); self._message('New project · Add your sources and annotation tracks.')
    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Open project',str(self.project.path.parent if self.project.path else BASE),'Annotation Studio project (*.studio.json *.ocumo.json *.json)')
        if path:self._load_project(path)
    def _load_project(self,path,force=False):
        if not force and not self._can_replace_project():return False
        try:
            project=Project.load(path)
            examples={(BASE/'examples'/name).resolve() for name in
                      ('S004_I02_example.ocumo.json','S004_I02_manual.studio.json','annotation_schema_demo.studio.json')}
            if Path(path).resolve() in examples:project.path=None
            recovered=project.settings.pop('_recovery_draft',None)
            original_path=project.settings.pop('_recovery_original_path',None)
            if original_path is not None:project.path=Path(original_path) if original_path else None
            self._install_project(project)
            if original_path is not None:
                self.history._saved=None
                if recovered:
                    existing=next((a for a in project.annotations if a.id==recovered.get('id')),None)
                    if existing:self.session.begin(existing.id)
                    elif recovered.get('temporal_kind')=='point':self.session.create_point(recovered['start_s'],recovered['track_id'])
                    else:self.session.create(recovered['start_s'],recovered['end_s'],recovered['track_id'])
                    self.session.update(**{k:v for k,v in recovered.items() if k not in ('id','source','original','history','temporal_kind')})
                    self.selected_id=self.session.draft.id; self._refresh_annotations()
            self._message(f'Opened {project.name}: {len(project.assets)} sources, {len(project.annotations)} segments.',9000); return True
        except Exception as exc:QMessageBox.critical(self,'Cannot open project',str(exc)); return False
    def load_example(self,checked=False,force=False):
        path=BASE/'examples/S004_I02_example.ocumo.json'
        if not path.exists():QMessageBox.information(self,'Sample not included','Use the complete package for the paired BVH sample, or open your own files.'); return
        self._load_project(path,force=force)
    def load_manual_example(self,checked=False,force=False):
        path=BASE/'examples/S004_I02_manual.studio.json'
        if not path.exists():
            QMessageBox.information(self,'Sample not included','Open the complete package for the manual BVH example, or create a new project and add your own sources.'); return
        if self._load_project(path,force=force):
            self._message('BVH example · use Automatic for motion proposals, or select a track to label. No reference labels are supplied.',12000)
    def load_schema_demo(self,checked=False,force=False):
        path=BASE/'examples/annotation_schema_demo.studio.json'
        if self._load_project(path,force=force):
            self.set_workflow('Overview',force=True); self.timeline.fit_all()
            self._message('SYNTHETIC UI DEMO · invented timings and object states; no recorded media or OCUMO reference labels.',20000)
    def save_project(self):
        if self.session.draft and self.session.dirty:
            if not self._settle_edit():return False
        if not self.project.path:return self.save_as()
        return self._save_to(self.project.path)
    def save_as(self):
        if self.session.draft and self.session.dirty:
            if not self._settle_edit():return False
        default=self.project.path or Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or str(Path.home()))/'Annotation_Studio.studio.json'
        path,_=QFileDialog.getSaveFileName(self,'Save project',str(default),'Annotation Studio project (*.studio.json)')
        if not path:return False
        if not path.lower().endswith('.json'):path+='.studio.json'
        return self._save_to(path)
    def _save_to(self,path):
        try:
            self.project.save(path); self.history.mark_saved(self.project); self._update_name(); self._remove_recovery(); self._message(f'Saved {Path(path).name}'); return True
        except Exception as exc:QMessageBox.critical(self,'Save failed',str(exc)); return False
    def recovery_path(self):
        base=Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation) or str(Path.home()/'.annotationstudio'))
        return base/'recovery.studio.json'
    def save_recovery(self):
        if self._initializing or not self._dirty():return
        try:
            p=deepcopy(self.project); p.settings['_recovery_original_path']=str(self.project.path) if self.project.path else ''
            if self.session.draft:p.settings['_recovery_draft']=asdict(self.session.draft)
            p.save(self.recovery_path()); self._message('Recovery copy updated.',1800)
        except Exception as exc:self._message(f'Recovery could not be written: {exc}',7000)
    def _remove_recovery(self):
        try:self.recovery_path().unlink(missing_ok=True)
        except OSError:pass
    def check_recovery(self):
        path=self.recovery_path()
        if path.exists() and QMessageBox.question(self,'Recover session','A recovery copy from a previous session is available. Open it?',QMessageBox.Yes|QMessageBox.No,QMessageBox.Yes)==QMessageBox.Yes:self._load_project(path,force=True)
    def open_recovery(self):
        path=self.recovery_path()
        if path.exists():self._load_project(path)
        else:self._message('No recovery copy is currently available.')

    def add_source_menu(self):
        kinds=['BVH / joint positions','Video (context / face / ego)','Audio','Gaze rays CSV','Gaze AOI CSV','Prop centroids']
        name,ok=QInputDialog.getItem(self,'Add source','Modality',kinds,0,False)
        if ok:self.add_asset_dialog(['motion','video','audio','gaze','aoi','props'][kinds.index(name)])
    def add_asset_dialog(self,kind,path=None):
        role,ok=QInputDialog.getItem(self,'Source actor','Map this source to:', ['R01','R02','Scene','Unknown'] if kind!='props' else ['Scene','R01','R02'],0,False)
        if not ok:return
        if kind=='gaze':
            mode,ok=QInputDialog.getItem(self,'Gaze format','CSV content',['3D gaze rays','AOI intervals / samples'],0,False)
            if not ok:return
            if mode.startswith('AOI'):kind='aoi'
        extra={}
        if kind=='video':
            view,ok=QInputDialog.getItem(self,'Video view','View',['Context','Face','Ego / privacy','Other'],0,False)
            if not ok:return
            extra['view']=view
        filters={'motion':'Motion (*.bvh *.npz)','video':'Video (*.mp4 *.mov *.mkv *.avi *.wmv *.webm)','audio':'Audio (*.wav *.flac *.mp3 *.m4a *.ogg)','gaze':'Gaze rays (*.csv)','aoi':'AOI (*.csv)','props':'Props (*.csv *.npz)'}
        if not path:
            path,_=QFileDialog.getOpenFileName(self,'Add '+kind,str(Path.home()),filters[kind])
        if not path:return
        self.add_asset(kind,role,path,extra=extra)
    def add_asset(self,kind,role,path,**kwargs):
        if kind=='motion' and any(a.enabled and a.kind=='motion' and a.role==role for a in self.project.assets):
            QMessageBox.information(self,'Actor already has motion','Disable or remove the existing motion source for this actor before adding another one.'); return None
        self._checkpoint(); asset=self.project.add_asset(kind,role,path,**kwargs)
        try:self._activate_asset(asset)
        except Exception as exc:
            self.project.assets.remove(asset); self.rebind_assets(); QMessageBox.warning(self,'Cannot load source',str(exc)); return None
        self._refresh_all(); self._refresh_audio_sources(prefer=asset.id); self._message(f'Loaded {asset.name}'); return asset
    def _activate_asset(self,asset):
        if not asset.enabled:return
        if not Path(asset.path).is_file():raise FileNotFoundError('File missing. Use Timing / relink to locate it.')
        if asset.kind=='motion':
            if asset.role not in ('R01','R02'):raise ValueError('Assign motion to R01 or R02.')
            if asset.role in self.motion:raise ValueError('Only one enabled motion source per actor is supported.')
            motion=open_motion(asset.path); self.motion[asset.role]=motion; self._asset_duration[asset.id]=motion.duration_s
            self.media.canvas.add_motion(asset.role,motion,asset.offset_s)
            if getattr(motion,'assumed_frame_rate',False):self._message(f'{asset.name}: no fps field; using 120 Hz. Add fps to the NPZ for exact timing.',10000)
        elif asset.kind=='video':self.media.bind_video(asset)
        elif asset.kind=='gaze':
            track=read_gaze_csv(asset.path,asset.role,asset.offset_s); self.media.canvas.set_gaze(asset.role,track)
            if hasattr(track,'times') and len(track.times):self._asset_duration[asset.id]=float(track.times[-1])-asset.offset_s
        elif asset.kind=='aoi':
            events=read_aoi_csv(asset.path,asset.offset_s); self.timeline.canvas.set_aoi(asset.role,events)
            if events:self._asset_duration[asset.id]=max(e for s,e,l in events)-asset.offset_s
        elif asset.kind=='props':
            track=read_props(asset.path,offset_s=asset.offset_s); self.media.canvas.set_props(track)
            if hasattr(track,'times') and len(track.times):self._asset_duration[asset.id]=float(track.times[-1])-asset.offset_s
        elif asset.kind=='audio':
            player=QMediaPlayer(self); output=QAudioOutput(self); output.setMuted(True); player.setAudioOutput(output)
            self.extra_audio[asset.id]=(player,output,asset)
            player.durationChanged.connect(lambda ms,ident=asset.id:self._media_duration_update(ident,ms))
            player.mediaStatusChanged.connect(lambda status,ident=asset.id:self._audio_loaded(ident,status))
            player.errorOccurred.connect(lambda *_,ident=asset.id:self._audio_error(ident))
            player.setSource(QUrl.fromLocalFile(asset.path))
            try:
                import soundfile as sf
                info=sf.info(asset.path); self._asset_duration[asset.id]=info.duration
                if Path(asset.path).suffix.lower()=='.wav':times,values=wav_envelope(asset.path,max_points=12000)
                else:
                    import numpy as np
                    values=[]; times=[]; block=max(1,round(info.frames/12000)); frame=0
                    with sf.SoundFile(asset.path) as stream:
                        for data in stream.blocks(blocksize=block,dtype='float32',always_2d=True):
                            times.append(frame/info.samplerate); values.append(float(np.max(np.abs(data)))); frame+=len(data)
                    times=np.asarray(times); values=np.asarray(values); values/=max(float(np.max(values,initial=0)),1e-9)
                self.timeline.canvas.set_audio(asset.role,times+asset.offset_s,values)
            except Exception as exc:self._message(f'Audio playback added; waveform unavailable: {exc}')
        else:raise ValueError(f'Unsupported source kind: {asset.kind}')
    def _audio_loaded(self,ident,status):
        if status in (QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia) and ident in self.extra_audio:self._sync_media(True)
    def _audio_error(self,ident):
        pair=self.extra_audio.get(ident)
        if pair and pair[0].errorString():self._asset_errors[ident]=pair[0].errorString(); self._update_assets(); self._message(pair[0].errorString())
    def _media_error(self,text):self._message(text,10000)
    def _media_duration_update(self,asset_id,ms):
        if ms>0 and any(a.id==asset_id for a in self.project.assets):self._asset_duration[asset_id]=ms/1000.; self._update_duration()
    def _selected_asset(self):
        item=self.assets.currentItem()
        return next((a for a in self.project.assets if item and a.id==item.data(0,Qt.UserRole)),None)
    def _update_assets(self):
        current=self._selected_asset(); ident=current.id if current else None
        self.assets.clear()
        for a in self.project.assets:
            icon='●' if a.enabled and a.id not in self._asset_errors else '○'
            item=QTreeWidgetItem([f'{icon}  {a.role}  ·  {a.kind.upper()}\n     {a.name}'])
            item.setData(0,Qt.UserRole,a.id); item.setToolTip(0,f'{a.path}\nMaster offset {a.offset_s:+.6f}s'+ ('\n'+self._asset_errors[a.id] if a.id in self._asset_errors else ''))
            if a.id in self._asset_errors:item.setForeground(0,QBrush(QColor('#A84A31')))
            self.assets.addTopLevelItem(item)
            if a.id==ident:self.assets.setCurrentItem(item)
    def edit_asset(self,*_):
        asset=self._selected_asset()
        if not asset:return
        dialog=AssetDialog(asset,self)
        if dialog.exec()!=QDialog.Accepted:return
        values=dialog.values()
        if asset.kind=='motion' and values['enabled'] and any(a.id!=asset.id and a.kind=='motion' and a.enabled and a.role==values['role'] for a in self.project.assets):
            QMessageBox.warning(self,'Motion source conflict','There is already an enabled motion source for that actor.'); return
        self._checkpoint()
        for key,value in values.items():setattr(asset,key,value)
        self.rebind_assets(); self._update_name()
    def remove_asset(self):
        asset=self._selected_asset()
        if not asset:return
        self._checkpoint(); self.project.assets.remove(asset); self.rebind_assets(); self._update_name()
    def rebind_assets(self):
        current=self._time; self._clear_media()
        for asset in self.project.assets:
            try:self._activate_asset(asset)
            except Exception as exc:self._asset_errors[asset.id]=str(exc)
        self._refresh_all(); self.seek(current)
    def _refresh_audio_sources(self,prefer=None):
        previous=self.listen.currentData()
        with QSignalBlocker(self.listen):
            self.listen.clear(); self.listen.addItem('Mute',('mute',''))
            for a in self.project.assets:
                if a.enabled and a.kind in ('audio','video'):self.listen.addItem(f'{a.role} · {a.extra.get("view",a.kind)}',(a.kind,a.id))
            index=next((i for i in range(self.listen.count()) if self.listen.itemData(i)==previous),0)
            if prefer:
                index=next((i for i in range(self.listen.count()) if self.listen.itemData(i)[1]==prefer),index)
            self.listen.setCurrentIndex(index)
        self._apply_audio_selection()
    def _apply_audio_selection(self,*_):
        selected=self.listen.currentData() or ('mute',''); volume=self.volume.value()/100
        for _,panel in self.media.panels:
            panel.audio.setMuted(not(panel.asset and selected==('video',panel.asset.id))); panel.audio.setVolume(volume)
        for player,output,asset in self.extra_audio.values():output.setMuted(selected!=('audio',asset.id)); output.setVolume(volume)
    def _update_duration(self):
        ends=[self._asset_duration.get(a.id,0)+a.offset_s for a in self.project.assets if a.enabled and a.id in self._asset_duration]
        ends.extend(a.end_s for a in self.project.annotations)
        manual=float(self.project.settings.get('manual_duration_s',0))
        duration=max([.1,manual,*ends]) if ends or manual else float(self.project.settings.get('duration_s',120.))
        self.project.settings['duration_s']=duration; self.timeline.set_duration(duration); self.scrub.setMaximum(round(duration*1000))
        self._set_frame_grid(self._quick_track)
        if self._time>duration:self.seek(duration)
    def _set_frame_grid(self,track_id):
        track=self.project.get_track(track_id)
        if track and workspace_for_track(track)=='Speech':
            self.timeline.canvas.frame_step=.001; self.timeline.canvas.snap_offset=0.
            self.editor.start.setSingleStep(.001); self.editor.end.setSingleStep(.001)
            self.timeline.snap.setToolTip('Speech time grid: 1 ms. Hold Shift for free adjustment. Stored source times keep their precision.')
            return
        motion=self.motion.get(track.role) if track else None
        asset=next((a for a in self.project.assets if track and a.kind=='motion' and a.enabled and a.role==track.role),None)
        self.timeline.canvas.frame_step=motion.frame_time if motion else min((m.frame_time for m in self.motion.values()),default=1/30)
        self.timeline.canvas.snap_offset=asset.offset_s if asset else 0.
        self.editor.start.setSingleStep(self.timeline.canvas.frame_step); self.editor.end.setSingleStep(self.timeline.canvas.frame_step)
        self.timeline.snap.setToolTip('Snap to the active motion frame grid; hold Shift for free adjustment.')

    def _axis_changed(self,value):
        if self._initializing or self._updating:return
        self._checkpoint(); self.project.settings['up_axis']=value[0]; self.auto.up_axis.setCurrentText(value[0]); self._update_name()
    def set_world_frame_verified(self,yes):
        if self._initializing or self._updating:return
        self._checkpoint(); self.project.settings['world_frame_verified']=bool(yes); self.media.canvas.world_verified=bool(yes); self.media.canvas.update(); self._update_name()

    def _set_speed(self):
        if self._playing:self._time=self._clock0+(time.perf_counter()-self._t0)*self._rate
        self._rate=float(self.speed.currentData() or 1); self._clock0=self._time; self._t0=time.perf_counter(); self._sync_media(True)
    def step_frame(self,direction):
        self.pause(); self.seek(self._time+direction*self.timeline.canvas.frame_step,follow=True)
    def toggle_play(self):self.pause() if self._playing else self.start()
    def _loop_bounds(self,a):
        if a is None:return None
        if a.is_point:
            return max(0.,a.start_s-.75),min(self.project.settings.get('duration_s',120.),a.start_s+.75)
        return a.start_s,a.end_s
    def start(self):
        a=self.session.draft or self._selected()
        bounds=self._loop_bounds(a)
        if self.loop.isChecked() and bounds and not bounds[0]<=self._time<bounds[1]:self.seek(bounds[0])
        elif self._time>=self.project.settings.get('duration_s',120.):self.seek(0.)
        self._playing=True; self._clock0=self._time; self._t0=time.perf_counter(); self.play.setText('Ⅱ  Pause'); self._sync_media(True)
    def pause(self):
        self._playing=False
        if hasattr(self,'play'):self.play.setText('▶  Play')
        if hasattr(self,'media'):self._sync_media(True)
    def seek(self,value,follow=False):
        self._time=max(0.,min(float(value),float(self.project.settings.get('duration_s',120.))))
        self._clock0=self._time; self._t0=time.perf_counter(); self._show_time(follow); self._sync_media(True)
    def _show_time(self,follow=False):
        self.time_label.setText(f'{int(self._time//60):02}:{self._time%60:06.3f}')
        with QSignalBlocker(self.scrub):self.scrub.setValue(round(self._time*1000))
        self.timeline.set_time(self._time,follow=follow); self.media.canvas.set_time(self._time)
    def _sync_media(self,force=False):
        self.media.sync(self._time,self._playing,force,self._rate)
        for player,output,asset in self.extra_audio.values():
            local=self._time-asset.offset_s; duration=player.duration()/1000.
            if local<0 or duration>0 and local>=duration:player.pause(); continue
            target=round(local*1000)
            if abs(player.playbackRate()-self._rate)>.001:player.setPlaybackRate(self._rate)
            if force or abs(player.position()-target)>120:player.setPosition(target)
            if self._playing:
                if player.playbackState()!=QMediaPlayer.PlayingState:player.play()
            else:player.pause()
    def _tick(self):
        if not self._playing:return
        self._time=self._clock0+(time.perf_counter()-self._t0)*self._rate
        a=self.session.draft or self._selected()
        bounds=self._loop_bounds(a)
        if self.loop.isChecked() and bounds and self._time>=bounds[1]:self.seek(bounds[0]); return
        if self._time>=self.project.settings.get('duration_s',120.):self._time=self.project.settings['duration_s']; self.pause()
        self._show_time(True)
        if time.perf_counter()-self._last_sync>.4:self._sync_media(False); self._last_sync=time.perf_counter()
    def mark_in(self):self._mark_in=self._time; self._message(f'IN {self._time:.3f}s · press O at the end, then Enter.')
    def mark_out(self):
        self._mark_out=self._time
        if self._mark_in is not None:self.auto.set_marked_range(*sorted((self._mark_in,self._mark_out)))
        self._message(f'OUT {self._time:.3f}s · press Enter to create a segment.')
    def create_marked(self):
        if self._mark_in is None or self._mark_out is None:return
        if not self._quick_track:self._message('Choose or add a track first.'); return
        if track_temporal_kind(self.project.get_track(self._quick_track))=='point':
            self.add_point(self._mark_in,self._quick_track); self._mark_in=None; self._mark_out=None; return
        start,end=sorted((self._mark_in,self._mark_out))
        if end-start<.001:return
        self.add_range(start,end,self._quick_track); self._mark_in=None; self._mark_out=None
    def quick_add(self):
        if not self._quick_track:self.add_track()
        if not self._quick_track:return
        if track_temporal_kind(self.project.get_track(self._quick_track))=='point':
            self.add_point(self._time,self._quick_track); return
        duration=self.project.settings.get('duration_s',120.); start=min(self._time,max(0,duration-1))
        self.add_range(start,min(duration,start+1),self._quick_track)
    def quick_add_point(self):
        track=self.project.get_track(self._quick_track)
        if track is None or track_temporal_kind(track)!='point':
            self._message('Select a Turn Transition point track, then click the timeline or press Ctrl+M.'); return
        self.add_point(self._time,track.id)

    def run_segmentation(self):
        if self._thread and self._thread.isRunning():return
        if not self.motion:QMessageBox.information(self,'Motion source required','Add an R01 or R02 BVH / joint-position NPZ first.'); return
        try:options=self.auto.motion_options()
        except ValueError as exc:QMessageBox.warning(self,'Analysis settings',str(exc)); return
        assets=deepcopy(self.project.assets); motions=dict(self.motion)
        self._job_replace=options.get('replace',True); self._job_scope=None
        self._start_job(lambda progress,cancel:run_motion_job(motions,assets,options,progress,cancel),'Motion segmentation')
    def run_audio(self):
        if self._thread and self._thread.isRunning():return
        ident=self.auto.audio_asset.currentData(); asset=next((a for a in self.project.assets if a.id==ident),None)
        if not asset:QMessageBox.information(self,'Audio source required','Add a WAV or FLAC audio source and choose its actor mapping.'); return
        try:options=dict(self.auto.audio_options())
        except ValueError as exc:QMessageBox.warning(self,'Audio settings',str(exc)); return
        asset=deepcopy(asset); model_id=options.pop('model_id'); self._job_replace=True
        self._job_scope={'source_asset_ids':[asset.id],'roles':[asset.role],'channels':['Speech'],'start_s':max(0.,asset.offset_s),'end_s':None,'sources':[f'auto:{model_id}']}
        options['source_asset_id']=asset.id
        if model_id=='energy':options['db_threshold']=options.pop('threshold',-36.)
        def job(progress,cancel):
            result=detect_audio(asset.path,model_id=model_id,role=asset.role,offset_s=asset.offset_s,progress=progress,cancel=cancel,**options)
            sources=sorted(set(a.source for a in result))
            scope=dict(self._job_scope)
            if sources:scope['sources']=sources
            return result,{'scope':scope,'summary':f'{model_id}: {len(result)} audio candidates'}
        self._start_job(job,'Audio analysis')
    def _start_job(self,job,title):
        self._job_assets_signature={a.id:(a.kind,a.role,a.path,a.offset_s,a.enabled) for a in self.project.assets}
        self._cancel_token=threading.Event(); worker=AnalysisWorker(job,self._cancel_token); thread=QThread(self)
        self._worker,self._thread=worker,thread; worker.moveToThread(thread); self.auto.set_busy(True); self.auto.set_progress(title+'…')
        thread.started.connect(worker.run); worker.progress.connect(self.auto.set_progress); worker.done.connect(self._auto_done); worker.failed.connect(self._auto_failed); worker.cancelled.connect(lambda:self.auto.set_progress('Cancelled · no partial results were inserted.'))
        worker.finished.connect(thread.quit); worker.finished.connect(worker.deleteLater); thread.finished.connect(self._job_finished); thread.finished.connect(thread.deleteLater); thread.start()
    def cancel_job(self):
        if self._cancel_token:self._cancel_token.set(); self.auto.set_progress('Cancellation requested · waiting for the current model step to return…')
    def _job_finished(self):
        self._thread=None; self._worker=None; self._cancel_token=None; self.auto.set_busy(False)
        if self._close_after_job:self._close_after_job=False; self.close()
    def _auto_done(self,result,detail):
        scope=detail.get('scope') or self._job_scope or {}
        current={a.id:(a.kind,a.role,a.path,a.offset_s,a.enabled) for a in self.project.assets}
        changed=[ident for ident in scope.get('source_asset_ids',[]) if current.get(ident)!=self._job_assets_signature.get(ident)]
        if changed:
            self.auto.set_progress('Sources changed during analysis. Results were discarded; run again with the current timing and mapping.')
            self._message('Analysis results discarded because a source path, actor mapping or time offset changed.',10000); return
        # Protect the active draft's saved record even if it has not yet been accepted.
        protected_id=self.session.draft.id if self.session.draft and not self.session.is_new else None
        self._checkpoint()
        base=next((a for a in self.project.annotations if a.id==protected_id),None)
        history=deepcopy(base.history) if base else None
        if base:base.history.append({'action':'active edit protection'})
        try:summary=merge_auto_results(self.project,result,scope,replace=self._job_replace)
        finally:
            if base:base.history=history
        self._refresh_annotations(rebind_editor=False); self._update_duration()
        msg=f'{summary.get("added",len(result))} candidates added · {summary.get("protected",0)} reviewed/edited records protected'

        if detail.get('skipped'):
            msg+=' · '+ '; '.join(f"{v.get('role','Source')}: {v.get('reason','skipped')}" for v in detail['skipped'])
        self.auto.set_progress(msg)
        result_ids={a.id for a in result} if summary['added'] else set()
        self._offer_candidate_review({a.id for a in self.project.annotations
                                      if a.id in result_ids and a.status=='pending'})
        self._message(msg,10000)
    def _auto_failed(self,error):
        self.auto.set_progress('Failed · '+error); QMessageBox.warning(self,'Analysis could not run',error)

    def import_annotations(self):
        path,_=QFileDialog.getOpenFileName(self,'Import annotations',str(BASE/'examples'),'Annotation CSV (*.csv)')
        if not path:return
        if not self._settle_edit():return
        try:
            annotations=import_annotation_csv(path); self._checkpoint(); count=self.project.import_annotations(annotations); self._refresh_annotations(); self._update_duration(); self._message(f'Imported {len(count)} records. Repeated stable IDs were skipped.')
        except Exception as exc:QMessageBox.warning(self,'Import failed',str(exc))
    def export_annotations(self):
        if not self._settle_edit():return
        dialog=ExportDialog(self,project=self.project)
        if dialog.exec()!=QDialog.Accepted:return
        state=dialog.review_state(); categories=dialog.selected_categories()
        annotations=select_annotations(self.project,state,categories)
        if not annotations:
            QMessageBox.information(self,'Nothing to export','No annotations match the selected types and review state.'); return
        eaf=dialog.format.currentIndex()==1; suffix='eaf' if eaf else 'csv'
        folder=self.project.path.parent if self.project.path else Path.home()
        if not eaf and dialog.export_layout()!='combined':
            parent=QFileDialog.getExistingDirectory(self,'Choose export parent folder',str(folder))
            if not parent:return
            try:
                result=export_annotation_bundle(self.project,parent,review_state=state,
                                                categories=categories,layout=dialog.export_layout())
                self._message(f"Exported {result['annotation_count']} annotations in {result['category_count']} types to {result['directory']}",15000)
            except Exception as exc:QMessageBox.critical(self,'Export failed',str(exc))
            return
        stem=suggested_export_stem(self.project)
        name=category_export_stem(categories[0]) if categories is not None and len(categories)==1 else 'annotations'
        default=folder/f'{stem}_{name}.{suffix}'
        path,_=QFileDialog.getSaveFileName(self,'Export',str(default),f'{suffix.upper()} (*.{suffix})')
        if not path:return
        if not path.lower().endswith('.'+suffix):path+='.'+suffix
        try:
            if eaf:export_eaf(annotations,path)
            else:export_annotation_csv(self.project,path,review_state=state,categories=categories)
            self._message(f'Exported {len(annotations)} annotations to {Path(path).name}.')
        except Exception as exc:QMessageBox.critical(self,'Export failed',str(exc))

    def keyPressEvent(self,event):
        focused=QApplication.focusWidget()
        if isinstance(focused,(QLineEdit,QPlainTextEdit,QAbstractSpinBox,QComboBox)) or (focused and isinstance(focused.parent(),QAbstractSpinBox)):
            super().keyPressEvent(event); return
        if event.modifiers() in (Qt.NoModifier,Qt.KeypadModifier):
            actions={Qt.Key_Space:self.toggle_play,Qt.Key_Left:lambda:self.step_frame(-1),Qt.Key_Right:lambda:self.step_frame(1),Qt.Key_I:self.mark_in,Qt.Key_O:self.mark_out,Qt.Key_Return:self.create_marked,Qt.Key_Enter:self.create_marked,Qt.Key_Delete:self.delete_selected}
            if event.key() in actions:actions[event.key()](); event.accept(); return
        super().keyPressEvent(event)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):event.acceptProposedAction()
    def dropEvent(self,event):
        mapping={'.bvh':'motion','.npz':'motion','.mp4':'video','.mov':'video','.mkv':'video','.avi':'video','.wav':'audio','.flac':'audio','.mp3':'audio','.m4a':'audio'}
        for url in event.mimeData().urls():
            path=url.toLocalFile(); ext=Path(path).suffix.lower()
            if ext=='.json':self._load_project(path)
            elif ext in mapping:self.add_asset_dialog(mapping[ext],path=path)
            elif ext=='.csv':
                kind,ok=QInputDialog.getItem(self,'CSV source','CSV content',['Gaze rays','Gaze AOI','Props','Annotations'],0,False)
                if ok and kind=='Annotations':
                    try:
                        self._checkpoint(); self.project.import_annotations(import_annotation_csv(path)); self._refresh_annotations(); self._update_duration()
                    except Exception as exc:QMessageBox.warning(self,'CSV import',str(exc))
                elif ok:self.add_asset_dialog({'Gaze rays':'gaze','Gaze AOI':'aoi','Props':'props'}[kind],path=path)
        event.acceptProposedAction()
    def shortcuts(self):
        QMessageBox.information(self,'Keyboard shortcuts','Space  Play / pause\nLeft / Right  One active time-grid step\nI / O, then Enter  Mark and create an interval\nCtrl+N  New annotation on active track\nCtrl+M  Point at playhead on a point track\nCtrl+Enter  Accept current edit\nEscape  Cancel current edit\nCtrl+Z / Ctrl+Y  Undo / redo\nCtrl+D  Duplicate annotation\nCtrl+Shift+K  Split an interval at playhead\nDelete  Delete selected annotation\nCtrl+S  Save project\nCtrl+0  Fit timeline\n\nIntervals: drag blank space to create; click to edit; drag edges to trim or the center to move. Points: click a point track to create a diamond; drag the diamond to move it. Hold Shift to bypass snapping.\n3D: drag to orbit; Shift+drag to pan; wheel to zoom.')
    def about(self):
        QMessageBox.information(self,'Annotation Studio',f'Annotation Studio {VERSION}\n\nAutomatic-first Motion and Speech, with editable label lists. Proposed workflow and installed detector support are shown separately. Intervals and true point events are supported.\n\nWorkspaces: Overview, Activity, Motion, Gesture, HOI, Affect, Speech, Spatial, Social and Review. Activity supports manual whole-activity intervals with optional objects and descriptions. HOI includes object actions and sustained states with stable Object IDs. Context queries compute temporal overlap without creating compound labels.\n\nBuilt in: motion proposals, audio energy, rule-based speech-turn candidates from attributed Speaking intervals, and derived timing. Optional: Silero VAD and YAMNet. No model download at launch. ASR, diarization, automatic contact detection and social-semantic inference remain development tasks.\n\nGaze results remain external references; new gaze and facial annotation are out of scope. Accepted records indicate human review, not a benchmark accuracy guarantee.')
    def closeEvent(self,event):
        self.pause()
        if self._thread and self._thread.isRunning():
            self._close_after_job=True; self.cancel_job(); self._message('Closing after the current analysis step has stopped.',12000); event.ignore(); return
        if not self._can_replace_project():event.ignore(); return
        self._remove_recovery(); self.timer.stop(); self.autosave_timer.stop(); self._clear_media(); event.accept()


def launch():
    import argparse
    parser=argparse.ArgumentParser(description='Annotation Studio desktop')
    parser.add_argument('project_file',nargs='?'); parser.add_argument('--project'); parser.add_argument('--example',action='store_true'); parser.add_argument('--manual-example',action='store_true'); parser.add_argument('--schema-demo',action='store_true'); parser.add_argument('--no-recovery',action='store_true')
    args,qt_args=parser.parse_known_args()
    app=QApplication([sys.argv[0],*qt_args]); app.setApplicationName('Annotation Studio'); app.setOrganizationName('AnnotationStudio'); app.setApplicationVersion(VERSION); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window=MainWindow(example=args.example,recover=not(args.no_recovery or args.example or args.manual_example or args.schema_demo or args.project or args.project_file))
    if args.manual_example:window.load_manual_example(force=True)
    if args.schema_demo:window.load_schema_demo(force=True)
    path=args.project or args.project_file
    if path:window._load_project(path,force=True)
    window.show()
    return app.exec()
