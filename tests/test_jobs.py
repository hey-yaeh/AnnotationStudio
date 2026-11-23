from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from threading import Event
import uuid

import pytest
from annotationstudio.models import Annotation, Asset, Project
from annotationstudio.bvh import BVHMotion
from annotationstudio.ontology import UNCLASSIFIED_MOTION
from annotationstudio.segmentation import SegmentationConfig
from annotationstudio.jobs import JobCancelled, run_motion_job, merge_auto_results
import annotationstudio.jobs as jobs


def candidate(start=2., end=4., *, asset='motion-r01', role='R01', channel='Right Arm',
              source='auto:graph', label='raise right arm', category='Motion Primitive',
              status='pending', history=None):
    attributes = {'source_asset_id': asset} if asset else {}
    annotation = Annotation(str(uuid.uuid4()), start, end, role=role, channel=channel,
                            source=source, label=label, category=category, status=status,
                            attributes=attributes, history=history or [])
    annotation.original = annotation.snapshot()
    return annotation


def scope(**overrides):
    record = {'source_asset_ids': ['motion-r01'], 'roles': ['R01'],
              'channels': ['Right Arm'], 'start_s': 0., 'end_s': 10.,
              'sources': ['auto:graph', 'auto:velocity']}
    record.update(overrides)
    return record


def test_rerun_preserves_accepted_and_skips_same_event_proposal():
    project = Project()
    accepted = candidate(status='approved')
    pending = candidate(6, 8)
    project.annotations = [accepted, pending]
    accepted_before = deepcopy(accepted)
    results = [candidate(2.05, 4.05), candidate(6.1, 8.1)]
    stats = merge_auto_results(project, results, scope())
    assert stats == {'added': 1, 'removed': 1, 'protected': 1, 'skipped_duplicates': 1}
    assert project.annotations[0] is accepted
    assert accepted.start_s == accepted_before.start_s and accepted.status == 'approved'
    assert len(project.annotations) == 2
    assert all(annotation.id != pending.id for annotation in project.annotations)


def test_coarse_legacy_candidates_are_preserved_and_duplicates_are_suppressed():
    project = Project()
    old = candidate(label='local arm movement (meaning uncertain)')
    fresh = candidate(label=UNCLASSIFIED_MOTION)
    project.annotations = [old]
    project.ensure_tracks()
    before = asdict(old)
    stats = merge_auto_results(project, [fresh], scope())
    assert stats['skipped_duplicates'] == 1 and stats['removed'] == 0
    assert [asdict(item) for item in project.annotations] == [before]


def test_real_bvh_job_keeps_coarse_candidates_and_original_prediction():
    examples = Path(__file__).resolve().parents[1] / 'examples'
    project = Project()
    assets = [project.add_asset('motion', role, examples / f'S004_I02_{role}_BVH.bvh')
              for role in ('R01', 'R02')]
    if any(not Path(asset.path).is_file() for asset in assets):
        pytest.skip('Packaged BVH samples are unavailable')
    results, details = run_motion_job({asset.role: BVHMotion(asset.path) for asset in assets}, assets, {
        'cfg': SegmentationConfig(channels=['Right Arm', 'Left Leg', 'Head']), 'structure': True,
    })
    assert all(item.status == 'pending' and item.role in ('R01', 'R02') for item in results)
    assert details['dyadic_count'] == 0
    unclassified = [item for item in results if item.label == UNCLASSIFIED_MOTION]
    assert {item.role for item in unclassified} == {'R01', 'R02'}
    assert all(item.original['native_prediction']['label'] != UNCLASSIFIED_MOTION for item in unclassified)
    merge_auto_results(project, results, details['scope'])
    label = project.resolve_label(UNCLASSIFIED_MOTION, 'Motion Primitive', include_deprecated=True)
    assert all(item.label_id == label.id for item in project.annotations if item.label == UNCLASSIFIED_MOTION)
    assert all(track.role != 'Both' for track in project.tracks)


def test_rejected_events_are_not_deleted_or_resurfaced_identically():
    project = Project()
    rejected = candidate(status='rejected')
    project.annotations = [rejected]
    stats = merge_auto_results(project, [candidate()], scope())
    assert stats['removed'] == 0 and stats['protected'] == 1
    assert stats['skipped_duplicates'] == 1 and project.annotations == [rejected]


def test_manual_pending_edits_are_protected():
    project = Project()
    edited = candidate(history=[{'action': 'save candidate'}])
    edited_without_history = candidate(6, 8)
    edited_without_history.label = 'human correction'
    project.annotations = [edited, edited_without_history]
    stats = merge_auto_results(project, [], scope())
    assert stats['removed'] == 0 and stats['protected'] == 2
    assert project.annotations == [edited, edited_without_history]


