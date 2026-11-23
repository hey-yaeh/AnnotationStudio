from copy import deepcopy
import math
import pytest

from annotationstudio.models import Project
from annotationstudio.speech_structure import (SOURCE, build_speech_structure,
                                               apply_speech_structure, dependency_issues)


def speech(project, start, end, role='R01', status='approved', track_id=None):
    return project.add_annotation(start, end, category='Speaking', label='Speaking',
        channel='Speech', role=role, status=status, track_id=track_id or '')


def turns(rows):
    return [x for x in rows if x.category == 'Speech Turn']


def labeled(rows, label):
    return [x for x in rows if x.label == label]


def build(project, **options):
    return build_speech_structure(project, attribution_confirmed=True, **options)


def test_attribution_is_explicit_and_unknown_role_is_not_assigned():
    p = Project()
    speech(p, 0, 1)
    speech(p, 2, 3, 'Unknown')
    with pytest.raises(ValueError, match='Confirm'):
        build_speech_structure(p)
    rows, report = build(p)
    assert report['speaking_intervals'] == 1
    assert {x.role for x in turns(rows)} == {'R01'}
    assert all(x.status == 'pending' and x.confidence is None for x in rows)


def test_same_speaker_pause_grouping_and_derived_gap_are_read_only():
    p = Project()
    speech(p, 0, 1)
    speech(p, 1.2, 2)
    speech(p, 3, 4, 'R02')
    before = deepcopy(p.to_dict())
    rows, report = build(p)
    assert p.to_dict() == before
    assert [(x.role, x.start_s, x.end_s) for x in turns(rows)] == [('R01', 0, 2), ('R02', 3, 4)]
    assert [(x.start_s, x.end_s) for x in labeled(rows, 'within-turn pause')] == [(1, 1.2)]
    assert [(x.start_s, x.end_s) for x in labeled(rows, 'between-turn gap')] == [(2, 3)]
    marker = labeled(rows, 'speaker change candidate')[0]
    assert marker.temporal_kind == 'point' and marker.start_s == marker.end_s == 3
    assert marker.attributes['boundary_offset_s'] == 1
    assert marker.attributes['conversational_floor_verified'] is False
    assert report['turn_candidates'] == 2


def test_short_other_contribution_blocks_merge_and_is_not_called_backchannel():
    p = Project()
    speech(p, 0, 1)
    speech(p, 1.25, 2)
    speech(p, 1.05, 1.15, 'R02')
    rows, _ = build(p)
    assert len(turns(rows)) == 3
    short = next(x for x in turns(rows) if x.role == 'R02')
    assert any('duration alone' in text for text in short.attributes['review_reasons'])
    assert all(x.label != 'vocal backchannel' for x in rows)


def test_reviewed_backchannel_allows_continuation_without_dropping_acoustic_evidence():
    p = Project()
    speech(p, 0, 1)
    speech(p, 1.25, 2)
    speech(p, 1.05, 1.15, 'R02')
    marker = p.add_annotation(1.05, 1.15, role='R02', channel='Speech',
        category='Dialogue Event', label='vocal backchannel', status='approved')
    rows, report = build(p)
    assert [(x.role, x.start_s, x.end_s) for x in turns(rows)] == [('R01', 0, 2)]
    assert report['excluded_reviewed_backchannels'] == 1
    assert marker.id in turns(rows)[0].attributes['source_annotation_ids']
    assert not labeled(rows, 'speaker change candidate')
    assert [(x.start_s, x.end_s) for x in labeled(rows, 'within-turn pause')] == [(1, 1.25)]


def test_unreviewed_or_partial_backchannel_does_not_discard_speech():
    p = Project()
    speech(p, 0, 2, 'R01')
    speech(p, .5, 1.0, 'R02')
    bc = p.add_annotation(.5, 1, role='R02', channel='Speech', category='Dialogue Event',
                          label='vocal backchannel', status='pending')
    rows, report = build(p)
    assert report['excluded_reviewed_backchannels'] == 0
    assert len(turns(rows)) == 2
    bc.status, bc.end_s = 'approved', .7
    _, report = build(p)
    assert report['excluded_reviewed_backchannels'] == 0


def test_nested_overlap_does_not_invent_long_gap_or_certain_handover():
    p = Project()
    speech(p, 0, 10)
    speech(p, 3, 4, 'R02')
    speech(p, 11, 12)
    rows, _ = build(p)
    assert [(x.start_s, x.end_s) for x in labeled(rows, 'overlapping speech')] == [(3, 4)]
    points = labeled(rows, 'speaker change candidate')
    assert len(points) == 1 and points[0].start_s == 3
    assert points[0].attributes['boundary_offset_s'] == -7
    assert points[0].attributes['actual_turn_overlap_s'] == 1
    assert not labeled(rows, 'between-turn gap')
    assert not labeled(rows, 'turn handover')


