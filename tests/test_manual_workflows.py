"""End-to-end manual list selection and current-scope regressions with real Qt."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from annotationstudio.ui import MainWindow
from annotationstudio.models import Project
from annotationstudio.ontology import WORKSPACES, WORKSPACE_CATEGORIES, LABEL_PRESETS, LEGACY_MOTION_RELATION
from annotationstudio.track_setup import TrackDialog, TrackLabelDialog


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    messages = []
    def message(parent, title, text, *args, **kwargs):
        messages.append((title, text)); return QMessageBox.Ok
    for method in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QMessageBox, method, message)
    monkeypatch.setattr(MainWindow, 'recovery_path', lambda self: tmp_path / 'recovery.json')
    widget = MainWindow(recover=False)
    widget.timer.stop(); widget.autosave_timer.stop(); widget.show()
    qapp.processEvents()
    widget.qa_messages = messages
    yield widget
    widget.session.cancel(); widget._preview_invalid = False
    widget.history.mark_saved(widget.project); widget.close(); widget.deleteLater()
    qapp.processEvents()


def choose_leaf(window, name):
    tree = window.label_palette.tree
    item = next(tree.topLevelItem(i).child(j)
                for i in range(tree.topLevelItemCount())
                for j in range(tree.topLevelItem(i).childCount())
                if tree.topLevelItem(i).child(j).data(0, Qt.UserRole) == name)
    tree.scrollToItem(item); QApplication.processEvents()
    QTest.mouseClick(tree.viewport(), Qt.LeftButton, pos=tree.visualItemRect(item).center())


def test_drag_list_accept_does_not_require_automatic_analysis(window):
    track = window.project.add_track(name='Posture', role='R01', category='Body Posture', channel='Full Body')
    window._refresh_annotations(); window._track_selected(track.id)
    assert window.right_tabs.currentWidget() is window.label_palette
    assert 'legs crossed' in window.label_palette.visible_label_names()
    choose_leaf(window, 'legs crossed')
    assert window.session.draft is None and not window.project.annotations
    canvas = window.timeline.canvas
    canvas.px_per_s = 70.; window.timeline._refresh_scroll(); window.timeline.scroll.setValue(0)
    row = next(row for row in canvas.rows if row.get('track') and row['track'].id == track.id)
    y = round(row['y'] + row['height'] / 2)
    window.timeline.area.ensureVisible(0, y, 0, 15); QApplication.processEvents()
    first = QPoint(round(canvas.time_x(2)), y); last = QPoint(round(canvas.time_x(4)), y)
    QTest.mousePress(canvas, Qt.LeftButton, pos=first)
    QTest.mouseMove(canvas, last, delay=20)
    QTest.mouseRelease(canvas, Qt.LeftButton, pos=last)
    assert window.session.draft is not None
    assert window.session.draft.track_id == track.id
    choose_leaf(window, 'legs crossed')
    assert window.session.draft.label == 'legs crossed'
    assert not window.project.annotations
    QTest.mouseClick(window.editor.accept, Qt.LeftButton)
    accepted = window.project.annotations[0]
    assert accepted.role == 'R01' and accepted.status == 'approved'
    assert accepted.label == 'legs crossed' and accepted.source == 'manual'
    assert accepted.end_s > accepted.start_s
    window.undo(); assert not window.project.annotations
    window.redo(); assert window.project.annotations[0].label == 'legs crossed'
    assert not window.qa_messages


def test_each_track_has_its_own_whitelist_and_search_survives_edit(window):
    p = window.project
    posture = p.add_track(name='Posture', role='R01', category='Body Posture', channel='Full Body')
    hands = p.add_track(name='Hands', role='R02', category='Hand Behavior', channel='Hands')
    selected = p.resolve_label('legs crossed', 'Body Posture')
    p.set_track_label_ids(posture, [selected.id])
    window._refresh_annotations(); window._track_selected(posture.id)
    assert window.label_palette.visible_label_names() == ['legs crossed']
    window.add_range(1, 3, posture.id)
    window.label_palette.search.setText('cross')
    choose_leaf(window, 'legs crossed')
    assert window.label_palette.search.text() == 'cross'
    window.cancel_edit(); window._track_selected(hands.id)
    names = window.label_palette.visible_label_names()
    assert 'fingers interlaced' in names and 'legs crossed' not in names
    assert window.label_palette.search.text() == ''
    window.add_custom_label('project hand pattern')
    assert 'project hand pattern' in window.label_palette.visible_label_names()
    assert not p.annotations


def test_new_dialogs_hide_gaze_face_and_enforce_pair_configuration(qapp):
    project = Project()
    dialog = TrackDialog(project=project)
    assert {'Gaze', 'Face'}.isdisjoint(dialog.workspace.itemText(i) for i in range(dialog.workspace.count()))
    dialog.workspace.setCurrentText('Social')
    assert set(dialog.category.itemText(i) for i in range(dialog.category.count())) == {
        'Interaction Event', 'Physical Interaction', 'Cognitive State Expression'}
    dialog.workspace.setCurrentText('Spatial')
    assert set(dialog.category.itemText(i) for i in range(dialog.category.count())) == {
        'Proxemic Movement', 'Spatial Configuration', 'Object Spatial Relation', 'Object-relative Movement'}
    dialog.category.setCurrentText('Spatial Configuration')
    assert dialog.role.currentText() == 'Both' and not dialog.role.isEnabled()
    assert dialog.values()['extra']['participants'] == ['R01', 'R02']
    dialog.category.setCurrentText('Proxemic Movement')
    assert dialog.role.currentText() == 'R01'
    assert 'target_role' not in dialog.values()['extra']
    dialog.target_role.setCurrentIndex(dialog.target_role.findData('R02'))
    assert dialog.values()['extra']['target_role'] == 'R02'
    assert dialog.target_role.findData('R01') == -1
    dialog.close(); dialog.deleteLater()


def test_narrowing_list_never_rewrites_existing_annotation(window):
    project = window.project
    track = project.add_track(name='Posture', category='Body Posture', channel='Full Body')
    a = project.add_annotation(2, 4, track_id=track.id, category=track.category,
                               label='legs crossed', status='approved')
    original = deepcopy(asdict(a))
    dialog = TrackLabelDialog(project, track)
    dialog.options.restrict.setChecked(True)
    for i in range(dialog.options.list.count()):
        item = dialog.options.list.item(i)
        item.setCheckState(Qt.Checked if item.text() == 'standing' else Qt.Unchecked)
    project.set_track_label_ids(track, dialog.allowed_ids())
    assert asdict(a) == original
    window._refresh_annotations(); window.select_annotation(a.id)
    assert 'legs crossed' in window.label_palette.visible_label_names()
    window.editor.end.setValue(5)
    assert window.accept_edit()
    assert project.annotations[0].label == 'legs crossed' and project.annotations[0].end_s == 5
    dialog.close(); dialog.deleteLater()


def test_legacy_gaze_and_face_remain_visible_without_new_workspaces(window):
    assert 'Gaze' not in WORKSPACES and 'Face' not in WORKSPACES
    assert 'Gaze / Attention' not in LABEL_PRESETS and 'Facial Expression' not in LABEL_PRESETS
    for category, workspace, label in [('Gaze / Attention', 'Gaze', 'look at partner'),
                                        ('Facial Expression', 'Face', 'smile')]:
        track = window.project.add_track(name='Historical', workspace=workspace, category=category)
        a = window.project.add_annotation(1, 2, track_id=track.id, category=category,
                                          label=label, status='approved')
        original = deepcopy(asdict(a))
        window.set_workflow('Motion', force=True); window._refresh_annotations()
        window.select_annotation(a.id)
        assert window._workflow == 'Overview'
        assert track in window.timeline.canvas.visible_tracks()
        assert label in window.label_palette.visible_label_names()
        window.cancel_edit()
        assert asdict(a) == original


def test_manual_example_is_empty_and_all_lists_have_annotation_guidance(private_samples):
    private_samples('S004_I02_manual.studio.json')
    root = Path(__file__).resolve().parents[1]
    project = Project.load(root / 'examples' / 'S004_I02_manual.studio.json')
    assert not project.annotations
    assert {asset.role for asset in project.assets} == {'R01', 'R02'}
    assert len(project.tracks) == 71
    assert all(track.workspace in WORKSPACES and track.category in {*LABEL_PRESETS, LEGACY_MOTION_RELATION}
               for track in project.tracks)
    assert sum(track.category == LEGACY_MOTION_RELATION for track in project.tracks) == 1


def test_all_annotation_lists_have_guidance():
    project = Project()
    assert len(WORKSPACE_CATEGORIES['Overview']) == 28
    for category, names in LABEL_PRESETS.items():
        for name in names:
            if name == 'Unlabeled': continue
            label = project.resolve_label(name, category)
            assert label.definition and label.boundary_rule and label.extra.get('zh')
            assert label.extra.get('auto_mode') in {'manual', 'builtin_candidate', 'optional_model', 'interface_only'}
