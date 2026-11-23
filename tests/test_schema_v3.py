"""Point-time and object-identity contracts across editing and interchange."""
from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.models import (
    Annotation, Project, SCHEMA_VERSION, export_csv, export_eaf,
    import_annotation_csv, track_temporal_kind,
)


def point_track(project):
    return project.add_track(name='Markers', role='R01', category='QC / Notes',
                             channel='Notes', extra={'temporal_kind': 'point'})


def test_point_has_one_time_and_interval_still_requires_duration():
    annotation = Annotation('marker', 0, 0, 'R02', temporal_kind='point')
    assert annotation.is_point and annotation.valid() and annotation.role == 'R02'
    assert not Annotation('interval', 0, 0).valid()
    assert not Annotation('unknown', 0, 1, temporal_kind='instant-ish').valid()
    assert not Annotation('point-with-duration', 1, 2, temporal_kind='point').valid()


@pytest.mark.parametrize('time_s', [-0.1, float('nan'), float('inf')])
def test_invalid_point_does_not_replace_draft_or_write_project(time_s):
    project = Project()
    track = point_track(project)
    session = EditSession(project, ProjectHistory())
    session.create_point(2, track.id)
    before = session.draft.snapshot()
    with pytest.raises(ValueError):
        session.create_point(time_s, track.id)
    assert session.draft.snapshot() == before
    assert not project.annotations


def test_point_move_is_atomic_and_cancel_is_isolated():
    project = Project()
    track = point_track(project)
    annotation = project.add_annotation(2, 2, temporal_kind='point', track_id=track.id,
        category=track.category, channel='Notes', label='manual marker',
        source='auto:test', original={'start_s': 2, 'end_s': 2, 'label': 'raw marker'})
    initial = deepcopy(annotation)
    session = EditSession(project, ProjectHistory())
    session.begin(annotation.id)
    session.update(start_s=3)
    assert (session.draft.start_s, session.draft.end_s) == (3, 3)
    session.update(end_s=4)
    assert (session.draft.start_s, session.draft.end_s) == (4, 4)
    before = session.draft.snapshot()
    with pytest.raises(ValueError):
        session.update(start_s=5, end_s=6, notes='must not leak')
    assert session.draft.snapshot() == before
    with pytest.raises(ValueError, match='cannot be edited'):
        session.update(temporal_kind='interval', end_s=5)
    session.cancel()
    assert asdict(project.annotations[0]) == asdict(initial)


def test_point_commit_and_undo_keep_temporal_type_and_provenance():
    project = Project()
    track = point_track(project)
    annotation = project.add_annotation(2, 2, temporal_kind='point', track_id=track.id,
        category=track.category, label='marker', channel='Notes', source='auto:test')
    original = deepcopy(annotation.original)
    history = ProjectHistory()
    session = EditSession(project, history)
    session.begin(annotation.id)
    session.update(start_s=2.125, label='reviewed marker')
    result = session.accept('reviewer-1')
    assert result.is_point and result.start_s == result.end_s == 2.125
    assert result.original == original and result.source == 'auto:test'
    assert result.history[-1]['after']['temporal_kind'] == 'point'
    assert history.undo(project)
    assert project.annotations[0].is_point and project.annotations[0].start_s == 2
    assert history.redo(project)
    assert project.annotations[0].start_s == project.annotations[0].end_s == 2.125


def test_point_track_creation_requires_one_timestamp_without_invented_duration():
    project = Project()
    track = point_track(project)
    assert track_temporal_kind(track) == 'point'
    session = EditSession(project, ProjectHistory())
    assert session.create(1, 1, track.id).is_point
    previous = session.draft.snapshot()
    with pytest.raises(ValueError):
        session.create(1, 2, track.id)
    assert session.draft.snapshot() == previous
    assert not project.annotations
    with pytest.raises(ValueError):
        project.add_track(name='Bad temporal type', extra={'temporal_kind': 'invalid'})


def test_schema_v3_objects_and_point_metadata_roundtrip(tmp_path):
    project = Project()
    sofa = project.add_object('Main sofa', 'sofa', id='sofa_01', notes='verified by video',
                              extra={'source_asset_id': 'unavailable-old-prop', 'retired': False})
    table = project.add_object('Table', 'table', id='table_01')
    state = project.add_annotation(0, 10, category='Action / HOI', label='sit on object',
                                   attributes={'object_id': sofa.id, 'effector': 'Full Body'})
    marker = project.add_annotation(4, 4, temporal_kind='point', category='QC / Notes',
                                    attributes={'related_annotation_ids': [state.id]})
    project.retire_object(table.id)
    saved = tmp_path / 'project.json'
    project.save(saved)
    assert json.loads(saved.read_text(encoding='utf-8'))['version'] == SCHEMA_VERSION == 3
    loaded = Project.load(saved)
    assert loaded.to_dict() == project.to_dict()
    assert loaded.get_object(table.id).retired
    assert next(a for a in loaded.annotations if a.id == marker.id).is_point
    assert loaded.get_object(sofa.id).extra['source_asset_id'] == 'unavailable-old-prop'


