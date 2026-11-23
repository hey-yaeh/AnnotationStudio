"""GUI regressions for actual point editing, object references and new navigation."""
from copy import deepcopy
from dataclasses import asdict

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QMessageBox

from annotationstudio.ui import MainWindow
from annotationstudio.models import Project
from annotationstudio.object_registry import ObjectRegistryDialog


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    messages = []
    for method in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QMessageBox, method,
            lambda parent, title, text, *a, **k: messages.append((title, text)) or QMessageBox.Ok)
    monkeypatch.setattr(MainWindow, 'recovery_path', lambda self: tmp_path / 'recovery.json')
    widget = MainWindow(recover=False)
    widget.timer.stop(); widget.autosave_timer.stop(); widget.show()
    qapp.processEvents()
    widget.qa_messages = messages
    yield widget
    widget.session.cancel(); widget._preview_invalid = False
    widget.history.mark_saved(widget.project); widget.close(); widget.deleteLater()
    qapp.processEvents()


def test_point_click_drag_accept_cancel_and_undo(window, qapp):
    track = window.project.add_track(name='Turn markers', category='Turn Transition',
                                    channel='Speech', role='Both')
    window.set_workflow('Speech', force=True); window._refresh_annotations()
    window._track_selected(track.id)
    canvas = window.timeline.canvas; canvas.px_per_s = 70
    canvas._rebuild(); window.timeline._refresh_scroll()
    row = next(r for r in canvas.rows if r.get('track') and r['track'].id == track.id)
    pos = QPoint(round(canvas.time_x(2)), round(row['y'] + row['height']/2))
    QTest.mouseClick(canvas, Qt.LeftButton, pos=pos)
    assert window.session.draft.is_point
    assert window.session.draft.start_s == window.session.draft.end_s
    assert window.editor.end.isHidden() and not window.editor.split.isEnabled()
    window.editor.label.setEditText('speaker change candidate')
    assert window.accept_edit()
    original = asdict(window.project.annotations[0])
    marker = window.project.annotations[0]
    rect = canvas.annotation_rect(marker)
    start = rect.center().toPoint(); finish = QPoint(start.x()+70, start.y())
    QTest.mousePress(canvas, Qt.LeftButton, pos=start)
    QTest.mouseMove(canvas, finish, delay=20)
    QTest.mouseRelease(canvas, Qt.LeftButton, pos=finish)
    assert window.session.draft.start_s == pytest.approx(3)
    assert window.session.draft.end_s == pytest.approx(3)
    assert asdict(window.project.annotations[0]) == original
    window.cancel_edit()
    assert asdict(window.project.annotations[0]) == original
    window.select_annotation(marker.id); window.editor.start.setValue(4.125)
    assert window.editor.end.value() == 4.125
    assert window.accept_edit()
    assert window.project.annotations[0].start_s == window.project.annotations[0].end_s == 4.125
    window.undo(); assert window.project.annotations[0].start_s == 2
    window.redo(); assert window.project.annotations[0].start_s == 4.125
    assert not window.qa_messages


def test_point_split_merge_and_preview_do_not_invent_duration(window):
    track = window.project.add_track(name='Points', category='Turn Transition', channel='Speech')
    window.add_point(5, track.id); window.editor.label.setEditText('turn handover')
    assert window.accept_edit()
    a = window.project.annotations[0]; before = asdict(a)
    window.select_annotation(a.id)
    window.split_selected(); window.merge_selected()
    assert asdict(a) == before and len(window.project.annotations) == 1
    assert window._loop_bounds(a) == (4.25, 5.75)
    assert a.start_s == a.end_s == 5
    window.duplicate_selected()
    assert window.session.draft.is_point and window.session.draft.start_s == 5
    window.cancel_edit()


