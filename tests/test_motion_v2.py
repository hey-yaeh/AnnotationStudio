"""Boundary, coordinate and malformed-input regressions for the motion core."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import wave
import numpy as np
import pytest

from annotationstudio.bvh import BVHMotion, NPZPoseMotion
from annotationstudio.segmentation import SegmentationConfig, segment_motion, _local_rotation_speed, _label
from annotationstudio.modalities import read_gaze_csv, read_props, read_aoi_csv, wav_envelope

BASE = Path(__file__).resolve().parent.parent


def make_bvh(path, rows, frame_time=.01, offset='0 0 0'):
    text = f'''HIERARCHY
ROOT Hips
{{
 OFFSET {offset}
 CHANNELS 3 Zrotation Xrotation Yrotation
}}
MOTION
Frames: {len(rows)}
Frame Time: {frame_time}
'''
    path.write_text(text + '\n'.join(' '.join(map(str, row)) for row in rows))
    return path


@pytest.fixture(scope='module')
def sample(private_samples):
    path, = private_samples('S004_I02_R01_BVH.bvh')
    return BVHMotion(path)


def test_selected_motion_channels_and_range_are_local_and_bounded(sample):
    cfg = SegmentationConfig(channels=['Right Arm'], start_s=85.013, end_s=98.017)
    annotations, features, times = segment_motion(sample, 'R01', cfg)
    assert annotations
    assert set(features) == {'Right Arm'}
    assert times[0] >= cfg.start_s and times[-1] <= cfg.end_s
    assert all(a.channel == 'Right Arm' and cfg.start_s <= a.start_s < a.end_s <= cfg.end_s for a in annotations)
    assert not hasattr(sample, '_seg_indices')
    # Concurrent workers can read the same motion object without a mutable
    # analysis-index scratch attribute racing between runs.
    def execute(_):
        out, _, _ = segment_motion(sample, 'R01', cfg)
        return [(a.start_s, a.end_s, a.label) for a in out]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(execute, (0, 1)))
    assert first == second


@pytest.mark.parametrize('kwargs', [
    {'channels': []}, {'channels': ['Unknown']}, {'sample_hz': 0},
    {'start_s': -1}, {'start_s': 2, 'end_s': 1}, {'end_s': float('nan')},
    {'low_fraction': .8, 'high_fraction': .2}, {'up_axis': 'Q'},
])
def test_invalid_segmentation_settings_fail_clearly(kwargs):
    with pytest.raises(ValueError):
        SegmentationConfig(**kwargs).validate()


def test_single_frame_preview_but_no_segmentation(tmp_path):
    motion = BVHMotion(make_bvh(tmp_path / 'one.bvh', [(0, 0, 0)]))
    assert motion.positions([]).shape == (0, 1, 3)
    assert motion.pose_at(0).shape == (1, 3)
    with pytest.raises(ValueError, match='at least three'):
        segment_motion(motion, 'R01')


def test_rotation_speed_uses_actual_nonuniform_frame_spacing(tmp_path):
    motion = BVHMotion(make_bvh(tmp_path / 'rotation.bvh', [(i * .6, 0, 0) for i in range(7)]))
    ids = np.array([0, 4, 6])
    speed = _local_rotation_speed(motion, 0, ids, ids * .01)
    assert np.allclose(speed, np.deg2rad(60), atol=1e-6)


def test_up_axis_changes_vertical_label_without_changing_coordinates():
    class Motion:
        def joint(self, *names):
            return 0 if 'Spine3' in names else 1
    positions = np.array([[[0., 0., 0.], [0., 0., 0.]], [[0., 0., 0.], [0., 1., 0.]]])
    before = positions.copy()
    assert _label(Motion(), 'Right Arm', positions, 1., 0, 1, 'Y') == 'raise right arm'
    assert _label(Motion(), 'Right Arm', positions, 1., 0, 1, 'Z') == 'local arm movement (meaning uncertain)'
    assert np.array_equal(before, positions)


@pytest.mark.parametrize('rows,offset', [([(float('nan'), 0, 0)], '0 0 0'), ([(0, 0, 0)], '0 inf 0')])
def test_nonfinite_bvh_rejected(tmp_path, rows, offset):
    with pytest.raises(ValueError, match='[Nn]on-finite|NaN|infinity'):
        BVHMotion(make_bvh(tmp_path / 'bad.bvh', rows, offset=offset))


@pytest.mark.parametrize('parents', [[1, 0], [-1, 2], [-1, .5], [-1]])
def test_invalid_npz_parent_graphs_rejected(tmp_path, parents):
    path = tmp_path / 'bad.npz'
    np.savez(path, positions=np.zeros((3, 2, 3)), parents=parents, fps=30.)
    with pytest.raises(ValueError, match='parent|parents|cycle'):
        NPZPoseMotion(path)


def test_gpos_npz_read_and_no_invented_topology(tmp_path):
    path = tmp_path / 'good.npz'
    np.savez(path, gpos=np.zeros((3, 2, 3)), fps=30., joint_names=['Root', 'Head'])
    motion = NPZPoseMotion(path)
    assert motion.nframes == 3
    assert motion.parents == [-1, -1]
    assert not motion.assumed_frame_rate
    assert motion.positions([0, 2]).shape == (2, 2, 3)
    with pytest.raises(ValueError, match='outside'):
        motion.positions([-1])


def test_gaze_props_offsets_gaps_and_extent(tmp_path):
    gaze = tmp_path / 'gaze.csv'
    gaze.write_text('time_s,origin_x,origin_y,origin_z,dir_x,dir_y,dir_z\n0,0,0,0,1,0,0\n0.1,0,0,0,1,0,0\nnan,0,0,0,1,0,0\n')
    track = read_gaze_csv(gaze, offset_s=3.)
    assert len(track.times) == 2
    assert track.ray_at(3.05) is not None
    assert track.ray_at(2.99) is None
    assert track.ray_at(3.11) is None
    props = tmp_path / 'props.csv'
    props.write_text('time_s,prop_id,x,y,z\n0,Cup,1,2,3\n0.1,Cup,2,2,3\n2,Cup,4,2,3\n')
    prop_track = read_props(props, offset_s=3.)
    assert prop_track.at(3.05) is not None
    assert prop_track.at(2.99) is None
    assert prop_track.at(5.01) is None
    assert prop_track.at(4.) is None
    aoi = tmp_path / 'aoi.csv'
    aoi.write_text('start_s,end_s,label\n0,2,face\nnan,5,object\n4,6,hand\n')
    assert read_aoi_csv(aoi, offset_s=-1) == [(0., 1., 'face'), (3., 5., 'hand')]


def test_pcm_wave_negative_limit_and_opposing_stereo_do_not_vanish(tmp_path):
    path = tmp_path / 'stereo.wav'
    data = np.tile(np.array([[-32768, 32767], [32767, -32768]], dtype='<i2'), (800, 1))
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(data.tobytes())
    times, envelope = wav_envelope(path, max_points=100)
    assert len(times) == 100
    assert np.allclose(envelope, 1.)


def test_scene_time_bounds_and_y_up_transform(tmp_path, qapp):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from annotationstudio.scene import SkeletonCanvas
    application = qapp
    path = tmp_path / 'pose.npz'
    np.savez(path, positions=np.array([[[0., 0., 0.], [0., 1., 0.]]] * 31),
             fps=30., joint_names=['Root', 'Head'], parents=[-1, 0])
    canvas = SkeletonCanvas()
    canvas.add_motion('R01', NPZPoseMotion(path), offset=3.)
    assert canvas.active_roles(2.9) == []
    assert canvas.active_roles(3.5) == ['R01']
    assert canvas.active_roles(4.01) == []
    canvas.set_up_axis('Y')
    canvas.set_view('front')
    canvas.resize(700, 400)
    canvas.set_time(3.5)
    assert canvas.project([0, 1, 0]).y() < canvas.project([0, 0, 0]).y()
    canvas.show()
    application.processEvents()
    capture = canvas.grab()
    assert not capture.isNull()
    assert capture.deviceIndependentSize().width() == 700
    canvas.close()
    canvas.deleteLater()
    application.processEvents()


def test_arm_labels_follow_bvh_joints_and_can_be_hidden(sample, qapp, monkeypatch):
    from annotationstudio.media import MediaWorkspace

    media = MediaWorkspace()
    media.resize(960, 440)
    canvas = media.canvas
    canvas.add_motion('R01', sample)
    canvas.add_motion('R02', sample, offset=10.)
    observed = {}
    paint = canvas._paint_arm_labels

    def read_labels(painter, labels):
        observed.update((name, point) for name, point, _, _ in labels)
        paint(painter, labels)

    monkeypatch.setattr(canvas, '_paint_arm_labels', read_labels)
    media.show()
    qapp.processEvents()
    try:
        assert media.arm_labels.isChecked()
        canvas.set_time(4.)
        canvas.set_view('side')
        observed.clear()
        shown = canvas.grab().toImage()
        pose = sample.pose_at(4.).astype(float)
        anchors = {
            f'{side} Arm': (pose[sample.joint(side + 'Arm')] + pose[sample.joint(side + 'ForeArm')]) * .5
            for side in ('Left', 'Right')
        }
        assert observed == {name: canvas.project(point) for name, point in anchors.items()}
        assert observed['Left Arm'].x() > observed['Right Arm'].x()

        media.arm_labels.click()
        observed.clear()
        hidden = canvas.grab().toImage()
        assert not observed
        assert shown != hidden

        media.arm_labels.click()
        canvas.az += np.pi
        observed.clear()
        canvas.grab()
        assert observed == {name: canvas.project(point) for name, point in anchors.items()}
        assert observed['Left Arm'].x() < observed['Right Arm'].x()

        canvas.set_time(14.)
        observed.clear()
        canvas.grab()
        assert set(observed) == {'R01 Left Arm', 'R01 Right Arm', 'R02 Left Arm', 'R02 Right Arm'}
        assert observed['R02 Left Arm'] == canvas.project(anchors['Left Arm'])
    finally:
        media.close()
        media.deleteLater()
        qapp.processEvents()
