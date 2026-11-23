"""Direction and excursion rules for head, elbow and knee motion proposals."""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial.transform import Rotation


TORSO_JOINTS = ('Spine3', 'UpperChest', 'Chest', 'Spine2', 'Spine1', 'Spine', 'Torso')
HEAD_SPEED_DEG_S = 18.
JOINT_SPEED_DEG_S = 24.
HEAD_AXIS_SHARE = .65
HEAD_REVERSAL_GAP_S = .25
HEAD_CYCLE_MAX_S = 1.6
HEAD_REVERSAL_BALANCE = .45


@dataclass(frozen=True)
class TorsoFrame:
    joint: int
    axes: np.ndarray
    head_chain: tuple[int, ...]


@dataclass(frozen=True)
class PrimitiveSpan:
    first: int
    last: int
    label: str
    evidence: dict


def _descendant_chain(motion, ancestor, joint):
    """Joints after an ancestor, in parent-to-child order; None if unrelated."""
    chain = []
    while joint != ancestor and joint >= 0:
        chain.append(joint)
        joint = motion.parents[joint]
    return tuple(reversed(chain)) if joint == ancestor else None


def anatomical_torso_frame(motion):
    """Use rest-pose arm anchors for lateral and the head chain for superior."""
    if not hasattr(motion, 'local_rotations'):
        return None
    left = motion.joint('LeftArm', 'LeftUpperArm', 'LeftShoulder')
    right = motion.joint('RightArm', 'RightUpperArm', 'RightShoulder')
    head = motion.joint('Head', 'Head1')
    if None in (left, right, head):
        return None
    for name in TORSO_JOINTS:
        torso = motion.joint(name)
        if torso is None:
            continue
        chains = [_descendant_chain(motion, torso, joint) for joint in (left, right, head)]
        if not all(chains):
            continue
        left_rest, right_rest, head_rest = [
            np.sum([motion.joints[joint].offset for joint in chain], axis=0) for chain in chains
        ]
        lateral = right_rest - left_rest
        lateral_length, head_distance = np.linalg.norm(lateral), np.linalg.norm(head_rest)
        if min(lateral_length, head_distance) < 1e-6:
            continue
        lateral /= lateral_length
        superior = head_rest - np.dot(head_rest, lateral) * lateral
        superior_length = np.linalg.norm(superior)
        if superior_length < .5 * head_distance:
            continue
        superior /= superior_length
        forward = np.cross(superior, lateral)
        return TorsoFrame(torso, np.stack((lateral, forward, superior)), chains[2])
    return None


def _chain_rotation(motion, chain, frame_ids):
    rotation = Rotation.identity(len(frame_ids))
    for joint in chain:
        local = motion.local_rotations(joint, frame_ids)
        if local is not None:
            rotation = rotation * local
    return rotation


def torso_local_positions(motion, torso, positions, frame_ids):
    chain = _descendant_chain(motion, -1, torso.joint)
    rotation = _chain_rotation(motion, chain, frame_ids).as_matrix()
    centered = positions - positions[:, torso.joint:torso.joint + 1]
    local = np.einsum('tji,tkj->tki', rotation, centered, optimize=True)
    return (local @ torso.axes.T).astype(np.float32)


def _smooth_angles(angles, times, smoothing_s):
    if not smoothing_s:
        return angles
    sample_interval = np.median(np.diff(times))
    return gaussian_filter1d(angles, smoothing_s / sample_interval, mode='nearest', axis=0)


def _directional_runs(angle, times, *, min_duration, min_excursion, onset_speed):
    """Split at rest or reversal using signed interval velocities and hysteresis."""
    speeds = np.diff(angle) / np.diff(times)
    direction = np.sign(speeds)
    direction[np.abs(speeds) < .5 * onset_speed] = 0
    breaks = np.r_[0, np.flatnonzero(np.diff(direction)) + 1, len(speeds)]
    for first, last in zip(breaks, breaks[1:]):
        if not direction[first] or last - first < 2 or times[last] - times[first] < min_duration:
            continue
        excursion = float(angle[last] - angle[first])
        if abs(excursion) >= min_excursion and np.max(np.abs(speeds[first:last])) >= onset_speed:
            yield int(first), int(last), excursion


def _reverse_in_time(first, second, times):
    smaller, larger = sorted((abs(first[2]), abs(second[2])))
    return (first[2] * second[2] < 0
            and times[second[0]] - times[first[1]] <= HEAD_REVERSAL_GAP_S
            and times[second[1]] - times[first[0]] <= HEAD_CYCLE_MAX_S
            and smaller >= HEAD_REVERSAL_BALANCE * larger)


