"""Named-object relations work without geometry and preserve prior records."""
from copy import deepcopy
from dataclasses import asdict
import csv

import pytest

from annotationstudio.annotation_fields import (
    annotation_object_ids, spatial_accept_error, spatial_label_name,
    validate_annotation_fields,
)
from annotationstudio.context_relations import intersect_tracks, export_context_csv
from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.models import Project, export_csv, import_annotation_csv


def setup(category='Object Spatial Relation', role='R01'):
    project = Project()
    track = project.add_track(name='Named object relation', category=category,
                              channel='Root', role=role)
    history = ProjectHistory()
    session = EditSession(project, history)
    return project, track, history, session


def draft(session, track, name, attrs=None):
    session.create(1, 4, track.id)
    session.update(label=name, attributes=deepcopy(attrs or {}))


def fields(primary=None, secondary=None, frame=None):
    return {'annotation_fields_version': 1, 'object_id': primary,
            'spatial_relation': {'secondary_object_id': secondary, 'reference_frame': frame}}


def test_name_only_object_and_spatial_annotation_roundtrip_without_assets(tmp_path):
    project, track, history, session = setup(role='R02')
    target = project.add_object('前方柜台')  # No class, media, props or geometry.
    assert target.object_class == '' and target.id and not project.assets
    draft(session, track, 'in front of object', fields(target.id, frame='object_intrinsic'))
    approved = session.accept('Annotator')
    assert approved.role == 'R02' and approved.attributes['object_id'] == target.id
    assert not project.assets and history.can_undo
    project.update_object(target.id, name='Main counter')
    project.save(tmp_path / 'project.studio.json')
    loaded = Project.load(tmp_path / 'project.studio.json')
    assert loaded.get_object(target.id).name == 'Main counter'
    assert not loaded.assets and asdict(loaded.annotations[0]) == asdict(approved)
    export_csv(loaded.annotations, tmp_path / 'annotations.csv')
    assert asdict(import_annotation_csv(tmp_path / 'annotations.csv')[0]) == asdict(approved)
    assert history.undo(project) and not project.annotations
    assert history.redo(project) and project.annotations[0].id == approved.id


def test_missing_named_target_fails_before_label_or_history_mutation():
    project, track, history, session = setup()
    draft(session, track, 'custom relative relation')
    before = deepcopy(project.to_dict())
    with pytest.raises(ValueError, match='Choose a named object'):
        session.accept()
    assert project.to_dict() == before and not history.can_undo
    assert project.resolve_label('custom relative relation', track.category) is None
    session.cancel()
    assert project.to_dict() == before


@pytest.mark.parametrize('name', ['in front of object', 'behind object', 'left of object', 'right of object'])
def test_directional_relations_need_an_explicit_reference(name):
    project, track, history, session = setup()
    obj = project.add_object('Counter')
    draft(session, track, name, fields(obj.id))
    with pytest.raises(ValueError, match='reference'):
        session.accept()
    assert not project.annotations and not history.can_undo
    session.update(attributes=fields(obj.id, frame='scene_reference'))
    accepted = session.accept()
    assert accepted.attributes['spatial_relation']['reference_frame'] == 'scene_reference'


def test_candidate_does_not_bypass_missing_target_on_later_accept():
    project, track, history, session = setup()
    draft(session, track, 'next to object')
    candidate = session.save_candidate()
    assert candidate.status == 'pending' and not candidate.attributes.get('object_id')
    session.begin(candidate.id)
    session.update(end_s=5)
    with pytest.raises(ValueError, match='named object'):
        session.accept()
    assert candidate.end_s == 4 and candidate.status == 'pending'


@pytest.mark.parametrize('category,name', [
    ('Object Spatial Relation', 'spatial relation uncertain'),
    ('Object-relative Movement', 'object-relative movement uncertain'),
])
def test_uncertainty_can_be_recorded_without_a_known_target(category, name):
    project, track, _, session = setup(category)
    draft(session, track, name)
    record = session.accept()
    assert record.label == name and not annotation_object_ids(record)


def test_between_requires_two_distinct_registered_targets_and_preserves_both(tmp_path):
    project, track, history, session = setup()
    first, second = project.add_object('Sofa'), project.add_object('Counter')
    draft(session, track, 'between objects', fields(first.id))
    for second_id, message in [(None, 'second object'), (first.id, 'different'), ('missing', 'active second')]:
        session.update(attributes=fields(first.id, second_id))
        with pytest.raises(ValueError, match=message):
            session.accept()
        assert not project.annotations and not history.can_undo
    project.retire_object(second.id)
    session.update(attributes=fields(first.id, second.id))
    with pytest.raises(ValueError, match='active second'):
        session.accept()
    project.update_object(second.id, extra={'retired': False})
    record = session.accept()
    assert annotation_object_ids(record) == (first.id, second.id)
    export_csv([record], tmp_path / 'between.csv')
    imported = import_annotation_csv(tmp_path / 'between.csv')[0]
    assert asdict(imported) == asdict(record)


def test_alias_and_renamed_core_identity_keep_direction_and_between_constraints():
    project, track, history, session = setup()
    obj = project.add_object('Counter')
    front = project.resolve_label('in front of object', track.category)
    project.rename_label(front.id, 'Customer side')
    draft(session, track, 'in front of object', fields(obj.id))
    assert spatial_label_name(project, session.draft) == 'in front of object'
    with pytest.raises(ValueError, match='reference'):
        session.accept()
    session.update(attributes=fields(obj.id, frame='object_intrinsic'))
    record = session.accept()
    assert record.label == 'Customer side' and record.label_id == front.id
    between = project.resolve_label('between objects', track.category)
    project.rename_label(between.id, 'In the gap')
    draft(session, track, 'In the gap', fields(obj.id))
    with pytest.raises(ValueError, match='second object'):
        session.accept()


