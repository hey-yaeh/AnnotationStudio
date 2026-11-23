from copy import deepcopy
import csv
import pytest

from annotationstudio.models import Project
from annotationstudio.context_relations import intersect_tracks, export_context_csv


def fixture_project():
    p = Project()
    a = p.add_track(name='Speech', category='Speaking', channel='Speech', role='R01')
    b = p.add_track(name='Object state', category='Action / HOI', channel='Right Hand', role='R01')
    return p, a, b


def annotate(p, track, start, end, label, **kwargs):
    return p.add_annotation(start, end, track_id=track.id, category=track.category,
                            channel=track.channel, role=kwargs.pop('role', track.role),
                            label=label, **kwargs)


def test_speaking_while_resting_is_derived_without_mutation():
    p, a, b = fixture_project()
    speech = annotate(p, a, 18, 24, 'Speaking', status='approved')
    hand = annotate(p, b, 10, 30, 'rest on object', status='approved', attributes={'object_id': 'table_01'})
    before = deepcopy(p.to_dict())
    rows, summary = intersect_tracks(p, a.id, b.id)
    assert len(rows) == 1 and (rows[0]['start_s'], rows[0]['end_s']) == (18, 24)
    assert rows[0]['source_a_id'] == speech.id and rows[0]['source_b_id'] == hand.id
    assert rows[0]['object_b'] == 'table_01'
    assert summary['overlap_union_s'] == 6 and summary['coverage_of_a'] == 1
    assert p.to_dict() == before


def test_overlapping_pair_rows_are_not_double_counted():
    p, a, b = fixture_project()
    annotate(p, a, 10, 20, 'Speaking')
    annotate(p, a, 15, 25, 'Speaking')
    annotate(p, b, 0, 30, 'rest on object')
    rows, summary = intersect_tracks(p, a.id, b.id)
    assert len(rows) == 2
    assert sum(x['duration_s'] for x in rows) == 20
    assert summary['overlap_union_s'] == 15
    assert summary['source_a_union_s'] == 15
    assert summary['coverage_of_a'] == 1
    assert summary['reviewed_overlap_union_s'] == 0


def test_roles_status_and_points_are_explicit_filters():
    p, a, b = fixture_project()
    annotate(p, a, 0, 5, 'Speaking', status='approved')
    annotate(p, b, 1, 2, 'touch object', role='R02', status='approved')
    annotate(p, b, 2, 3, 'touch object', status='rejected')
    annotate(p, b, 3, 4, 'rest on object', status='pending')
    annotate(p, b, 4, 4, 'contact marker', temporal_kind='point')
    rows, summary = intersect_tracks(p, a.id, b.id)
    assert len(rows) == 1 and rows[0]['label_b'] == 'rest on object'
    rows, summary = intersect_tracks(p, a.id, b.id, approved_only=True)
    assert rows == [] and summary['overlap_union_s'] == 0
    rows, _ = intersect_tracks(p, a.id, b.id, same_actor=False, approved_only=True)
    assert len(rows) == 1 and rows[0]['role_b'] == 'R02'


def test_label_and_object_filters_and_adjacent_intervals():
    p, a, b = fixture_project()
    annotate(p, a, 0, 4, 'Speaking')
    annotate(p, b, 0, 2, 'rest on object', attributes={'object_id': 'table_01'})
    annotate(p, b, 1, 3, 'rest on object', attributes={'object_id': 'table_02'})
    annotate(p, b, 3, 4, 'touch object', attributes={'object_id': 'table_01'})
    annotate(p, b, 4, 5, 'rest on object', attributes={'object_id': 'table_01'})
    rows, summary = intersect_tracks(p, a.id, b.id, label_b='rest on object', object_b='table_01')
    assert len(rows) == 1 and summary['overlap_union_s'] == 2
    assert summary['source_b_union_s'] == 3  # includes a non-overlapping source interval
    assert summary['coverage_of_a'] == .5


def test_empty_query_and_invalid_track_are_explicit():
    p, a, b = fixture_project()
    rows, summary = intersect_tracks(p, a.id, b.id)
    assert rows == [] and summary['coverage_of_a'] is None
    with pytest.raises(ValueError, match='different'):
        intersect_tracks(p, a.id, a.id)
    with pytest.raises(ValueError, match='existing'):
        intersect_tracks(p, a.id, 'missing')


def test_export_preserves_source_ids_and_unicode(tmp_path):
    p, a, b = fixture_project()
    first = annotate(p, a, 0, 2, 'Speaking')
    second = annotate(p, b, 1, 3, '手搁在桌上', attributes={'object_id': 'table_01'})
    rows, _ = intersect_tracks(p, a.id, b.id)
    target = tmp_path / 'context.csv'
    export_context_csv(target, rows)
    with target.open(encoding='utf-8-sig', newline='') as file:
        exported = list(csv.DictReader(file))
    assert exported[0]['source_a_id'] == first.id
    assert exported[0]['source_b_id'] == second.id
    assert exported[0]['label_b'] == '手搁在桌上'


def test_pair_limit_fails_instead_of_silently_truncating():
    p, a, b = fixture_project()
    for _ in range(2):
        annotate(p, a, 0, 2, 'Speaking')
        annotate(p, b, 0, 2, 'rest on object')
    with pytest.raises(ValueError, match='Too many'):
        intersect_tracks(p, a.id, b.id, max_pairs=2)


def test_context_dialog_is_read_only_and_filters_invalidate_export(qapp):
    from annotationstudio.context_dialog import ContextQueryDialog
    p, a, b = fixture_project()
    annotate(p, a, 18, 24, 'Speaking')
    annotate(p, b, 10, 30, 'rest on object', attributes={'object_id': 'table_01'})
    before = deepcopy(p.to_dict())
    dialog = ContextQueryDialog(p)
    dialog.track_a.setCurrentIndex(dialog.track_a.findData(a.id))
    dialog.track_b.setCurrentIndex(dialog.track_b.findData(b.id))
    dialog.calculate()
    assert dialog.summary['overlap_union_s'] == 6
    assert dialog.export_button.isEnabled()
    assert p.to_dict() == before
    dialog.approved_only.setChecked(True)
    assert dialog.rows is None and not dialog.export_button.isEnabled()
    dialog.close()


@pytest.mark.parametrize('role', ['Unknown', 'Scene', 'Both'])
def test_same_actor_requires_known_individual_identity(role):
    p, a, b = fixture_project()
    annotate(p, a, 0, 2, 'Speaking', role=role)
    annotate(p, b, 1, 3, 'rest on object', role=role)
    rows, summary = intersect_tracks(p, a.id, b.id, same_actor=True)
    assert rows == [] and summary['overlap_union_s'] == 0
    rows, summary = intersect_tracks(p, a.id, b.id, same_actor=False)
    assert len(rows) == 1 and summary['overlap_union_s'] == 1


def test_unknown_actor_time_does_not_dilute_known_actor_coverage():
    p, a, b = fixture_project()
    annotate(p, a, 0, 2, 'Speaking', role='R01')
    annotate(p, a, 10, 12, 'Speaking', role='Unknown')
    annotate(p, b, 0, 2, 'rest on object', role='R01')
    rows, summary = intersect_tracks(p, a.id, b.id, same_actor=True)
    assert len(rows) == 1
    assert summary['source_a_count'] == 1 and summary['source_a_union_s'] == 2
    assert summary['coverage_of_a'] == 1
