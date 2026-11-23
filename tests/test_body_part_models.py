"""Anatomical primitive defaults, read-only suggestions and legacy continuity."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path

import pytest

from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.models import PRIMITIVE_CHANNELS, Project, Track


def primitive_track(project, channel, role='R01'):
    return next(track for track in project.tracks
                if (track.role, track.category, track.channel) == (role, 'Motion Primitive', channel))


def names(project, channel, role='R01', **kwargs):
    return {label.name for label in project.labels_for_track(
        primitive_track(project, channel, role), **kwargs)}


def test_new_project_covers_each_major_part_for_both_actors():
    project = Project()
    assert PRIMITIVE_CHANNELS == (
        'Left Arm', 'Right Arm', 'Head', 'Torso', 'Left Hand', 'Right Hand',
        'Left Leg', 'Right Leg', 'Root', 'Full Body',
    )
    assert len([track for track in project.tracks if track.category == 'Motion Primitive']) == 20
    for role in ('R01', 'R02'):
        tracks = [track for track in project.tracks if track.role == role and track.category == 'Motion Primitive']
        assert [track.channel for track in tracks] == list(PRIMITIVE_CHANNELS)
        assert all(track.category == 'Motion Primitive' and track.workspace == 'Motion' for track in tracks)
        assert all(track.body_parts == [track.channel] for track in tracks)
    assert project.tracks[0].channel == 'Left Arm'
    assert project.tracks[1].channel == 'Right Arm'
    assert not any('Foot' in track.channel for track in project.tracks)


def test_explicit_fill_is_idempotent_and_preserves_customized_tracks():
    project = Project()
    leg = primitive_track(project, 'Left Leg')
    leg.name = 'My existing left-leg track'
    leg.visible = False
    leg.extra['allowed_label_ids'] = []
    existing = asdict(leg)
    missing = primitive_track(project, 'Right Leg')
    project.tracks.remove(missing)
    # A posture track with the same channel must not suppress a primitive track.
    project.add_track(name='Right-leg posture', category='Body Posture', channel='Right Leg')
    additions = project.ensure_primitive_tracks(roles=('R01', 'R01'))
    assert len(additions) == 1 and additions[0].channel == 'Right Leg'
    assert additions[0].id != missing.id
    assert asdict(project.get_track(leg.id)) == existing
    before = project.to_dict()
    assert project.ensure_primitive_tracks() == []
    assert project.to_dict() == before


def test_invalid_fill_roles_fail_before_any_mutation():
    project = Project()
    project.tracks.clear()
    for roles in [('R01', 'Both'), ('R01', None), 'R01', None]:
        with pytest.raises(ValueError):
            project.ensure_primitive_tracks(roles=roles)
        assert project.tracks == []
    assert project.ensure_primitive_tracks(roles=[]) == []
    assert len(project.ensure_primitive_tracks(roles=('R02',))) == 10
    assert all(track.role == 'R02' for track in project.tracks)


def test_loading_existing_project_does_not_fill_absent_body_parts(tmp_path):
    project = Project()
    project.tracks = [primitive_track(project, 'Left Arm'), primitive_track(project, 'Right Arm')]
    project.tracks[0].name = 'Historical arm label lane'
    payload = project.to_dict()
    payload['version'] = 2
    for track in payload['tracks']:
        track['extra'].pop('temporal_kind', None)
    old_tracks = deepcopy(payload['tracks'])
    path = tmp_path / 'old.json'
    path.write_text(json.dumps(payload))
    loaded = Project.load(path)
    assert [asdict(track) for track in loaded.tracks] == old_tracks
    loaded.save(tmp_path / 'saved.json')
    assert len(Project.load(tmp_path / 'saved.json').tracks) == 2
    assert len(loaded.ensure_primitive_tracks()) == 18


def test_leg_head_and_arm_labels_are_accessible_on_correct_sides():
    project = Project()
    for role in ('R01', 'R02'):
        left_leg, right_leg = names(project, 'Left Leg', role), names(project, 'Right Leg', role)
        assert 'bend left knee' in left_leg and 'bend right knee' not in left_leg
        assert 'bend right knee' in right_leg and 'bend left knee' not in right_leg
        assert 'raise right arm' not in left_leg | right_leg
        left_arm, right_arm = names(project, 'Left Arm', role), names(project, 'Right Arm', role)
        assert 'raise left arm' in left_arm and 'raise right arm' not in left_arm
        assert 'raise right arm' in right_arm and 'raise left arm' not in right_arm
        assert 'head nod' in names(project, 'Head', role)
        assert 'head nod' not in left_arm | right_arm


def test_uncertainty_remains_available_and_broad_forms_are_retired():
    project = Project()
    for channel in PRIMITIVE_CHANNELS:
        assert {'Unlabeled', 'not visible'} <= names(project, channel), channel
        assert not {'movement', 'hold', 'rest'} & names(project, channel)


def test_custom_unspecified_labels_stay_browsable_and_declared_parts_filter():
    project = Project()
    unknown = project.add_label('Unclassified recorded action', 'Motion Primitive')
    explicit = project.add_label('My right-leg primitive', 'Motion Primitive', extra={'body_parts': ['Right Leg']})
    blank = project.add_label('Any-part action', 'Motion Primitive', extra={'body_parts': []})
    for channel in PRIMITIVE_CHANNELS:
        available = project.labels_for_track(primitive_track(project, channel))
        assert unknown in available and blank in available
    assert explicit in project.labels_for_track(primitive_track(project, 'Right Leg'))
    assert explicit not in project.labels_for_track(primitive_track(project, 'Left Leg'))


def test_core_metadata_fallback_is_read_only():
    project = Project()
    label = project.resolve_label('raise right arm', 'Motion Primitive')
    label.extra.pop('body_parts')
    label.definition = 'Preserve this authored definition'
    before = project.to_dict()
    assert label not in project.labels_for_track(primitive_track(project, 'Left Arm'))
    assert label in project.labels_for_track(primitive_track(project, 'Right Arm'))
    assert project.to_dict() == before
    assert 'body_parts' not in label.extra


def test_legacy_hands_match_both_hands_and_full_body_has_its_own_scope():
    project = Project()
    hands = project.add_track(name='Both hands', channel='Hands', category='Motion Primitive')
    choices = {label.name for label in project.labels_for_track(hands)}
    assert {'wave left hand (kinematic)', 'wave right hand (kinematic)', 'open hand'} <= choices
    assert {'head nod', 'bend right knee'}.isdisjoint(choices)
    all_names = {label.name for label in project.labels_for('Motion Primitive')}
    assert names(project, 'Full Body') == {'move legs apart', 'bring legs together', 'not visible', 'Unlabeled'}
    preview = Track(id='preview', name='Preview', category='Motion Primitive', channel=None)
    assert {label.name for label in project.labels_for_track(preview)} == all_names


def test_part_filter_is_additional_to_label_subset_and_can_be_disabled_for_preview():
    project = Project()
    left = primitive_track(project, 'Left Leg')
    right_label = project.resolve_label('bend right knee', 'Motion Primitive')
    project.set_track_label_ids(left, [right_label.id])
    before = project.to_dict()
    assert project.labels_for_track(left) == []
    assert project.labels_for_track(left, match_body_part=False) == [right_label]
    assert project.to_dict() == before


def test_existing_out_of_part_label_survives_boundary_edit_and_save(tmp_path):
    project = Project()
    leg = primitive_track(project, 'Left Leg')
    record = project.add_annotation(1, 3, track_id=leg.id, channel='Left Leg',
        category='Motion Primitive', label='raise right arm', status='approved',
        original={'historical_mapping': 'retain'}, attributes={'imported': True})
    label_id = record.label_id
    assert record.label not in names(project, 'Left Leg')
    session = EditSession(project, ProjectHistory())
    session.begin(record.id)
    session.update(end_s=3.25)
    accepted = session.accept('reviewer')
    assert accepted.label == 'raise right arm' and accepted.label_id == label_id
    assert accepted.original == {'historical_mapping': 'retain'}
    path = tmp_path / 'legacy-map.json'
    project.save(path)
    loaded = Project.load(path)
    assert loaded.annotations[0].id == accepted.id
    assert loaded.annotations[0].label_id == label_id
    assert loaded.annotations[0].end_s == 3.25


def test_manual_example_builder_adds_all_parts_without_duplicates(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('body_part_example_builder', root / 'scripts/build_manual_example.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    examples = tmp_path / 'examples'
    examples.mkdir()
    original = Project('Original')
    original.tracks.clear()
    original.add_asset('motion', 'R01', examples / 'r01.bvh')
    original.add_asset('motion', 'R02', examples / 'r02.bvh')
    original.save(examples / 'S004_I02_example.ocumo.json')
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    builder.build()
    generated = Project.load(examples / 'S004_I02_manual.studio.json')
    assert len(generated.tracks) == 72 and generated.annotations == []
    assert all(track.category != 'Activity Relation' for track in generated.tracks)
    assert [asset.id for asset in generated.assets] == [asset.id for asset in original.assets]
    primitive = [track for track in generated.tracks if track.category == 'Motion Primitive']
    keys = [(track.role, track.channel) for track in primitive]
    assert len(keys) == len(set(keys)) == 20
    assert set(keys) == {(role, channel) for role in ('R01', 'R02') for channel in PRIMITIVE_CHANNELS}
