"""Name-only spatial annotation through the actual desktop editor."""
from copy import deepcopy
from dataclasses import asdict

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QDialog, QMessageBox

from annotationstudio.models import Project
from annotationstudio.object_registry import ObjectRegistryDialog
from annotationstudio.theme import STYLE
from annotationstudio.ui import MainWindow


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    messages = []
    for method in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QMessageBox, method,
            lambda parent, title, text, *args, **kwargs:
                messages.append((title, text)) or QMessageBox.Ok)
    monkeypatch.setattr(MainWindow, 'recovery_path', lambda self: tmp_path / 'recovery.json')
    widget = MainWindow(recover=False)
    widget.timer.stop(); widget.autosave_timer.stop(); widget.show()
    qapp.processEvents(); widget.qa_messages = messages
    yield widget
    widget.session.cancel(); widget._preview_invalid = False
    widget.history.mark_saved(widget.project); widget.close(); widget.deleteLater()
    qapp.processEvents()


def choose(combo, value):
    index = combo.findData(value)
    assert index >= 0, value
    combo.setCurrentIndex(index)


def track(project, *, role='R01', category='Object Spatial Relation'):
    return project.add_track(name=f'{role} {category}', role=role,
                             category=category, channel='Root')


def register_name(window, monkeypatch, name):
    """Exercise the real isolated dialog and controller without a modal wait."""
    class NameOnlyDialog(ObjectRegistryDialog):
        def exec(self):
            assert not self.project.assets
            self.name.setText(name)
            assert not self.object_id.text() and not self.object_class.text()
            self._finish()
            return self.result()

    monkeypatch.setattr('annotationstudio.ui.ObjectRegistryDialog', NameOnlyDialog)
    before = {obj.id for obj in window.project.objects}
    window.manage_objects()
    return next(obj for obj in window.project.objects if obj.id not in before)


def test_name_only_object_can_be_used_by_spatial_and_hoi_without_media(window, monkeypatch, tmp_path):
    project = window.project
    assert not project.assets and not project.objects
    counter = register_name(window, monkeypatch, '前方柜台')
    assert counter.id and counter.name == '前方柜台' and counter.object_class == ''
    assert not project.assets
    lane = track(project, role='R02')
    window.set_workflow('Spatial', force=True)
    window.add_range(1, 8, lane.id)
    editor = window.editor
    window.choose_palette_label('beside object')
    assert editor.object_id.isVisible() and editor.objects.isVisible()
    assert editor.hand.isHidden() and editor.target_role.isHidden()
    assert editor.spatial_reference.isHidden() and editor.secondary_object_id.isHidden()
    assert not editor.accept.isEnabled()
    choose(editor.object_id, counter.id)
    assert '前方柜台' in editor.object_id.currentText()
    assert editor.accept.isEnabled() and window.accept_edit()
    record = project.annotations[-1]
    assert record.role == 'R02' and record.attributes['object_id'] == counter.id
    assert 'spatial_relation' not in record.attributes and 'effector' not in record.attributes

    hoi = project.add_track(name='R02 hands on counter', role='R02',
                            category='Action / HOI', channel='Hands')
    window.set_workflow('HOI', force=True); window.add_range(2, 7, hoi.id)
    editor.choose_label('rest on object'); choose(editor.object_id, counter.id)
    editor.hand.setCurrentText('Both hands')
    assert window.accept_edit()
    assert project.annotations[-1].attributes['object_id'] == counter.id
    assert project.annotations[-1].attributes['effector'] == 'Both hands'
    project.save(tmp_path / 'names_only.json')
    loaded = Project.load(tmp_path / 'names_only.json')
    assert not loaded.assets and loaded.get_object(counter.id).name == '前方柜台'
    assert {a.attributes['object_id'] for a in loaded.annotations} == {counter.id}
    assert not window.qa_messages


def test_directional_relation_requires_named_target_and_selected_reference(window):
    project = window.project; counter = project.add_object('Counter')
    lane = track(project); window.add_range(1, 5, lane.id)
    editor = window.editor; editor.choose_label('in front of object')
    assert editor.spatial_reference.isVisible() and editor.spatial_reference.currentData() is None
    assert not editor.accept.isEnabled() and editor.candidate.isEnabled()
    choose(editor.object_id, counter.id)
    assert not editor.accept.isEnabled()
    assert 'reference' in editor.accept.toolTip().lower()
    choose(editor.spatial_reference, 'object_intrinsic')
    assert editor.accept.isEnabled() and window.accept_edit()
    record = project.annotations[-1]
    assert record.attributes['spatial_relation']['reference_frame'] == 'object_intrinsic'
    assert not project.assets
    window.select_annotation(record.id); editor.choose_label('near object')
    assert editor.spatial_reference.isHidden()
    # Unedited attributes remain on the isolated draft instead of being sent
    # back as an unnecessary patch by values().
    attrs = editor.values().get('attributes', window.session.draft.attributes)
    assert attrs['spatial_relation']['reference_frame'] == 'object_intrinsic'
    window.cancel_edit()
    assert record.label == 'in front of object'
    assert not window.qa_messages


