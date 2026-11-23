"""Manual-list selection, relation attribution, and lossless v2 compatibility."""
from copy import deepcopy
from dataclasses import asdict
import json
import uuid

import pytest

from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.models import Annotation, Label, Project, Track, track_relation_attributes
from annotationstudio.ontology import LABEL_PRESETS, LEGACY_LABEL_PRESETS


OLD_NAMESPACE = uuid.UUID('f9ee1185-2f20-5d88-bafd-9413131745c5')


def legacy_id(category, name):
    return str(uuid.uuid5(OLD_NAMESPACE, f'core:{category}:{name}'))


def active_label(project, category='Motion Primitive'):
    return next(label for label in project.labels_for(category) if label.name != 'Unlabeled')


def test_active_core_has_manual_guidance_and_historical_ids_survive():
    project = Project()
    active_pairs = {(category, name) for category, names in LABEL_PRESETS.items() for name in names}
    for category, name in active_pairs:
        label = project.get_label(legacy_id(category, name))
        assert label is not None and not label.deprecated
        assert label.definition and label.boundary_rule
        assert all(key in label.extra for key in ('group', 'zh', 'body_parts', 'auto_mode', 'auto_method'))
    historical_count = 0
    for category, names in LEGACY_LABEL_PRESETS.items():
        for name in names:
            historical_count += 1
            label = project.get_label(legacy_id(category, name))
            assert label is not None
            if (category, name) not in active_pairs:
                assert label.deprecated and label.extra['legacy']
    assert historical_count >= 190
    assert len({label.id for label in project.labels}) == len(project.labels)


def test_track_lists_filter_category_scope_and_explicit_empty_list():
    project = Project()
    track = project.tracks[0]
    core = next(label for label in project.labels_for_track(track) if label.name != 'Unlabeled')
    custom = project.add_label('custom arm action', track.category)
    temporary = project.add_label('scratch action', track.category, scope='temporary')
    foreign = project.add_label('custom object action', 'Action / HOI')
    labels = project.labels_for_track(track.id)
    assert core in labels and custom in labels and temporary not in labels and foreign not in labels
    project.set_track_label_ids(track, [])
    assert project.labels_for_track(track) == []
    project.set_track_label_ids(track.id, [custom.id, core.id, custom.id, temporary.id])
    assert track.extra['allowed_label_ids'] == [custom.id, core.id, temporary.id]
    assert {label.id for label in project.labels_for_track(track)} == {custom.id, core.id}
    track.extra['label_scope'] = 1
    assert project.labels_for_track(track) == [custom]
    track.extra['label_scope'] = 2
    assert project.labels_for_track(track) == [temporary]
    project.set_track_label_ids(track, None)
    assert 'allowed_label_ids' not in track.extra
    assert project.labels_for_track(track) == [temporary]


def test_list_updates_are_atomic_and_custom_inclusion_is_additive():
    project = Project()
    track = project.tracks[0]
    chosen = active_label(project)
    another = project.add_label('another arm action', track.category)
    foreign = active_label(project, 'Speaking')
    project.set_track_label_ids(track, [chosen.id])
    for invalid in ([foreign.id], ['missing-id'], chosen.id, [17]):
        with pytest.raises(ValueError):
            project.set_track_label_ids(track, invalid)
        assert track.extra['allowed_label_ids'] == [chosen.id]
    project.allow_label_on_track(track, another)
    project.allow_label_on_track(track.id, another.id)
    assert track.extra['allowed_label_ids'] == [chosen.id, another.id]
    project.set_track_label_ids(track, None)
    project.allow_label_on_track(track, another)
    assert 'allowed_label_ids' not in track.extra
    preview = deepcopy(track)
    preview.id = 'uncommitted-preview'
    assert project.labels_for_track(preview) == project.labels_for_track(track)
    with pytest.raises(ValueError):
        project.set_track_label_ids(preview, [])