def test_adjacent_turns_create_point_without_fake_duration():
    p = Project()
    speech(p, 0, 1)
    speech(p, 1, 2, 'R02')
    rows, _ = build(p)
    point = labeled(rows, 'speaker change candidate')[0]
    assert point.valid() and point.start_s == point.end_s == 1
    assert not labeled(rows, 'between-turn gap')
    assert not labeled(rows, 'overlapping speech')


def test_rerun_is_idempotent_and_dependency_snapshots_resolve():
    p = Project()
    speech(p, 0, 1)
    speech(p, 1.2, 2)
    speech(p, 3, 4, 'R02')
    rows, report = build(p)
    apply_speech_structure(p, rows, report)
    first_ids = {x.id for x in p.annotations}
    first_count = len(p.annotations)
    rows, report = build(p)
    counts = apply_speech_structure(p, rows, report)
    assert len(p.annotations) == first_count and {x.id for x in p.annotations} == first_ids
    assert counts['blocked_dependencies'] == 0
    assert all(not dependency_issues(p, x) for x in p.annotations if x.source == SOURCE)


def test_curated_turn_boundaries_drive_new_timing_and_old_accepted_markers_stay_protected():
    p = Project()
    speech(p, 0, 2)
    speech(p, 3, 4, 'R02')
    rows, report = build(p)
    apply_speech_structure(p, rows, report)
    turn = next(x for x in p.annotations if x.category == 'Speech Turn' and x.role == 'R01')
    point = next(x for x in p.annotations if x.category == 'Turn Transition')
    point.status = 'approved'
    before = turn.snapshot()
    turn.end_s, turn.status = 2.2, 'approved'
    turn.record_change(before, 'accept')
    rows, report = build(p)
    gap = labeled(rows, 'between-turn gap')[0]
    assert (gap.start_s, gap.end_s) == (2.2, 3)
    counts = apply_speech_structure(p, rows, report)
    actual = next(x for x in p.annotations if x.id == turn.id)
    assert actual.end_s == 2.2 and actual.status == 'approved'
    assert next(x for x in p.annotations if x.id == point.id).status == 'approved'
    assert counts['stale_protected'] >= 1


def test_rejected_turn_is_not_regenerated():
    p = Project()
    speech(p, 0, 1)
    speech(p, 2, 3, 'R02')
    rows, report = build(p)
    apply_speech_structure(p, rows, report)
    turn = next(x for x in p.annotations if x.category == 'Speech Turn' and x.role == 'R01')
    turn.status = 'rejected'
    rows, report = build(p)
    assert not any(x.category == 'Speech Turn' and x.role == 'R01' for x in rows)
    apply_speech_structure(p, rows, report)
    assert next(x for x in p.annotations if x.id == turn.id).status == 'rejected'


@pytest.mark.parametrize('change', ['edit', 'add_speech', 'add_backchannel', 'delete'])
def test_changed_input_set_rejects_preview_atomically(change):
    p = Project()
    item = speech(p, 0, 1)
    rows, report = build(p)
    if change == 'edit':
        item.end_s = 1.1
    elif change == 'add_speech':
        speech(p, 2, 3, 'R02')
    elif change == 'add_backchannel':
        p.add_annotation(.2, .3, category='Dialogue Event', label='vocal backchannel',
                         channel='Speech', role='R02', status='approved')
    else:
        p.annotations.remove(item)
    before = deepcopy(p.to_dict())
    with pytest.raises(ValueError, match='changed'):
        apply_speech_structure(p, rows, report)
    assert p.to_dict() == before


def test_selected_tracks_and_review_filter_are_respected():
    p = Project()
    a = speech(p, 0, 1, status='pending')
    b = speech(p, 2, 3, 'R02')
    rows, report = build(p, track_ids=[b.track_id], approved_only=True)
    assert report['speaking_intervals'] == 1
    assert [x.role for x in turns(rows)] == ['R02']
    with pytest.raises(ValueError, match='No eligible'):
        build(p, track_ids=[a.track_id], approved_only=True)
    with pytest.raises(ValueError, match='at least one'):
        build(p, track_ids=[])


@pytest.mark.parametrize('bad', [math.nan, math.inf, -1, True])
def test_invalid_parameters_are_rejected(bad):
    p = Project()
    speech(p, 0, 1)
    with pytest.raises(ValueError):
        build(p, merge_gap_s=bad)


def test_dialog_requires_attribution_and_never_mutates_project(qapp):
    from annotationstudio.speech_tools import SpeechStructureDialog
    p = Project()
    speech(p, 0, 1)
    speech(p, 2, 3, 'R02')
    before = deepcopy(p.to_dict())
    dialog = SpeechStructureDialog(p)
    assert not dialog.generate_button.isEnabled()
    dialog.confirm_attribution.setChecked(True)
    assert dialog.generate_button.isEnabled()
    dialog.generate_preview()
    assert dialog.annotations and dialog.report['turn_candidates'] == 2
    assert dialog.apply_button.isEnabled()
    assert p.to_dict() == before
    dialog.merge_gap.setValue(.5)
    assert dialog.annotations is None and not dialog.apply_button.isEnabled()
    dialog.close()


