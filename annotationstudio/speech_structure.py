"""Deterministic speech-structure proposals from already attributed speech.

This module does not perform VAD, diarization, ASR or conversational intent
recognition. Every generated annotation remains a candidate. Explicitly reviewed
backchannels may be excluded from floor-taking proposals; short duration alone
never makes an utterance a backchannel.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import uuid

from .models import Annotation

SOURCE = 'auto:speech-structure:v1'
_NAMESPACE = uuid.UUID('71d4b8f0-65b0-5f29-91e7-550c85d6fbba')
_EPS = 1e-8


def _references(annotation):
    """Explicit upstream IDs, tolerating older/imported attribute payloads."""
    attrs = annotation.attributes
    references = set()
    snapshots = attrs.get('dependency_snapshots', {})
    if isinstance(snapshots, dict):
        references.update(key for key in snapshots if isinstance(key, str) and key)
    source_ids = attrs.get('source_annotation_ids', ())
    if isinstance(source_ids, (list, tuple, set)):
        references.update(key for key in source_ids if isinstance(key, str) and key)
    for key in ('from_turn_id', 'to_turn_id', 'parent_turn_id'):
        value = attrs.get(key)
        if isinstance(value, str) and value:
            references.add(value)
    return references


def _snapshot(annotation):
    """Fields affecting time/identity/derivation, excluding UI placement."""
    result = {key: deepcopy(getattr(annotation, key)) for key in
              ('id', 'start_s', 'end_s', 'role', 'category', 'label', 'status',
               'temporal_kind')}
    result['dependency_ids'] = sorted(_references(annotation))
    return result


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


def _is_interval(annotation):
    return getattr(annotation, 'temporal_kind', 'interval') == 'interval' and annotation.valid()


def _is_speaking(annotation):
    return (annotation.category == 'Speaking'
            and annotation.label.strip().casefold() == 'speaking'
            and annotation.role in ('R01', 'R02') and annotation.status != 'rejected'
            and _is_interval(annotation))


def _protected(annotation):
    if annotation.status != 'pending' or annotation.history:
        return True
    original = annotation.original or {}
    return any(key in original and original[key] != getattr(annotation, key)
               for key in ('start_s', 'end_s', 'role', 'category', 'label',
                           'notes', 'tags', 'reviewer', 'temporal_kind', 'attributes'))


def _union(spans):
    result = []
    for start, end in sorted((float(s), float(e)) for s, e in spans if e > s):
        if result and start <= result[-1][1] + _EPS:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _intersects(first, second):
    return min(first.end_s, second.end_s) - max(first.start_s, second.start_s) > _EPS


def _source_ids(annotation):
    return set(annotation.attributes.get('source_annotation_ids', ()))


def dependency_issues(project, annotation):
    """Return missing/changed/cyclic upstream IDs, including transitive sources.

    Reviewed metadata is never modified. A point whose retained turn parent has
    stale Speaking inputs is therefore visible to the review queue as well.
    """
    current = {item.id: item for item in project.annotations}
    issues, visited = set(), set()

    def visit(item, path):
        if item.id in path:
            issues.add(item.id)
            return
        if item.id in visited:
            return
        visited.add(item.id)
        expected = item.attributes.get('dependency_snapshots', {})
        if not isinstance(expected, dict):
            expected = {}
        for key in _references(item):
            if key not in current:
                issues.add(key)
                continue
            if key in expected and _snapshot(current[key]) != expected[key]:
                issues.add(key)
            visit(current[key], path | {item.id})

    visit(annotation, set())
    return sorted(issues)


def _retained_dependencies(project, scope_key):
    """Pin replaceable parents used by records that will survive this run."""
    current = {x.id: x for x in project.annotations}
    eligible = {x.id for x in project.annotations if x.source == SOURCE
                and x.attributes.get('scope_key') == scope_key and not _protected(x)}
    retained, pinning_roots = set(), set()
    for root in project.annotations:
        if root.id in eligible:
            continue
        stack, visited, reached = list(_references(root)), set(), set()
        while stack:
            key = stack.pop()
            if key in visited or key not in current:
                continue
            visited.add(key)
            if key in eligible:
                reached.add(key)
            stack.extend(_references(current[key]) - visited)
        if reached:
            retained.update(reached)
            pinning_roots.add(root.id)
    return retained, pinning_roots


def _subtract_coverage(start, end, coverage):
    """Split source speech around curated intervals; never discard residuals."""
    cursor, result = start, []
    for left, right in coverage:
        if right <= cursor + _EPS:
            continue
        if left >= end - _EPS:
            break
        if left > cursor + _EPS:
            result.append((cursor, min(left, end)))
        cursor = max(cursor, right)
        if cursor >= end - _EPS:
            break
    if cursor < end - _EPS:
        result.append((cursor, end))
    return result


def _input_snapshots(project, settings, scope_key):
    selected = settings.get('track_ids')
    sources = [x for x in project.annotations if _is_speaking(x)
               and (not settings.get('approved_only') or x.status == 'approved')
               and (selected is None or x.track_id in selected)]
    markers = [x for x in project.annotations
               if x.category in ('Dialogue Event', 'Speech / Dialogue')
               and x.label.strip().casefold() in ('vocal backchannel', 'backchannel')
               and x.status == 'approved' and x.role in ('R01', 'R02')
               and _is_interval(x)]
    retained, roots = _retained_dependencies(project, scope_key)
    preserved = [x for x in project.annotations if x.id in retained or x.id in roots
                 or (x.source == SOURCE and x.attributes.get('scope_key') == scope_key and _protected(x))]
    return {x.id: _snapshot(x) for x in [*sources, *markers, *preserved]}


def _proposal(project, start, end, role, category, label, dependencies,
              settings, scope_key, discriminator, *, point=False, reasons=None,
              attributes=None):
    dependencies = list({item.id: item for item in dependencies}.values())
    snapshots = {item.id: _snapshot(item) for item in dependencies}
    identity = [category, label, role, sorted(snapshots), discriminator]
    attrs = {
        'algorithm': 'speech-structure-rules-v1',
        'scope_key': scope_key,
        'parameters': deepcopy(settings),
        'source_annotation_ids': sorted(snapshots),
        'dependency_snapshots': snapshots,
        'dependency_signature': _hash(snapshots),
        'all_dependencies_reviewed': bool(dependencies) and all(item.status == 'approved' for item in dependencies),
        'review_reasons': list(dict.fromkeys(reasons or [])),
        'attribution_confirmed_for_run': True,
        'conversational_floor_verified': False,
    }
    if role == 'Both':
        attrs['participants'] = ['R01', 'R02']
    attrs.update(attributes or {})
    known = project.resolve_label(label, category)
    annotation = Annotation(
        id=str(uuid.uuid5(_NAMESPACE, json.dumps(identity, sort_keys=True))),
        start_s=float(start), end_s=float(end), role=role, channel='Speech',
        category=category, label=label, label_id=known.id if known else '',
        layer='L2 · Action / Gesture', source=SOURCE, confidence=None,
        status='pending', temporal_kind='point' if point else 'interval',
        notes='; '.join(attrs['review_reasons']), attributes=attrs,
    )
    annotation.original = annotation.snapshot()
    return annotation


def build_speech_structure(project, *, attribution_confirmed=False,
                           merge_gap_s=0.3, approved_only=False,
                           short_turn_s=0.6, track_ids=None):
    """Return ``(pending_annotations, report)`` without mutating ``project``.

    Same-speaker speech segments are joined across a configurable short pause
    only when another non-backchannel speaker does not occupy the gap. Reviewed
    ``vocal backchannel`` intervals may explain intervening speech. Durations
    merely flag ambiguity; they never classify backchannels or interruptions.

    Existing reviewed/edited results from this exact input-track scope are
    retained and used as timing anchors. Their boundaries are not overwritten.
    ``report`` captures input signatures for an optimistic-commit check.
    """
    if not attribution_confirmed:
        raise ValueError('Confirm that selected Speaking tracks are assigned to the correct R01/R02 before building turns.')
    for value, name in ((merge_gap_s, 'merge_gap_s'), (short_turn_s, 'short_turn_s')):
        if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError(f'{name} must be a finite nonnegative number')
    merge_gap_s, short_turn_s = float(merge_gap_s), float(short_turn_s)
    selected = None if track_ids is None else sorted(set(track_ids))
    if selected is not None and not selected:
        raise ValueError('Select at least one Speaking track.')
    speech = sorted((item for item in project.annotations if _is_speaking(item)
                     and (not approved_only or item.status == 'approved')
                     and (selected is None or item.track_id in selected)),
                    key=lambda item: (item.start_s, item.end_s, item.id))
    if not speech:
        raise ValueError('No eligible R01/R02 Speaking intervals. Generate/import speech or adjust the track and review filters.')
    scope_key = _hash({'tracks': selected if selected is not None else '__all_speaking__'})
    settings = {'merge_gap_s': merge_gap_s, 'short_turn_s': short_turn_s,
                'approved_only': bool(approved_only), 'track_ids': selected,
                'backchannel_policy': 'approved_explicit_intervals_only'}
    backchannels = [item for item in project.annotations
                    if item.category in ('Dialogue Event', 'Speech / Dialogue')
                    and item.label.strip().casefold() in ('vocal backchannel', 'backchannel')
                    and item.status == 'approved' and item.role in ('R01', 'R02')
                    and _is_interval(item)]
    bc_union = {role: _union((item.start_s, item.end_s) for item in backchannels
                            if item.role == role) for role in ('R01', 'R02')}
    excluded = [item for item in speech if any(start <= item.start_s + _EPS
                and end >= item.end_s - _EPS for start, end in bc_union[item.role])]
    excluded_ids = {item.id for item in excluded}
    floor_speech = [item for item in speech if item.id not in excluded_ids]
    retained_ids, pinning_roots = _retained_dependencies(project, scope_key)
    curated = [x for x in project.annotations if x.source == SOURCE
               and x.category == 'Speech Turn' and x.attributes.get('scope_key') == scope_key
               and _protected(x)]
    dependency_turns = [x for x in project.annotations if x.id in retained_ids
                        and x.category == 'Speech Turn' and _is_interval(x)]
    preserved_turns = list({x.id: x for x in [*curated, *dependency_turns]}.values())
    coverage = {role: _union((x.start_s, x.end_s) for x in preserved_turns if x.role == role)
                for role in ('R01', 'R02')}
    originals = {x.id: x for x in speech}
    generated_turns = []
    clipped_fragments = 0
    for role in ('R01', 'R02'):
        same = []
        for original in floor_speech:
            if original.role != role:
                continue
            for start, end in _subtract_coverage(original.start_s, original.end_s, coverage[role]):
                piece = deepcopy(original)
                piece.start_s, piece.end_s = start, end
                if abs(start-original.start_s) > _EPS or abs(end-original.end_s) > _EPS:
                    clipped_fragments += 1
                same.append(piece)
        same.sort(key=lambda x: (x.start_s, x.end_s, x.id))
        other = [item for item in floor_speech if item.role != role]
        groups = []
        for item in same:
            if groups:
                previous = groups[-1]
                previous_end = max(segment.end_s for segment in previous)
                gap = item.start_s - previous_end
                blocked = gap > _EPS and (
                    any(x.start_s < item.start_s - _EPS and x.end_s > previous_end + _EPS for x in other)
                    or any(left < item.start_s - _EPS and right > previous_end + _EPS
                           for left, right in coverage[role]))
                if gap <= _EPS or (gap <= merge_gap_s + _EPS and not blocked):
                    previous.append(item)
                    continue
            groups.append([item])
        for group in groups:
            start, end = min(x.start_s for x in group), max(x.end_s for x in group)
            deps = list({x.id: originals[x.id] for x in group}.values())
            clips = [x for x in group if abs(x.start_s-originals[x.id].start_s) > _EPS
                     or abs(x.end_s-originals[x.id].end_s) > _EPS]
            blockers = [old for old in preserved_turns if old.role == role
                        and any(_intersects(old, source) for source in deps)] if clips else []
            reasons = ['Rule-based grouping; conversational turn boundaries need review where ambiguous.']
            if end - start <= short_turn_s + _EPS:
                reasons.append('Short contribution: may be a turn or feedback; duration alone does not decide.')
            if any(x.start_s < end - _EPS and x.end_s > start + _EPS for x in other):
                reasons.append('Another speaker overlaps this candidate; floor transfer is unresolved.')
            related_bc = [x for x in backchannels if x.start_s < end - _EPS and x.end_s > start + _EPS]
            if related_bc:
                reasons.append('Uses an explicitly reviewed backchannel as context.')
            if any(x.status != 'approved' for x in group):
                reasons.append('Includes unreviewed Speaking boundaries.')
            if coverage[role]:
                reasons.append('Unclaimed speech around preserved turn boundaries; curated coverage is not overwritten.')
            if clips:
                reasons.append('Source speech crosses a preserved turn boundary; only its uncovered portion is proposed.')
            discriminator = ['residual_turn', start, end, sorted(x.id for x in blockers)] if clips else 'turn'
            generated_turns.append(_proposal(
                project, start, end, role, 'Speech Turn', 'speaker turn',
                [*deps, *related_bc, *blockers], settings, scope_key, discriminator, reasons=reasons,
                attributes={'speaking_annotation_ids': [x.id for x in deps],
                            'backchannel_annotation_ids': [x.id for x in related_bc],
                            'residual_after_curated_coverage': bool(coverage[role]),
                            'clipped_to_preserved_boundaries': bool(clips),
                            'preserved_boundary_turn_ids': [x.id for x in blockers]}))

    anchors = sorted([*generated_turns, *(x for x in preserved_turns if x.status != 'rejected')],
                     key=lambda x: (x.start_s, x.end_s, x.role, x.id))
    annotations = list(generated_turns)
    timing = []

    # Acoustic overlap comes from both original speech streams, including
    # backchannels, and is independent of the conversational floor hypothesis.
    unions = {role: _union((x.start_s, x.end_s) for x in speech if x.role == role)
              for role in ('R01', 'R02')}
    left, right = unions['R01'], unions['R02']
    i = j = 0
    while i < len(left) and j < len(right):
        start, end = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if end - start > _EPS:
            deps = [x for x in speech if x.start_s < end - _EPS and x.end_s > start + _EPS]
            timing.append(_proposal(project, start, end, 'Both', 'Speech Timing',
                'overlapping speech', deps, settings, scope_key, [start, end],
                reasons=['Acoustic overlap does not establish interruption or turn transfer.']))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1

    for turn in anchors:
        within = _union((max(turn.start_s, x.start_s), min(turn.end_s, x.end_s))
                        for x in speech if x.role == turn.role and _intersects(x, turn))
        for before, after in zip(within, within[1:]):
            start, end = before[1], after[0]
            if end - start <= _EPS:
                continue
            relevant = [x for x in speech if x.role == turn.role
                        and x.start_s <= end + _EPS and x.end_s >= start - _EPS]
            timing.append(_proposal(project, start, end, turn.role, 'Speech Timing',
                'within-turn pause', [turn, *relevant], settings, scope_key, [turn.id, start, end],
                reasons=['Pause in this actor\'s speech; the other actor may be audible.'],
                attributes={'parent_turn_id': turn.id}))

    # For each entry, take an actually active other speaker, or the most recently
    # ending previous turn. Nested short contributions must not create a false
    # long gap after the main speaker has already continued.
    for index, incoming in enumerate(anchors):
        earlier = [x for x in anchors[:index] if x.start_s < incoming.start_s - _EPS]
        if not earlier:
            continue
        active_other = [x for x in earlier if x.role != incoming.role
                        and x.end_s > incoming.start_s + _EPS]
        if active_other:
            outgoing = max(active_other, key=lambda x: (x.start_s, x.end_s, x.id))
        else:
            finished = [x for x in earlier if x.end_s <= incoming.start_s + _EPS]
            if not finished:
                continue
            outgoing = max(finished, key=lambda x: (x.end_s, x.start_s, x.id))
            if outgoing.role == incoming.role:
                continue
        delta = incoming.start_s - outgoing.end_s
        actual_overlap = max(0., min(incoming.end_s, outgoing.end_s) - incoming.start_s)
        reasons = ['Speaker-entry candidate; does not confirm a conversational handover.']
        if delta < -_EPS:
            reasons.append('Overlapping entry; interruption/backchannel status is unresolved.')
        between = [x for x in speech if delta > _EPS and x.start_s < incoming.start_s - _EPS
                   and x.end_s > outgoing.end_s + _EPS]
        attrs = {'from_turn_id': outgoing.id, 'to_turn_id': incoming.id,
                 'from_role': outgoing.role, 'to_role': incoming.role,
                 'boundary_offset_s': delta, 'actual_turn_overlap_s': actual_overlap,
                 'anchor_convention': 'incoming_turn_start',
                 'contains_intervening_speech': bool(between)}
        timing.append(_proposal(project, incoming.start_s, incoming.start_s, 'Both',
            'Turn Transition', 'speaker change candidate', [outgoing, incoming],
            settings, scope_key, [outgoing.id, incoming.id], point=True,
            reasons=reasons, attributes=attrs))
        if delta > _EPS and not between:
            timing.append(_proposal(project, outgoing.end_s, incoming.start_s, 'Both',
                'Speech Timing', 'between-turn gap', [outgoing, incoming], settings,
                scope_key, [outgoing.id, incoming.id],
                reasons=['Derived gap between candidate/reviewed turns; depends on their validity.'],
                attributes={'from_turn_id': outgoing.id, 'to_turn_id': incoming.id,
                            'from_role': outgoing.role, 'to_role': incoming.role}))
    annotations.extend(timing)
    all_inputs = _input_snapshots(project, settings, scope_key)
    report = {
        'scope_key': scope_key, 'parameters': settings,
        'input_snapshots': all_inputs,
        'speaking_intervals': len(speech),
        'roles': sorted({x.role for x in speech}),
        'excluded_reviewed_backchannels': len(excluded),
        'curated_turns_retained': len(curated),
        'retained_dependency_parents': len(retained_ids),
        'retained_dependency_turns': len(dependency_turns),
        'residual_turn_candidates': sum(bool(x.attributes.get('residual_after_curated_coverage')) for x in generated_turns),
        'clipped_speaking_fragments': clipped_fragments,
        'turn_candidates': len(generated_turns),
        'timing_intervals': sum(x.temporal_kind == 'interval' for x in timing),
        'transition_points': sum(x.temporal_kind == 'point' for x in timing),
        'generated': len(annotations),
        'limitations': ['No diarization or ASR is performed.',
                        'Short pauses are a project rule, not a universal definition of conversational turns.',
                        'Speaker changes remain candidates, not confirmed handovers.'],
    }
    return annotations, report


def apply_speech_structure(project, proposals, report, *, replace=True):
    """Commit a complete preview atomically; caller owns undo/checkpoint.

    Protect reviewed/rejected/edited results and unrelated scopes. Dependency
    snapshots prevent a preview being committed after its inputs changed.
    """
    incoming = deepcopy(list(proposals))
    if len({item.id for item in incoming}) != len(incoming):
        raise ValueError('Duplicate IDs in speech-structure proposals')
    for item in incoming:
        if item.source != SOURCE or item.status != 'pending' or not item.valid():
            raise ValueError('Speech structure accepts only valid pending results from this generator.')
    scope = report.get('scope_key')
    if not scope or any(x.attributes.get('scope_key') != scope for x in incoming):
        raise ValueError('Speech-structure scope mismatch')
    expected_inputs = report.get('input_snapshots')
    if not isinstance(expected_inputs, dict) or _input_snapshots(project, report.get('parameters', {}), scope) != expected_inputs:
        raise ValueError('The selected inputs changed after the preview. Generate the preview again.')
    retained_ids, _ = _retained_dependencies(project, scope)
    kept, removed, protected = [], [], []
    for item in project.annotations:
        same = item.source == SOURCE and item.attributes.get('scope_key') == scope
        if same and replace and not _protected(item) and item.id not in retained_ids:
            removed.append(item)
        else:
            kept.append(item)
            if same and _protected(item):
                protected.append(item)
    accepted = {x.id: x for x in kept}
    additions, skipped, blocked = [], 0, 0
    for item in incoming:  # turns precede their timing dependencies
        if item.id in accepted:
            skipped += 1
            continue
        deps = item.attributes.get('dependency_snapshots', {})
        if any(key not in accepted or _snapshot(accepted[key]) != expected
               for key, expected in deps.items()):
            blocked += 1
            continue
        # A human may have moved a derived event without changing its ID. If
        # source edits regenerate a different ID, retain the intentional edit.
        duplicate = any(old.category == item.category and old.role == item.role
                        and old.label == item.label and _source_ids(old) == _source_ids(item)
                        and bool(_source_ids(item)) for old in protected)
        if item.category == 'Turn Transition' and item.temporal_kind == 'point':
            duplicate = duplicate or any(old.category == 'Turn Transition'
                and old.temporal_kind == 'point' and abs(old.start_s-item.start_s) <= _EPS
                and old.attributes.get('from_role') == item.attributes.get('from_role')
                and old.attributes.get('to_role') == item.attributes.get('to_role')
                for old in protected)
        if duplicate:
            skipped += 1
            continue
        additions.append(item)
        accepted[item.id] = item
    project.annotations = kept + additions
    project.ensure_tracks()
    stale = sum(bool(dependency_issues(project, item)) for item in protected)
    return {'added': len(additions), 'removed': len(removed),
            'protected': len(protected), 'skipped_duplicates': skipped,
            'blocked_dependencies': blocked, 'stale_protected': stale,
            'retained_dependency_parents': len(retained_ids),
            'retained_dependency_turns': report.get('retained_dependency_turns', 0),
            'residual_turn_candidates': report.get('residual_turn_candidates', 0),
            'clipped_speaking_fragments': report.get('clipped_speaking_fragments', 0)}
