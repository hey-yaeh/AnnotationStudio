"""BVH / numeric pose reader and vectorized forward kinematics.

BVH local Euler channel order is honored per joint. The reader never assumes a
physical length unit, nor that separately exported actors share a world frame.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import re
import math
import numpy as np
from scipy.spatial.transform import Rotation


@dataclass
class Joint:
    name: str
    parent: int
    offset: tuple[float, float, float]
    channels: tuple[str, ...]
    channel_start: int


class BVHMotion:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        lines = self.path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        self.joints: list[Joint] = []
        i = 0
        while i < len(lines) and lines[i].strip() != 'HIERARCHY':
            i += 1
        if i == len(lines):
            raise ValueError('BVH has no HIERARCHY section')
        i += 1
        channel_count = 0

        def parse_joint(parent: int, idx: int) -> int:
            nonlocal channel_count
            header = lines[idx].strip()
            m = re.match(r'^(ROOT|JOINT)\s+(.+)$', header)
            if not m:
                raise ValueError(f'Expected ROOT/JOINT at line {idx+1}: {header!r}')
            name = m.group(2).strip()
            if idx + 1 >= len(lines) or lines[idx + 1].strip() != '{':
                raise ValueError(f'Missing opening brace for {name}')
            joint_idx = len(self.joints)
            self.joints.append(Joint(name, parent, (0., 0., 0.), (), channel_count))
            idx += 2
            offset = (0., 0., 0.)
            channels: tuple[str, ...] = ()
            saw_channels = False
            while idx < len(lines):
                l = lines[idx].strip()
                if l.startswith('OFFSET '):
                    vals = l.split()[1:]
                    if len(vals) != 3:
                        raise ValueError(f'Invalid OFFSET at {idx + 1}')
                    offset = tuple(float(x) for x in vals)
                    if not all(math.isfinite(x) for x in offset):
                        raise ValueError(f'Non-finite OFFSET for {name}')
                    idx += 1
                elif l.startswith('CHANNELS '):
                    values = l.split()
                    if saw_channels or len(values) < 2:
                        raise ValueError(f'Invalid or repeated CHANNELS for {name}')
                    saw_channels = True
                    nc = int(values[1]); channels = tuple(values[2:])
                    allowed = {axis + kind for axis in 'xyz' for kind in ('position', 'rotation')}
                    if any(c.lower() not in allowed for c in channels) or len(set(c.lower() for c in channels)) != len(channels):
                        raise ValueError(f'Unsupported or duplicate motion channel for {name}')
                    if nc < 0 or len(channels) != nc:
                        raise ValueError(f'Invalid channel count for {name}')
                    self.joints[joint_idx].channel_start = channel_count
                    channel_count += nc
                    idx += 1
                elif l.startswith('JOINT '):
                    idx = parse_joint(joint_idx, idx)
                elif l.startswith('End Site'):
                    # End Site has OFFSET only, no animation channels.
                    if idx + 1 >= len(lines) or lines[idx + 1].strip() != '{':
                        raise ValueError('Invalid End Site')
                    depth = 1; idx += 2
                    while depth and idx < len(lines):
                        depth += (lines[idx].count('{') - lines[idx].count('}'))
                        idx += 1
                    if depth:
                        raise ValueError(f'Unclosed End Site for {name}')
                elif l == '}':
                    self.joints[joint_idx].offset = offset
                    self.joints[joint_idx].channels = channels
                    return idx + 1
                elif not l:
                    idx += 1
                else:
                    raise ValueError(f'Unrecognized BVH header line {idx+1}: {l[:100]}')
            raise ValueError(f'Unclosed joint: {name}')

        while i < len(lines) and not lines[i].strip().startswith('ROOT '):
            i += 1
        if i >= len(lines):
            raise ValueError('No ROOT joint')
        i = parse_joint(-1, i)
        while i < len(lines) and lines[i].strip() != 'MOTION':
            i += 1
        if i >= len(lines):
            raise ValueError('BVH has no MOTION section')
        if i + 2 >= len(lines):
            raise ValueError('BVH motion header is incomplete')
        frame_match = re.fullmatch(r'\s*Frames\s*:\s*(\d+)\s*', lines[i + 1])
        time_match = re.fullmatch(r'\s*Frame\s+Time\s*:\s*([0-9.eE+-]+)\s*', lines[i + 2])
        if not frame_match or not time_match:
            raise ValueError('BVH needs valid Frames and Frame Time header lines')
        nframes = int(frame_match.group(1))
        self.frame_time = float(time_match.group(1))
        if not math.isfinite(self.frame_time) or self.frame_time <= 0 or nframes < 1:
            raise ValueError('Invalid frames or frame time')
        vals = np.fromstring(' '.join(lines[i + 3:]), sep=' ', dtype=np.float32)
        expected = nframes * channel_count
        if vals.size != expected:
            raise ValueError(f'MOTION has {vals.size} numbers; expected {expected} ({nframes} x {channel_count})')
        if not np.isfinite(vals).all():
            raise ValueError('BVH motion data contain NaN or infinity')
        self.frames = vals.reshape(nframes, channel_count)
        self.nframes = nframes
        self.duration_s = (nframes - 1) * self.frame_time
        self.names = [j.name for j in self.joints]
        self.parents = [j.parent for j in self.joints]
        if len(set(n.lower() for n in self.names)) != len(self.names):
            raise ValueError('BVH joint names must be unique (ignoring case)')
        self.name_to_index = {n.lower(): i for i, n in enumerate(self.names)}
        self._offsets = np.asarray([j.offset for j in self.joints], dtype=np.float32)
        self._plan = []
        for joint in self.joints:
            pos = [(k, joint.channel_start + n) for n, k in enumerate(joint.channels) if k.lower().endswith('position')]
            rot = [(k[0].upper(), joint.channel_start + n) for n, k in enumerate(joint.channels) if k.lower().endswith('rotation')]
            self._plan.append((pos, rot))

    def joint(self, *names: str) -> int | None:
        for name in names:
            value = self.name_to_index.get(name.lower())
            if value is not None:
                return value
        return None

    def sample_indices(self, max_hz: float = 30.) -> np.ndarray:
        if not math.isfinite(float(max_hz)) or max_hz <= 0:
            raise ValueError('Sample rate must be finite and positive')
        step = max(1, int(round(1.0 / (self.frame_time * max_hz))))
        idx = np.arange(0, self.nframes, step, dtype=np.int32)
        if idx[-1] != self.nframes - 1:
            idx = np.r_[idx, self.nframes - 1]
        return idx

    def pose_at(self, time_s: float) -> np.ndarray:
        if not math.isfinite(float(time_s)):
            raise ValueError('Preview time must be finite')
        index = max(0, min(self.nframes - 1, int(round(time_s / self.frame_time))))
        return self.positions(np.asarray([index], dtype=np.int32))[0]

    @staticmethod
    def _channel_rotations(angles, channels):
        order = ''.join(axis for axis, _ in channels)
        return Rotation.from_euler(order, angles, degrees=True)

    def local_rotations(self, joint_index: int, frame_ids: np.ndarray) -> Rotation | None:
        """Rotation in the parent frame, using this joint's declared channel order."""
        channels = self._plan[joint_index][1]
        if not channels:
            return None
        columns = [column for _, column in channels]
        return self._channel_rotations(self.frames[np.ix_(frame_ids, columns)], channels)

    def positions(self, frame_ids: Sequence[int] | np.ndarray) -> np.ndarray:
        """Returns [T,J,3] FK positions in native BVH length units."""
        raw_ids = np.asarray(frame_ids).reshape(-1)
        if not np.isfinite(raw_ids).all() or np.any(raw_ids != np.floor(raw_ids)):
            raise ValueError('Frame indices must be finite integers')
        ids = raw_ids.astype(np.int64)
        if np.any(ids < 0) or np.any(ids >= self.nframes):
            raise ValueError('Requested frame index outside recording')
        n = len(ids)
        if n == 0:
            return np.empty((0, len(self.joints), 3), dtype=np.float32)
        data = self.frames[ids]
        positions: list[np.ndarray] = []
        orientations: list[np.ndarray] = []
        eye = np.broadcast_to(np.eye(3, dtype=np.float32), (n, 3, 3))
        for j, joint in enumerate(self.joints):
            trans = np.broadcast_to(self._offsets[j], (n,3)).copy()
            pchannels, rchannels = self._plan[j]
            for axis, index in pchannels:
                trans[:, 'XYZ'.index(axis[0].upper())] += data[:, index]
            if rchannels:
                angles = data[:, [column for _, column in rchannels]]
                R = self._channel_rotations(angles, rchannels).as_matrix().astype(np.float32)
            else:
                R = eye
            if joint.parent == -1:
                positions.append(trans)
                orientations.append(R)
            else:
                parent_R = orientations[joint.parent]
                positions.append(positions[joint.parent] + np.einsum('nij,nj->ni', parent_R, trans))
                orientations.append(parent_R @ R)
        return np.stack(positions, axis=1)

    def scale_hint(self) -> float:
        """Robust relative scale, not a conversion to meters."""
        hips = self.joint('Hips', 'Pelvis', 'Root')
        head = self.joint('Head', 'Head1')
        if hips is None or head is None:
            return max(1., float(np.linalg.norm(self._offsets, axis=1).sum() * .2))
        p = self.pose_at(0.)
        return max(1., float(np.linalg.norm(p[head] - p[hips])))


