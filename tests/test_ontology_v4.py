"""Ontology migrations must preserve meaning while exposing truthful capability."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import uuid

from annotationstudio.models import core_labels, CHANNELS
from annotationstudio.ontology import (
    LABEL_PRESETS, LEGACY_LABEL_PRESETS, WORKSPACES, WORKSPACE_CATEGORIES,
    category_info, category_workspace, label_spec,
)

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = uuid.UUID('f9ee1185-2f20-5d88-bafd-9413131745c5')


def _catalog_module():
    spec = importlib.util.spec_from_file_location(
        'annotationstudio_catalog_export', ROOT / 'scripts' / 'export_label_catalog.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_physical_spatial_and_social_types_are_separated():
    assert category_workspace('Proxemic Movement') == 'Spatial'
    assert category_workspace('Spatial Configuration') == 'Spatial'
    assert category_workspace('Activity Relation') == 'Motion'
    assert WORKSPACE_CATEGORIES['Social'] == ('Interaction Event', 'Physical Interaction',
                                               'Cognitive State Expression')
    assert WORKSPACE_CATEGORIES['HOI'] == ('Action / HOI',)
    assert not {'Gaze', 'Face'} & set(WORKSPACES)
    actual = [category for workspace in WORKSPACES if workspace != 'Overview'
              for category in WORKSPACE_CATEGORIES[workspace]]
    assert len(actual) == len(set(actual))
    assert set(actual) == set(LABEL_PRESETS)


def test_retired_v03_labels_keep_original_ids_and_interval_meaning():
    labels = {(label.category, label.name): label for label in core_labels()}
    for category, name in (
        ('Dialogue Event', 'speaker turn'),
        ('Dialogue Event', 'turn handover'),
        ('Speaking', 'Overlapping speech'),
    ):
        assert name not in LABEL_PRESETS[category]
        assert name in LEGACY_LABEL_PRESETS[category]
        label = labels[(category, name)]
        assert label.deprecated
        assert label.id == str(uuid.uuid5(NAMESPACE, f'core:{category}:{name}'))
        assert label_spec(category, name)['temporal_kind'] == 'interval'
    assert labels[('Turn Transition', 'turn handover')].id != labels[('Dialogue Event', 'turn handover')].id


def test_new_transition_point_does_not_invent_duration():
    assert category_info('Speech Turn')['temporal_kind'] == 'interval'
    assert category_info('Speech Timing')['temporal_kind'] == 'interval'
    assert category_info('Turn Transition')['temporal_kind'] == 'point'
    for name in LABEL_PRESETS['Turn Transition']:
        info = label_spec('Turn Transition', name)
        assert info['temporal_kind'] == 'point'
        if name != 'Unlabeled':
            assert 'point' in info['boundary_rule'].lower()


def test_recommended_automation_is_not_current_detector_availability():
    planned = label_spec('Motion Primitive', 'head flexion')
    assert planned['recommended_workflow'] == 'automatic_primary'
    assert planned['implementation_status'] == 'planned_rule'
    assert planned['auto_mode'] == 'manual'  # retained historical capability field
    available = label_spec('Motion Primitive', 'raise right arm')
    assert available['recommended_workflow'] == 'automatic_primary'
    assert available['implementation_status'] == 'builtin'
    specific = label_spec('Motion Primitive', 'flex right elbow')
    assert specific['implementation_status'] == 'builtin'
    assert specific['auto_mode'] == 'builtin_candidate'
    turn = label_spec('Speech Turn', 'speaker turn')
    assert turn['recommended_workflow'] == 'automatic_primary'
    assert 'no built-in diarization or ASR' in turn['auto_method']
    handover = label_spec('Turn Transition', 'turn handover')
    assert handover['implementation_status'] == 'manual'
    assert handover['auto_mode'] == 'manual'


def test_speech_qualifiers_do_not_inherit_vad_capability():
    assert label_spec('Speaking', 'Speaking')['implementation_status'] == 'optional_model'
    for name in ('Speaker unknown', 'Unintelligible speech', 'silence (reviewed)'):
        assert label_spec('Speaking', name)['implementation_status'] == 'manual'
    for name in ('Breathing', 'Crying'):
        info = label_spec('Vocal Event', name)
        assert info['auto_mode'] == 'interface_only'
        assert info['implementation_status'] == 'planned_model'
        assert 'not enabled by the current GUI' in info['auto_method']


def test_waving_is_a_side_specific_kinematic_form_not_an_existing_greeting_detector():
    for side, other in (('right', 'left'), ('left', 'right')):
        name = f'wave {side} hand (kinematic)'
        info = label_spec('Motion Primitive', name)
        assert name in LABEL_PRESETS['Motion Primitive']
        assert info['semantic_kind'] == 'motion'
        assert info['temporal_kind'] == 'interval'
        assert info['recommended_workflow'] == 'automatic_primary'
        assert info['implementation_status'] == 'planned_rule'
        assert info['auto_mode'] == 'manual'
        assert info['body_parts'] == [f'{side.title()} Hand', f'{side.title()} Arm']
        assert f'{other.title()} Hand' not in info['body_parts']
        assert f'waving {side} hand' in info['aliases']
        assert 'not inferred' in info['description']
        assert 'No waving detector is implemented' in info['auto_method']
        assert 'do not duplicate' in info['boundary_rule']
    assert 'greeting wave' in LABEL_PRESETS['Gesture Type']
    assert label_spec('Gesture Type', 'greeting wave')['semantic_kind'] == 'communicative_function'


def test_primitive_body_parts_cover_both_legs_and_actual_output_channels():
    for name in LABEL_PRESETS['Motion Primitive']:
        assert set(label_spec('Motion Primitive', name)['body_parts']) <= set(CHANNELS)
    for side in ('left', 'right'):
        info = label_spec('Motion Primitive', f'{side} leg movement')
        assert info['body_parts'] == [f'{side.title()} Leg']
        assert info['implementation_status'] == 'builtin'
        assert info['auto_mode'] == 'builtin_candidate'
    for name in ('movement', 'hold', 'rest', 'not visible'):
        parts = label_spec('Motion Primitive', name)['body_parts']
        assert {'Left Leg', 'Right Leg', 'Left Hand', 'Right Hand', 'Full Body'} <= set(parts)
    assert 'Full Body' in label_spec('Motion Primitive', 'bilateral arm co-activity (not classified)')['body_parts']


def test_leg_patterns_distinguish_builtin_knee_rules_from_planned_kicks():
    for side in ('left', 'right'):
        for name in (f'bend {side} knee', f'straighten {side} knee', f'kick {side} leg (kinematic)'):
            info = label_spec('Motion Primitive', name)
            assert name in LABEL_PRESETS['Motion Primitive']
            assert info['body_parts'] == [f'{side.title()} Leg']
            assert info['semantic_kind'] == 'motion'
            assert info['recommended_workflow'] == 'automatic_primary'
            if name.startswith('kick '):
                assert info['implementation_status'] == 'planned_rule'
                assert info['auto_mode'] == 'manual'
                assert 'detector is implemented' in info['auto_method']
            else:
                assert info['implementation_status'] == 'builtin'
                assert info['auto_mode'] == 'builtin_candidate'
                assert 'thigh / shank' in info['auto_method']
        assert 'hip-knee-ankle' in label_spec('Motion Primitive', f'bend {side} knee')['boundary_rule']
        kick = label_spec('Motion Primitive', f'kick {side} leg (kinematic)')
        assert 'not a strictly atomic' in kick['description']
        assert 'not inferred' in kick['description']
    for name in ('cross legs', 'uncross legs'):
        info = label_spec('Motion Primitive', name)
        assert info['body_parts'] == ['Left Leg', 'Right Leg']
        assert info['semantic_kind'] == 'motion'
        assert info['implementation_status'] == 'planned_rule'
        assert 'primarily moving leg' in info['boundary_rule']
        assert 'Do not duplicate' in info['boundary_rule']
    assert 'cross leg' in label_spec('Motion Primitive', 'cross legs')['aliases']


def test_squat_kneel_states_are_separate_from_transitions_and_contact_is_not_assumed():
    parts = {'Root', 'Full Body', 'Left Leg', 'Right Leg'}
    for name in ('squatting', 'kneeling'):
        info = label_spec('Body Posture', name)
        assert info['semantic_kind'] == 'state'
        assert info['temporal_kind'] == 'interval'
        assert info['implementation_status'] == 'planned_rule'
        assert set(info['body_parts']) == parts
        assert 'established' in info['boundary_rule']
    kneel = label_spec('Body Posture', 'kneeling')
    assert 'BVH alone does not establish contact' in kneel['description']
    assert 'posture uncertain' in kneel['boundary_rule']
    for name in ('lower into squat', 'rise from squat', 'kneel down', 'rise from kneeling'):
        info = label_spec('Locomotion', name)
        assert name in LABEL_PRESETS['Locomotion']
        assert info['semantic_kind'] == 'motion'
        assert info['recommended_workflow'] == 'automatic_primary'
        assert info['implementation_status'] == 'planned_rule'
        assert set(info['body_parts']) == parts
        assert 'No squat/kneel transition detector' in info['auto_method']
    # New crossing motion must not replace historical sustained posture identities.
    live = {(label.category, label.name): label for label in core_labels()}
    for name in ('legs crossed', 'right leg over left', 'left leg over right', 'ankles crossed'):
        label = live[('Body Posture', name)]
        assert not label.deprecated
        assert label.id == str(uuid.uuid5(NAMESPACE, f'core:Body Posture:{name}'))
        assert label_spec('Body Posture', name)['semantic_kind'] == 'state'


def test_finer_primitive_vocabulary_uses_actor_body_parts_without_new_side_name_combinations():
    expected = {
        ('Head',): ('head flexion', 'head extension', 'turn head left', 'turn head right',
                    'tilt head left', 'tilt head right'),
        ('Torso', 'Root'): ('bend torso forward', 'straighten torso', 'lean torso backward',
                            'bend torso left', 'bend torso right', 'rotate torso left', 'rotate torso right'),
        ('Left Arm', 'Right Arm'): ('move arm outward', 'move arm inward'),
        ('Left Hand', 'Right Hand'): ('open hand', 'close hand', 'flex wrist', 'extend wrist'),
        ('Left Leg', 'Right Leg'): ('raise leg', 'lower leg', 'hip flexion', 'hip extension',
                                   'move leg outward', 'move leg inward'),
        ('Full Body', 'Left Leg', 'Right Leg'): ('move legs apart', 'bring legs together'),
    }
    assert sum(len(names) for names in expected.values()) == 27
    for parts, names in expected.items():
        for name in names:
            info = label_spec('Motion Primitive', name)
            assert name in LABEL_PRESETS['Motion Primitive']
            assert info['body_parts'] == list(parts)
            assert info['recommended_workflow'] == 'automatic_primary'
            assert info['implementation_status'] == 'planned_rule'
            assert info['auto_mode'] == 'manual'
            assert info['semantic_kind'] == 'motion'
            assert info['temporal_kind'] == 'interval'
            assert info['auto_method'].startswith('No ')
            assert set(parts) <= set(CHANNELS)
    assert 'raise thigh' in label_spec('Motion Primitive', 'hip flexion')['aliases']
    assert 'raise thigh' not in label_spec('Motion Primitive', 'raise leg')['aliases']
    assert 'split leg' in label_spec('Motion Primitive', 'move legs apart')['aliases']
    assert 'Do not duplicate' in label_spec('Motion Primitive', 'move legs apart')['boundary_rule']
    assert 'not by itself prove release' in label_spec('Motion Primitive', 'open hand')['description']


def test_specific_posture_scope_is_sustained_and_keeps_generic_choices_as_alternatives():
    expected = (
        'lying', 'lying supine', 'lying prone', 'lying on left side', 'lying on right side',
        'half-kneeling', 'standing on left leg', 'standing on right leg', 'legs apart', 'legs together',
        'front split', 'middle split', 'head upright', 'head lowered', 'head tilted back',
        'head turned left', 'head turned right', 'head tilted left', 'head tilted right',
        'torso upright', 'torso leaned left', 'torso leaned right', 'torso rotated left',
        'torso rotated right', 'arm raised', 'arm extended forward', 'arm hanging down',
        'elbow bent', 'elbow straight', 'leg raised', 'knee bent', 'knee straight',
    )
    assert len(expected) == 32
    for name in expected:
        info = label_spec('Body Posture', name)
        assert name in LABEL_PRESETS['Body Posture']
        assert info['semantic_kind'] == 'state'
        assert info['temporal_kind'] == 'interval'
        assert info['implementation_status'] == 'planned_rule'
        assert info['auto_mode'] == 'manual'
        assert 'established' in info['boundary_rule']
        assert set(info['body_parts']) <= set(CHANNELS)
    for name in ('front split', 'middle split'):
        assert 'leg separation' in label_spec('Body Posture', name)['boundary_rule']
        assert 'legs apart' in label_spec('Body Posture', name)['boundary_rule']
    assert 'stand' in label_spec('Body Posture', 'standing')['aliases']
    assert 'does not establish squatting or kneeling' in label_spec('Body Posture', 'knee bent')['description']
    assert 'elbow may be partly bent' in label_spec('Body Posture', 'arm extended forward')['description']


def test_support_dependent_postures_require_assistance_and_historical_transition_remains_a_process():
    for name in ('lying', 'lying supine', 'lying prone', 'lying on left side', 'lying on right side',
                 'kneeling', 'half-kneeling', 'standing on left leg', 'standing on right leg'):
        info = label_spec('Body Posture', name)
        assert info['recommended_workflow'] == 'assisted'
        assert info['implementation_status'] == 'planned_rule'
        assert 'support' in (info['description'] + info['evidence_mode']).lower()
    transition = label_spec('Body Posture', 'posture transition')
    assert transition['semantic_kind'] == 'posture_transition'
    assert transition['temporal_kind'] == 'interval'
    assert 'not a maintained state' in transition['description']
    live = next(label for label in core_labels()
                if label.category == 'Body Posture' and label.name == 'posture transition')
    assert live.id == str(uuid.uuid5(NAMESPACE, 'core:Body Posture:posture transition'))
    assert not live.deprecated


def test_object_states_use_explicit_object_relation_and_general_body_parts():
    for name in ('rest on object', 'sit on object', 'lean against object',
                 'lie on object', 'stand on object', 'support body on object'):
        info = label_spec('Action / HOI', name)
        assert info['semantic_kind'] == 'object_state'
        assert info['uses_object_reference'] is True
        assert info['temporal_kind'] == 'interval'
        assert info['implementation_status'] == 'planned_rule'
        assert 'No automatic relation detector' in info['auto_method']
    assert 'Full Body' in label_spec('Action / HOI', 'sit on object')['body_parts']
    assert 'Torso' in label_spec('Action / HOI', 'touch object')['body_parts']
    assert label_spec('Action / HOI', 'hold object')['semantic_kind'] == 'object_state'
    assert label_spec('Action / HOI', 'pick up object')['semantic_kind'] == 'object_action'


def test_every_active_label_has_bilingual_definition_and_separate_policy_fields():
    workflows = {'automatic_primary', 'automatic_derived', 'assisted', 'manual_primary'}
    implementations = {'builtin', 'optional_model', 'planned_rule', 'planned_model', 'manual'}
    for category, names in LABEL_PRESETS.items():
        assert len(names) == len(set(names))
        for name in names:
            info = label_spec(category, name)
            assert info['zh'] and info['description'] and info['description_zh']
            assert info['boundary_rule'] and info['boundary_rule_zh']
            assert info['recommended_workflow'] in workflows
            assert info['implementation_status'] in implementations
            assert info['temporal_kind'] in {'point', 'interval'}
            assert info['semantic_kind']
            # Returned mutable lists must not mutate shared ontology metadata.
            info['body_parts'].append('TEST MUTATION')
            assert 'TEST MUTATION' not in label_spec(category, name)['body_parts']


def test_catalog_rows_match_live_ids_and_exclude_placeholders():
    exporter = _catalog_module()
    payload = exporter.catalog_payload()
    live = {label.id: label for label in core_labels()}
    assert payload['active_label_count'] == sum(len(names) - 1 for names in LABEL_PRESETS.values())
    assert payload['active_category_count'] == len(LABEL_PRESETS)
    for row in payload['labels']:
        assert row['label_en'] != 'Unlabeled'
        assert live[row['label_id']].name == row['label_en']
        assert live[row['label_id']].category == row['category']
        assert not live[row['label_id']].deprecated
    rendered = exporter.rendered_files()
    csv_rows = list(csv.DictReader(io.StringIO(rendered['label_catalog.csv'].lstrip('\ufeff'))))
    json_rows = json.loads(rendered['label_catalog.json'])['labels']
    assert [row['label_id'] for row in csv_rows] == [row['label_id'] for row in json_rows]
    assert {row['temporal_kind'] for row in csv_rows} == {'interval', 'point'}


def test_catalog_check_is_nonmutating_and_detects_stale_files(tmp_path):
    exporter = _catalog_module()
    assert exporter.main(['--output-dir', str(tmp_path)]) == 0
    assert exporter.main(['--output-dir', str(tmp_path), '--check']) == 0
    path = tmp_path / 'label_catalog.json'
    path.write_text('stale', encoding='utf-8')
    assert exporter.main(['--output-dir', str(tmp_path), '--check']) == 1
    assert path.read_text(encoding='utf-8') == 'stale'