def test_new_speech_after_curated_turn_gets_residual_candidate():
    p = Project()
    first = speech(p, 0, 1)
    rows, report = build(p)
    apply_speech_structure(p, rows, report)
    curated = next(x for x in p.annotations if x.category == 'Speech Turn')
    curated.status = 'approved'
    second = speech(p, 1.1, 2)
    rows, report = build(p, merge_gap_s=.3)
    assert [(x.start_s, x.end_s) for x in turns(rows)] == [(1.1, 2)]
    assert second.id in turns(rows)[0].attributes['speaking_annotation_ids']
    assert report['residual_turn_candidates'] == 1
    counts = apply_speech_structure(p, rows, report)
    actual = sorted((x.start_s, x.end_s) for x in p.annotations if x.category == 'Speech Turn')
    assert actual == [(0, 1), (1.1, 2)]
    assert counts['blocked_dependencies'] == 0
    assert next(x for x in p.annotations if x.id == curated.id).status == 'approved'


def test_curated_middle_of_source_produces_two_nonoverlapping_residuals():
    p = Project()
    raw = speech(p, 0, 5)
    rows, report = build(p)
    apply_speech_structure(p, rows, report)
    curated = next(x for x in p.annotations if x.category == 'Speech Turn')
    before = curated.snapshot()
    curated.start_s, curated.end_s, curated.status = 1, 3, 'approved'
    curated.record_change(before, 'accept')
    # A very large merge gap must still respect the curated middle interval.
    rows, report = build(p, merge_gap_s=5)
    assert [(x.start_s, x.end_s) for x in turns(rows)] == [(0, 1), (3, 5)]
    assert len({x.id for x in turns(rows)}) == 2
    assert report['clipped_speaking_fragments'] == 2
    assert all(curated.id in x.attributes['preserved_boundary_turn_ids'] for x in turns(rows))
    counts = apply_speech_structure(p, rows, report)
    assert counts['blocked_dependencies'] == 0
    actual = sorted((x.start_s, x.end_s) for x in p.annotations if x.category == 'Speech Turn')
    assert actual == [(0, 1), (1, 3), (3, 5)]


def test_reviewed_transition_pins_parent_turns_before_regrouping():
    p = Project()
    speech(p, 0, 1)
    speech(p, 1.2, 2)
    speech(p, 3, 4, 'R02')
    rows, report = build(p, merge_gap_s=.1)
    apply_speech_structure(p, rows, report)
    point = next(x for x in p.annotations if x.category == 'Turn Transition')
    point.status = 'approved'
    expected_from = point.attributes['from_turn_id']
    expected_to = point.attributes['to_turn_id']
    point_snapshot = deepcopy(point.snapshot())
    rows, report = build(p, merge_gap_s=.3)
    assert report['retained_dependency_turns'] == 2
    assert all((x.start_s, x.end_s) != (0, 2) for x in turns(rows))
    counts = apply_speech_structure(p, rows, report)
    ids = {x.id for x in p.annotations}
    assert expected_from in ids and expected_to in ids
    assert next(x for x in p.annotations if x.id == point.id).snapshot() == point_snapshot
    transitions = [x for x in p.annotations if x.category == 'Turn Transition']
    assert len(transitions) == 1
    assert counts['retained_dependency_parents'] >= 2
    active_turns = sorted((x.role, x.start_s, x.end_s) for x in p.annotations if x.category == 'Speech Turn')
    assert active_turns == [('R01', 0, 1), ('R01', 1.2, 2), ('R02', 3, 4)]


def test_dependency_review_follows_retained_parent_to_changed_speech():
    p = Project()
    raw = speech(p, 0, 1)
    speech(p, 2, 3, 'R02')
    rows, report = build(p)
    apply_speech_structure(p, rows, report)
    point = next(x for x in p.annotations if x.category == 'Turn Transition')
    point.status = 'approved'
    raw.end_s = 1.1
    assert raw.id in dependency_issues(p, point)
    rows, report = build(p)
    counts = apply_speech_structure(p, rows, report)
    assert counts['stale_protected'] >= 1
    assert raw.id in dependency_issues(p, point)


def test_dependency_cycles_are_reported_without_recursion_loop():
    p = Project()
    a = speech(p, 0, 1)
    b = speech(p, 2, 3, 'R02')
    a.attributes['source_annotation_ids'] = [b.id]
    b.attributes['source_annotation_ids'] = [a.id]
    assert dependency_issues(p, a) == [a.id]
