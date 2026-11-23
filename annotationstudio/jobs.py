"""Background auto-annotation jobs and conservative candidate replacement.

Jobs never mutate a Project. The UI can discard a cancelled batch, then take a
single history checkpoint immediately before ``merge_auto_results`` commits a
successful batch. Human-reviewed annotations are never replacement targets.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, replace as dataclass_replace
from pathlib import Path
import math
import uuid

from .models import Annotation
from .ontology import COARSE_MOTION_LABELS, UNCLASSIFIED_MOTION
from .segmentation import (
    DEFAULT_CHANNELS, SegmentationConfig, segment_motion,
    detect_phase_structures, detect_dyadic_coactivity,
)

_ALL_COARSE_MOTION_LABELS = COARSE_MOTION_LABELS | {UNCLASSIFIED_MOTION}

class JobCancelled(RuntimeError):
    pass


def _check_cancel(cancel):
    if cancel is None:
        return
    requested = cancel() if callable(cancel) else cancel.is_set()
    if requested:
        raise JobCancelled('Automatic annotation was cancelled; no results were committed')


def _progress(callback, message):
    if callback:
        callback(message)


def _finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'{name} must be a finite number') from error
    if not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return value


def _master_range(start, end):
    start = _finite_number(start, 'Start time')
    if start < 0:
        raise ValueError('Master start time cannot be negative')
    if end is not None:
        end = _finite_number(end, 'End time')
        if end <= start:
            raise ValueError('End time must be greater than start time')
    return start, end


def _matching_asset(role, motion, assets):
    candidates = [asset for asset in assets
                  if asset.kind == 'motion' and asset.role == role and asset.enabled]
    if getattr(motion, 'path', None) is not None:
        motion_path = Path(motion.path).resolve()
        candidates = [asset for asset in candidates if Path(asset.path).resolve() == motion_path]
    return candidates[-1] if candidates else None


def _source_ids(annotation):
    attributes = annotation.attributes or {}
    ids = set()
    one = attributes.get('source_asset_id')
    if isinstance(one, str) and one:
        ids.add(one)
    many = attributes.get('source_asset_ids', [])
    if isinstance(many, (list, tuple, set)):
        ids.update(value for value in many if isinstance(value, str) and value)
    return ids


def _attach_native_provenance(annotation, asset, cfg, run_id, start, end):
    candidate = deepcopy(annotation)
    raw_prediction = deepcopy(candidate.original) or candidate.snapshot()
    native_start, native_end = candidate.start_s, candidate.end_s
    clipped_start, clipped_end = max(start, native_start), min(end, native_end)
    if clipped_end <= clipped_start:
        return None
    offset = float(asset.offset_s)
    candidate.start_s = max(0., clipped_start + offset)
    candidate.end_s = clipped_end + offset
    if not candidate.valid():
        return None
    if candidate.category == 'Motion Primitive' and candidate.label in COARSE_MOTION_LABELS:
        candidate.label = UNCLASSIFIED_MOTION
        candidate.label_id = ''
    model_version = 'signal-processing-0.3' if cfg.fine_primitives else 'signal-processing-0.2'
    candidate.attributes.update({
        'source_asset_id': asset.id, 'source_asset_ids': [asset.id],
        'source_offset_s': offset, 'source_file': str(asset.path),
        'original_native_span': {'start_s': native_start, 'end_s': native_end},
        'native_start_s': clipped_start, 'native_end_s': clipped_end,
        'analysis_native_range': {'start_s': start, 'end_s': end},
        'time_basis': 'master seconds', 'model_id': cfg.mode,
        'model_version': model_version, 'config': asdict(cfg), 'run_id': run_id,
    })
    candidate.original = candidate.snapshot()
    candidate.original['native_prediction'] = raw_prediction
    candidate.original['time_basis'] = 'master seconds'
    return candidate


def _attach_derived_provenance(candidate, related, assets_by_id, cfg, run_id):
    raw_prediction = deepcopy(candidate.original) or candidate.snapshot()
    ids = sorted(set().union(*(_source_ids(annotation) for annotation in related))) if related else []
    offsets = {asset_id: float(assets_by_id[asset_id].offset_s)
               for asset_id in ids if asset_id in assets_by_id}
    spans = {asset_id: {'start_s': candidate.start_s - offset, 'end_s': candidate.end_s - offset}
             for asset_id, offset in offsets.items()}
    candidate.attributes.update({
        'source_asset_id': ids[0] if len(ids) == 1 else '', 'source_asset_ids': ids,
        'source_offset_s': next(iter(offsets.values())) if len(offsets) == 1 else None,
        'source_offsets_s': offsets,
        'original_native_span': next(iter(spans.values())) if len(spans) == 1 else spans,
        'time_basis': 'master seconds', 'model_id': candidate.source.removeprefix('auto:'),
        'model_version': 'signal-processing-0.2', 'config': asdict(cfg), 'run_id': run_id,
        'related_annotation_ids': [annotation.id for annotation in related],
    })
    candidate.original = candidate.snapshot()
    candidate.original['detector_prediction'] = raw_prediction
    candidate.original['time_basis'] = 'master seconds'
    return candidate


def run_motion_job(motions, assets, options, progress=None, cancel=None):
    """Run selected source-local clips, then return master-clock proposals.

    ``progress`` receives a message string. Cancellation is checked between
    source analyses and before returning; a single segmentation call is not
    forcibly interrupted. ``details['scope']`` can be passed directly to the
    conservative merge function, including the actual assets processed.
    """
    _check_cancel(cancel)
    cfg = deepcopy(options.get('cfg') or SegmentationConfig())
    if isinstance(cfg, dict):
        cfg = SegmentationConfig(**cfg)
    if not isinstance(cfg, SegmentationConfig):
        raise ValueError('cfg must be a SegmentationConfig')
    start, end = _master_range(options.get('master_start', 0.), options.get('master_end'))
    cfg.validate()
    roles = list(dict.fromkeys(options.get('roles') if options.get('roles') is not None else motions.keys()))
    run_id = str(uuid.uuid4())
    proposals, processed, skipped, per_role = [], [], [], {}
    assets_by_id = {asset.id: asset for asset in assets}
    for role in roles:
        _check_cancel(cancel)
        motion = motions.get(role)
        if motion is None:
            skipped.append({'role': role, 'reason': 'No loaded motion for this actor'})
            continue
        asset = _matching_asset(role, motion, assets)
        if asset is None:
            skipped.append({'role': role, 'reason': 'No matching enabled source asset'})
            continue
        offset = _finite_number(asset.offset_s, 'Asset offset')
        duration = _finite_number(motion.duration_s, 'Motion duration')
        native_start = max(0., start - offset)
        native_end = min(duration, end - offset) if end is not None else duration
        if native_end <= native_start:
            skipped.append({'role': role, 'asset_id': asset.id,
                            'reason': 'Selected master range does not intersect this source'})
            continue
        local_cfg = dataclass_replace(cfg, start_s=native_start, end_s=native_end)
        _progress(progress, f'{role}: analysing {native_start:.3f}–{native_end:.3f} source seconds')
        found, _features, _times = segment_motion(motion, role, local_cfg)
        _check_cancel(cancel)
        current = [_attach_native_provenance(annotation, asset, local_cfg, run_id, native_start, native_end)
                   for annotation in found]
        current = [annotation for annotation in current if annotation is not None]
        proposals.extend(current)
        processed.append(asset.id)
        per_role[role] = {'count': len(current), 'asset_id': asset.id,
                          'native_range': [native_start, native_end], 'offset_s': offset}
    _check_cancel(cancel)
    # Structures must only use this run's L1 proposals, already on the master
    # clock. Do not mix accepted labels or previous runs into model inference.
    by_id = {annotation.id: annotation for annotation in proposals}
    phases, dyadic = [], []
    if options.get('structure', False):
        _progress(progress, 'Finding kinematic phase structures in the current batch')
        phases = detect_phase_structures(proposals)
        for candidate in phases:
            ids = candidate.attributes.get('related_annotation_ids', [])
            related = [by_id[annotation_id] for annotation_id in ids if annotation_id in by_id]
            _attach_derived_provenance(candidate, related, assets_by_id, cfg, run_id)
    _check_cancel(cancel)
    if options.get('dyadic', False):
        _progress(progress, 'Finding simultaneous arm activity on the master clock')
        dyadic = detect_dyadic_coactivity(proposals)
        for candidate in dyadic:
            related = [annotation for annotation in proposals
                       if annotation.role in ('R01', 'R02')
                       and annotation.channel in ('Left Arm', 'Right Arm')
                       and min(annotation.end_s, candidate.end_s) > max(annotation.start_s, candidate.start_s)]
            _attach_derived_provenance(candidate, related, assets_by_id, cfg, run_id)
    _check_cancel(cancel)
    results = sorted(proposals + phases + dyadic, key=lambda annotation: (annotation.start_s, annotation.role, annotation.channel))
    channels = list(dict.fromkeys(cfg.channels or DEFAULT_CHANNELS))
    scope_roles = list(per_role)
    sources = ['auto:graph', 'auto:velocity']
    if options.get('structure', False):
        channels.append('Full Body')
        sources.append('auto:phase-structure')
    if options.get('dyadic', False):
        channels.append('Dyadic')
        sources.append('auto:dyadic-overlap')
        if 'R01' in per_role and 'R02' in per_role:
            scope_roles.append('Both')
    details = {'run_id': run_id, 'count': len(results), 'per_role': per_role, 'skipped': skipped,
               'l1_count': len(proposals), 'structure_count': len(phases), 'dyadic_count': len(dyadic),
               'scope': {'source_asset_ids': list(dict.fromkeys(processed)), 'roles': scope_roles,
                         'channels': list(dict.fromkeys(channels)), 'start_s': start, 'end_s': end,
                         'sources': sources}}
    _progress(progress, f'Completed: {len(results)} pending motion proposals; review labels and boundaries')
    _check_cancel(cancel)
    return results, details


_SOURCE_FAMILIES = {
    'motion': ('auto:graph', 'auto:velocity', 'auto:phase-structure', 'auto:dyadic-overlap'),
    'bvh': ('auto:graph', 'auto:velocity', 'auto:phase-structure', 'auto:dyadic-overlap'),
    'graph': ('auto:graph',), 'velocity': ('auto:velocity',),
    'phase': ('auto:phase-structure',), 'dyadic': ('auto:dyadic-overlap',),
    'energy': ('auto:energy',), 'silero': ('auto:silero',), 'yamnet': ('auto:yamnet',),
}


def _matches_source(source, requested):
    for item in requested:
        for prefix in _SOURCE_FAMILIES.get(item, (item,)):
            if prefix.endswith('*') and source.startswith(prefix[:-1]):
                return True
            if source == prefix or source.startswith(prefix + ':') or source.startswith(prefix + '/'):
                return True
    return False


def _same_event_kind(first, second):
    # A reviewed sigh must not suppress laughter (or a gesture suppress motion)
    # just because they overlap. Graph and velocity may propose the same motion.
    first_family = 'kinematics' if first.source in ('auto:graph', 'auto:velocity') else first.source
    second_family = 'kinematics' if second.source in ('auto:graph', 'auto:velocity') else second.source
    label_matches = (bool(first.label_id) and first.label_id == second.label_id) or (
        first.label.strip().casefold() == second.label.strip().casefold())
    if first.category == second.category == 'Motion Primitive' and first_family == 'kinematics':
        label_matches = label_matches or (
            first.label in _ALL_COARSE_MOTION_LABELS and second.label in _ALL_COARSE_MOTION_LABELS)
    return (first.role == second.role and first.channel == second.channel
            and first.category == second.category and first.layer == second.layer
            and first_family == second_family and label_matches
            and bool(_source_ids(first)) and _source_ids(first) == _source_ids(second))


def _obvious_duplicate(first, second):
    if _same_event_kind(first, second):
        intersection = max(0., min(first.end_s, second.end_s) - max(first.start_s, second.start_s))
        union = max(first.end_s, second.end_s) - min(first.start_s, second.start_s)
        # Keep distinct shorter events nested inside a reviewed longer one.
        if union > 0 and intersection / union >= .85:
            return True
    return _same_original_primitive(first, second)


def _same_original_primitive(candidate, reviewed):
    """Suppress an exact repeat of a fine rule proposal after its label is edited."""
    evidence = candidate.attributes.get('primitive_evidence')
    original = reviewed.original or {}
    original_attributes = original.get('attributes')
    if not isinstance(evidence, dict) or not isinstance(original_attributes, dict):
        return False
    original_evidence = original_attributes.get('primitive_evidence')
    asset_id = candidate.attributes.get('source_asset_id')
    return (isinstance(original_evidence, dict) and bool(asset_id)
            and asset_id == original_attributes.get('source_asset_id')
            and all(getattr(candidate, field) == original.get(field)
                    for field in ('role', 'channel', 'category', 'label', 'start_s', 'end_s'))
            and all(evidence.get(field) == original_evidence.get(field)
                    for field in ('rule', 'first_frame', 'last_frame')))


def _has_manual_edits(annotation):
    if annotation.history:
        return True
    # Older plugins may preserve an original prediction without appending a
    # history entry. Treat visible edits as protected in that case as well.
    original = annotation.original or {}
    return any(key in original and original[key] != getattr(annotation, key)
               for key in ('start_s', 'end_s', 'label', 'role', 'channel',
                           'category', 'notes', 'tags', 'reviewer'))


def merge_auto_results(project, results, scope, replace=True):
    """Commit proposals while protecting reviewed, edited and unrelated data.

    Replacements require explicit asset identity, matching source/actor/body
    part, full containment in the requested master interval, pending state and
    empty edit history. Legacy proposals lacking an asset ID are preserved.
    Source filters accept exact IDs (including ':'/'/' version suffixes), an
    explicit trailing '*' prefix, or the named families above.
    """
    start, end = _master_range(scope.get('start_s', 0.), scope.get('end_s'))
    asset_ids = set(scope.get('source_asset_ids') or [])
    roles = set(scope.get('roles') or [])
    channels = None if scope.get('channels') is None else set(scope['channels'])
    sources = list(scope.get('sources') or [])
    incoming = [deepcopy(annotation) for annotation in results]
    for annotation in incoming:
        if not annotation.valid() or annotation.status != 'pending' or not annotation.source.startswith('auto:'):
            raise ValueError('Automatic jobs may commit only valid pending auto annotations')
    kept, replaceable, protected = [], [], 0
    duplicate_protection = []
    for annotation in project.annotations:
        filter_matches = (annotation.source.startswith('auto:')
                          and _matches_source(annotation.source, sources)
                          and annotation.role in roles
                          and (channels is None or annotation.channel in channels))
        ids = _source_ids(annotation)
        identity_matches = bool(ids) and ids.issubset(asset_ids)
        overlaps = annotation.end_s > start and (end is None or annotation.start_s < end)
        contained = annotation.start_s >= start - 1e-9 and (end is None or annotation.end_s <= end + 1e-9)
        historical_coarse = (annotation.category == 'Motion Primitive'
                             and annotation.label in COARSE_MOTION_LABELS)
        edited = _has_manual_edits(annotation)
        eligible = (filter_matches and identity_matches and contained and not historical_coarse
                    and annotation.status == 'pending' and not edited)
        if replace and eligible:
            replaceable.append(annotation)
        else:
            kept.append(annotation)
            if historical_coarse or edited or annotation.status in ('approved', 'rejected'):
                duplicate_protection.append(annotation)
            # Unknown v1 asset provenance is itself a protection reason; another
            # known asset outside scope is simply unrelated, not "protected".
            if replace and filter_matches and overlaps and (identity_matches or not ids):
                protected += 1
    kept_ids = {annotation.id for annotation in kept}
    additions, skipped_duplicates = [], 0
    for annotation in incoming:
        if annotation.id in kept_ids or any(_obvious_duplicate(annotation, old) for old in duplicate_protection):
            skipped_duplicates += 1
            continue
        kept_ids.add(annotation.id)
        additions.append(annotation)
    # No in-place mutation happens until all validation and comparisons finish.
    project.annotations = kept + additions
    project.ensure_tracks()
    return {'added': len(additions), 'removed': len(replaceable), 'protected': protected,
            'skipped_duplicates': skipped_duplicates}