def test_v2_loading_preserves_original_records_and_unresolved_objects(tmp_path):
    project = Project()
    record = project.add_annotation(1, 3, category='Action / HOI', label='touch object',
        status='approved', attributes={'object_id': 'legacy_table_id'},
        original={'legacy_source': 'keep this'}, history=[{'custom': 'original event'}])
    payload = project.to_dict()
    payload['version'] = 2
    payload.pop('objects')
    for track in payload['tracks']:
        track['extra'].pop('temporal_kind', None)
    for annotation in payload['annotations']:
        annotation.pop('temporal_kind')
    annotation_before = deepcopy(payload['annotations'][0])
    track_before = deepcopy(payload['tracks'])
    path = tmp_path / 'old-v2.json'
    path.write_text(json.dumps(payload))
    loaded = Project.load(path)
    annotation_after = asdict(loaded.annotations[0])
    assert annotation_after.pop('temporal_kind') == 'interval'
    assert annotation_after == annotation_before
    assert [asdict(t) for t in loaded.tracks] == track_before
    assert loaded.annotations[0].id == record.id
    assert loaded.get_object('legacy_table_id') is None
    assert loaded.objects == []
    # Unknown old references are preserved, not silently invented or rejected.
    loaded.save(tmp_path / 'upgraded.json')


def test_zero_length_legacy_interval_does_not_silently_become_point(tmp_path):
    project = Project()
    project.add_annotation(1, 2)
    payload = project.to_dict()
    payload['version'] = 2
    payload['annotations'][0].pop('temporal_kind')
    payload['annotations'][0]['end_s'] = 1
    path = tmp_path / 'bad-v2.json'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='Invalid times'):
        Project.load(path)


def test_csv_preserves_point_times_and_explicit_empty_manual_provenance(tmp_path):
    project = Project()
    project.add_annotation(0, 0, temporal_kind='point', label='start marker',
                            attributes={'object_id': 'legacy-unresolved'})
    project.add_annotation(1, 2, label='movement')
    expected = [asdict(a) for a in project.annotations]
    path = tmp_path / 'records.csv'
    export_csv(project.annotations, path)
    loaded = import_annotation_csv(path)
    assert [asdict(a) for a in loaded] == expected
    assert loaded[0].is_point and loaded[0].original == {}
    assert not loaded[1].is_point


def test_bad_point_csv_reports_row_instead_of_padding(tmp_path):
    path = tmp_path / 'bad-point.csv'
    path.write_text('start_s,end_s,temporal_kind\n1,2,point\n')
    with pytest.raises(ValueError, match='CSV row 2'):
        import_annotation_csv(path)


def test_eaf_rejects_points_before_touching_destination(tmp_path):
    annotations = [Annotation('interval', 0, 2), Annotation('point', 1, 1, temporal_kind='point')]
    path = tmp_path / 'existing.eaf'
    path.write_text('original content')
    with pytest.raises(ValueError, match='Point events have no duration'):
        export_eaf(annotations, path)
    assert path.read_text(encoding='utf-8') == 'original content'
    missing = tmp_path / 'not_created.eaf'
    with pytest.raises(ValueError):
        export_eaf(annotations, missing)
    assert not missing.exists()


def test_object_rename_retirement_and_undo_preserve_annotation_references():
    project = Project()
    history = ProjectHistory()
    obj = project.add_object('Table', 'table', id='table_01')
    annotation = project.add_annotation(1, 3, category='Action / HOI', label='touch object',
                                         attributes={'object_id': obj.id})
    annotation_before = asdict(annotation)
    history.mark_saved(project)
    history.checkpoint(project)
    project.update_object(obj.id, name='Round table', notes='near sofa')
    project.retire_object(obj.id)
    assert project.get_object(obj.id).name == 'Round table'
    assert project.get_object(obj.id).retired
    assert asdict(project.annotations[0]) == annotation_before
    assert history.is_dirty(project)
    assert history.undo(project)
    assert project.get_object(obj.id).name == 'Table'
    assert not project.get_object(obj.id).retired
    assert not history.is_dirty(project)
    assert history.redo(project)
    assert project.get_object(obj.id).retired


def test_object_validation_and_invalid_update_are_atomic():
    project = Project()
    extras = {'source': {'asset_id': 'prop-file'}}
    obj = project.add_object('Table', id='table_01', extra=extras)
    extras['source']['asset_id'] = 'different'
    assert obj.extra['source']['asset_id'] == 'prop-file'
    initial = asdict(obj)
    with pytest.raises(ValueError, match='immutable'):
        project.update_object(obj.id, id='new-id')
    with pytest.raises(ValueError, match='cannot be empty'):
        project.update_object(obj.id, name=' ', notes='must not leak')
    with pytest.raises(ValueError, match='boolean'):
        project.update_object(obj.id, extra={'retired': 'false'})
    assert asdict(obj) == initial
    with pytest.raises(ValueError, match='Duplicate'):
        project.add_object('Other table', id='table_01')
    with pytest.raises(ValueError, match='cannot be empty'):
        project.add_object(' ')
    assert len(project.objects) == 1
