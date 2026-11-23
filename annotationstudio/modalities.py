"""Adapter layer for gaze rays, prop centroids, AOI intervals and audio envelope.

Only well-defined coordinate schemas are interpreted. Never silently transform
between eye tracker, C3D and BVH coordinate frames.
"""
from __future__ import annotations
import csv
import math
from dataclasses import dataclass
from pathlib import Path
import wave
import numpy as np

@dataclass
class GazeTrack:
    times: np.ndarray
    origins: np.ndarray
    endpoints: np.ndarray
    role: str
    file: str
    def ray_at(self, time_s:float, tolerance=.18):
        if len(self.times)==0 or not np.isfinite(time_s):return None
        if time_s < self.times[0] or time_s > self.times[-1]:return None
        i=int(np.searchsorted(self.times,time_s))
        candidates=[max(0,min(len(self.times)-1,i)),max(0,min(len(self.times)-1,i-1))]
        i=min(candidates,key=lambda n:abs(self.times[n]-time_s))
        return (self.origins[i],self.endpoints[i]) if abs(self.times[i]-time_s)<=tolerance else None


def _column(mapping, *variants):
    for v in variants:
        if v.lower() in mapping: return mapping[v.lower()]
    return None


def read_gaze_csv(path, role='R01', offset_s=0.0):
    """Use sample time_s, origin XYZ, and either target XYZ or direction XYZ."""
    if not math.isfinite(float(offset_s)):
        raise ValueError('Gaze offset must be finite')
    records=[]
    with open(path,encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f)
        if rd.fieldnames is None:raise ValueError('Empty gaze CSV')
        cols={str(k).lower().strip():k for k in rd.fieldnames}
        tkey=_column(cols,'time_s','time','timestamp_s','relative_time_s','aligned_time_s','c3d_time_s')
        if not tkey: raise ValueError('Gaze CSV: require time_s or another supported time column')
        def getxyz(stems):
            for stem in stems:
                c=[_column(cols,f'{stem}_{a}',f'{stem}{a}',f'{stem}.{a}') for a in 'xyz']
                if all(c):return c
            return None
        o=getxyz(('origin','gaze_origin','ray_origin','eye_origin','start'))
        e=getxyz(('target','gaze_target','hit','ray_end','endpoint','end'))
        d=getxyz(('direction','gaze_direction','ray_direction','dir','gaze_dir'))
        if not o or (not e and not d):
            raise ValueError('Gaze CSV schema unsupported. Expected origin_x/y/z plus target_x/y/z or dir_x/y/z. No coordinate conversion is guessed.')
        for row in rd:
            try:
                t=float(row[tkey])+offset_s
                orig=np.asarray([float(row[c]) for c in o],dtype=np.float32)
                target=np.asarray([float(row[c]) for c in e],dtype=np.float32) if e else None
                direction=np.asarray([float(row[c]) for c in d],dtype=np.float32) if d else None
                if not np.isfinite(t) or not np.isfinite(orig).all():continue
                if target is None:
                    norm=float(np.linalg.norm(direction))
                    if norm<1e-8:continue
                    target=orig+direction/norm*100 # visual ray length in supplied native units
                if np.isfinite(target).all():records.append((t,orig,target))
            except (ValueError,TypeError,KeyError): continue
    if not records: raise ValueError('No valid gaze samples')
    records = sorted({record[0]: record for record in records}.values(), key=lambda v: v[0])
    return GazeTrack(np.asarray([x[0] for x in records]),np.stack([x[1] for x in records]),
                     np.stack([x[2] for x in records]),role,str(path))


@dataclass
class PropTrack:
    times: np.ndarray
    positions: np.ndarray  # [T,P,3]; missing individual props are NaN.
    names: list[str]

    def at(self, t, tolerance=.25):
        if len(self.times) == 0 or not np.isfinite(t):
            return None
        if t < self.times[0] or t > self.times[-1]:
            return None
        i = min(len(self.times) - 1, int(np.searchsorted(self.times, t)))
        if i > 0 and abs(self.times[i - 1] - t) < abs(self.times[i] - t):
            i -= 1
        return self.positions[i] if abs(self.times[i] - t) <= tolerance else None


def read_props(path, fps=120., offset_s=0.):
    if not math.isfinite(float(offset_s)):
        raise ValueError('Prop offset must be finite')
    path = Path(path)
    if path.suffix.lower() == '.npz':
        with np.load(path, allow_pickle=False) as f:
            key = next((k for k in ('prop_positions', 'translations', 'positions', 'xyz')
                        if k in f and f[k].ndim in (2, 3) and f[k].shape[-1] == 3), None)
            if key is None:
                raise ValueError('Props NPZ needs NxPx3 or Nx3 positions. Mesh formats need an explicit adapter.')
            xyz = np.asarray(f[key], dtype=np.float32)
            if xyz.ndim == 2:
                xyz = xyz[:, None, :]
            if len(xyz) == 0 or xyz.shape[1] == 0 or np.isinf(xyz).any():
                raise ValueError('Prop positions must be nonempty and cannot contain infinity')
            valid = np.isfinite(xyz).all(axis=-1)
            if not valid.any():
                raise ValueError('No finite prop positions')
            xyz[~valid] = np.nan
            fps = float(np.asarray(f['fps']).item()) if 'fps' in f else float(fps)
            if not math.isfinite(fps) or fps <= 0:
                raise ValueError('Prop sample rate must be finite and positive')
            names = [str(s) for s in f['prop_names']] if 'prop_names' in f else [f'Prop {i + 1}' for i in range(xyz.shape[1])]
            if len(names) != xyz.shape[1] or len(set(names)) != len(names):
                raise ValueError('Prop names must be unique with one name per prop')
            tkey = next((k for k in ('time_s', 'times', 'timestamps_s') if k in f), None)
            times = np.asarray(f[tkey], dtype=float) if tkey else np.arange(len(xyz)) / fps
            if times.ndim != 1 or len(times) != len(xyz) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
                raise ValueError('Prop times must be finite, increasing and match frame count')
            times = times + offset_s
        return PropTrack(times, xyz, names)
    records = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            try:
                t = float(row.get('time_s') or row.get('time')) + offset_s
                xyz = tuple(float(row[axis]) for axis in 'xyz')
                if not np.isfinite(t) or not np.isfinite(xyz).all():
                    continue
                records.append((t, row.get('prop_id') or 'Prop', *xyz))
            except (TypeError, ValueError, KeyError):
                continue
    if not records:
        raise ValueError('No valid prop XYZ rows')
    names, times = sorted({r[1] for r in records}), sorted({r[0] for r in records})
    lookup = {(t, name): (x, y, z) for t, name, x, y, z in records}
    positions = np.full((len(times), len(names), 3), np.nan, dtype=np.float32)
    for i, t in enumerate(times):
        for j, name in enumerate(names):
            if (t, name) in lookup:
                positions[i, j] = lookup[t, name]
    return PropTrack(np.asarray(times), positions, names)


