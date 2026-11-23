"""Fine proposals through real BVH parsing, segmentation and the review merge."""
from dataclasses import asdict

import numpy as np
import pytest

from annotationstudio.bvh import BVHMotion
from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.jobs import merge_auto_results, run_motion_job
from annotationstudio.models import Project, import_annotation_csv
from annotationstudio.annotation_export import export_annotation_csv
from annotationstudio.segmentation import SegmentationConfig, segment_motion


def _bvh(tmp_path, motions, *, up='Z', calibrated=True):
    superior = (0, 0, 1) if up == 'Z' else (0, 1, 0)
    inferior = tuple(-value for value in superior)
    time = np.arange(701) / 100.
    channels = []

    def joint(name, offset, order, *children):
        return name, offset, order, children

    def emit(joint_spec, root=False):
        name, offset, order, children = joint_spec
        rotation = [f'{axis}rotation' for axis in order]
        columns = ['Xposition', 'Yposition', 'Zposition', *rotation] if root else rotation
        channels.extend((name, column) for column in columns)
        return '\n'.join([
            f'{"ROOT" if root else "JOINT"} {name}', '{',
            'OFFSET ' + ' '.join(map(str, offset)), f'CHANNELS {len(columns)} ' + ' '.join(columns),
            *(emit(child) for child in children), '}',
        ])

    arms, legs = [], []
    for side, sign in [('Left', -1), ('Right', 1)]:
        arm = side + 'Arm' if calibrated else side + 'Limb'
        arms.append(joint(arm, (sign, 0, 0), 'XZY',
                          joint(side + 'ForeArm', (sign, 0, 0), 'YZX',
                                joint(side + 'Hand', (sign, 0, 0), 'XYZ'))))
        legs.append(joint(side + 'UpLeg', (sign * .4, 0, 0), 'ZXY',
                          joint(side + 'Leg', inferior, 'YXZ', joint(side + 'Foot', inferior, 'XYZ'))))
    neck = joint('Neck', superior, 'YZX', joint('Head', superior, 'XZY'))
    torso = joint('Spine3', superior, 'ZXY', neck, *arms)
    hierarchy = emit(joint('Hips', (0, 0, 0), 'YXZ', torso, *legs), root=True)
    data = np.zeros((len(time), len(channels)))
    for (name, axis), knots in motions.items():
        values = np.interp(time, *zip(*knots))
        data[:, channels.index((name, f'{axis}rotation'))] = (values + 180) % 360 - 180
    path = tmp_path / 'known-movements.bvh'
    path.write_text(f'HIERARCHY\n{hierarchy}\nMOTION\nFrames: {len(time)}\nFrame Time: 0.01\n'
                    + '\n'.join(' '.join(f'{value:.4f}' for value in row) for row in data))
    return BVHMotion(path)


@pytest.mark.parametrize('up,hz,mode', [('Z', 30., 'graph'), ('Y', 50., 'velocity')])
def test_head_turn_nod_and_shake_are_separated_from_torso_motion(tmp_path, up, hz, mode):
    motion = _bvh(tmp_path, {
        ('Hips', up): [(0, 160), (7, 440)],
        ('Spine3', 'X'): [(0, 0), (7, 35)],
        ('Neck', 'X'): [(1, 0), (1.43, 27), (1.9, 0)],
        ('Neck', up): [(2.7, 0), (3.1, -26), (3.55, 0), (4.6, 0), (5.15, 35)],
    }, up=up)
    cfg = SegmentationConfig(channels=['Head', 'Right Arm', 'Root'], up_axis=up, sample_hz=hz, mode=mode)
    events, _, _ = segment_motion(motion, 'R02', cfg)
    head = [item for item in events if item.channel == 'Head']
    specific = [item for item in head if 'primitive_evidence' in item.attributes]
    assert [item.label for item in specific] == ['head nod', 'head shake', 'head rotation']
    for item, (start, end) in zip(specific, [(1, 1.9), (2.7, 3.55), (4.6, 5.15)]):
        assert item.start_s == pytest.approx(start, abs=.20)
        assert item.end_s == pytest.approx(end, abs=.20)
        assert item.role == 'R02' and item.status == 'pending' and item.confidence is None
        assert item.attributes['primitive_evidence']['joints'] == ['Neck', 'Head']
        assert all(other is item or other.end_s <= item.start_s or other.start_s >= item.end_s for other in head)
    assert not any(item.channel == 'Right Arm' for item in events)


