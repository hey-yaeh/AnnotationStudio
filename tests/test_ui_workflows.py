"""Real Qt interaction regressions using generated motion files.

No model accuracy is measured here. The media test uses synthetic test signals
and verifies decoding, timeline offsets and seeks only.
"""
from __future__ import annotations
import os
import sys
import shutil
import subprocess
import time
import wave
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
if sys.platform.startswith('linux') and os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
    # Qt 6.12's PipeWire initialization segfaults in this no-audio-server
    # container; this test-only fallback avoids changing desktop user setup.
    os.environ.setdefault('QT_AUDIO_BACKEND', 'pulseaudio')

import numpy as np
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from annotationstudio.ui import MainWindow
from annotationstudio.theme import STYLE
from annotationstudio.ontology import WORKSPACES
from annotationstudio.models import Annotation
from annotationstudio.timeline import LABEL_W
from test_primitive_rules import _bvh

_APP = None


@pytest.fixture(scope='module')
def app(qapp):
    global _APP
    _APP = qapp
    _APP.setStyleSheet(STYLE)
    return _APP


@pytest.fixture(scope='module')
def motion_files(tmp_path_factory):
    files = {}
    for role in ('R01', 'R02'):
        folder = tmp_path_factory.mktemp(role)
        arm = {('RightForeArm', 'Z'): [(2., 0), (2.7, 48), (3.8, 48), (4.3, 0)]}
        files[role] = _bvh(folder, arm).path
    return files


@pytest.fixture
def window(app, monkeypatch, tmp_path, motion_files):
    messages = []
    def message(parent, title, text, *args, **kwargs):
        messages.append((title, text))
        return QMessageBox.Ok
    for name in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QMessageBox, name, message)
    # Avoid writing the user's recovery location while running test windows.
    monkeypatch.setattr(MainWindow, 'recovery_path', lambda self: tmp_path / 'qa-recovery.json')
    widget = MainWindow(recover=False)
    widget.autosave_timer.stop()
    for role, path in motion_files.items():
        assert widget.add_asset('motion', role, path) is not None
    track = next(track for track in widget.project.tracks
                 if track.role == 'R01' and track.channel == 'Right Arm')
    widget.project.add_annotation(
        2.05, 3.8, role='R01', channel='Right Arm', track_id=track.id,
        category='Motion Primitive', label='flex right elbow', source='auto:velocity')
    widget._refresh_annotations()
    widget.show()
    widget.timeline.fit_all()
    QTest.qWait(100)
    widget.qa_messages = messages
    assert len(widget.motion) == 2
    yield widget
    if widget._thread is not None:
        widget.cancel_job()
        wait_until(lambda: widget._thread is None, timeout=15.)
    widget.session.cancel()
    widget._preview_invalid = False
    widget.history.mark_saved(widget.project)
    widget.close()
    widget.deleteLater()
    app.processEvents()


def wait_until(predicate, timeout=8.):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError('Timed out waiting for the Qt workflow')
        QTest.qWait(15)


def sample_arm(window):
    return next(a for a in window.project.annotations
                if a.role == 'R01' and a.channel == 'Right Arm'
                and a.source == 'auto:velocity' and a.end_s - a.start_s > 1)


def prepare_interval_view(window, annotation):
    canvas = window.timeline.canvas
    canvas.px_per_s = 70.
    window.timeline._refresh_scroll()
    window.timeline.scroll.setValue(round(max(0., annotation.start_s - 4.) * 1000))
    window.timeline.reveal(annotation)
    QApplication.processEvents()
    return canvas


def mouse_drag(widget, first, last):
    QTest.mouseMove(widget, first)
    QTest.mousePress(widget, Qt.LeftButton, pos=first)
    QTest.mouseMove(widget, last, delay=30)
    QTest.mouseRelease(widget, Qt.LeftButton, pos=last)
    QApplication.processEvents()