def _validate_parents(values, joint_count):
    raw = np.asarray(values)
    if raw.ndim != 1 or len(raw) != joint_count:
        raise ValueError('NPZ parents must have one entry per joint')
    if not np.issubdtype(raw.dtype, np.number) or not np.isfinite(raw).all() or np.any(raw != np.floor(raw)):
        raise ValueError('NPZ parents must be finite integer indices')
    parents = [int(value) for value in raw]
    if any(p < -1 or p >= joint_count for p in parents):
        raise ValueError('NPZ parent index is outside the skeleton')
    # Parent order need not be topological, but cycles and self-parenting are
    # invalid. A forest (more than one -1 root) is permitted.
    resolved = set()
    for start in range(joint_count):
        path = set()
        node = start
        while node != -1 and node not in resolved:
            if node in path:
                raise ValueError('NPZ skeleton parent graph contains a cycle')
            path.add(node)
            node = parents[node]
        resolved.update(path)
    return parents


class NPZPoseMotion:
    """Joint positions only; no SMPL mesh, units or skeleton topology inferred."""
    KEYS = ('joint_positions', 'joints', 'positions', 'joint_xyz', 'xyz', 'gpos')

    def __init__(self, path: str | Path, assumed_hz: float = 120.):
        self.path = Path(path)
        with np.load(self.path, allow_pickle=False) as f:
            key = next((k for k in self.KEYS if k in f and f[k].ndim == 3 and f[k].shape[-1] == 3), None)
            if key is None:
                raise ValueError('NPZ needs NxJx3 joint positions. Raw SMPL-H pose parameters require an explicit body model.')
            self._positions = np.asarray(f[key], dtype=np.float32)
            if not self._positions.shape[0] or not self._positions.shape[1]:
                raise ValueError('NPZ motion must contain at least one frame and one joint')
            if not np.isfinite(self._positions).all():
                raise ValueError('NPZ joint positions contain NaN or infinity')
            self.assumed_frame_rate = 'fps' not in f
            hz = float(np.asarray(f['fps']).item()) if 'fps' in f else float(assumed_hz)
            if not math.isfinite(hz) or hz <= 0:
                raise ValueError('NPZ fps must be finite and positive')
            self.frame_time = 1.0 / hz
            count = self._positions.shape[1]
            if 'joint_names' in f:
                raw_names = np.asarray(f['joint_names'])
                if raw_names.ndim != 1 or len(raw_names) != count:
                    raise ValueError('NPZ joint_names must have one name per joint')
                self.names = [s.decode('utf-8') if isinstance(s, bytes) else str(s) for s in raw_names]
            else:
                self.names = [f'J{i:02d}' for i in range(count)]
            if len({name.lower() for name in self.names}) != count or any(not name.strip() for name in self.names):
                raise ValueError('NPZ joint names must be nonempty and unique (ignoring case)')
            self.has_topology = 'parents' in f
            self.parents = _validate_parents(f['parents'], count) if self.has_topology else [-1] * count
        self.nframes = self._positions.shape[0]
        self.duration_s = (self.nframes - 1) * self.frame_time
        self.name_to_index = {n.lower(): i for i, n in enumerate(self.names)}

    def joint(self, *names):
        for name in names:
            if name.lower() in self.name_to_index:
                return self.name_to_index[name.lower()]
        return None

    def sample_indices(self, max_hz=30.):
        if not math.isfinite(float(max_hz)) or max_hz <= 0:
            raise ValueError('Sample rate must be finite and positive')
        step = max(1, int(round(1. / (self.frame_time * max_hz))))
        ids = np.arange(0, self.nframes, step, dtype=np.int32)
        return ids if ids[-1] == self.nframes - 1 else np.r_[ids, self.nframes - 1]

    def positions(self, frame_ids):
        raw = np.asarray(frame_ids).reshape(-1)
        if not np.isfinite(raw).all() or np.any(raw != np.floor(raw)):
            raise ValueError('Frame indices must be finite integers')
        ids = raw.astype(np.int64)
        if np.any(ids < 0) or np.any(ids >= self.nframes):
            raise ValueError('Requested frame index outside recording')
        return self._positions[ids]

    def pose_at(self, time_s):
        if not math.isfinite(float(time_s)):
            raise ValueError('Preview time must be finite')
        i = max(0, min(self.nframes - 1, int(round(time_s / self.frame_time))))
        return self._positions[i]

    def scale_hint(self):
        p = self.pose_at(0.)
        return max(.01, float(np.percentile(np.linalg.norm(p - p[0], axis=1), 85)))


def open_motion(path: str | Path):
    suffix = Path(path).suffix.lower()
    if suffix == '.bvh':
        return BVHMotion(path)
    if suffix == '.npz':
        return NPZPoseMotion(path)
    raise ValueError('Motion file must be BVH or a joint-position NPZ')