def test_between_requires_two_distinct_named_objects_and_keeps_hidden_fields(window):
    project = window.project
    left = project.add_object('Left sofa'); right = project.add_object('Counter')
    lane = track(project); window.add_range(2, 8, lane.id)
    editor = window.editor; editor.choose_label('between objects')
    assert editor.secondary_object_id.isVisible() and editor.spatial_reference.isHidden()
    assert editor.object_label.text() == 'Object A'
    choose(editor.object_id, left.id); choose(editor.secondary_object_id, left.id)
    assert not editor.accept.isEnabled()
    with pytest.raises(ValueError, match='different'):
        window.session.accept()
    choose(editor.secondary_object_id, right.id)
    assert editor.accept.isEnabled()
    editor.choose_label('next to object')
    assert editor.secondary_object_id.isHidden()
    assert editor.values()['attributes']['spatial_relation']['secondary_object_id'] == right.id
    editor.choose_label('between objects')
    assert editor.secondary_object_id.text() == right.id
    assert window.accept_edit()
    record = project.annotations[-1]; snapshot = deepcopy(asdict(record))
    window.select_annotation(record.id); choose(editor.secondary_object_id, left.id)
    editor.end.setValue(9); window.cancel_edit()
    assert asdict(record) == snapshot
    window.undo(); assert not project.annotations
    window.redo(); assert project.annotations[-1].attributes['spatial_relation']['secondary_object_id'] == right.id
    assert not window.qa_messages


def test_incomplete_spatial_candidate_can_be_saved_then_finished(window):
    lane = track(window.project); window.add_range(1, 4, lane.id)
    editor = window.editor; editor.choose_label('between objects')
    assert not editor.accept.isEnabled() and editor.candidate.isEnabled()
    assert window.keep_candidate()
    record = window.project.annotations[-1]
    assert record.status == 'pending' and 'object_id' not in record.attributes
    left = window.project.add_object('Sofa'); right = window.project.add_object('Cabinet')
    window.select_annotation(record.id)
    choose(editor.object_id, left.id); choose(editor.secondary_object_id, right.id)
    assert window.accept_edit() and window.project.annotations[-1].status == 'approved'
    assert not window.qa_messages


def test_object_registry_rename_refresh_preserves_unfinished_editor_values(window, monkeypatch):
    project = window.project; counter = project.add_object('Counter')
    lane = track(project); window.add_range(5, 10, lane.id)
    editor = window.editor; editor.choose_label('in front of object')
    choose(editor.object_id, counter.id); choose(editor.spatial_reference, 'scene_reference')
    editor.notes.setText('Keep my draft note')
    editor.end.setValue(4)  # Deliberately unfinished, invalid interval in the controls.
    assert window._preview_invalid

    class RenameDialog(ObjectRegistryDialog):
        def exec(self):
            row = next(r for r in range(self.table.rowCount())
                       if self.table.item(r, 0).text() == counter.id)
            self.table.selectRow(row); self.name.setText('White counter')
            self._finish(); return self.result()

    monkeypatch.setattr('annotationstudio.ui.ObjectRegistryDialog', RenameDialog)
    window.manage_objects()
    assert project.get_object(counter.id).name == 'White counter'
    assert editor.end.value() == 4 and editor.notes.text() == 'Keep my draft note'
    assert editor.object_id.text() == counter.id and 'White counter' in editor.object_id.currentText()
    assert editor.spatial_reference.currentData() == 'scene_reference'
    assert not editor.accept.isEnabled()
    editor.end.setValue(11)
    assert window.accept_edit()
    assert project.annotations[-1].attributes['object_id'] == counter.id
    assert project.annotations[-1].notes == 'Keep my draft note'
    assert not window.qa_messages