def test_edge_and_center_drags_stay_draft_until_accept(window):
    annotation = sample_arm(window)
    original = deepcopy(asdict(annotation))
    canvas = prepare_interval_view(window, annotation)
    rect = canvas.annotation_rect(annotation)
    edge = QPoint(round(rect.left() + 2), round(rect.center().y()))
    mouse_drag(canvas, edge, edge + QPoint(28, 0))
    assert window.session.draft is not None
    assert window.session.draft.start_s > original['start_s'] + .25
    assert asdict(annotation) == original
    QTest.mouseClick(window.editor.cancel, Qt.LeftButton)
    assert window.session.draft is None
    assert asdict(annotation) == original

    rect = canvas.annotation_rect(annotation)
    middle = rect.center().toPoint()
    mouse_drag(canvas, middle, middle + QPoint(35, 0))
    draft = window.session.draft
    assert draft is not None
    assert draft.start_s > original['start_s'] + .35
    assert draft.end_s - draft.start_s == pytest.approx(original['end_s'] - original['start_s'])
    assert asdict(annotation) == original
    committed_start = window.editor.start.value()
    QTest.mouseClick(window.editor.accept, Qt.LeftButton)
    assert window.session.draft is None
    saved = next(a for a in window.project.annotations if a.id == annotation.id)
    assert saved.status == 'approved'
    assert saved.start_s == pytest.approx(committed_start)
    assert saved.original and saved.history
    assert not window.qa_messages


def test_blank_drag_label_accept_undo_redo(window):
    track = window.project.add_track(name='QA posture', role='R01', workspace='Motion',
                                     category='Body Posture', channel='Full Body')
    window._refresh_annotations()
    canvas = window.timeline.canvas
    canvas.px_per_s = 60.
    window.timeline._refresh_scroll()
    window.timeline.scroll.setValue(0)
    row = next(row for row in canvas.rows if row.get('track') and row['track'].id == track.id)
    window.timeline.area.ensureVisible(0, int(row['y'] + row['height'] / 2), 0, 20)
    QApplication.processEvents()
    first = QPoint(round(canvas.time_x(2.)), round(row['y'] + 15))
    last = QPoint(round(canvas.time_x(4.)), first.y())
    before = len(window.project.annotations)
    mouse_drag(canvas, first, last)
    assert window.session.is_new
    assert len(window.project.annotations) == before
    label = next(label.name for label in window.project.labels_for('Body Posture') if label.name != 'Unlabeled')
    window.editor.label.setCurrentText(label)
    ident = window.session.draft.id
    QTest.mouseClick(window.editor.accept, Qt.LeftButton)
    accepted = next(a for a in window.project.annotations if a.id == ident)
    assert accepted.status == 'approved' and accepted.label_id
    assert len(window.project.annotations) == before + 1
    window.undo()
    assert all(a.id != ident for a in window.project.annotations)
    window.redo()
    assert next(a for a in window.project.annotations if a.id == ident).status == 'approved'
    assert not window.qa_messages


def test_workspaces_and_hoi_edit_fields_are_independent(window):
    assert len(WORKSPACES) == 10
    assert 'Gaze' not in WORKSPACES and 'Face' not in WORKSPACES
    for name in WORKSPACES:
        QTest.mouseClick(window.nav[name], Qt.LeftButton)
        assert window._workflow == name
        assert window.timeline.canvas.workspace == name
    assert 'HOI' in window.nav and 'Affect' in window.nav
    assert 'Face' not in window.nav and 'Gaze' not in window.nav
    track = window.project.add_track(name='Cup handling', role='R01', workspace='HOI',
                                     category='Action / HOI', channel='Hands')
    window._refresh_annotations()
    QTest.mouseClick(window.nav['HOI'], Qt.LeftButton)
    window.add_range(3., 5., track.id)
    assert window.editor.object_id.isVisible()
    window.editor.label.setCurrentText('hold object')
    window.editor.object_id.setText('cup_01')
    window.editor.hand.setCurrentText('Both hands')
    assert window.accept_edit()
    saved = window._selected()
    assert saved.attributes['object_id'] == 'cup_01'
    assert saved.attributes['effector'] == 'Both hands'
    assert window.project.get_track(saved.track_id).workspace == 'HOI'
    QTest.mouseClick(window.nav['Gesture'], Qt.LeftButton)
    assert track.id not in {item.id for item in window.timeline.canvas.visible_tracks()}
    assert not window.qa_messages


def test_duplicate_track_types_and_overlaps_have_separate_hit_targets(window):
    track1 = window.project.add_track(name='Hands A', role='R01', workspace='Motion',
                                      category='Hand Behavior', channel='Hands')
    track2 = window.project.add_track(name='Hands B', role='R01', workspace='Motion',
                                      category='Hand Behavior', channel='Hands')
    first = window.project.add_annotation(2., 5., track_id=track1.id, role='R01', channel='Hands', category='Hand Behavior', label='hands touching')
    overlap = window.project.add_annotation(3., 6., track_id=track1.id, role='R01', channel='Hands', category='Hand Behavior', label='fingers interlaced')
    other = window.project.add_annotation(2., 5., track_id=track2.id, role='R01', channel='Hands', category='Hand Behavior', label='hand clasp')
    window._refresh_annotations()
    canvas = window.timeline.canvas
    rectangles = [canvas.annotation_rect(a) for a in (first, overlap, other)]
    assert all(rect is not None for rect in rectangles)
    assert not rectangles[0].intersects(rectangles[1])
    assert not rectangles[0].intersects(rectangles[2])
    for annotation, rectangle in zip((first, overlap, other), rectangles):
        position = rectangle.center()
        assert canvas._annotation_at(position.x(), position.y()).id == annotation.id
    assert len([t for t in canvas.visible_tracks() if t.category == 'Hand Behavior']) == 2


