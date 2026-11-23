"""Behavioral regression tests for the persistent editor data model."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import csv
import json
import xml.etree.ElementTree as ET

import pytest
from annotationstudio.models import (
    Annotation, Asset, Project, export_csv, export_eaf, import_annotation_csv,
)
from annotationstudio.editing import ProjectHistory
from annotationstudio.ontology import WORKSPACES, WORKSPACE_CATEGORIES, category_workspace

BASE = Path(__file__).resolve().parent.parent


def test_old_project_migrates_ids_tracks_and_unmapped_predictions(tmp_path, private_samples):
    private_samples('S004_I02_example.ocumo.json', 'S004_I02_R01_BVH.bvh', 'S004_I02_R02_BVH.bvh')
    old = json.loads((BASE / 'examples/S004_I02_example.ocumo.json').read_text(encoding='utf-8'))
    project = Project.load(BASE / 'examples/S004_I02_example.ocumo.json')
    assert [a.id for a in project.annotations] == [a['id'] for a in old['annotations']]
    assert len(project.annotations) == 167
    assert all(project.get_track(a.track_id) for a in project.annotations)
    assert all(a.original['start_s'] == a.start_s for a in project.annotations)
    assert project.annotations[0].label_id == ''
    assert not project.resolve_label(project.annotations[0].label, 'Motion Primitive')
    saved = tmp_path / 'migrated.annotation.json'
    project.save(saved)
    reread = Project.load(saved)
    assert reread.to_dict() == project.to_dict()
    assert all(Path(asset.path).is_file() for asset in reread.assets)


def test_multiple_tracks_and_composite_body_parts_roundtrip(tmp_path):
    project = Project()
    assert len(project.tracks) == 22
    one = project.add_track(name='Hands', channel='Hands', category='Hand Behavior',
                            body_parts=['Left Hand', 'Right Hand'])
    two = project.add_track(name='Hands', channel='Hands', category='Hand Behavior')
    assert one.id != two.id and one.workspace == 'Motion'
    annotation = project.add_annotation(2, 4, channel='Hands', category='Hand Behavior',
                                        label='fingers interlaced', track_id=one.id)
    assert annotation.label_id
    project.save(tmp_path / 'composite.json')
    reread = Project.load(tmp_path / 'composite.json')
    assert reread.get_track(one.id).body_parts == ['Left Hand', 'Right Hand']
    assert reread.annotations[0].track_id == one.id


def test_core_label_ids_stable_custom_names_rename_and_merge():
    project, second = Project(), Project()
    assert [label.id for label in project.labels] == [label.id for label in second.labels]
    old = project.add_label('cup touch', 'Action / HOI', scope='project')
    annotation = project.add_annotation(0, 1, label=old.name, category=old.category)
    original_id = old.id
    project.rename_label(old.id, 'touch cup')
    assert old.id == original_id and annotation.label == 'touch cup'
    assert project.resolve_label('cup touch', old.category) is old
    new = project.add_label('touch vessel', 'Action / HOI')
    project.merge_labels(old.id, new.id)
    assert old.deprecated and old.extra['replaced_by'] == new.id
    assert annotation.label_id == new.id and annotation.label == new.name
    assert annotation.original['label'] == 'cup touch'
    assert len(annotation.history) == 2
    assert old not in project.labels_for(old.category)
    assert old in project.labels_for(old.category, include_deprecated=True)


def test_automatic_unknown_label_does_not_expand_ontology():
    project = Project()
    number = len(project.labels)
    annotation = project.add_annotation(0, 1, source='auto:test', label='an unknown model class')
    assert len(project.labels) == number and not annotation.label_id
    assert annotation.original['label'] == annotation.label
    previous = annotation.snapshot()
    annotation.label = 'human correction'
    annotation.record_change(previous, 'accept', 'annotator-1')
    assert annotation.original['label'] == 'an unknown model class'
    assert annotation.history[-1]['reviewer'] == 'annotator-1'
    assert 'history' not in annotation.history[-1]['before']


def test_atomic_save_failure_preserves_existing_file(tmp_path, monkeypatch):
    project = Project('Before')
    saved = tmp_path / 'project.json'
    project.save(saved)
    original = saved.read_bytes()
    project.name = 'After'
    def fail_replace(*_args):
        raise OSError('simulated full disk / unavailable destination')
    monkeypatch.setattr('annotationstudio.models.os.replace', fail_replace)
    with pytest.raises(OSError):
        project.save(saved)
    assert saved.read_bytes() == original
    assert not list(tmp_path.glob('*.tmp'))
    assert project.path == saved


@pytest.mark.parametrize('start,end', [(float('nan'), 1), (0, float('inf')), (-1, 2), (2, 2), (3, 1)])
def test_invalid_boundaries_rejected(start, end):
    with pytest.raises(ValueError):
        Project().add_annotation(start, end)


def test_nonfinite_saved_metadata_cannot_replace_project(tmp_path):
    project = Project()
    saved = tmp_path / 'project.json'
    project.save(saved)
    original = saved.read_bytes()
    project.settings['invalid'] = float('nan')
    with pytest.raises(ValueError):
        project.save(saved)
    assert saved.read_bytes() == original


def test_duplicate_ids_cannot_corrupt_project(tmp_path):
    project = Project()
    annotation = project.add_annotation(1, 2)
    assert project.import_annotations([deepcopy(annotation)]) == []
    with pytest.raises(ValueError, match='Duplicate'):
        project.import_annotations([annotation], duplicate='error')
    project.annotations.append(deepcopy(annotation))
    with pytest.raises(ValueError, match='Duplicate'):
        project.save(tmp_path / 'bad.json')


def test_csv_review_corrected_boundaries_and_label_take_priority(tmp_path):
    path = tmp_path / 'review.csv'
    path.write_text('event_id,start_s,end_s,corrected_start_s,corrected_end_s,kinematic_L1_labels,approved_L1_labels,review_status\n'
                    'event-1,1,4,1.25,3.75,movement,raise right arm,approved\n')
    annotation = import_annotation_csv(path)[0]
    assert (annotation.start_s, annotation.end_s) == (1.25, 3.75)
    assert annotation.label == 'raise right arm'
    assert annotation.original['start_s'] == 1
    assert annotation.original['end_s'] == 4
    assert annotation.original['label'] == 'movement'
    assert annotation.id == import_annotation_csv(path)[0].id
    assert annotation.status == 'approved'


def test_csv_provenance_and_ids_roundtrip(tmp_path):
    project = Project()
    annotation = project.add_annotation(1, 3, source='auto:example', confidence=0.7,
                                        attributes={'object': 'cup', 'parts': ['Left Hand', 'Right Hand']})
    before = annotation.snapshot()
    annotation.start_s = 1.3
    annotation.status = 'approved'
    annotation.record_change(before, 'accept', 'reviewer')
    saved = tmp_path / 'annotations.csv'
    export_csv(project.annotations, saved)
    loaded = import_annotation_csv(saved)
    assert asdict(loaded[0]) == asdict(annotation)


@pytest.mark.parametrize('values', ['nan,2', '1,inf', '-1,2', '2,1'])
def test_bad_csv_reports_row_number(tmp_path, values):
    path = tmp_path / 'bad.csv'
    path.write_text(f'start_s,end_s\n{values}\n')
    with pytest.raises(ValueError, match='CSV row 2'):
        import_annotation_csv(path)


def test_eaf_overlaps_split_into_nonoverlapping_subtiers(tmp_path):
    project = Project()
    for start, end in [(0, 2), (1, 3), (2, 2.00001), (3, 4), (3.9999, 4.00001)]:
        project.add_annotation(start, end)
    path = tmp_path / 'overlaps.eaf'
    export_eaf(project.annotations, path)
    root = ET.parse(path).getroot()
    slots = {node.attrib['TIME_SLOT_ID']: int(node.attrib['TIME_VALUE'])
             for node in root.findall('./TIME_ORDER/TIME_SLOT')}
    assert len(root.findall('.//ALIGNABLE_ANNOTATION')) == 5
    assert len(root.findall('TIER')) == 2
    for tier in root.findall('TIER'):
        intervals = [(slots[node.attrib['TIME_SLOT_REF1']], slots[node.attrib['TIME_SLOT_REF2']])
                     for node in tier.findall('.//ALIGNABLE_ANNOTATION')]
        assert all(end > start for start, end in intervals)
        assert all(intervals[i - 1][1] <= intervals[i][0] for i in range(1, len(intervals)))


def test_undo_redo_restores_tracks_labels_and_annotations_together(tmp_path):
    project = Project()
    project.path = tmp_path / 'new-save-as-location.json'
    history = ProjectHistory()
    history.mark_saved(project)
    assert not history.is_dirty(project)
    initial_tracks = len(project.tracks)
    history.checkpoint(project)
    track = project.add_track(name='Object contact', category='Action / HOI')
    label = project.add_label('touch cup', 'Action / HOI')
    project.add_annotation(4, 6, track_id=track.id, category=label.category, label=label.name)
    assert history.is_dirty(project)
    assert history.undo(project)
    assert not project.annotations and len(project.tracks) == initial_tracks
    assert not project.get_label(label.id)
    assert project.path == tmp_path / 'new-save-as-location.json'
    assert not history.is_dirty(project)
    assert history.redo(project)
    assert len(project.annotations) == 1 and project.get_label(label.id)
    assert history.is_dirty(project)
    assert not history.redo(project)


def test_future_schema_and_editing_state_are_not_saved(tmp_path):
    project = Project()
    path = tmp_path / 'project.json'
    project.save(path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    raw['version'] = 999
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='Unsupported'):
        Project.load(path)
    with pytest.raises(ValueError, match='transient'):
        project.add_annotation(0, 1, status='editing')


def test_workspace_separation_and_speech_are_not_inferred_listening():
    assert WORKSPACES == ('Overview', 'Activity', 'Motion', 'Gesture', 'HOI', 'Speech',
                          'Spatial', 'Social', 'Affect', 'Review')
    assert category_workspace('Action / HOI') == 'HOI'
    assert category_workspace('Facial Expression') == 'Face'
    assert category_workspace('Emotion') == 'Affect'
    assert all(category_workspace(category) == 'Speech'
               for category in ('Speaking', 'Vocal Event', 'Audio Activity'))
    project = Project()
    assert not any('listener' in label.name.lower() for label in project.labels_for('Speaking'))


def test_windows_relative_paths_load_on_linux(tmp_path):
    asset = Asset.deserialize({'id': 'a', 'kind': 'video', 'role': 'R01',
                               'path': 'media\\face.mp4', 'relative_to_project': True}, tmp_path)
    assert Path(asset.path) == tmp_path / 'media' / 'face.mp4'


def test_edit_draft_and_cancel_never_modify_project():
    from annotationstudio.editing import EditSession
    project = Project()
    annotation = project.add_annotation(1, 4, label='raise right arm', status='approved')
    before = project.to_dict()
    session = EditSession(project, ProjectHistory())
    session.begin(annotation.id)
    assert not session.dirty and session.draft is not annotation
    session.update(start_s=2, label='lower right arm')
    assert session.dirty and project.to_dict() == before
    session.cancel()
    assert session.draft is None and not session.dirty
    assert project.to_dict() == before


def test_accept_preserves_prediction_and_undo_restores_original():
    from annotationstudio.editing import EditSession
    project = Project()
    annotation = project.add_annotation(1, 4, label='unmapped prediction', source='auto:test',
                                        confidence=.81, attributes={'native_start_s': .2})
    initial = deepcopy(annotation)
    history = ProjectHistory()
    session = EditSession(project, history)
    session.begin(annotation.id)
    session.update(start_s=1.5, end_s=3.8, label='Reviewed custom action')
    committed = session.accept('coder-01')
    assert committed is annotation and committed.status == 'approved'
    assert committed.source == 'auto:test' and committed.confidence == .81
    assert committed.original == initial.original
    assert committed.original['label'] == 'unmapped prediction'
    assert committed.label_id == project.resolve_label('Reviewed custom action', committed.category).id
    assert committed.history[-1]['before']['start_s'] == 1
    assert committed.history[-1]['after']['start_s'] == 1.5
    assert committed.history[-1]['reviewer'] == 'coder-01'
    assert session.draft is None
    with pytest.raises(ValueError, match='No active'):
        session.accept()
    assert history.undo(project)
    assert asdict(project.annotations[0]) == asdict(initial)
    assert project.resolve_label('Reviewed custom action', committed.category) is None
    assert not history.can_undo
    assert history.redo(project)
    assert project.annotations[0].status == 'approved'


def test_new_draft_requires_label_and_candidate_can_remain_unlabeled():
    from annotationstudio.editing import EditSession
    project = Project()
    history = ProjectHistory()
    session = EditSession(project, history)
    session.create(0, 2, project.tracks[0].id)
    assert session.is_new and session.dirty and not project.annotations
    with pytest.raises(ValueError, match='Choose a label'):
        session.accept()
    assert not history.can_undo and not project.annotations
    candidate = session.save_candidate()
    assert candidate.status == 'pending' and candidate.label == 'Unlabeled'
    assert len(project.annotations) == 1
    assert history.undo(project) and not project.annotations


def test_bad_draft_update_is_atomic_and_identity_cannot_change():
    from annotationstudio.editing import EditSession
    project = Project()
    session = EditSession(project, ProjectHistory())
    session.create(1, 3, project.tracks[0].id)
    before = asdict(session.draft)
    for values in ({'start_s': 5}, {'end_s': float('nan')}, {'id': 'wrong-id'},
                   {'source': 'manual'}, {'original': {}}, {'track_id': 'missing'}):
        with pytest.raises(ValueError):
            session.update(**values)
        assert asdict(session.draft) == before
    assert not project.annotations


def test_save_model_candidate_keeps_unknown_label_unmapped():
    from annotationstudio.editing import EditSession
    project = Project()
    annotation = project.add_annotation(1, 4, source='auto:test', label='Novel model output')
    label_count = len(project.labels)
    session = EditSession(project, ProjectHistory())
    session.begin(annotation.id)
    session.update(start_s=1.1)
    result = session.save_candidate()
    assert result.status == 'pending' and not result.label_id
    assert len(project.labels) == label_count


def test_edit_conflict_does_not_overwrite_external_changes():
    from annotationstudio.editing import EditSession
    project = Project()
    annotation = project.add_annotation(1, 4, label='raise right arm')
    history = ProjectHistory()
    session = EditSession(project, history)
    session.begin(annotation.id)
    session.update(end_s=3)
    annotation.notes = 'External change'
    with pytest.raises(ValueError, match='outside'):
        session.accept()
    assert annotation.end_s == 4 and annotation.notes == 'External change'
    assert not history.can_undo


def test_intentionally_empty_tracks_survive_save_and_load(tmp_path):
    project = Project()
    assert len(project.tracks) == 22
    project.tracks.clear()
    project.ensure_tracks()
    assert project.tracks == []
    path = tmp_path / 'empty.studio.json'
    project.save(path)
    reopened = Project.load(path)
    assert reopened.tracks == [] and reopened.annotations == []
    assert len(Project().tracks) == 22


def test_manual_composite_body_parts_are_copied_and_exported(tmp_path):
    from annotationstudio.editing import EditSession
    project = Project()
    hands = project.add_track(name='Two hands', category='Hand Behavior', channel='Hands',
                               body_parts=['Left Hand', 'Right Hand'])
    posture = project.add_track(name='Crossed legs', category='Body Posture', channel='Full Body',
                                 body_parts=['Left Leg', 'Right Leg'])
    session = EditSession(project, ProjectHistory())
    draft = session.create(1., 3., hands.id)
    assert draft.attributes['body_parts'] == ['Left Hand', 'Right Hand']
    assert draft.attributes['body_parts'] is not hands.body_parts
    session.update(track_id=posture.id, label='legs crossed')
    assert session.draft.attributes['body_parts'] == ['Left Leg', 'Right Leg']
    accepted = session.accept()
    path = tmp_path / 'composite.csv'
    export_csv([accepted], path)
    loaded = import_annotation_csv(path)[0]
    assert loaded.attributes['body_parts'] == ['Left Leg', 'Right Leg']
    posture.body_parts.append('Torso')
    assert accepted.attributes['body_parts'] == ['Left Leg', 'Right Leg']