def test_registry_counts_second_target_and_retired_existing_reference_stays_editable(window, qapp):
    project = window.project; a = project.add_object('Counter'); b = project.add_object('Sofa')
    lane = track(project); window.add_range(1, 7, lane.id)
    editor = window.editor; editor.choose_label('between objects')
    choose(editor.object_id, a.id); choose(editor.secondary_object_id, b.id)
    assert window.accept_edit(); record = project.annotations[-1]
    dialog = ObjectRegistryDialog(project)
    counts = {dialog.table.item(r, 0).text(): dialog.table.item(r, 3).text()
              for r in range(dialog.table.rowCount())}
    assert counts == {a.id: '1', b.id: '1'}
    dialog.reject(); dialog.deleteLater(); qapp.processEvents()
    project.retire_object(b.id)
    window.select_annotation(record.id)
    assert editor.secondary_object_id.text() == b.id
    assert 'retired' in editor.secondary_object_id.currentText()
    editor.end.setValue(8)
    assert editor.accept.isEnabled() and window.accept_edit()
    assert project.annotations[-1].attributes['spatial_relation']['secondary_object_id'] == b.id
    assert not window.qa_messages


def test_old_unresolved_and_future_fields_survive_binding_and_boundary_edit(window):
    project = window.project; lane = track(project)
    label = project.resolve_label('in front of object', lane.category)
    attrs = {'annotation_fields_version': 99, 'object_id': 'unregistered_counter',
             'spatial_relation': {'reference_frame': 'future_convention',
                                  'secondary_object_id': 'old_secondary', 'other': [1, 2]},
             'external': {'keep': True}}
    record = project.add_annotation(1, 7, track_id=lane.id, role=lane.role,
        category=lane.category, channel=lane.channel, label=label.name, label_id=label.id,
        status='approved', attributes=deepcopy(attrs))
    window.select_annotation(record.id); editor = window.editor
    assert editor.object_id.text() == 'unregistered_counter'
    assert editor.spatial_reference.currentData() == 'future_convention'
    assert editor.secondary_object_id.isHidden()
    assert editor.values().get('attributes', attrs) == attrs
    editor.start.setValue(1.5)
    assert editor.accept.isEnabled() and window.accept_edit()
    assert project.annotations[-1].attributes == attrs
    assert not window.qa_messages


def test_movement_region_and_uncertainty_use_name_only_targets(window):
    project = window.project; region = project.add_object('Waiting area')
    lane = track(project, category='Object-relative Movement')
    window.add_range(1, 4, lane.id); editor = window.editor
    editor.choose_label('enter object region'); choose(editor.object_id, region.id)
    assert editor.spatial_reference.isHidden() and editor.secondary_object_id.isHidden()
    assert window.accept_edit()
    assert project.annotations[-1].attributes['object_id'] == region.id
    window.add_range(5, 6, lane.id); editor.choose_label('object-relative movement uncertain')
    assert editor.object_id.text() == '' and editor.accept.isEnabled()
    assert window.accept_edit()
    assert not project.assets and not window.qa_messages


def test_spatial_controls_fit_minimum_window_and_do_not_show_affect_fields(window, qapp):
    old_style = qapp.styleSheet(); qapp.setStyleSheet(STYLE)
    try:
        project = window.project; a = project.add_object('Counter'); b = project.add_object('Sofa')
        lane = track(project); window.set_workflow('Spatial', force=True)
        window.resize(1220, 800); window.add_range(1, 6, lane.id)
        editor = window.editor
        for label in ('between objects', 'in front of object', 'beside object'):
            editor.choose_label(label); choose(editor.object_id, a.id)
            if label == 'between objects':choose(editor.secondary_object_id, b.id)
            if label == 'in front of object':choose(editor.spatial_reference, 'object_intrinsic')
            for _ in range(4):qapp.processEvents()
            assert editor.affect_mode.isHidden() and editor.intensity.isHidden()
            assert editor.evidence_fields.isHidden() and editor.more_details.isHidden()
            assert editor.hand.isHidden()
            for widget in (editor.object_id, editor.secondary_object_id,
                           editor.spatial_reference, editor.objects,
                           editor.start, editor.end, editor.accept, editor.cancel):
                if widget.isVisible():
                    bounds = QRect(widget.mapTo(editor, QPoint(0, 0)), widget.size())
                    assert editor.rect().contains(bounds), (label, widget.objectName(), bounds)
                    assert widget.height() >= widget.minimumSizeHint().height()
            assert window.timeline.height() >= 100
            assert editor.accept.isEnabled()
    finally:
        qapp.setStyleSheet(old_style)