def test_label_typing_survives_preview_refresh(window):
    annotation = sample_arm(window)
    window.select_annotation(annotation.id)
    edit = window.editor.label.lineEdit()
    edit.setFocus()
    edit.selectAll()
    QTest.keyClicks(edit, 'custom arm preparation')
    assert edit.text() == 'custom arm preparation'
    assert window.session.draft.label == edit.text()
    window._refresh_annotations(rebind_editor=False)
    assert window.editor.label.lineEdit() is edit
    assert edit.text() == 'custom arm preparation'
    window.change_span(annotation.id, annotation.start_s + .1, annotation.end_s)
    assert edit.text() == 'custom arm preparation'
    assert window.session.draft.label == edit.text()
    window.cancel_edit()
    assert annotation.label != 'custom arm preparation'


def test_real_motion_thread_keeps_accepted_and_active_drafts(window):
    gesture_track = window.project.add_track(name='Gesture Type', role='R01', workspace='Gesture',
                                             category='Gesture Type', channel='Hands')
    window._refresh_annotations()
    window.set_workflow('Gesture')
    window.submodule.setCurrentText('Gesture Type')
    canvas = window.timeline.canvas
    window.timeline.role_filter.setCurrentText('R02')
    canvas.collapsed.add('R01')
    canvas.px_per_s = 160.
    window.timeline._refresh_scroll()
    window.timeline.scroll.setValue(0)
    window.seek(0.)
    QTest.mouseClick(window.auto_detect_button, Qt.LeftButton)
    assert window.right_tabs.currentWidget() is window.auto
    assert window.auto.tabs.tabText(window.auto.tabs.currentIndex()) == 'Motion'
    assert window._workflow == 'Gesture'
    window.auto._select_parts(False)
    window.auto.parts['Right Arm'].setChecked(True)
    window.auto.motion_role.setCurrentIndex(window.auto.motion_role.findData('R01'))
    window.auto.set_marked_range(0., 6.)
    window.auto.structure.setChecked(False)
    assert 'dyadic' not in window.auto.motion_options()
    QTest.mouseClick(window.auto.motion_run, Qt.LeftButton)
    wait_until(lambda: window._thread is None, timeout=20.)
    generated = [a for a in window.project.annotations if a.source == 'auto:graph']
    assert len(generated) >= 2
    assert window.nav['Gesture'].isChecked()
    assert canvas.category_filter == 'Gesture Type'
    assert window.session.draft is None
    assert canvas.filter_role == 'All'
    assert 'R01' not in canvas.collapsed
    first_candidate = min(generated, key=lambda a: a.start_s)
    candidate_rect = canvas.annotation_rect(first_candidate)
    assert candidate_rect is not None
    assert canvas.row_at(candidate_rect.center().y())['kind'] == 'reference'
    assert first_candidate.track_id not in {track.id for track in canvas.visible_tracks()}
    assert canvas.visible_start <= first_candidate.start_s <= canvas.visible_start + canvas.time_visible_span()
    viewport = window.timeline.area.viewport()
    assert viewport.rect().intersects(candidate_rect.toAlignedRect().translated(canvas.mapTo(viewport, QPoint())))
    assert window._time == 0.
    assert window.right_tabs.currentWidget() is window.review
    assert window.review.latest_only.isChecked()
    assert window.review.table.rowCount() == len(generated)
    assert {window.review.table.item(i, 0).data(Qt.UserRole)
            for i in range(window.review.table.rowCount())} == {a.id for a in generated}
    reference_before = asdict(first_candidate)
    QTest.mouseClick(canvas, Qt.LeftButton,
                     pos=QPoint(round(candidate_rect.left() + 4), round(candidate_rect.center().y())))
    assert window._time == first_candidate.start_s
    assert window.session.draft is None
    window.timeline.motion_refs.click()
    assert canvas.annotation_rect(first_candidate) is None
    window.timeline.motion_refs.click()
    assert canvas.annotation_rect(first_candidate) is not None

    gesture_row = next(row for row in canvas.rows
                       if row['kind'] == 'track' and row['track'].id == gesture_track.id)
    gesture_y = round(gesture_row['y'] + gesture_row['height'] / 2)
    window.timeline.area.ensureVisible(0, gesture_y, 0, 15)
    gesture_start = QPoint(round(canvas.time_x(first_candidate.start_s)), gesture_y)
    mouse_drag(canvas, gesture_start, gesture_start + QPoint(70, 0))
    assert window.session.draft.track_id == gesture_track.id
    window.choose_palette_label('gesture (unclassified)')
    assert window.accept_edit()
    assert window._selected().category == 'Gesture Type'
    assert asdict(first_candidate) == reference_before
    assert window.nav['Gesture'].isChecked()

    window.open_latest_review()
    reference = window.review.table.item(0, 2)
    QTest.mouseClick(window.review.table.viewport(), Qt.LeftButton,
                     pos=window.review.table.visualItemRect(reference).center())
    assert window.session.draft is None
    assert window.nav['Gesture'].isChecked()

    window.set_workflow('Motion')
    window.open_latest_review()
    specific = {a.id for a in generated if 'primitive_evidence' in a.attributes}
    first = next(window.review.table.item(i, 2) for i in range(window.review.table.rowCount())
                 if window.review.table.item(i, 2).data(Qt.UserRole) in specific)
    accepted_id = first.data(Qt.UserRole)
    window.review.table.scrollToItem(first)
    rect = window.review.table.visualItemRect(first)
    QTest.mouseClick(window.review.table.viewport(), Qt.LeftButton, pos=rect.center())
    assert window.session.draft.id == accepted_id
    assert window.right_tabs.currentWidget() is window.label_palette
    assert 'BVH rule' in window.editor.source.text()
    assert 'Measured excursion' in window.editor.source.toolTip()
    window.editor.start.setValue(window.session.draft.start_s + .05)
    window.editor.label.setCurrentText('QA reviewed arm movement')
    assert window.accept_edit()
    assert window.right_tabs.currentWidget() is window.review
    assert window.review.table.rowCount() == len(generated) - 1
    before = deepcopy(asdict(window._selected()))
    editing = next(a for a in generated if a.id != accepted_id)
    window.select_annotation(editing.id)
    window.editor.label.setCurrentText('QA uncommitted preparation')
    saved_before = deepcopy(asdict(next(a for a in window.project.annotations if a.id == editing.id)))
    window.run_segmentation()
    wait_until(lambda: window._thread is None, timeout=20.)
    assert asdict(next(a for a in window.project.annotations if a.id == accepted_id)) == before
    assert asdict(next(a for a in window.project.annotations if a.id == editing.id)) == saved_before
    assert window.session.draft.id == editing.id
    assert window.session.draft.label == 'QA uncommitted preparation'
    assert window.editor.label.currentText() == 'QA uncommitted preparation'
    assert window.right_tabs.currentWidget() is window.label_palette
    assert not window.qa_messages
    window.cancel_edit()