def test_v2_roundtrip_keeps_legacy_records_custom_labels_and_unmapped_outputs(tmp_path):
    project = Project('Legacy research project')
    payload = project.to_dict()
    old_labels = [asdict(Label(
        id=legacy_id(category, name), name=name, category=category, scope='core',
        definition='Original project definition', boundary_rule='Original boundary rule',
        extra={'local_note': 'preserve'},
    )) for category, names in LEGACY_LABEL_PRESETS.items() for name in names]
    custom = Label(id='old-custom', name='custom posture', category='Body Posture',
                   aliases=['local alias'], version=4, extra={'team': 'OCUMO'})
    old_labels.append(asdict(custom))
    track = Track(id='mixed-legacy-track', name='Original mixed track', role='Both',
                  workspace='Social', category='Social Interaction', channel='Dyadic',
                  body_parts=['Full Body'], extra={'label_scope': 0, 'original_setting': 17})
    accepted = Annotation(
        id='old-accepted', start_s=1.25, end_s=3.75, role='R01', channel='Root',
        category='Social Interaction', label='approach', status='approved',
        source='auto:stage2', confidence=.73, reviewer='coder-original', track_id=track.id,
        label_id=legacy_id('Social Interaction', 'approach'),
        original={'label': 'distance decreasing', 'start_s': 1., 'end_s': 4.},
        history=[{'action': 'accept', 'reviewer': 'coder-original', 'keep': [1, 2]}],
        attributes={'target_role': 'R02', 'body_parts': ['Root']},
    )
    custom_annotation = Annotation(
        id='old-custom-annotation', start_s=5., end_s=7., role='R02', channel='Full Body',
        category=custom.category, label=custom.name, label_id=custom.id, track_id=track.id,
        status='approved', attributes={'body_parts': ['Left Leg', 'Right Leg']},
    )
    # A known-looking text is still explicitly unmapped in the saved project.
    # Adding core labels during load must not reinterpret this old prediction.
    unmapped = Annotation(id='old-unmapped', start_s=8., end_s=9., category='Speaking',
                          label='Speaking', source='auto:legacy', track_id=track.id)
    records = [asdict(item) for item in (accepted, custom_annotation, unmapped)]
    payload.update(labels=old_labels, annotations=records, tracks=[asdict(track)])
    source = tmp_path / 'old.json'
    source.write_text(json.dumps(payload), encoding='utf-8')
    loaded = Project.load(source)
    loaded.ensure_tracks()
    assert [asdict(item) for item in loaded.annotations] == records
    assert [asdict(item) for item in loaded.tracks] == [asdict(track)]
    assert all(asdict(loaded.get_label(record['id'])) == record for record in old_labels)
    assert all(loaded.get_label(legacy_id(category, name)) for category, names in LABEL_PRESETS.items()
               for name in names)
    assert not loaded.annotations[-1].label_id and loaded.annotations[-1].original == {}
    # Deprecated=False remains exactly as saved, but obsolete presets are not
    # proposed as new current labels unless historical browsing is requested.
    retired = loaded.get_label(accepted.label_id)
    assert not retired.deprecated and retired not in loaded.labels_for_track(track)
    assert retired in loaded.labels_for_track(track, include_deprecated=True)
    target = tmp_path / 'resaved.json'
    loaded.save(target)
    reread = Project.load(target)
    assert [asdict(item) for item in reread.annotations] == records
    assert reread.to_dict() == loaded.to_dict()


def test_unknown_automatic_text_does_not_map_when_vocabulary_changes(tmp_path):
    project = Project()
    annotation = project.add_annotation(1., 3., source='auto:test', label='Novel model output')
    before = deepcopy(annotation.original)
    label = project.add_label(annotation.label, annotation.category)
    project.ensure_tracks()
    assert not annotation.label_id and annotation.original == before
    session = EditSession(project, ProjectHistory())
    session.begin(annotation.id)
    session.update(start_s=1.1)
    session.save_candidate()
    assert not annotation.label_id
    path = tmp_path / 'unknown.json'
    project.save(path)
    reread = Project.load(path)
    assert not reread.annotations[0].label_id
    session = EditSession(reread, ProjectHistory())
    session.begin(annotation.id)
    accepted = session.accept()
    assert accepted.label_id == label.id and accepted.original == before


def test_accept_known_disallowed_label_fails_without_mutation_or_checkpoint():
    project = Project()
    track = project.tracks[0]
    label = active_label(project)
    project.set_track_label_ids(track, [])
    before = project.to_dict()
    history = ProjectHistory()
    session = EditSession(project, history)
    session.create(0., 2., track.id)
    session.update(label=label.name, label_id=label.id)
    with pytest.raises(ValueError, match='outside the track label list'):
        session.accept()
    assert project.to_dict() == before and not history.can_undo
    assert session.draft is not None


def test_custom_accept_adds_label_and_list_membership_in_one_undoable_action():
    project = Project()
    track = project.tracks[0]
    project.set_track_label_ids(track, [])
    before = project.to_dict()
    history = ProjectHistory()
    session = EditSession(project, history)
    session.create(2., 4., track.id)
    session.update(label='new manual gesture')
    session.cancel()
    assert project.to_dict() == before and not history.can_undo
    session.create(2., 4., track.id)
    session.update(label='new manual gesture')
    accepted = session.accept('coder-1')
    label = project.get_label(accepted.label_id)
    assert label.scope == 'project'
    assert track.extra['allowed_label_ids'] == [label.id]
    assert project.labels_for_track(track) == [label]
    committed = project.to_dict()
    assert history.undo(project)
    assert project.to_dict() == before
    assert history.redo(project)
    assert project.to_dict() == committed


