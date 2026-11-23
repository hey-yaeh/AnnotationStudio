"""Read-only temporal co-occurrence queries over existing annotation tracks.

No compound label is manufactured: speech, posture and object relationships
keep their original boundaries. Export rows retain both source annotation IDs.
"""
from __future__ import annotations
import csv
from pathlib import Path
from .annotation_fields import active_secondary_object_id


CSV_COLUMNS = ('start_s', 'end_s', 'duration_s', 'role_a', 'role_b',
               'category_a', 'label_a', 'object_a', 'status_a', 'source_a_id',
               'category_b', 'label_b', 'object_b', 'status_b', 'source_b_id',
               'both_reviewed', 'secondary_object_a', 'secondary_object_b')


def union_duration(spans):
    """Length of the time union, never the sum of overlapping pair rows."""
    total, current = 0.0, None
    for start, end in sorted((float(s), float(e)) for s, e in spans if e > s):
        if current is None:
            current = [start, end]
        elif start <= current[1]:
            current[1] = max(current[1], end)
        else:
            total += current[1] - current[0]
            current = [start, end]
    return total + (current[1] - current[0] if current else 0.0)


def _selected(project, track_id, approved_only=False, label=None, object_id=None):
    if project.get_track(track_id) is None:
        raise ValueError('Select an existing annotation track.')
    return sorted((item for item in project.annotations
                   if item.track_id == track_id and item.status != 'rejected'
                   and (not approved_only or item.status == 'approved')
                   and getattr(item, 'temporal_kind', 'interval') == 'interval'
                   and item.valid()
                   and (not label or item.label == label)
                   and (not object_id or object_id in (
                       item.attributes.get('object_id'), active_secondary_object_id(project, item)))),
                  key=lambda x: (x.start_s, x.end_s, x.id))


def intersect_tracks(project, first_track_id, second_track_id, *, same_actor=True,
                     approved_only=False, label_a=None, label_b=None,
                     object_a=None, object_b=None, max_pairs=100000):
    """Return ``(rows, summary)`` without touching source labels or intervals.

    ``coverage_of_a`` uses the union of eligible A intervals as denominator.
    Same-actor mode requires the same known individual (R01 or R02); Unknown,
    Scene and Both are not individual identities. Across actors, totals refer
    to elapsed time, not participant-seconds.
    A pairwise export can contain overlapping rows; use ``overlap_union_s`` for
    the aggregate rather than summing each row's duration.
    Object filters match the primary target or an active between-objects
    second target. Retained hidden secondary references are not active targets.
    """
    if first_track_id == second_track_id:
        raise ValueError('Choose two different tracks for a co-occurrence query.')
    if not isinstance(max_pairs, int) or max_pairs < 1:
        raise ValueError('max_pairs must be a positive integer')
    a = _selected(project, first_track_id, approved_only, label_a, object_a)
    b = _selected(project, second_track_id, approved_only, label_b, object_b)
    if same_actor:
        a = [item for item in a if item.role in ('R01', 'R02')]
        b = [item for item in b if item.role in ('R01', 'R02')]
    rows = []
    first = 0
    for x in a:
        while first < len(b) and b[first].end_s <= x.start_s:
            first += 1
        for y in b[first:]:
            if y.start_s >= x.end_s:
                break
            if same_actor and (x.role not in ('R01', 'R02') or y.role != x.role):
                continue
            start, end = max(x.start_s, y.start_s), min(x.end_s, y.end_s)
            if end <= start:
                continue
            if len(rows) >= max_pairs:
                raise ValueError('Too many intersecting pairs. Restrict labels, objects or tracks before exporting.')
            rows.append({
                'start_s': start, 'end_s': end, 'duration_s': end-start,
                'role_a': x.role, 'role_b': y.role,
                'category_a': x.category, 'label_a': x.label,
                'object_a': str(x.attributes.get('object_id', '')),
                'status_a': x.status, 'source_a_id': x.id,
                'category_b': y.category, 'label_b': y.label,
                'object_b': str(y.attributes.get('object_id', '')),
                'status_b': y.status, 'source_b_id': y.id,
                'both_reviewed': x.status == 'approved' and y.status == 'approved',
                'secondary_object_a': active_secondary_object_id(project, x),
                'secondary_object_b': active_secondary_object_id(project, y),
            })
    rows.sort(key=lambda x: (x['start_s'], x['end_s'], x['source_a_id'], x['source_b_id']))
    overlap = union_duration((x['start_s'], x['end_s']) for x in rows)
    duration_a = union_duration((x.start_s, x.end_s) for x in a)
    duration_b = union_duration((x.start_s, x.end_s) for x in b)
    reviewed_overlap = union_duration((x['start_s'], x['end_s']) for x in rows if x['both_reviewed'])
    summary = {
        'source_a_count': len(a), 'source_b_count': len(b), 'pair_rows': len(rows),
        'source_a_union_s': duration_a, 'source_b_union_s': duration_b,
        'overlap_union_s': overlap, 'reviewed_overlap_union_s': reviewed_overlap,
        'coverage_of_a': overlap/duration_a if duration_a > 0 else None,
        'coverage_of_b': overlap/duration_b if duration_b > 0 else None,
        'same_actor': bool(same_actor), 'approved_only': bool(approved_only),
        'aggregation': 'union of elapsed time; not participant-seconds or sum of pair durations',
        'interpretation': 'Temporal co-occurrence only; no causal, gestural or conversational function is inferred.',
    }
    return rows, summary


def export_context_csv(path, rows):
    """Export the explicitly requested current result; source IDs stay intact."""
    with Path(path).open('w', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows({key: row.get(key, '') for key in CSV_COLUMNS} for row in rows)