def read_aoi_csv(path, offset_s=0.):
    """Events: start_s,end_s,label,role or samples: time_s,label. Returns tuples."""
    if not math.isfinite(float(offset_s)):
        raise ValueError('AOI offset must be finite')
    with open(path,encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if not rows:return []
    intervals=[]
    if 'start_s' in rows[0] and 'end_s' in rows[0]:
        for r in rows:
            try:
                s=float(r['start_s'])+offset_s;e=float(r['end_s'])+offset_s
                label=r.get('label') or r.get('aoi') or r.get('target') or 'AOI'
                if np.isfinite(s) and np.isfinite(e) and e>max(0.,s):intervals.append((max(0.,s),e,label))
            except (ValueError,TypeError):pass
        return sorted(intervals)
    time_col=next((key for key in ('time_s','time','timestamp_s') if key in rows[0]),None)
    label_col=next((key for key in ('label','aoi','target','face_aoi','body_aoi') if key in rows[0]),None)
    if not time_col or not label_col:raise ValueError('AOI CSV needs start_s/end_s/label or time_s/label')
    samples=[]
    for r in rows:
        try:
            t = float(r[time_col]) + offset_s
            if np.isfinite(t):samples.append((t,r[label_col]))
        except (ValueError,TypeError):pass
    samples.sort()
    if not samples:return []
    start=samples[0][0];label=samples[0][1]
    for (prev_t,_),(t,new) in zip(samples,samples[1:]):
        if new!=label or t-prev_t>.25:
            if prev_t-start>=.05:intervals.append((start,prev_t,label))
            start=t;label=new
    if samples[-1][0]-start>=.05:intervals.append((start,samples[-1][0],label))
    return [(max(0.,s),e,label) for s,e,label in intervals if e>max(0.,s)]


def wav_envelope(path, max_points=2500):
    """Memory-bounded peak envelope, including PCM24 and floating-point WAV.

    Each block takes the maximum across channels, so opposing stereo phases
    do not erase audible energy. The returned amplitude is display-normalized,
    not a speech probability or a loudness measurement.
    """
    if not isinstance(max_points, (int, np.integer)) or max_points < 1:
        raise ValueError('max_points must be a positive integer')
    try:
        reader = wave.open(str(path), 'rb')
    except (wave.Error, EOFError) as exc:
        # soundfile supports IEEE-float and RF64 WAV. It is optional for the
        # basic viewer; ordinary integer PCM works with the standard library.
        try:
            import soundfile as sf
        except ImportError:
            raise ValueError('This WAV encoding needs soundfile for waveform preview') from exc
        with sf.SoundFile(path) as f:
            count, sr = len(f), f.samplerate
            step = max(1, (count + max_points - 1) // max_points)
            peaks = []
            for block in f.blocks(blocksize=step, dtype='float32', always_2d=True):
                peaks.append(float(np.max(np.abs(block))) if len(block) else 0.)
    else:
        with reader as f:
            count, sr, channels, width = f.getnframes(), f.getframerate(), f.getnchannels(), f.getsampwidth()
            if width not in (1, 2, 3, 4):
                raise ValueError('Unsupported PCM sample width for waveform preview')
            if sr <= 0 or channels < 1:
                raise ValueError('Corrupt WAV header')
            step = max(1, (count + max_points - 1) // max_points)
            peaks = []
            while True:
                block = f.readframes(step)
                if not block:
                    break
                if width == 3:
                    raw = np.frombuffer(block, dtype=np.uint8)
                    raw = raw[:len(raw) // 3 * 3].reshape(-1, 3).astype(np.int32)
                    arr = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
                    arr = ((arr ^ 0x800000) - 0x800000).astype(np.float64)
                else:
                    dtype = {1: np.uint8, 2: np.dtype('<i2'), 4: np.dtype('<i4')}[width]
                    arr = np.frombuffer(block, dtype=dtype).astype(np.float64)
                    if width == 1:
                        arr -= 128.
                peaks.append(float(np.max(np.abs(arr))) if len(arr) else 0.)
    envelope = np.asarray(peaks, dtype=np.float32)
    if not np.isfinite(envelope).all():
        raise ValueError('WAV contains non-finite samples')
    envelope = envelope / (np.max(envelope) + 1e-8) if len(envelope) else envelope
    return np.arange(len(envelope)) * (step / sr), envelope
