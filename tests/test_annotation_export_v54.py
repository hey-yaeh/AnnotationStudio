"""Export scopes, metadata and transactions are independent of timeline views."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path, PureWindowsPath
import csv
import hashlib
import json

import pytest

from annotationstudio import annotation_export as export
from annotationstudio.models import Annotation, Asset, Project, SceneObject, import_annotation_csv


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize('stem', ['Synthetic_annotation_demo_NOT_OCUMO_reference_la', '标注😀' * 12])
def test_windows_bundle_budgets_final_files_including_utf16_and_collision(stem):
    parent = PureWindowsPath('D:/') / ('parent_' + 'x' * 130)
    filenames = ['long_project_name_annotations.csv', 'long_project_name_export_manifest.json']
    name = export._bundle_directory_base(parent, stem, filenames, '20261119_120000',
                                         '0123456789ab', windows=True)
    assert name != f'{stem}_exports_20261119_120000_0123456789ab'
    assert all(export._path_units(parent / (name + '_02') / leaf) <= 259 for leaf in filenames)


def test_windows_bundle_rejects_parent_with_no_room_for_usable_files():
    parent = PureWindowsPath('D:/') / ('x' * 210)
    with pytest.raises(ValueError, match='shorter parent folder'):
        export._bundle_directory_base(parent, 'project', ['project_export_manifest.json'],
                                      '20261119_120000', '0123456789ab', windows=True)


@pytest.fixture
def project():
    result = Project('Practice_Session')
    result.tracks = []
    primitive = result.add_track(name='R01 right arm', role='R01', category='Motion Primitive',
                                 channel='Right Arm', visible=False)
    hoi = result.add_track(name='R01 contact', role='R01', category='Action / HOI', channel='Hands')
    spatial = result.add_track(name='R01 position', role='R01', category='Object Spatial Relation', channel='Root')
    affect = result.add_track(name='R02 affect', role='R02', category='Perceived Affect', channel='Emotion')
    point = result.add_track(name='Transition', role='R02', category='Turn Transition', channel='Speech')
    result.objects = [
        SceneObject('counter', '柜台，"入口"\n第二行', 'counter', 'A named target, no model'),
        SceneObject('sofa', 'Window sofa', 'sofa', extra={'retired': True, 'future': {'keep': 1}}),
        SceneObject('unused', 'Unused table', 'table'),
    ]
    result.annotations = [
        Annotation('primitive-r01', 1.25, 3.75, role='R01', category='Motion Primitive',
                   label='raise right arm', channel='Right Arm', track_id=primitive.id,
                   status='approved', source='motion-rule-v1', confidence=0.0,
                   original={'label': 'motion candidate', 'start_s': 1.1},
                   history=[{'action': 'accept', 'future': ['kept']}],
                   attributes={'body_parts': ['Right Arm', 'Right Hand'], 'future': {'x': None}}),
        Annotation('primitive-r02', 2, 4, role='R02', category='Motion Primitive',
                   label='hold', channel='Left Arm', status='pending'),
        Annotation('speech-rejected', 2.5, 5, role='R02', category='Speaking',
                   label='Speaking', channel='Speech', status='rejected'),
        Annotation('hoi', 3, 10, role='R01', category='Action / HOI',
                   label='rest on object', channel='Hands', track_id=hoi.id,
                   status='approved', attributes={'object_id': 'counter', 'effector': 'Hands'}),
        Annotation('between', 4, 5.5, role='R01', category='Object Spatial Relation',
                   label='between objects', channel='Root', track_id=spatial.id,
                   status='approved', attributes={'annotation_fields_version': 1, 'object_id': 'counter',
                       'spatial_relation': {'secondary_object_id': 'sofa'}}),
        Annotation('beside', 5.5, 9, role='R01', category='Object Spatial Relation',
                   label='beside object', channel='Root', track_id=spatial.id,
                   status='approved', attributes={'object_id': 'missing-object',
                       'spatial_relation': {'secondary_object_id': 'sofa', 'reference_frame': 'scene_reference'}}),
        Annotation('affect', 6, 8, role='R02', category='Perceived Affect',
                   label='valence / arousal rating', channel='Emotion', track_id=affect.id,
                   status='approved', attributes={'annotation_fields_version': 1,
                       'affect': {'annotation_mode': 'valence_arousal', 'valence': 0,
                                  'arousal': None, 'intensity': 4, 'future': {'keep': True}}}),
        Annotation('handoff-point', 8.123456789, 8.123456789, role='R02',
                   category='Turn Transition', label='floor transfer', channel='Speech',
                   track_id=point.id, status='approved', temporal_kind='point',
                   attributes={'target_role': 'R01'}),
    ]
    return result


def test_total_and_split_tables_are_exact_partitions_with_stable_provenance(project, tmp_path):
    before = deepcopy(project.to_dict())
    result = export.export_annotation_bundle(project, tmp_path, layout='both')
    manifest = json.loads(Path(result['manifest_path']).read_text(encoding='utf-8'))
    combined = next(table for table in manifest['tables'] if table['kind'] == 'combined')
    total = read_csv(Path(result['directory']) / combined['filename'])
    pieces = [read_csv(Path(result['directory']) / table['filename'])
              for table in manifest['tables'] if table['kind'] == 'annotation_type']
    by_id = {row['id']: row for row in total}
    flattened = [row for piece in pieces for row in piece]
    assert len(flattened) == len(by_id) == result['annotation_count'] == 6
    assert {row['id']: row for row in flattened} == by_id
    assert all(row['status'] == 'approved' for row in total)
    assert by_id['primitive-r01']['source'] == 'motion-rule-v1'
    assert by_id['primitive-r01']['confidence'] == '0.0'
    assert by_id['handoff-point']['start_s'] == by_id['handoff-point']['end_s'] == '8.123456789'
    assert by_id['handoff-point']['temporal_kind'] == 'point'
    assert project.to_dict() == before
    for item in manifest['files']:
        data = (Path(result['directory']) / item['filename']).read_bytes()
        assert len(data) == item['bytes']
        assert hashlib.sha256(data).hexdigest() == item['sha256']


@pytest.mark.parametrize('review_state,expected', [('accepted', 6), ('candidates_accepted', 7), ('all', 8)])
def test_review_filters_are_explicit_and_never_promote_records(project, review_state, expected):
    before = [asdict(item) for item in project.annotations]
    selected = export.select_annotations(project, review_state)
    assert len(selected) == expected
    assert [asdict(item) for item in project.annotations] == before
    assert export.select_annotations(project, review_state, []) == []
    only = export.select_annotations(project, review_state, ['Motion Primitive'])
    assert {row.category for row in only} == {'Motion Primitive'}


def test_custom_legacy_and_mixed_hidden_track_types_remain_selectable(project, tmp_path):
    hidden = project.tracks[0]
    project.annotations.append(Annotation('legacy', 20, 21, category='Legacy gesture',
        label='authored', track_id=hidden.id, status='approved', channel='Hands'))
    rows = {row['category']: row for row in export.available_export_types(project)}
    assert rows['Motion Primitive']['total_count'] == 2
    assert rows['Motion Primitive']['count'] == 1
    assert rows['Legacy gesture']['count'] == 1
    result = export.export_annotation_csv(project, tmp_path / 'legacy.csv', categories=['Legacy gesture'])
    exported = read_csv(result['path'])
    assert len(exported) == 1
    assert exported[0]['category'] == 'Legacy gesture'
    assert exported[0]['workspace'] == hidden.workspace
    assert exported[0]['track_name'] == hidden.name
    assert project.annotations[-1].category == 'Legacy gesture'


def test_flat_objects_and_sidecar_preserve_names_missing_and_inactive_references(project, tmp_path):
    result = export.export_annotation_bundle(project, tmp_path, layout='both')
    table = next(table for table in result['tables'] if table['kind'] == 'combined')
    rows = {row['id']: row for row in read_csv(Path(result['directory']) / table['filename'])}
    assert rows['hoi']['object_name'] == '柜台，"入口"\n第二行'
    assert rows['hoi']['object_class'] == 'counter'
    assert rows['hoi']['effector'] == 'Hands'
    assert rows['between']['secondary_object_id'] == 'sofa'
    assert rows['between']['secondary_object_name'] == 'Window sofa'
    assert rows['beside']['secondary_object_id'] == ''
    assert rows['beside']['spatial_reference_frame'] == ''
    assert rows['beside']['object_id'] == 'missing-object'
    assert rows['beside']['object_name'] == ''
    assert json.loads(rows['beside']['attributes'])['spatial_relation']['secondary_object_id'] == 'sofa'
    objects = {row['object_id']: row for row in read_csv(result['objects_path'])}
    assert set(objects) == {'counter', 'sofa', 'missing-object'}
    assert objects['sofa']['retired'] == 'True'
    assert objects['sofa']['reference_count'] == '2'
    assert objects['missing-object']['missing'] == 'True'
    assert objects['missing-object']['object_name'] == ''


def test_directional_aliases_and_core_renames_keep_active_reference_frame(project, tmp_path):
    spec = project.resolve_label('in front of object', 'Object Spatial Relation')
    spec.name = 'front region (project wording)'
    row = project.annotations[4]
    row.label_id, row.label = spec.id, spec.name
    row.attributes['spatial_relation'] = {'reference_frame': 'object_intrinsic', 'secondary_object_id': 'sofa'}
    result = export.export_annotation_csv(project, tmp_path / 'front.csv', categories=['Object Spatial Relation'])
    exported = {item['id']: item for item in read_csv(result['path'])}
    assert exported['between']['spatial_reference_frame'] == 'object_intrinsic'
    assert exported['between']['secondary_object_id'] == ''
    assert row.attributes['spatial_relation']['secondary_object_id'] == 'sofa'


def test_affect_values_keep_zero_unknown_inactive_and_future_scales(project, tmp_path):
    row = deepcopy(project.annotations[6])
    row.id = 'legacy-continuous'
    row.attributes = {'annotation_fields_version': 99, 'affect': {
        'annotation_mode': 'future_continuous', 'valence': 0.125,
        'arousal': None, 'intensity': {'future_shape': 4}}}
    project.annotations.append(row)
    result = export.export_annotation_csv(project, tmp_path / 'affect.csv', categories=['Perceived Affect'])
    exported = {item['id']: item for item in read_csv(result['path'])}
    assert exported['affect']['affect_valence'] == '0'
    assert exported['affect']['affect_arousal'] == ''
    assert exported['affect']['affect_intensity'] == '4'
    assert exported['affect']['affect_mode'] == 'valence_arousal'
    assert exported[row.id]['affect_valence'] == '0.125'
    assert exported[row.id]['annotation_fields_version'] == '99'
    assert exported[row.id]['affect_intensity'] == ''
    assert json.loads(exported[row.id]['attributes']) == row.attributes


def test_enriched_csv_round_trips_every_native_field_with_unicode_and_empty_original(project, tmp_path):
    result = export.export_annotation_csv(project, tmp_path / 'all.csv', review_state='all')
    assert Path(result['path']).read_bytes().startswith(b'\xef\xbb\xbf')
    restored = {row.id: asdict(row) for row in import_annotation_csv(result['path'])}
    assert restored == {row.id: asdict(row) for row in project.annotations}
    assert restored['hoi']['original'] == {}
    assert restored['hoi']['confidence'] is None


def test_portable_names_handle_reserved_sidecars_case_and_alias_collisions(tmp_path):
    project = Project('../../CON')
    categories = ['objects', 'annotations', 'export_manifest', 'Foo', 'foo',
                  'Action / HOI', 'HOI', '../../NUL', 'Aux', '音频', '..\\outside']
    project.annotations = [Annotation(str(index), index, index + 1, category=category,
                                     label='test', status='approved')
                           for index, category in enumerate(categories)]
    first = export.export_annotation_bundle(project, tmp_path, layout='both')
    second = export.export_annotation_bundle(project, tmp_path, layout='both')
    assert first['directory'] != second['directory']
    assert Path(first['directory']).parent == tmp_path
    names = [Path(path).name for path in first['paths']]
    assert len(names) == len({name.casefold() for name in names})
    assert all(Path(path).parent == Path(first['directory']) for path in first['paths'])
    assert all(not any(char in name for char in '<>:"/\\|?*') for name in names)
    assert all(not name.endswith(('.', ' ')) for name in names)
    assert {table['category'] for table in first['tables'] if table['kind'] == 'annotation_type'} == set(categories)
    assert set(names) == {Path(path).name for path in second['paths']}
    assert export.category_export_stem('Action / HOI') == 'hoi'
    project.path = tmp_path / 'Practice_Session.studio.json'
    assert export.suggested_export_stem(project) == 'Practice_Session'


def test_selected_zero_count_types_are_skipped_explicitly(project, tmp_path):
    result = export.export_annotation_bundle(project, tmp_path, categories=['Motion Primitive', 'Speaking'], layout='by_type')
    assert result['type_counts'] == {'Motion Primitive': 1}
    manifest = json.loads(Path(result['manifest_path']).read_text(encoding='utf-8'))
    assert manifest['skipped_empty_categories'] == ['Speaking']
    assert len(manifest['tables']) == 1
    assert manifest['tables'][0]['kind'] == 'annotation_type'


@pytest.mark.parametrize('mutation', ['empty_selection', 'invalid_time', 'invalid_rating', 'nan_metadata', 'duplicate_id'])
def test_invalid_exports_leave_existing_file_and_folder_contents_untouched(project, tmp_path, mutation):
    target = tmp_path / 'existing.csv'
    target.write_bytes(b'previous result')
    options = {}
    if mutation == 'empty_selection':
        options['categories'] = []
    elif mutation == 'invalid_time':
        project.annotations[0].end_s = project.annotations[0].start_s
    elif mutation == 'invalid_rating':
        project.annotations[6].attributes['affect']['valence'] = 20
    elif mutation == 'nan_metadata':
        project.annotations[0].attributes['future']['x'] = float('nan')
    else:
        project.annotations.append(deepcopy(project.annotations[0]))
    with pytest.raises(ValueError):
        export.export_annotation_csv(project, target, **options)
    with pytest.raises(ValueError):
        export.export_annotation_bundle(project, tmp_path, **options)
    assert target.read_bytes() == b'previous result'
    assert list(tmp_path.iterdir()) == [target]


def test_failed_file_write_and_bundle_stage_clean_up_without_touching_existing_outputs(project, tmp_path, monkeypatch):
    target = tmp_path / 'existing.csv'
    target.write_bytes(b'previous result')
    original = export._write_bytes
    calls = 0

    def fail_write(path, payload):
        nonlocal calls
        calls += 1
        original(path, payload[:20])
        raise OSError('simulated disk write failure')

    monkeypatch.setattr(export, '_write_bytes', fail_write)
    with pytest.raises(OSError, match='simulated'):
        export.export_annotation_csv(project, target)
    assert target.read_bytes() == b'previous result'
    with pytest.raises(OSError, match='simulated'):
        export.export_annotation_bundle(project, tmp_path, layout='both')
    assert calls == 2
    assert list(tmp_path.iterdir()) == [target]


def test_single_csv_cannot_overwrite_media_or_project_even_through_symlink(project, tmp_path):
    source = tmp_path / 'gaze.csv'
    source.write_bytes(b'raw input')
    project.assets.append(Asset('gaze', 'gaze', 'R01', str(source)))
    saved = tmp_path / 'project.studio.json'
    saved.write_bytes(b'project input')
    project.path = saved
    alias = tmp_path / 'alias.csv'
    try:
        alias.symlink_to(source)
    except (OSError, NotImplementedError):
        alias = source
    for path in (source, saved, alias):
        with pytest.raises(ValueError, match='read-only export inputs'):
            export.export_annotation_csv(project, path)
    assert source.read_bytes() == b'raw input'
    assert saved.read_bytes() == b'project input'


def test_invalid_options_cannot_fall_back_to_unfiltered_export(project, tmp_path):
    for options in ({'review_state': 'approved'}, {'categories': 'Motion Primitive'}):
        with pytest.raises(ValueError):
            export.export_annotation_csv(project, tmp_path / 'bad.csv', **options)
    with pytest.raises(ValueError):
        export.export_annotation_bundle(project, tmp_path, layout='combined')
    assert not list(tmp_path.iterdir())