def test_existing_retired_or_unresolved_targets_survive_boundary_edits_and_cancel(tmp_path):
    project, track, history, session = setup()
    target = project.add_object('Counter')
    draft(session, track, 'next to object', fields(target.id))
    record = session.accept()
    project.retire_object(target.id)
    session.begin(record.id)
    session.update(start_s=1.5, notes='Boundary correction')
    record = session.accept()
    assert record.attributes['object_id'] == target.id and record.start_s == 1.5
    # Authored imported reference with a future payload remains preserved.
    record.attributes = {'annotation_fields_version': 9, 'object_id': 'legacy_unregistered',
                         'spatial_relation': {'secondary_object_id': 'legacy_second',
                                              'reference_frame': {'future': True},
                                              'extra': ['retain']}, 'original_format': {'keep': 1}}
    record.source = 'imported:study'
    original = deepcopy(record.attributes)
    project.save(tmp_path / 'legacy.json')
    loaded = Project.load(tmp_path / 'legacy.json')
    new_session = EditSession(loaded, ProjectHistory())
    new_session.begin(record.id)
    new_session.update(end_s=8, notes='Boundary-only edit')
    revised = new_session.accept()
    assert revised.attributes == original and revised.source == 'imported:study'
    new_session.begin(revised.id)
    new_session.update(attributes=fields('different_unregistered'))
    with pytest.raises(ValueError, match='registered'):
        new_session.accept()
    new_session.cancel()
    assert loaded.annotations[0].attributes == original


def test_current_relations_reject_retired_primary_targets():
    project, track, history, session = setup('Object-relative Movement')
    target = project.add_object('Counter')
    project.retire_object(target.id)
    draft(session, track, 'move toward object', fields(target.id))
    with pytest.raises(ValueError, match='active object'):
        session.accept()
    assert not history.can_undo and not project.annotations


@pytest.mark.parametrize('patch', [
    {'spatial_relation': []},
    {'spatial_relation': {'secondary_object_id': 3}},
    {'spatial_relation': {'reference_frame': False}},
    {'spatial_relation': {}, 'object_id': ['a']},
])
def test_invalid_v1_fields_are_rejected_without_mutating_the_draft(patch):
    _, track, history, session = setup()
    draft(session, track, 'beside object')
    before = deepcopy(session.draft)
    with pytest.raises(ValueError):
        session.update(attributes={'annotation_fields_version': 1, **patch})
    assert session.draft == before and not history.can_undo


def test_reference_usage_counts_retained_ids_but_context_matches_only_active_targets(tmp_path, qapp):
    from annotationstudio.context_dialog import ContextQueryDialog

    project, track, _, session = setup()
    first, second = project.add_object('Sofa'), project.add_object('Counter')
    draft(session, track, 'between objects', fields(first.id, second.id))
    relation = session.accept()
    speech = project.add_track(name='Speech', role='R01', category='Speaking', channel='Speech')
    project.add_annotation(0, 6, label='Speaking', track_id=speech.id, role='R01', category='Speaking', channel='Speech')
    before = deepcopy(project.to_dict())
    rows, _ = intersect_tracks(project, speech.id, track.id, object_b=second.id)
    assert len(rows) == 1 and rows[0]['object_b'] == first.id
    assert rows[0]['secondary_object_b'] == second.id
    export_context_csv(tmp_path / 'context.csv', rows)
    with (tmp_path / 'context.csv').open(encoding='utf-8-sig', newline='') as f:
        exported = list(csv.DictReader(f))
    assert exported[0]['secondary_object_b'] == second.id
    dialog = ContextQueryDialog(project)
    dialog.track_b.setCurrentIndex(dialog.track_b.findData(track.id))
    assert dialog.object_b.findData(second.id) >= 0
    dialog.object_b.setCurrentIndex(dialog.object_b.findData(second.id))
    dialog.calculate()
    assert second.id in dialog.table.item(0, 5).text()
    dialog.close()
    assert project.to_dict() == before
    session.begin(relation.id)
    session.update(label='beside object')
    record = session.accept()
    assert annotation_object_ids(record) == (first.id, second.id)  # Hidden value preserved.
    rows, _ = intersect_tracks(project, speech.id, track.id, object_b=second.id)
    assert rows == []
    rows, _ = intersect_tracks(project, speech.id, track.id, object_b=first.id)
    assert len(rows) == 1 and rows[0]['secondary_object_b'] == ''


def test_supplement_adds_object_spatial_tracks_only_explicitly(tmp_path):
    project = Project()
    project.tracks.clear()
    authored = project.add_track(name='Authored restricted lane', category='Object Spatial Relation',
                                  role='R02', channel='Root', visible=False,
                                  extra={'allowed_label_ids': []})
    snapshot = asdict(authored)
    project.save(tmp_path / 'old.json')
    loaded = Project.load(tmp_path / 'old.json')
    assert len(loaded.tracks) == 1 and asdict(loaded.tracks[0]) == snapshot
    additions = loaded.ensure_annotation_tracks()
    assert asdict(loaded.get_track(authored.id)) == snapshot
    for category in ('Object Spatial Relation', 'Object-relative Movement'):
        assert {t.role for t in loaded.tracks if t.category == category} == {'R01', 'R02'}
    assert len(loaded.tracks) == 71 and additions
    assert loaded.ensure_annotation_tracks() == []