def test_audio_rerun_does_not_remove_other_model_or_event_kind():
    project = Project()
    silero = candidate(source='auto:silero', channel='Speech', category='Speaking', label='Speaking', asset='audio-1')
    yamnet = candidate(source='auto:yamnet', channel='Speech', category='Vocal Event', label='Sigh', asset='audio-1')
    accepted_sigh = candidate(5, 7, source='auto:yamnet', channel='Speech', category='Vocal Event',
                              label='Sigh', asset='audio-1', status='approved')
    new_laughter = candidate(5, 7, source='auto:yamnet', channel='Speech', category='Vocal Event',
                             label='Laughter', asset='audio-1')
    project.annotations = [silero, yamnet, accepted_sigh]
    stats = merge_auto_results(project, [new_laughter], scope(source_asset_ids=['audio-1'],
                               channels=['Speech'], sources=['auto:yamnet']))
    assert silero in project.annotations and accepted_sigh in project.annotations
    assert yamnet not in project.annotations
    assert stats['added'] == 1 and stats['skipped_duplicates'] == 0


def test_partial_range_only_replaces_fully_contained_candidates():
    project = Project()
    inside = candidate(3, 5)
    crossing_start = candidate(1, 4)
    crossing_end = candidate(6, 9)
    outside = candidate(9, 10)
    other_channel = candidate(4, 6, channel='Left Arm')
    project.annotations = [inside, crossing_start, crossing_end, outside, other_channel]
    stats = merge_auto_results(project, [], scope(start_s=2., end_s=8.))
    assert stats['removed'] == 1
    assert project.annotations == [crossing_start, crossing_end, outside, other_channel]


def test_asset_identity_is_required_and_other_source_is_untouched():
    project = Project()
    target = candidate()
    legacy = candidate(asset=None)
    other = candidate(asset='different-recording')
    project.annotations = [target, legacy, other]
    stats = merge_auto_results(project, [], scope())
    assert stats['removed'] == 1 and stats['protected'] == 1
    assert project.annotations == [legacy, other]


def test_multiasset_event_requires_all_sources_and_role_in_scope():
    project = Project()
    both = candidate(role='Both', channel='Dyadic', source='auto:dyadic-overlap', asset=None)
    both.attributes['source_asset_ids'] = ['motion-r01', 'motion-r02']
    project.annotations = [both]
    partial = scope(roles=['Both'], channels=['Dyadic'], sources=['dyadic'])
    assert merge_auto_results(project, [], partial)['removed'] == 0
    full = dict(partial, source_asset_ids=['motion-r01', 'motion-r02'])
    assert merge_auto_results(project, [], full)['removed'] == 1


def test_different_action_or_category_is_never_hidden_by_overlap():
    project = Project()
    project.annotations = [candidate(status='approved')]
    lowering = candidate(label='lower right arm')
    gesture = candidate(label='raise right arm', category='Gesture')
    stats = merge_auto_results(project, [lowering, gesture], scope())
    assert stats['added'] == 2 and stats['skipped_duplicates'] == 0


def test_same_class_nested_short_event_is_not_deduplicated():
    project = Project()
    project.annotations = [candidate(1, 9, status='approved')]
    stats = merge_auto_results(project, [candidate(3, 4)], scope())
    assert stats['added'] == 1


def test_append_mode_and_duplicate_ids_are_safe():
    project = Project()
    old = candidate()
    project.annotations = [old]
    new = candidate(5, 7)
    stats = merge_auto_results(project, [deepcopy(old), new, deepcopy(new)], scope(), replace=False)
    assert stats['removed'] == 0 and stats['added'] == 1 and stats['skipped_duplicates'] == 2
    assert len({annotation.id for annotation in project.annotations}) == 2


def test_validation_precedes_any_project_mutation():
    project = Project()
    project.annotations = [candidate()]
    before = project.to_dict()
    with pytest.raises(ValueError, match='pending'):
        merge_auto_results(project, [candidate(status='approved')], scope())
    assert project.to_dict() == before


def test_source_filter_uses_explicit_family_not_accidental_substring():
    project = Project()
    intended = candidate(source='auto:yamnet:v2')
    different = candidate(source='auto:yamnet-other')
    project.annotations = [intended, different]
    stats = merge_auto_results(project, [], scope(sources=['auto:yamnet']))
    assert stats['removed'] == 1 and project.annotations == [different]


def make_asset(role='R01', offset=5., asset_id='motion-r01', path='/tmp/motion-r01.bvh'):
    return Asset(id=asset_id, kind='motion', role=role, path=path, offset_s=offset)


