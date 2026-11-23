r"""Read-only local development checks; no inference or model downloads.

Run with the project's interpreter: ``.venv/bin/python scripts/doctor.py`` or
``.venv\Scripts\python.exe scripts\doctor.py``. Missing optional ML packages
and omitted sample BVH files are informational, not core failures.
"""
from __future__ import annotations

import argparse
import importlib
from importlib import metadata, util
import json
from pathlib import Path
import platform
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _distribution(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _discoverable(name):
    # Only top-level modules: find_spec on a dotted name could import its parent.
    try:
        return util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def inspect_environment():
    checks = []
    app_version = None
    schema = None
    vocabulary = None
    imports = {}
    neural_modules = ('torch', 'tensorflow', 'silero_vad', 'pyannote', 'whisperx')
    neural_before = {name for name in neural_modules if name in sys.modules}

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})

    supported = (platform.python_implementation() == 'CPython'
                 and sys.version_info[:2] in ((3, 11), (3, 12))
                 and struct.calcsize('P') == 8)
    check('Python runtime', supported,
          f'{platform.python_implementation()} {platform.python_version()}, {struct.calcsize("P") * 8}-bit; supported: CPython 3.11/3.12, 64-bit')
    for module in ('numpy', 'scipy', 'soundfile', 'PySide6.QtCore', 'PySide6.QtWidgets',
                   'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets'):
        try:
            imports[module] = importlib.import_module(module)
            check('Import ' + module, True, 'Available; no GUI window or media playback started.')
        except Exception as error:
            check('Import ' + module, False, f'{type(error).__name__}: {error}')

    try:
        app = importlib.import_module('annotationstudio')
        app_version = app.__version__
        for module in ('models', 'editing', 'ontology', 'segmentation', 'speech_structure',
                       'context_relations', 'object_registry', 'editor', 'ui'):
            importlib.import_module('annotationstudio.' + module)
        check('Local application imports', True, f'Annotation Studio {app_version} from {ROOT}')
    except Exception as error:
        check('Local application imports', False, f'{type(error).__name__}: {error}')

    try:
        from annotationstudio.models import Project, SCHEMA, SCHEMA_VERSION
        from annotationstudio.ontology import LABEL_PRESETS, WORKSPACES, category_info
        project = Project('Read-only doctor probe')
        project.add_object('Doctor object', 'table', id='doctor_table')
        track = project.add_track(name='Doctor point track', category='Turn Transition',
                                  role='Both', channel='Speech')
        point = project.add_annotation(
            .25, .25, track_id=track.id, category='Turn Transition', role='Both',
            channel='Speech', label='speaker change candidate', temporal_kind='point')
        project.validate()
        payload = project.to_dict()
        json.dumps(payload, allow_nan=False)
        valid = (SCHEMA_VERSION == 3 and point.is_point and point.valid()
                 and payload['objects'][0]['id'] == 'doctor_table'
                 and category_info('Turn Transition')['temporal_kind'] == 'point')
        schema = {'name': SCHEMA, 'version': SCHEMA_VERSION}
        vocabulary = {'workspaces': len(WORKSPACES), 'types': len(LABEL_PRESETS),
                      'active_labels': sum(len(values) - 1 for values in LABEL_PRESETS.values())}
        check('Project schema and in-memory point/object probe', valid,
              f'{SCHEMA} v{SCHEMA_VERSION}; no project file was created or modified.')
    except Exception as error:
        check('Project schema and in-memory point/object probe', False,
              f'{type(error).__name__}: {error}')

    optional = []
    for distribution, module, purpose, integrated in (
        ('torch', 'torch', 'Optional Silero runtime', True),
        ('silero-vad', 'silero_vad', 'Optional Speaking candidates', True),
        ('tensorflow', 'tensorflow', 'Optional YAMNet runtime', True),
        ('tensorflow-hub', 'tensorflow_hub', 'Optional explicitly requested YAMNet download', True),
        ('pyannote.audio', 'pyannote', 'Diarization is not integrated in this release', False),
        ('whisperx', 'whisperx', 'ASR/alignment is not integrated in this release', False),
    ):
        optional.append({'distribution': distribution, 'version': _distribution(distribution),
                         'module_discoverable': _discoverable(module), 'purpose': purpose,
                         'adapter_in_release': integrated,
                         'inference_checked': False, 'weights_loaded': False})
    neural_after = {name for name in neural_modules if name in sys.modules}
    loaded = sorted(neural_after - neural_before)
    check('No optional neural framework was imported', not loaded,
          'Only package metadata/module discovery was queried.' if not loaded else
          'Unexpected imports: ' + ', '.join(loaded))

    samples = []
    for name in ('S004_I02_R01_BVH.bvh', 'S004_I02_R02_BVH.bvh',
                 'S004_I02_manual.studio.json', 'S004_I02_example.ocumo.json'):
        path = ROOT / 'examples' / name
        samples.append({'path': str(path.relative_to(ROOT)), 'present': path.is_file(),
                        'size_bytes': path.stat().st_size if path.is_file() else None})
    versions = {name: _distribution(name) for name in ('PySide6', 'numpy', 'scipy', 'soundfile', 'pytest')}
    if 'PySide6.QtCore' in imports:
        versions['Qt'] = imports['PySide6.QtCore'].qVersion()
    return {
        'ok': all(row['ok'] for row in checks), 'application_version': app_version,
        'root': str(ROOT), 'python_executable': sys.executable,
        'python_version': platform.python_version(), 'platform': platform.platform(),
        'is_virtual_environment': sys.prefix != sys.base_prefix,
        'versions': versions, 'schema': schema, 'vocabulary': vocabulary,
        'checks': checks, 'optional_dependencies': optional, 'samples': samples,
        'limitations': [
            'This is a read-only import/schema check, not a GUI playback or detection accuracy test.',
            'Optional packages being installed does not establish that model weights or inference work.',
            'Missing BVH samples are expected in a source-only package.',
            'The checker does not download weights, run inference, open media, or modify raw data.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print a structured result instead of the readable report.')
    args = parser.parse_args(argv)
    result = inspect_environment()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('Annotation Studio local developer check')
        print('Project: ' + result['root'])
        print('Interpreter: ' + result['python_executable'])
        print('Platform: ' + result['platform'])
        for row in result['checks']:
            print(f"[{'OK' if row['ok'] else 'FAIL'}] {row['name']}: {row['detail']}")
        print('\nVersions: ' + ', '.join(f'{key}={value or "not installed"}' for key, value in result['versions'].items()))
        if result['vocabulary']:
            info = result['vocabulary']
            print(f"Vocabulary: {info['workspaces']} workspaces, {info['types']} types, {info['active_labels']} active labels.")
        print('\nOptional dependencies (metadata only; no inference):')
        for row in result['optional_dependencies']:
            state = row['version'] or ('module found; distribution metadata unavailable' if row['module_discoverable'] else 'not installed')
            print(f"  {row['distribution']}: {state} - {row['purpose']}")
        print('\nSample files (source-only packages may omit BVH):')
        for row in result['samples']:
            print(f"  {'present' if row['present'] else 'absent'}: {row['path']}")
        print('\n' + '\n'.join(result['limitations']))
        print('\nCore checks passed.' if result['ok'] else '\nCore checks failed. Fix the reported environment/import errors before launching.')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
