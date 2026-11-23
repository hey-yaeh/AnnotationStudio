"""Vocabulary additions must keep observation, interpretation and history apart."""
import uuid

from annotationstudio.models import core_labels, CHANNELS
from annotationstudio.ontology import (
    LABEL_PRESETS, LEGACY_LABEL_PRESETS, WORKSPACES,
    WORKSPACE_CATEGORIES, category_info, category_workspace, label_spec,
)


def test_new_layers_are_routed_to_existing_workspaces_with_explicit_actor_scope():
    for category, workspace in (
        ('Whole-body Action', 'Motion'), ('Gait Pattern', 'Motion'),
        ('Physical Interaction', 'Social'), ('Cognitive State Expression', 'Social'),
        ('Speech Disfluency', 'Speech'),
    ):
        assert category_workspace(category) == workspace
        assert category in WORKSPACE_CATEGORIES[workspace]
        assert category_info(category)['actor_scope'] == 'single'
        assert category_info(category)['temporal_kind'] == 'interval'
    assert not {'Face', 'Gaze'} & set(WORKSPACES)
    assert 'Action / HOI' in WORKSPACE_CATEGORIES['HOI']


def test_retired_combined_neutral_retains_original_identity_and_meaning():
    key = ('Perceived Affect', 'neutral / no reliable cue')
    assert key[1] not in LABEL_PRESETS[key[0]]
    assert key[1] in LEGACY_LABEL_PRESETS[key[0]]
    labels = {(label.category, label.name): label for label in core_labels()}
    old = labels[key]
    assert old.deprecated
    assert old.id == str(uuid.uuid5(
        uuid.UUID('f9ee1185-2f20-5d88-bafd-9413131745c5'),
        'core:Perceived Affect:neutral / no reliable cue'))
    assert old.definition == label_spec(*key)['description']
    assert 'not proof' in old.definition.lower()
    for name in ('perceived neutral', 'no clear affect display', 'affect uncertain',
                 'insufficient evidence', 'mixed affect'):
        label = labels[('Perceived Affect', name)]
        assert not label.deprecated
        assert label.id != old.id
        assert label_spec('Perceived Affect', name)['implementation_status'] == 'manual'


def test_new_vocabulary_does_not_claim_a_connected_classifier():
    added = []
    for category, names in LABEL_PRESETS.items():
        for name in names:
            spec = label_spec(category, name)
            if spec.get('introduced_in') != '0.5.0':
                continue
            added.append((category, name))
            assert spec['implementation_status'] in {'manual', 'planned_rule', 'planned_model'}
            assert spec['auto_mode'] == 'manual'
            assert spec['description_zh'] and spec['boundary_rule_zh']
            assert spec['description'] and spec['boundary_rule'] and spec['evidence_mode']
            assert set(spec['body_parts']) <= set(CHANNELS)
    assert added
    # A retained implemented detector must not be downgraded by category expansion.
    assert label_spec('Motion Primitive', 'raise right arm')['implementation_status'] == 'builtin'
    assert label_spec('Speaking', 'Speaking')['implementation_status'] == 'optional_model'


def test_fall_gait_assistance_are_not_posture_cognition_or_affect_synonyms():
    fall = label_spec('Whole-body Action', 'fall down')
    assert 'performed intentionally' in fall['description']
    assert 'injury' in fall['description']
    assert 'stable new support' in fall['boundary_rule']
    assert 'fall down' not in LABEL_PRESETS['Body Posture']
    assert 'staggering gait' not in LABEL_PRESETS['Perceived Affect']
    gait = label_spec('Gait Pattern', 'staggering gait')
    assert 'does not identify intoxication' in gait['description']
    helper = label_spec('Physical Interaction', 'assist partner to rise')
    assert helper['actor_role'] == 'helper'
    assert helper['target_role_name'] == 'recipient'
    assert helper['relation_symmetry'] == 'directed'
    assert 'Success is an outcome' in helper['description']
    assert not helper.get('uses_object_reference', False)
    assert 'stand up' in LABEL_PRESETS['Locomotion']
    assert 'stand up' not in LABEL_PRESETS['Whole-body Action']