def test_motion_job_clips_native_range_then_applies_offset_once(monkeypatch):
    asset = make_asset(offset=5.)
    motion = SimpleNamespace(path=Path(asset.path), duration_s=10.)
    calls = []
    def fake_segment(actual_motion, role, cfg):
        calls.append(deepcopy(cfg))
        found = candidate(cfg.start_s + .25, cfg.end_s - .25)
        found.original['segmentation_detail'] = {'preserve': True}
        return [found], {}, []
    monkeypatch.setattr(jobs, 'segment_motion', fake_segment)
    cfg = SegmentationConfig(channels=['Right Arm'])
    output, details = run_motion_job({'R01': motion}, [asset], {
        'cfg': cfg, 'roles': ['R01'], 'master_start': 6., 'master_end': 9.,
    })
    assert calls[0].start_s == 1. and calls[0].end_s == 4.
    assert cfg.start_s == 0. and cfg.end_s is None
    annotation = output[0]
    assert (annotation.start_s, annotation.end_s) == (6.25, 8.75)
    assert annotation.attributes['original_native_span'] == {'start_s': 1.25, 'end_s': 3.75}
    assert annotation.attributes['source_offset_s'] == 5.
    assert annotation.original['start_s'] == 6.25
    assert annotation.original['native_prediction']['start_s'] == 1.25
    assert annotation.original['native_prediction']['segmentation_detail'] == {'preserve': True}
    assert details['scope']['source_asset_ids'] == [asset.id]
    assert details['count'] == 1 and details['per_role']['R01']['count'] == 1


def test_negative_offset_and_nonintersecting_assets(monkeypatch):
    one = make_asset(offset=-5.)
    two = make_asset('R02', 20., 'motion-r02', '/tmp/motion-r02.bvh')
    motions = {asset.role: SimpleNamespace(path=Path(asset.path), duration_s=10.) for asset in [one, two]}
    calls = []
    def fake_segment(motion, role, cfg):
        calls.append((role, cfg.start_s, cfg.end_s))
        return [candidate(cfg.start_s, cfg.end_s, role=role)], {}, []
    monkeypatch.setattr(jobs, 'segment_motion', fake_segment)
    output, details = run_motion_job(motions, [one, two], {
        'cfg': SegmentationConfig(channels=['Right Arm']), 'master_start': 0., 'master_end': 4.,
        'roles': ['R01', 'R02', 'R03'],
    })
    assert calls == [('R01', 5., 9.)]
    assert (output[0].start_s, output[0].end_s) == (0., 4.)
    assert len(details['skipped']) == 2
    assert details['scope']['source_asset_ids'] == ['motion-r01']


def test_cancelled_batch_never_returns_partial_results(monkeypatch):
    event = Event()
    asset = make_asset()
    motion = SimpleNamespace(path=Path(asset.path), duration_s=10.)
    def fake_segment(motion, role, cfg):
        event.set()
        return [candidate(1, 2)], {}, []
    monkeypatch.setattr(jobs, 'segment_motion', fake_segment)
    with pytest.raises(JobCancelled):
        run_motion_job({'R01': motion}, [asset], {'roles': ['R01']}, cancel=event)
    event.set()
    with pytest.raises(JobCancelled):
        run_motion_job({}, [], {}, cancel=lambda: event.is_set())


def test_phase_and_dyadic_use_only_master_clock_current_batch(monkeypatch):
    one = make_asset(offset=10.)
    two = make_asset('R02', 9., 'motion-r02', '/tmp/motion-r02.bvh')
    motions = {asset.role: SimpleNamespace(path=Path(asset.path), duration_s=8.) for asset in [one, two]}
    def fake_segment(motion, role, cfg):
        local = [(1., 2., 'raise right arm'), (2.5, 3.5, 'lower right arm')]
        if role == 'R02':
            local = [(2., 4., 'raise right arm')]
        return [candidate(start, end, role=role, label=label) for start, end, label in local], {}, []
    monkeypatch.setattr(jobs, 'segment_motion', fake_segment)
    results, details = run_motion_job(motions, [one, two], {
        'cfg': SegmentationConfig(channels=['Right Arm']), 'master_start': 0., 'master_end': 20.,
        'roles': ['R01', 'R02'], 'structure': True, 'dyadic': True,
    })
    phases = [annotation for annotation in results if annotation.source == 'auto:phase-structure']
    dyadic = [annotation for annotation in results if annotation.source == 'auto:dyadic-overlap']
    assert len(phases) == 1 and phases[0].start_s == 11. and phases[0].end_s == 13.5
    assert phases[0].attributes['source_asset_id'] == one.id
    assert dyadic and dyadic[0].start_s == 11.
    assert set(dyadic[0].attributes['source_asset_ids']) == {one.id, two.id}
    assert 'Both' in details['scope']['roles'] and 'Dyadic' in details['scope']['channels']
    assert all(annotation.attributes['run_id'] == details['run_id'] for annotation in results)
    assert all(annotation.original['time_basis'] == 'master seconds' for annotation in results)


def test_asset_path_mismatch_is_skipped_instead_of_wrong_offset(monkeypatch):
    asset = make_asset()
    wrong_motion = SimpleNamespace(path=Path('/tmp/another-recording.bvh'), duration_s=10.)
    def forbidden(*_args):
        raise AssertionError('Must not analyse a mismatched source')
    monkeypatch.setattr(jobs, 'segment_motion', forbidden)
    results, details = run_motion_job({'R01': wrong_motion}, [asset], {})
    assert not results and details['skipped'][0]['reason'] == 'No matching enabled source asset'