def head_spans(motion, torso, frame_ids, times, cfg):
    if torso is None:
        return []
    rotation = _chain_rotation(motion, torso.head_chain, frame_ids)
    # Spatial increments are expressed in the torso frame before projection.
    # This follows the shortest frame-to-frame change across Euler wraparound.
    increments = (rotation[1:] * rotation[:-1].inv()).as_rotvec()
    accumulated = np.vstack((np.zeros(3), np.cumsum(np.rad2deg(increments @ torso.axes.T), axis=0)))
    angles = _smooth_angles(accumulated, times, cfg.smoothing_s)
    total_travel = np.r_[0., np.cumsum(np.sum(np.abs(np.diff(angles, axis=0)), axis=1))]
    spans = []
    for axis, name, label in ((0, 'pitch', 'head nod'), (2, 'yaw', 'head shake')):
        directional = list(_directional_runs(
            angles[:, axis], times, min_duration=cfg.primitive_min_duration_s,
            min_excursion=cfg.head_min_excursion_deg, onset_speed=HEAD_SPEED_DEG_S,
        ))
        i = 0
        while i < len(directional):
            j = i
            while j + 1 < len(directional) and _reverse_in_time(directional[j], directional[j + 1], times):
                j += 1
            group = directional[i:j + 1]
            i = j + 1
            first, last = group[0][0], group[-1][1]
            travel = sum(abs(run[2]) for run in group)
            axis_share = travel / (total_travel[last] - total_travel[first])
            if axis_share < HEAD_AXIS_SHARE:
                continue
            if len(group) == 1 and name == 'pitch':
                continue
            spans.append(PrimitiveSpan(first, last, label if len(group) > 1 else 'head rotation', {
                'rule': 'torso_relative_head_rotation', 'axis': name,
                'axis_share': round(axis_share, 3), 'minimum_axis_share': HEAD_AXIS_SHARE,
                'torso_joint': motion.names[torso.joint],
                'joints': [motion.names[joint] for joint in torso.head_chain],
                'excursions_deg': [round(run[2], 2) for run in group],
                'onset_speed_deg_s': HEAD_SPEED_DEG_S,
                'maximum_reversal_gap_s': HEAD_REVERSAL_GAP_S,
                'maximum_cycle_s': HEAD_CYCLE_MAX_S,
                'minimum_reversal_balance': HEAD_REVERSAL_BALANCE,
            }))
    return sorted(spans, key=lambda span: span.first)


def hinge_spans(motion, channel, positions, times, cfg):
    side, part = channel.split()
    if part == 'Arm':
        names = (('Arm', 'UpperArm'), ('ForeArm', 'Elbow'), ('Hand', 'Wrist'))
        bend, straighten = f'flex {side.lower()} elbow', f'extend {side.lower()} elbow'
    else:
        names = (('UpLeg', 'Thigh', 'Hip'), ('Leg', 'Knee', 'Shin'), ('Foot', 'Ankle'))
        bend, straighten = f'bend {side.lower()} knee', f'straighten {side.lower()} knee'
    joints = [motion.joint(*(side + alias for alias in aliases)) for aliases in names]
    if None in joints or not all(_descendant_chain(motion, a, b) for a, b in zip(joints, joints[1:])):
        return []
    first_bone, second_bone = np.diff(positions[:, joints].astype(np.float64), axis=1).transpose(1, 0, 2)
    if any(np.any(np.linalg.norm(bone, axis=1) < 1e-6) for bone in (first_bone, second_bone)):
        return []
    cross = np.linalg.norm(np.cross(first_bone, second_bone), axis=1)
    dot = np.einsum('ij,ij->i', first_bone, second_bone)
    flexion = _smooth_angles(np.rad2deg(np.arctan2(cross, dot)), times, cfg.smoothing_s)
    return [PrimitiveSpan(first, last, bend if excursion > 0 else straighten, {
        'rule': 'adjacent_bone_angle', 'joints': [motion.names[joint] for joint in joints],
        'excursion_deg': round(excursion, 2), 'onset_speed_deg_s': JOINT_SPEED_DEG_S,
    }) for first, last, excursion in _directional_runs(
        flexion, times, min_duration=cfg.primitive_min_duration_s,
        min_excursion=cfg.joint_min_excursion_deg, onset_speed=JOINT_SPEED_DEG_S,
    )]