def test_synthetic_video_audio_decode_seek_and_offsets(window, tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg command is needed to create synthetic QA media')
    video_path = tmp_path / 'synthetic_test_clip.mp4'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=10',
                    '-t', '10', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video_path)],
                   check=True, capture_output=True, timeout=30.)
    audio_path = tmp_path / 'synthetic_tone.wav'
    rate = 16000
    tone = (np.sin(2 * np.pi * 440 * np.arange(rate * 10) / rate) * 4000).astype('<i2')
    with wave.open(str(audio_path), 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(tone.tobytes())
    video_asset = window.add_asset('video', 'R01', video_path, offset_s=2., extra={'view': 'Synthetic QA'})
    audio_asset = window.add_asset('audio', 'R02', audio_path, offset_s=1.)
    assert video_asset is not None and audio_asset is not None
    panel = next(p for p in window.media.videos() if p.asset and p.asset.id == video_asset.id)
    player = window.extra_audio[audio_asset.id][0]
    frames = []
    panel.video.videoSink().videoFrameChanged.connect(lambda frame: frames.append(frame.startTime()) if frame.isValid() else None)
    wait_until(lambda: panel.player.duration() >= 9900 and player.duration() >= 9900)
    window.seek(4.)
    window.start()
    wait_until(lambda: bool(frames))
    window.pause()
    window.seek(7.)
    wait_until(lambda: abs(panel.player.position() - 5000) < 130 and abs(player.position() - 6000) < 130)
    wait_until(lambda: any(abs(stamp - 5000000) < 200000 for stamp in frames), timeout=5.)
    assert panel.player.error() == QMediaPlayer.NoError
    assert player.error() == QMediaPlayer.NoError
    assert panel.stack.currentWidget() is panel.video
    window.seek(.5)
    assert panel.stack.currentWidget() is panel.placeholder
    assert panel.empty.text() == 'OUTSIDE SOURCE RANGE'
    window.seek(13.)
    assert panel.stack.currentWidget() is panel.placeholder
    assert not window.qa_messages


def test_cross_actor_drag_uses_selected_source_frame_grid(window):
    """A new interval's first click must already use the destination actor grid."""
    canvas = window.timeline.canvas
    r01_track = next(t for t in window.project.tracks if t.role == 'R01' and t.workspace == 'Motion')
    target = window.project.add_track(name='QA offset posture', role='R02', workspace='Motion',
                                      category='Body Posture', channel='Full Body')
    asset = next(a for a in window.project.assets if a.kind == 'motion' and a.role == 'R02')
    motion = window.motion['R02']
    old_offset, old_step = asset.offset_s, motion.frame_time
    try:
        # Metadata-only test perturbation; raw BVH bytes remain untouched.
        asset.offset_s, motion.frame_time = .037, .02
        window._refresh_annotations()
        window._track_selected(r01_track.id)
        assert canvas.frame_step == window.motion['R01'].frame_time
        canvas.px_per_s = 80.
        window.timeline._refresh_scroll()
        window.timeline.scroll.setValue(0)
        row = next(row for row in canvas.rows if row.get('track') and row['track'].id == target.id)
        window.timeline.area.ensureVisible(0, int(row['y'] + row['height'] / 2), 0, 20)
        QApplication.processEvents()
        first = QPoint(round(canvas.time_x(2.125)), round(row['y'] + 15))
        last = QPoint(round(canvas.time_x(4.175)), first.y())
        raw_start, raw_end = canvas.x_time(first.x()), canvas.x_time(last.x())
        expected_start = .037 + round((raw_start - .037) / .02) * .02
        expected_end = .037 + round((raw_end - .037) / .02) * .02
        mouse_drag(canvas, first, last)
        assert window.session.is_new
        assert window.session.draft.track_id == target.id
        assert canvas.frame_step == pytest.approx(.02)
        assert canvas.snap_offset == pytest.approx(.037)
        assert window.session.draft.start_s == pytest.approx(expected_start)
        assert window.session.draft.end_s == pytest.approx(expected_end)
        assert canvas.snapped(2.123456, Qt.ShiftModifier) == pytest.approx(2.123456)
        window.cancel_edit()
        window._track_selected(r01_track.id)
        assert canvas.frame_step == window.motion['R01'].frame_time
        assert canvas.snap_offset == next(a.offset_s for a in window.project.assets if a.kind == 'motion' and a.role == 'R01')
    finally:
        window.cancel_edit()
        asset.offset_s, motion.frame_time = old_offset, old_step
        window._set_frame_grid(r01_track.id)


def test_timeline_focus_keeps_playback_shortcuts_out_of_text_fields(window):
    annotation = sample_arm(window)
    canvas = prepare_interval_view(window, annotation)
    window.select_annotation(annotation.id)
    window.editor.label.lineEdit().setFocus()
    QTest.mouseClick(canvas, Qt.LeftButton, pos=canvas.annotation_rect(annotation).center().toPoint())
    assert QApplication.focusWidget() is canvas
    QTest.keyClick(canvas, Qt.Key_Space)
    assert window._playing
    QTest.keyClick(canvas, Qt.Key_Space)
    assert not window._playing
    edit = window.editor.label.lineEdit()
    edit.setFocus()
    edit.setText('custom')
    edit.setCursorPosition(len(edit.text()))
    QTest.keyClick(edit, Qt.Key_Space)
    assert edit.text() == 'custom '
    assert not window._playing


def test_auto_batch_does_not_commit_after_source_mapping_changes(window):
    asset = window.project.assets[0]
    window._job_assets_signature = {a.id:(a.kind,a.role,a.path,a.offset_s,a.enabled) for a in window.project.assets}
    before = len(window.project.annotations)
    old_offset = asset.offset_s
    candidate = Annotation('stale-run', 10., 12., role=asset.role, source='auto:graph',
                           attributes={'source_asset_id':asset.id})
    asset.offset_s += 1.
    try:
        window._auto_done([candidate], {'scope':{'source_asset_ids':[asset.id]}})
        assert len(window.project.annotations) == before
        assert 'discarded' in window.auto.progress.text()
    finally:
        asset.offset_s = old_offset