def test_cognitive_and_speech_evidence_does_not_assert_private_state():
    identity = label_spec('Cognitive State Expression', 'identity query')
    assert 'does not prove non-recognition' in identity['description']
    nonrecognition = label_spec('Cognitive State Expression', 'explicit non-recognition statement')
    assert 'rather than verifying private belief' in nonrecognition['description']
    hesitation = label_spec('Cognitive State Expression', 'hesitation display')
    assert 'silent pause alone is insufficient' in hesitation['description']
    assert 'within-turn pause' in LABEL_PRESETS['Speech Timing']
    assert 'within-turn pause' not in LABEL_PRESETS['Speech Disfluency']
    assert 'hesitation display' not in LABEL_PRESETS['Perceived Affect']
    assert 'identity query' not in LABEL_PRESETS['Interaction Event']


def test_body_local_additions_preserve_sides_and_object_relation_direction():
    for name in ('ankle dorsiflexion', 'ankle plantarflexion', 'foot inversion', 'foot eversion'):
        assert label_spec('Motion Primitive', name)['body_parts'] == ['Left Leg', 'Right Leg']
    for name in ('forearm pronation', 'forearm supination'):
        assert label_spec('Motion Primitive', name)['body_parts'] == ['Left Arm', 'Right Arm']
    state = label_spec('Action / HOI', 'object resting on body')
    assert state['uses_object_reference'] is True
    assert state['semantic_kind'] == 'object_state'
    assert 'differs from rest on object' in state['description']
    transfer = label_spec('Action / HOI', 'transfer object between own hands')
    assert 'distinct from a partner handover' in transfer['description']
    assert transfer['semantic_kind'] == 'object_action'


def test_retained_special_boundaries_do_not_fall_back_to_wrong_category_translation():
    from annotationstudio.ontology import _CATEGORY_BOUNDARIES_ZH

    # A retained precise English rule needs its matching Chinese rule. This
    # catches the old propagation of movement onset text onto held/absent states.
    for category, names in LABEL_PRESETS.items():
        # Later additive categories define their translations in CATEGORY_INFO
        # instead of the historical translation table. Check both sources.
        category_boundary_zh = (_CATEGORY_BOUNDARIES_ZH.get(category)
                                or category_info(category).get('boundary_rule_zh'))
        for name in names:
            spec = label_spec(category, name)
            if name == 'Unlabeled' or spec.get('introduced_in') == '0.5.0':
                continue
            if spec['boundary_rule'] != category_info(category)['boundary_rule']:
                assert category_boundary_zh, category
                assert spec['boundary_rule_zh'] != category_boundary_zh, (category, name)


def test_chinese_boundaries_distinguish_hold_silence_missing_data_and_timing():
    hold = label_spec('Motion Primitive', 'hold')['boundary_rule_zh']
    assert '姿态建立并持续保持' in hold and '首次明确离开' in hold
    missing = label_spec('Motion Primitive', 'not visible')['boundary_rule_zh']
    assert '无法评估' in missing and '证据恢复' in missing
    silence = label_spec('Speaking', 'silence (reviewed)')['boundary_rule_zh']
    assert '已实际试听' in silence and '音频缺失或静音不等于' in silence
    transition = label_spec('Body Posture', 'posture transition')['boundary_rule_zh']
    assert '离开前一姿态' in transition and '不纳入两端的持续姿态' in transition
    overlap = label_spec('Speech Timing', 'overlapping speech')['boundary_rule_zh']
    assert '正时长的交集' in overlap
    point = label_spec('Turn Transition', 'transition uncertain')['boundary_rule_zh']
    assert '单个时间点' in point and '不将标记扩成任意时长' in point