def test_hoi_object_choice_keeps_id_through_rename_and_cancel(window):
    p = window.project
    obj = p.add_object('Round table', 'table', id='table_01')
    track = p.add_track(name='Right hand support', category='Action / HOI', channel='Right Hand')
    window.add_range(1, 9, track.id)
    window.editor.label.setEditText('rest on object')
    window.editor.object_id.setCurrentIndex(window.editor.object_id.findData(obj.id))
    window.editor.hand.setCurrentText('Right hand')
    assert window.session.draft.attributes['object_id'] == obj.id
    assert not p.annotations
    assert window.accept_edit()
    a = p.annotations[0]
    assert a.attributes['object_id'] == obj.id and a.attributes['effector'] == 'Right hand'
    p.update_object(obj.id, name='Table beside sofa')
    window.select_annotation(a.id)
    assert 'Table beside sofa' in window.editor.object_id.currentText()
    assert window.editor.object_id.text() == obj.id
    window.editor.object_id.setCurrentIndex(0); window.cancel_edit()
    assert a.attributes['object_id'] == obj.id
    assert not window.qa_messages


def test_object_dialog_is_isolated_and_legacy_reference_visible(qapp):
    p = Project(); p.add_object('Sofa', 'sofa', id='sofa_01')
    original = deepcopy(p.objects)
    dialog = ObjectRegistryDialog(p)
    dialog.name.setText('Desk'); dialog.object_class.setText('table')
    assert dialog._store()
    assert len(dialog.result_objects()) == 2 and p.objects == original
    dialog.reject(); dialog.deleteLater()
    assert p.objects == original
    from annotationstudio.object_registry import ObjectPicker
    picker = ObjectPicker(); picker.bind(p, 'old_unknown_id')
    assert picker.text() == 'old_unknown_id' and 'Unregistered' in picker.currentText()
    picker.deleteLater()


def test_spatial_view_reorganizes_without_mutating_imported_track(window):
    track = window.project.add_track(name='Old proximity', category='Proxemic Movement', workspace='Social')
    original = asdict(track)
    window._refresh_annotations(); window.set_workflow('Spatial', force=True)
    assert track in window.timeline.canvas.visible_tracks()
    assert asdict(track) == original
    window.set_workflow('Social', force=True)
    assert track not in window.timeline.canvas.visible_tracks()


def test_automatic_first_and_speech_time_grid(window):
    window.set_workflow('Motion', force=True)
    assert window.right_tabs.currentWidget() is window.auto
    window.set_workflow('Speech', force=True)
    assert window.right_tabs.currentWidget() is window.auto
    track = window.project.add_track(name='Speech points', category='Turn Transition', channel='Speech')
    window._track_selected(track.id)
    assert window.timeline.canvas.frame_step == .001
    assert window.right_tabs.currentWidget() is window.label_palette


def test_speech_turn_preview_adds_only_new_candidates_to_latest_queue(window, monkeypatch):
    from annotationstudio.speech_tools import SpeechStructureDialog

    speaking = [window.project.add_annotation(start, start+1., role=role, channel='Speech',
                                              category='Speaking', label='speaking', status='approved')
                for start, role in ((1., 'R01'), (3., 'R02'))]
    original = [asdict(annotation) for annotation in speaking]

    def apply_preview(dialog):
        dialog.confirm_attribution.setChecked(True)
        dialog.generate_preview()
        assert dialog.apply_button.isEnabled()
        return QDialog.Accepted

    monkeypatch.setattr(SpeechStructureDialog, 'exec', apply_preview)
    window.set_workflow('Speech')
    QTest.mouseClick(window.auto_detect_button, Qt.LeftButton)
    assert window.auto.tabs.tabText(window.auto.tabs.currentIndex()) == 'Audio'
    QTest.mouseClick(window.auto.turn_button, Qt.LeftButton)
    assert window.right_tabs.currentWidget() is window.review
    assert window.review.latest_only.isChecked()
    fresh = [a for a in window.project.annotations if a not in speaking]
    assert {a.category for a in fresh} >= {'Speech Turn', 'Turn Transition'}
    assert all(a.status == 'pending' for a in fresh)
    assert window.review.table.rowCount() == len(fresh)
    assert [asdict(annotation) for annotation in speaking] == original
