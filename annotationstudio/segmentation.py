"""Interpretable motion candidates, preserving native coordinates and time.

Velocity hysteresis and graph / multi-scale features find kinematic changes.
Scores are relative salience, not calibrated probabilities or semantic labels.
A source-local range can be processed independently; the caller applies an
asset's master-clock offset once when inserting the resulting annotations.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import math
import uuid
import numpy as np
from scipy.ndimage import gaussian_filter1d
from .models import Annotation
from .primitive_rules import (
    anatomical_torso_frame, head_spans, hinge_spans, torso_local_positions,
)

DEFAULT_CHANNELS = ('Left Arm', 'Right Arm', 'Left Leg', 'Right Leg', 'Head', 'Torso', 'Root')
MOTION_CHANNELS = ('Head', 'Torso', 'Left Arm', 'Right Arm', 'Left Hand', 'Right Hand',
                   'Hands', 'Left Leg', 'Right Leg', 'Root', 'Full Body')
_TORSO_RELATIVE_CHANNELS = ('Head', 'Left Arm', 'Right Arm')
_HINGE_CHANNELS = ('Left Arm', 'Right Arm', 'Left Leg', 'Right Leg')


@dataclass
class SegmentationConfig:
    mode: str = 'graph'
    sample_hz: float = 30.
    smoothing_s: float = .10
    high_fraction: float = .34
    low_fraction: float = .18
    min_duration_s: float = .35
    merge_gap_s: float = .25
    graph_weight: float = .24
    channels: tuple[str, ...] | list[str] | None = None
    start_s: float = 0.
    end_s: float | None = None
    up_axis: str = 'Z'
    fine_primitives: bool = True
    primitive_min_duration_s: float = .16
    head_min_excursion_deg: float = 7.
    joint_min_excursion_deg: float = 12.

    def validate(self):
        if self.mode not in ('graph', 'velocity'):
            raise ValueError('Choose graph or velocity segmentation')
        for name in ('sample_hz', 'smoothing_s', 'high_fraction', 'low_fraction',
                     'min_duration_s', 'merge_gap_s', 'graph_weight', 'start_s',
                     'primitive_min_duration_s', 'head_min_excursion_deg', 'joint_min_excursion_deg'):
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError(f'{name} must be a finite number')
        if self.sample_hz <= 0 or self.smoothing_s < 0 or self.min_duration_s <= 0 or self.merge_gap_s < 0:
            raise ValueError('Sample rate and minimum duration must be positive; smoothing and gap must be nonnegative')
        if not isinstance(self.fine_primitives, bool):
            raise ValueError('Specific primitive detection must be enabled or disabled')
        if self.primitive_min_duration_s <= 0 or not (
                0 < self.head_min_excursion_deg < 180 and 0 < self.joint_min_excursion_deg < 180):
            raise ValueError('Specific primitive rules need a positive duration and angles between 0 and 180 degrees')
        if not 0 <= self.low_fraction <= self.high_fraction <= 1:
            raise ValueError('Thresholds must satisfy 0 <= low <= high <= 1')
        if not 0 <= self.graph_weight <= 1:
            raise ValueError('Graph weight must be between 0 and 1')
        if self.start_s < 0:
            raise ValueError('Source-local start time must be nonnegative')
        if self.end_s is not None and (not math.isfinite(float(self.end_s)) or self.end_s <= self.start_s):
            raise ValueError('End time must be finite and greater than start time')
        if str(self.up_axis).upper() not in ('Y', 'Z'):
            raise ValueError('Up axis must be Y or Z')
        if self.channels is not None:
            if isinstance(self.channels, str) or not self.channels:
                raise ValueError('Select at least one motion channel')
            unknown = set(self.channels) - set(MOTION_CHANNELS)
            if unknown:
                raise ValueError('Unsupported motion channels: ' + ', '.join(sorted(unknown)))
        return self


def _safe_gradient(x, t):
    if len(t) < 2:
        return np.zeros_like(x)
    # Native sample times matter: the final appended frame can be closer to
    # the previous frame than the requested sampling interval.
    return np.gradient(x, t, axis=0)


def _smooth(x, sigma_frames):
    if sigma_frames <= 0:
        return np.array(x, copy=True)
    return gaussian_filter1d(x, max(.55, float(sigma_frames)), axis=0, mode='nearest')


def _local_rotation_speed(motion, joint_index, frame_indices, times):
    if not hasattr(motion, 'local_rotations') or joint_index is None or len(frame_indices) < 2:
        return np.zeros(len(frame_indices), dtype=np.float32)
    seq = motion.local_rotations(joint_index, frame_indices)
    if seq is None:
        return np.zeros(len(frame_indices), dtype=np.float32)
    increments = (seq[:-1].inv() * seq[1:]).magnitude() / np.diff(times)
    return np.r_[increments[0], increments].astype(np.float32)


def _graph_temporal_energy(motion, pos, time_s, scale, body_pos=None):
    n = pos.shape[1]
    edges = [(p, i) for i, p in enumerate(motion.parents) if 0 <= p < n]
    adjacency = np.zeros((n, n), dtype=np.float32)
    for parent, child in edges:
        adjacency[parent, child] = adjacency[child, parent] = 1.
    degrees = adjacency.sum(1)
    ds = 1. / np.sqrt(np.maximum(1., degrees))
    laplacian = np.eye(n, dtype=np.float32) - ds[:, None] * adjacency * ds[None, :]
    root = motion.joint('Hips', 'Pelvis', 'Root') or 0
    def derivative(coordinates):
        spatial = np.einsum('ij,tjk->tik', laplacian, coordinates / scale, optimize=True)
        return _safe_gradient(spatial, time_s)

    world_derivative = derivative(pos - pos[:, root:root + 1, :])
    torso_derivative = derivative(body_pos) if body_pos is not None else world_derivative
    selected = {
        'Head': ['Head', 'Neck', 'Neck1'],
        'Left Arm': ['LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand'],
        'Right Arm': ['RightShoulder', 'RightArm', 'RightForeArm', 'RightHand'],
        'Torso': ['Spine', 'Spine1', 'Spine2', 'Spine3'],
        'Left Leg': ['LeftUpLeg', 'LeftLeg', 'LeftFoot'],
        'Right Leg': ['RightUpLeg', 'RightLeg', 'RightFoot'],
    }
    result = {}
    for channel, names in selected.items():
        ids = [motion.joint(name) for name in names]
        ids = [i for i in ids if i is not None]
        change = torso_derivative if channel in _TORSO_RELATIVE_CHANNELS else world_derivative
        result[channel] = (np.sqrt(np.mean(np.sum(change[:, ids] ** 2, axis=-1), axis=1))
                           if ids else np.zeros(len(time_s)))
    return result


def _movement_features(motion, pos, times, cfg, frame_indices, torso=None, local_pos=None):
    scale = float(motion.scale_hint())
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Motion has no usable finite body scale')
    dt = float(np.median(np.diff(times)))
    sm = _smooth(pos, cfg.smoothing_s / dt)
    body = _smooth(local_pos, cfg.smoothing_s / dt) if local_pos is not None else None
    joint = motion.joint

    def relative_velocity(child, anchor, coordinates=sm):
        if child is None or anchor is None:
            return np.zeros(len(times), dtype=np.float32)
        movement = (coordinates[:, child] - coordinates[:, anchor]) / scale
        return np.linalg.norm(_safe_gradient(movement, times), axis=-1)

    hips = joint('Hips', 'Pelvis', 'Root') or 0
    spine = joint('Spine3', 'Chest', 'Spine2', 'Spine1', 'Spine')
    spine = spine if spine is not None else hips
    upper_pos = sm if body is None else body
    upper_anchor = spine if body is None else torso.joint
    feats = {
        'Left Arm': (.7 * relative_velocity(joint('LeftHand', 'LeftWrist'), upper_anchor, upper_pos)
                     + .3 * relative_velocity(joint('LeftForeArm', 'LeftElbow'), upper_anchor, upper_pos)),
        'Right Arm': (.7 * relative_velocity(joint('RightHand', 'RightWrist'), upper_anchor, upper_pos)
                      + .3 * relative_velocity(joint('RightForeArm', 'RightElbow'), upper_anchor, upper_pos)),
        'Left Leg': .75 * relative_velocity(joint('LeftFoot', 'LeftAnkle'), hips) + .25 * relative_velocity(joint('LeftLeg', 'LeftKnee'), hips),
        'Right Leg': .75 * relative_velocity(joint('RightFoot', 'RightAnkle'), hips) + .25 * relative_velocity(joint('RightLeg', 'RightKnee'), hips),
        'Head': (.4 * relative_velocity(joint('Head', 'Head1'), upper_anchor, upper_pos)
                 + .6 * _local_rotation_speed(motion, joint('Head', 'Head1'), frame_indices, times)),
        'Torso': .5 * relative_velocity(spine, hips) + .5 * _local_rotation_speed(motion, joint('Spine3', 'Spine2', 'Spine'), frame_indices, times),
        'Root': np.linalg.norm(_safe_gradient(sm[:, hips] / scale, times), axis=1),
    }
    if cfg.mode == 'graph':
        graph = _graph_temporal_energy(motion, sm, times, scale, body)
        for key in feats:
            if key == 'Root':
                continue
            g = np.asarray(graph[key])
            gp, vp = np.percentile(g, 95), np.percentile(feats[key], 95)
            if gp > 1e-8:
                feats[key] = (1 - cfg.graph_weight) * feats[key] + cfg.graph_weight * g * (vp / gp)
            wave = np.maximum.reduce([
                np.abs(gaussian_filter1d(feats[key], max(.8, s / dt), order=1)) / max(.8, s / dt)
                for s in (.10, .25, .60)
            ])
            w95 = np.percentile(wave, 95)
            if w95 > 1e-8:
                feats[key] = .86 * feats[key] + .14 * wave * (np.percentile(feats[key], 95) / w95)

    # Finger motion is relative to its own wrist. It is a candidate channel,
    # not a recognizer of interlaced fingers or other semantic hand postures.
    for side in ('Left', 'Right'):
        wrist = joint(side + 'Hand', side + 'Wrist')
        fingers = [i for i, name in enumerate(motion.names)
                   if name.lower().startswith(side.lower()) and
                   any(token in name.lower() for token in ('thumb', 'index', 'middle', 'ring', 'pinky', 'little'))]
        finger_energy = np.mean([relative_velocity(i, wrist) for i in fingers], axis=0) if fingers else np.zeros(len(times))
        feats[side + ' Hand'] = .6 * finger_energy + .4 * _local_rotation_speed(motion, wrist, frame_indices, times)
    feats['Hands'] = np.maximum(feats['Left Hand'], feats['Right Hand'])
    feats['Full Body'] = np.mean([feats[key] for key in DEFAULT_CHANNELS], axis=0)
    wanted = cfg.channels if cfg.channels is not None else DEFAULT_CHANNELS
    return {key: _smooth(feats[key], .11 / dt) for key in dict.fromkeys(wanted)}, sm, body, scale


def _binary_intervals(times, score, cfg):
    if len(times) < 3:
        return []
    lo, hi = np.percentile(score, [15, 90])
    if hi - lo < 1e-5:
        return []
    high = lo + cfg.high_fraction * (hi - lo)
    low = lo + cfg.low_fraction * (hi - lo)
    on, start, ranges = False, 0, []
    for i, value in enumerate(score):
        if not on and value >= high:
            on, start = True, i
        elif on and value < low:
            # Merge before applying min duration, so two short fragments
            # separated by a tiny dip can form one meaningful interval.
            ranges.append([start, max(start, i - 1)])
            on = False
    if on:
        ranges.append([start, len(times) - 1])
    merged = []
    for first, last in ranges:
        if merged and times[first] - times[merged[-1][1]] <= cfg.merge_gap_s:
            merged[-1][1] = last
        else:
            merged.append([first, last])
    return [(float(times[a]), float(times[b]), float(np.max(score[a:b + 1])), a, b)
            for a, b in merged if times[b] - times[a] >= cfg.min_duration_s]


def _label(motion, channel, pos, scale, i0, i1, up_axis='Z', *, torso=None):
    if channel in ('Left Arm', 'Right Arm'):
        side = channel.split()[0]
        if torso is None:
            moving = motion.joint(side + 'Hand')
            anchor = motion.joint('Spine3', 'Spine2', 'Spine1', 'Spine', 'Chest')
            vertical_axis = 'XYZ'.index(up_axis.upper())
        else:
            moving = motion.joint(side + 'ForeArm', side + 'Elbow')
            anchor = torso.joint
            vertical_axis = 2
        if moving is not None and anchor is not None:
            delta = (pos[i1, moving] - pos[i1, anchor]) - (pos[i0, moving] - pos[i0, anchor])
            vertical = delta[vertical_axis] / scale
            if vertical >= .12:
                return 'raise left arm' if channel.startswith('Left') else 'raise right arm'
            if vertical <= -.12:
                return 'lower left arm' if channel.startswith('Left') else 'lower right arm'
        return 'local arm movement (meaning uncertain)'
    return {
        'Head': 'head / neck movement', 'Torso': 'torso movement',
        'Left Leg': 'left leg movement', 'Right Leg': 'right leg movement',
        'Left Hand': 'left hand / finger movement', 'Right Hand': 'right hand / finger movement',
        'Hands': 'hand / finger movement', 'Full Body': 'whole-body movement',
        'Root': 'pelvis translation / locomotion candidate',
    }.get(channel, 'motion candidate')


def _provenance(annotation, parameters=None, related_ids=None):
    """Populate v2 fields when available, without breaking legacy consumers."""
    if hasattr(annotation, 'original'):
        annotation.original = {key: getattr(annotation, key) for key in
                               ('start_s', 'end_s', 'role', 'channel', 'label', 'source', 'confidence')}
    if hasattr(annotation, 'attributes'):
        annotation.attributes.update({'score_type': 'relative_salience', 'semantic_validation': 'unverified'})
        if parameters is not None:
            annotation.attributes['segmentation_config'] = parameters
            annotation.attributes['time_basis'] = 'source-local seconds; caller applies asset offset'
        if related_ids:
            annotation.attributes['related_annotation_ids'] = related_ids
    return annotation


def _subtract_specific_spans(first, last, spans):
    for span in spans:
        if span.last <= first:
            continue
        if span.first >= last:
            break
        if span.first > first:
            yield first, span.first
        first = max(first, span.last)
        if first >= last:
            return
    yield first, last


def segment_motion(motion, role: str, cfg: SegmentationConfig | None = None):
    cfg = (cfg or SegmentationConfig()).validate()
    if motion.nframes < 3:
        raise ValueError('Motion segmentation needs at least three source frames; this asset can still be previewed')
    start = float(cfg.start_s)
    end = min(float(motion.duration_s), float(cfg.end_s) if cfg.end_s is not None else float(motion.duration_s))
    if start >= end:
        raise ValueError('Selected time range does not intersect the motion recording')
    all_ids = motion.sample_indices(cfg.sample_hz)
    first = max(0, int(np.ceil(start / motion.frame_time - 1e-9)))
    last = min(motion.nframes - 1, int(np.floor(end / motion.frame_time + 1e-9)))
    ids = np.unique(np.r_[first, all_ids[(all_ids >= first) & (all_ids <= last)], last]).astype(np.int64)
    ids = ids[(ids >= first) & (ids <= last)]
    times = ids.astype(np.float64) * motion.frame_time
    if len(times) < 3:
        raise ValueError('Selected range contains fewer than three analysis samples; choose a longer range or higher sample rate')
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError('Motion sample times must be finite and strictly increasing')
    pos = motion.positions(ids)
    if not np.isfinite(pos).all():
        raise ValueError('Motion positions contain NaN or infinity; repair the source or select a valid clip')
    requested_channels = cfg.channels or DEFAULT_CHANNELS
    use_fine = cfg.fine_primitives and hasattr(motion, 'local_rotations')
    torso = None
    if use_fine and any(channel in _TORSO_RELATIVE_CHANNELS for channel in requested_channels):
        torso = anatomical_torso_frame(motion)
    local_pos = torso_local_positions(motion, torso, pos, ids) if torso is not None else None
    features, sm, body, scale = _movement_features(motion, pos, times, cfg, ids, torso, local_pos)
    annotations = []
    parameters = asdict(cfg)
    for channel, score in features.items():
        if not np.isfinite(score).all():
            raise ValueError(f'Non-finite features in {channel}')
        specific = []
        if use_fine:
            if channel == 'Head':
                specific = head_spans(motion, torso, ids, times, cfg)
            elif channel in _HINGE_CHANNELS:
                specific = hinge_spans(motion, channel, pos, times, cfg)
        for span in specific:
            candidate = Annotation(id=str(uuid.uuid4()), start_s=max(start, float(times[span.first])),
                                   end_s=min(end, float(times[span.last])), role=role, channel=channel,
                                   layer='L1 · Kinematics', label=span.label, source=f'auto:{cfg.mode}')
            _provenance(candidate, parameters=parameters)
            candidate.attributes.pop('score_type', None)
            candidate.attributes['primitive_evidence'] = {
                **span.evidence, 'first_frame': int(ids[span.first]), 'last_frame': int(ids[span.last]),
            }
            annotations.append(candidate)
        p95 = max(float(np.percentile(score, 95)), 1e-8)
        for _, _, _, i0, i1 in _binary_intervals(times, score, cfg):
            coordinates = sm if body is None else body
            broad_label = _label(motion, channel, coordinates, scale, i0, i1, cfg.up_axis, torso=torso)
            # A torso-relative upper-arm lift can coexist with a measured elbow
            # flexion. Generic regional activity has no such independent evidence.
            independent = torso is not None and broad_label.startswith(('raise ', 'lower '))
            remains = [(i0, i1)] if independent else _subtract_specific_spans(i0, i1, specific)
            for first, last in remains:
                if times[last] - times[first] < cfg.min_duration_s:
                    continue
                label = broad_label if (first, last) == (i0, i1) else _label(
                    motion, channel, coordinates, scale, first, last, cfg.up_axis, torso=torso,
                )
                strength = min(1., float(np.max(score[first:last + 1])) / p95)
                candidate = Annotation(id=str(uuid.uuid4()), start_s=max(start, float(times[first])),
                                       end_s=min(end, float(times[last])), role=role, channel=channel,
                                       layer='L1 · Kinematics', label=label, source=f'auto:{cfg.mode}',
                                       confidence=round(strength, 3))
                annotations.append(_provenance(candidate, parameters=parameters))
    return sorted(annotations, key=lambda x: (x.start_s, x.role, x.channel)), features, times


def detect_phase_structures(annotations: list[Annotation], max_gap_s: float = 2.4):
    if not np.isfinite(max_gap_s) or max_gap_s < 0:
        raise ValueError('Maximum phase gap must be finite and nonnegative')
    output = []
    for role in sorted({a.role for a in annotations}):
        for channel in ('Left Arm', 'Right Arm'):
            group = sorted([a for a in annotations if a.role == role and a.channel == channel and
                            a.layer.startswith('L1') and a.status != 'rejected'], key=lambda a: a.start_s)
            for a, b in zip(group, group[1:]):
                gap = b.start_s - a.end_s
                if gap < 0 or gap > max_gap_s:
                    continue
                if a.label.startswith('raise') and b.label.startswith('lower'):
                    label = 'raise → hold → lower (candidate)' if gap >= .25 else 'raise → lower (candidate)'
                    candidate = Annotation(str(uuid.uuid4()), a.start_s, b.end_s, role, channel,
                                           'L2 · Action / Gesture', label, source='auto:phase-structure',
                                           notes='Kinematic phase sequence. Low motion between phases does not establish a semantic hold or gesture.')
                    output.append(_provenance(candidate, related_ids=[a.id, b.id]))
        left = [a for a in annotations if a.role == role and a.channel == 'Left Arm' and a.layer.startswith('L1') and a.status != 'rejected']
        right = [a for a in annotations if a.role == role and a.channel == 'Right Arm' and a.layer.startswith('L1') and a.status != 'rejected']
        for a in left:
            for b in right:
                t0, t1 = max(a.start_s, b.start_s), min(a.end_s, b.end_s)
                if t1 - t0 >= .65:
                    candidate = Annotation(str(uuid.uuid4()), t0, t1, role, 'Full Body',
                                           'L2 · Action / Gesture', 'bilateral arm co-activity (not classified)',
                                           source='auto:phase-structure', notes='Overlapping arm activity; gesture meaning needs review.')
                    output.append(_provenance(candidate, related_ids=[a.id, b.id]))
    return sorted(output, key=lambda a: a.start_s)


def detect_dyadic_coactivity(annotations: list[Annotation]):
    left = [x for x in annotations if x.role == 'R01' and x.channel in ('Left Arm', 'Right Arm') and x.layer.startswith('L1') and x.status != 'rejected']
    right = [x for x in annotations if x.role == 'R02' and x.channel in ('Left Arm', 'Right Arm') and x.layer.startswith('L1') and x.status != 'rejected']
    spans = []
    for a in left:
        for b in right:
            s, e = max(a.start_s, b.start_s), min(a.end_s, b.end_s)
            if e - s >= .4:
                spans.append((s, e))
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s - merged[-1][1] <= .2:
            merged[-1][1] = max(e, merged[-1][1])
        else:
            merged.append([s, e])
    return [_provenance(Annotation(str(uuid.uuid4()), s, e, 'Both', 'Dyadic',
                                  'L3 · Interaction', 'co-active arms (relationship unverified)',
                                  category='Activity Relation', source='auto:dyadic-overlap',
                                  notes='Temporal overlap only. Response, imitation and causality are not inferred.'))
            for s, e in merged]
