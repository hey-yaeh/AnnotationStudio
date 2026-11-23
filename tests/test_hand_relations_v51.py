"""Hand-specific refinements must not rewrite earlier annotations or vocabularies."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from annotationstudio.label_palette import LabelPalette
from annotationstudio.models import Project, core_labels, export_csv, import_annotation_csv
from annotationstudio.ontology import (FINE_PRIMITIVE_AUTO_METHODS, LEGACY_MOTION_RELATION,
                                       RETIRED_PRIMITIVE_LABELS, label_spec)
from annotationstudio.ontology_v51 import HAND_MENU_GROUPS


NEW_HAND_LABELS = {'hand under chin', 'hand to chin', 'hand to cheek',
                   'chin resting on hand', 'cheek resting on hand'}


def test_all_previous_active_label_ids_meanings_and_capabilities_are_preserved():
    baseline = json.loads((Path(__file__).parents[1] / 'docs/reports/v0_5_0_label_catalog.json').read_text(encoding='utf-8'))
    current = {label.id: label for label in core_labels()}
    for row in baseline['labels']:
        label = current[row['label_id']]
        assert (label.name, label.category, label.definition) == (
            row['label_en'], row['category'], row['description_en'])
        retired = label.category == LEGACY_MOTION_RELATION or (
            label.category == 'Motion Primitive' and label.name in RETIRED_PRIMITIVE_LABELS)
        assert label.deprecated == retired
        if label.category == 'Motion Primitive' or (label.category, label.name) == (
                'Interaction Event', 'acknowledgment'):
            assert set(row['aliases']) <= set(label.aliases)
        else:
            assert label.aliases == row['aliases']
        revised_guidance = (label.category, label.name) == ('Interaction Event', 'imitation')
        if not revised_guidance:
            assert label.boundary_rule == row['boundary_rule_en']
        for field in ('recommended_workflow', 'implementation_status', 'auto_mode',
                      'auto_method', 'semantic_kind', 'temporal_kind', 'body_parts',
                      'description_zh', 'boundary_rule_zh'):
            if (label.category == 'Motion Primitive' and label.name in FINE_PRIMITIVE_AUTO_METHODS
                    and field in ('implementation_status', 'auto_mode', 'auto_method')):
                continue
            if not (revised_guidance and field == 'boundary_rule_zh'):
                assert label.extra[field] == row[field], (label.name, field)


def test_old_group_display_is_read_only_and_custom_group_interpretations_survive():
    project = Project()
    cases = [
        ('fingers interlaced', 'Hand configuration', 'Inter-hand arrangement'),
        ('palms together', 'Hand configurations', 'Inter-hand arrangement'),
        ('hand resting', 'Hand configuration', 'Hand placement'),
        ('open palm', 'Hand configurations', 'Hand configuration'),
        ('clap hands (kinematic)', 'Repetitive hand actions', 'Repetitive action'),
    ]
    for name, original_group, expected in cases:
        label = project.resolve_label(name, 'Hand Behavior')
        label.extra['group'] = original_group
        snapshot = deepcopy(asdict(label))
        assert LabelPalette._entry(label)['group'] == expected
        assert asdict(label) == snapshot
        label.extra['group'] = 'Our authored grouping'
        assert LabelPalette._entry(label)['group'] == 'Our authored grouping'
        label.scope = 'project'; label.extra['group'] = original_group
        assert LabelPalette._entry(label)['group'] == original_group


def test_old_project_load_adds_new_vocabulary_without_reclassifying_saved_contact(tmp_path):
    project = Project('Historical contact')
    project.labels = [label for label in project.labels if not (
        label.category == 'Hand Behavior' and label.name in NEW_HAND_LABELS)]
    contact = project.resolve_label('hand to face', 'Hand Behavior')
    contact.definition = 'Our reviewed coarse face-contact protocol.'
    contact.extra['study_note'] = {'retain': True}
    hand_rest = project.resolve_label('hand resting', 'Hand Behavior')
    hand_rest.extra['group'] = 'Hand configuration'
    track = project.add_track(name='Authored face-contact lane', category='Hand Behavior',
                              role='R02', channel='Left Hand', visible=False)
    project.set_track_label_ids(track, [contact.id])
    record = project.add_annotation(2.0, 6.0, track_id=track.id, role='R02',
                                    channel='Left Hand', category='Hand Behavior',
                                    label=contact.name, label_id=contact.id, status='approved',
                                    notes='Original broad observation, not relabelled.')
    before_labels = {label.id: deepcopy(asdict(label)) for label in project.labels}
    before_record = deepcopy(asdict(record)); before_track = deepcopy(asdict(track))
    path = tmp_path / 'previous.studio.json'; project.save(path)
    loaded = Project.load(path)
    assert asdict(loaded.annotations[0]) == before_record
    assert asdict(loaded.get_track(track.id)) == before_track
    for ident, previous in before_labels.items():
        assert asdict(loaded.get_label(ident)) == previous
    assert {label.name for label in loaded.labels_for('Hand Behavior')} >= NEW_HAND_LABELS
    assert [label.name for label in loaded.labels_for_track(track.id)] == ['hand to face']
    assert LabelPalette._entry(loaded.get_label(hand_rest.id))['group'] == 'Hand placement'
    saved_again = tmp_path / 'preserved.studio.json'; loaded.save(saved_again)
    reloaded = Project.load(saved_again)
    assert asdict(reloaded.annotations[0]) == before_record
    assert asdict(reloaded.get_label(contact.id)) == before_labels[contact.id]
    assert asdict(reloaded.get_label(hand_rest.id)) == before_labels[hand_rest.id]


def test_new_relation_records_keep_hand_identity_and_single_label_on_roundtrip(tmp_path):
    project = Project('Synthetic self-support schema')
    for side, name in [('Left Hand', 'cheek resting on hand'), ('Right Hand', 'chin resting on hand')]:
        track = project.add_track(name=side, role='R01', category='Hand Behavior', channel=side)
        label = project.resolve_label(name, 'Hand Behavior')
        project.add_annotation(1., 4., track_id=track.id, category=track.category,
                               role='R01', channel=side, label=name, label_id=label.id,
                               notes='Synthetic protocol example; no measured force.')
    expected = [asdict(record) for record in project.annotations]
    path = tmp_path / 'relations.studio.json'; project.save(path)
    loaded = Project.load(path)
    assert [asdict(record) for record in loaded.annotations] == expected
    assert len(loaded.annotations) == 2  # no extra broad self-touch/face-contact records
    output = tmp_path / 'relations.csv'; export_csv(loaded.annotations, output)
    imported = import_annotation_csv(output)
    # CSV intentionally orders tied times by stable ID, not insertion order.
    # Compare every persisted field by identity so random UUIDs cannot make
    # this round-trip contract intermittently fail.
    assert len(imported) == len(expected)
    assert {record.id: asdict(record) for record in imported} == {
        record['id']: record for record in expected}


def test_hand_palette_has_seven_groups_and_separates_positive_gap_from_contact(qapp):
    project = Project()
    track = project.add_track(name='Hand relation', role='R01', category='Hand Behavior',
                              channel='Left Hand')
    palette = LabelPalette()
    try:
        palette.bind(project, track)
        assert [palette.tree.topLevelItem(i).text(0)
                for i in range(palette.tree.topLevelItemCount())] == list(HAND_MENU_GROUPS)
        palette.search.setText('托腮')
        assert palette.visible_label_names() == ['cheek resting on hand']
        palette.search.setText('hand–chin contact')
        assert palette.visible_label_names() == ['hand to chin']
        for name in NEW_HAND_LABELS:
            spec = label_spec('Hand Behavior', name)
            assert spec['temporal_kind'] == 'interval' and spec['semantic_kind'] == 'state'
            assert spec['auto_mode'] == 'manual' and spec['implementation_status'] == 'planned_model'
            assert spec['body_parts'] == ['Left Hand', 'Right Hand']
        placement = label_spec('Hand Behavior', 'hand under chin')
        assert 'visible gap' in placement['description']
        assert 'obscured' in placement['description']
        assert 'force' in label_spec('Hand Behavior', 'chin resting on hand')['description']
    finally:
        palette.close(); palette.deleteLater(); qapp.processEvents()