def test_head_wraparound_and_missing_body_axes_do_not_create_false_shakes(tmp_path):
    cfg = SegmentationConfig(channels=['Head'], smoothing_s=.06)
    yaw = {('Head', 'Z'): [(1, 170), (1.6, 200)]}
    motion = _bvh(tmp_path, yaw)
    events, _, _ = segment_motion(motion, 'R01', cfg)
    assert [item.label for item in events if 'primitive_evidence' in item.attributes] == ['head rotation']
    fallback, _, _ = segment_motion(_bvh(tmp_path, yaw, calibrated=False), 'R01', cfg)
    assert fallback and {item.label for item in fallback} == {'head / neck movement'}
    legacy, _, _ = segment_motion(motion, 'R01', SegmentationConfig(channels=['Head'], fine_primitives=False))
    assert legacy and {item.label for item in legacy} == {'head / neck movement'}


def test_mixed_head_axes_keep_the_activity_unclassified(tmp_path):
    change = [(1, 0), (1.7, 35)]
    motion = _bvh(tmp_path, {('Head', axis): change for axis in ('X', 'Z')})
    cfg = SegmentationConfig(channels=['Head'])
    events, _, _ = segment_motion(motion, 'R01', cfg)
    assert events and {item.label for item in events} == {'head / neck movement'}


def test_hinge_reversals_keep_anatomical_side_and_exclude_the_held_angle(tmp_path):
    motion = _bvh(tmp_path, {
        ('Hips', 'Z'): [(0, 20), (7, 400)],
        ('LeftForeArm', 'Z'): [(1, 0), (1.6, -50), (3, -50), (3.55, 0)],
        ('RightLeg', 'X'): [(2, 0), (2.65, 60), (4, 60), (4.55, 0)],
    })
    cfg = SegmentationConfig(channels=['Left Arm', 'Right Arm', 'Left Leg', 'Right Leg'])
    events, _, _ = segment_motion(motion, 'R01', cfg)
    measured = [item for item in events if 'primitive_evidence' in item.attributes]
    assert [(item.channel, item.label) for item in measured] == [
        ('Left Arm', 'flex left elbow'), ('Right Leg', 'bend right knee'),
        ('Left Arm', 'extend left elbow'), ('Right Leg', 'straighten right knee'),
    ]
    assert measured[0].end_s < 1.9 and measured[2].start_s > 2.7
    assert measured[1].end_s < 2.95 and measured[3].start_s > 3.7
    assert measured[0].attributes['primitive_evidence']['excursion_deg'] > 40
    assert measured[2].attributes['primitive_evidence']['excursion_deg'] < -40


def test_fine_candidate_master_clock_review_rerun_and_export(tmp_path):
    motion = _bvh(tmp_path, {('LeftLeg', 'X'): [(1, 0), (1.7, 55), (2.5, 55), (3.1, 0)]})
    project = Project()
    asset = project.add_asset('motion', 'R02', motion.path, offset_s=5.25)
    options = {'cfg': SegmentationConfig(channels=['Left Leg']), 'master_start': 6., 'master_end': 8.6}
    results, details = run_motion_job({'R02': motion}, [asset], options)
    merge_auto_results(project, results, details['scope'])
    bend = next(item for item in project.annotations if item.label == 'bend left knee')
    native = bend.original['native_prediction']
    assert native['label'] == bend.label
    assert bend.start_s == pytest.approx(native['start_s'] + asset.offset_s)
    assert bend.end_s == pytest.approx(native['end_s'] + asset.offset_s)
    assert bend.attributes['primitive_evidence']['first_frame'] * motion.frame_time == pytest.approx(native['start_s'])
    assert bend.label_id == project.resolve_label(bend.label, bend.category).id

    session = EditSession(project, ProjectHistory())
    session.begin(bend.id)
    session.update(label='hip flexion')
    assert session.accept()
    accepted = next(item for item in project.annotations if item.id == bend.id)
    previous = asdict(accepted)
    saved = tmp_path / 'reviewed.studio.json'
    project.save(saved)
    project = Project.load(saved)
    results, details = run_motion_job({'R02': motion}, [asset], options)
    stats = merge_auto_results(project, results, details['scope'])
    assert stats['skipped_duplicates'] >= 1
    assert not any(item.label == 'bend left knee' for item in project.annotations)
    assert asdict(next(item for item in project.annotations if item.id == bend.id)) == previous
    path = tmp_path / 'reviewed.csv'
    export_annotation_csv(project, path)
    assert [asdict(item) for item in import_annotation_csv(path)] == [previous]