def test_custom_label_respects_temporary_track_scope():
    project = Project()
    track = project.tracks[0]
    track.extra.update(label_scope=2, allowed_label_ids=[])
    session = EditSession(project, ProjectHistory())
    session.create(0., 1., track.id)
    session.update(label='pilot-only distinction')
    accepted = session.accept()
    label = project.get_label(accepted.label_id)
    assert label.scope == 'temporary' and project.labels_for_track(track) == [label]


def test_retired_current_label_can_be_resized_without_reclassifying_legacy_track():
    project = Project()
    track = project.add_track(name='Legacy pair', role='Both', category='Social Interaction',
                              channel='Dyadic', extra={'allowed_label_ids': []})
    old = project.get_label(legacy_id('Social Interaction', 'approach'))
    annotation = project.add_annotation(
        1., 4., track_id=track.id, category=old.category, label=old.name, label_id=old.id,
        role='R01', channel='Root', status='approved', source='auto:old',
        attributes={'target_role': 'R02', 'body_parts': ['Root']},
    )
    before = deepcopy(annotation)
    count = len(project.labels)
    history = ProjectHistory()
    session = EditSession(project, history)
    session.begin(annotation.id)
    session.update(track_id=track.id, label=old.name, start_s=1.2)
    accepted = session.accept()
    assert accepted.label_id == old.id and accepted.label == old.name
    assert accepted.role == 'R01' and accepted.channel == 'Root'
    assert accepted.attributes == before.attributes and accepted.original == before.original
    assert accepted.source == before.source and len(project.labels) == count
    assert project.labels_for_track(track) == []
    assert history.undo(project)
    assert asdict(project.annotations[0]) == asdict(before)


def test_explicit_actor_target_and_pair_participants_survive_save(tmp_path):
    project = Project()
    directed = project.add_track(name='R01 proximity', role='R01', category='Proxemic Movement',
                                 channel='Root', extra={'target_role': 'R02'})
    no_target = project.add_track(name='R02 proximity', role='R02', category='Proxemic Movement', channel='Root')
    pair = project.add_track(name='Pair layout', role='Both', category='Spatial Configuration', channel='Dyadic')
    assert track_relation_attributes(directed) == {'target_role': 'R02'}
    assert track_relation_attributes(no_target) == {}
    assert track_relation_attributes(pair) == {'participants': ['R01', 'R02']}
    session = EditSession(project, ProjectHistory())
    for track in (directed, no_target, pair):
        session.create(0., 2., track.id)
        session.update(label=active_label(project, track.category).name)
        session.accept()
    path = tmp_path / 'relations.json'
    project.save(path)
    loaded = Project.load(path)
    first, second, third = loaded.annotations
    assert first.role == 'R01' and first.attributes['target_role'] == 'R02'
    assert second.role == 'R02' and 'target_role' not in second.attributes
    assert third.role == 'Both' and third.attributes['participants'] == ['R01', 'R02']


def test_track_move_changes_relation_defaults_and_preserves_unrelated_attributes():
    project = Project()
    first = project.add_track(name='First', role='R01', category='Proxemic Movement', channel='Root',
                              extra={'target_role': 'R02'})
    other = project.add_track(name='Other', role='R02', category='Proxemic Movement', channel='Root',
                              extra={'target_role': 'R01'})
    pair = project.add_track(name='Pair', role='Both', category='Spatial Configuration', channel='Dyadic')
    session = EditSession(project, ProjectHistory())
    session.create(0., 3., first.id)
    session.update(label=active_label(project, first.category).name,
                   attributes={**session.draft.attributes, 'notes_from_import': {'keep': 1}})
    session.update(track_id=other.id)
    assert session.draft.role == 'R02' and session.draft.attributes['target_role'] == 'R01'
    session.update(track_id=pair.id)
    assert session.draft.role == 'Both' and session.draft.category == 'Spatial Configuration'
    assert session.draft.layer == 'L1 · Kinematics' and session.draft.label == 'Unlabeled'
    assert 'target_role' not in session.draft.attributes
    assert session.draft.attributes['participants'] == ['R01', 'R02']
    session.update(track_id=project.tracks[0].id)
    assert session.draft.layer == 'L1 · Kinematics'
    assert 'participants' not in session.draft.attributes and 'target_role' not in session.draft.attributes
    assert session.draft.attributes['notes_from_import'] == {'keep': 1}
    assert session.draft.attributes['body_parts'] == project.tracks[0].body_parts
    assert not project.annotations
    session.cancel()
    assert not project.annotations and first.extra['target_role'] == 'R02'


def test_label_merge_redirects_restricted_track_lists():
    project = Project()
    track = project.tracks[0]
    source = project.add_label('local old name', track.category)
    target = project.add_label('local preferred name', track.category)
    project.set_track_label_ids(track, [source.id, target.id])
    project.merge_labels(source.id, target.id)
    assert track.extra['allowed_label_ids'] == [target.id]
    assert project.labels_for_track(track) == [target]
