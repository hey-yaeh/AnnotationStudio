"""Read-only, lossless CSV tables and per-type export bundles.

The native Annotation fields remain authoritative and importable. Additional
columns are convenient views of stored metadata; they never reclassify a
record, apply an asset offset, or create an object. Save project remains the
separate route for the complete vocabulary, tracks and media references.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import unicodedata
import uuid

from . import __version__
from .annotation_fields import (
    OBJECT_DIRECTIONAL_LABELS, active_secondary_object_id,
    annotation_object_ids, spatial_label_name, validate_annotation_fields,
)
from .models import Annotation, SCHEMA, SCHEMA_VERSION, STATUSES, _check_unique, _finite
from .ontology import WORKSPACE_CATEGORIES, category_workspace


REVIEW_STATES = ('accepted', 'candidates_accepted', 'all')
NATIVE_COLUMNS = tuple(Annotation.__dataclass_fields__)
DERIVED_COLUMNS = (
    'workspace', 'track_name', 'annotation_fields_version',
    'object_id', 'object_name', 'object_class',
    'secondary_object_id', 'secondary_object_name', 'spatial_reference_frame',
    'effector', 'target_role', 'affect_mode', 'affect_intensity',
    'affect_valence', 'affect_arousal',
)
CSV_COLUMNS = NATIVE_COLUMNS + DERIVED_COLUMNS
OBJECT_COLUMNS = ('object_id', 'object_name', 'object_class', 'notes',
                  'retired', 'missing', 'reference_count', 'extra')
_WINDOWS_RESERVED = {'con', 'prn', 'aux', 'nul',
                     *(f'com{i}' for i in range(1, 10)),
                     *(f'lpt{i}' for i in range(1, 10))}


def _categories(categories):
    if categories is None:
        return None
    if isinstance(categories, str):
        raise ValueError('Annotation types must be a list, not a single string.')
    result = tuple(dict.fromkeys(categories))
    if any(not isinstance(value, str) for value in result):
        raise ValueError('Annotation type names must be strings.')
    return result


def _review_matches(annotation, review_state):
    if review_state == 'accepted':
        return annotation.status == 'approved'
    if review_state == 'candidates_accepted':
        return annotation.status in {'pending', 'approved'}
    return True


def select_annotations(project, review_state='accepted', categories=None):
    """Select committed records across the project, never only visible tracks.

    ``None`` means every type; an empty iterable means no types. Returned
    objects belong to the project and are only read by the exporters.
    """
    if review_state not in REVIEW_STATES:
        raise ValueError('Choose accepted, candidates_accepted or all review states.')
    categories = _categories(categories)
    chosen = None if categories is None else set(categories)
    return sorted((annotation for annotation in project.annotations
                   if _review_matches(annotation, review_state)
                   and (chosen is None or annotation.category in chosen)),
                  key=lambda item: (item.start_s, item.role, item.id))


def _type_order(category):
    ordered = tuple(WORKSPACE_CATEGORIES['Overview'])
    if category in ordered:
        return (0, ordered.index(category), '', '')
    return (1, 0, category.casefold(), category)


def available_export_types(project, review_state='accepted'):
    """Return counts for authored track/annotation types, including old types."""
    selected = select_annotations(project, review_state)
    total = Counter(annotation.category for annotation in project.annotations)
    counts = Counter(annotation.category for annotation in selected)
    types = set(total) | {track.category for track in project.tracks}
    workspaces = {}
    tracks = {track.id: track for track in project.tracks}
    for track in project.tracks:
        workspaces.setdefault(track.category, set()).add(track.workspace)
    for annotation in project.annotations:
        track = tracks.get(annotation.track_id)
        workspaces.setdefault(annotation.category, set()).add(
            track.workspace if track is not None else category_workspace(annotation.category))
    return [{'category': category,
             'workspace': ' / '.join(sorted(workspaces.get(category, {category_workspace(category)}))),
             'total_count': total[category], 'count': counts[category]}
            for category in sorted(types, key=_type_order)]


def _safe_component(value, fallback, *, lower=True, max_length=48):
    text = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_')
    if lower:
        text = text.lower()
    if not text:
        text = fallback + '_' + hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:8]
    if text.casefold() in _WINDOWS_RESERVED:
        text = fallback + '_' + text
    return text[:max_length].rstrip('_') or fallback


def suggested_export_stem(project):
    """A compact portable stem, without directory components or extensions."""
    if project.path:
        text = Path(project.path).name
        for suffix in ('.studio.json', '.ocumo.json', '.json'):
            if text.lower().endswith(suffix):
                text = text[:-len(suffix)]
                break
    else:
        text = project.name
    return _safe_component(text, 'project', lower=False)


def category_export_stem(category):
    aliases = {'Action / HOI': 'hoi', 'Perceived Affect': 'affect'}
    return aliases.get(category, _safe_component(category, 'type'))


def _category_filenames(categories, stem):
    bases = {category: category_export_stem(category) for category in categories}
    counts = Counter(value.casefold() for value in bases.values())
    used = {'annotations', 'objects', 'export_manifest'}
    result = {}
    for category in sorted(categories, key=_type_order):
        base = bases[category]
        if counts[base.casefold()] > 1 or base.casefold() in used:
            base = base[:36] + '_' + hashlib.sha256(category.encode('utf-8')).hexdigest()[:10]
        candidate, index = base, 2
        while candidate.casefold() in used:
            candidate = f'{base}_{index}'
            index += 1
        used.add(candidate.casefold())
        result[category] = f'{stem}_{candidate}.csv'
    return result


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _scalar(value):
    # Unknown containers remain in the original attributes JSON, rather than
    # being coerced into a made-up scalar rating or target identifier.
    return value if value is not None and isinstance(value, (str, int, float, bool)) else ''


def _dict(value):
    return value if isinstance(value, dict) else {}


def _string(value):
    return value if isinstance(value, str) else ''


def _prepare(project, review_state, categories):
    annotations = select_annotations(project, review_state, categories)
    if not annotations:
        raise ValueError('No annotations match the selected types and review state.')
    _check_unique(annotations, 'annotation')
    _check_unique(project.objects, 'scene object')
    _check_unique(project.tracks, 'track')
    _check_unique(project.labels, 'label')
    objects = {obj.id: obj for obj in project.objects}
    tracks = {track.id: track for track in project.tracks}
    rows, reference_counts = [], Counter()
    for annotation in annotations:
        if not annotation.valid():
            raise ValueError(f'Invalid annotation times: {annotation.id}')
        if annotation.status not in STATUSES:
            raise ValueError(f'Invalid review state: {annotation.id}')
        if annotation.confidence is not None and not _finite(annotation.confidence):
            raise ValueError(f'Nonfinite confidence: {annotation.id}')
        if not isinstance(annotation.original, dict) or not isinstance(annotation.history, list):
            raise ValueError(f'Invalid annotation provenance: {annotation.id}')
        validate_annotation_fields(annotation.attributes)
        row = asdict(annotation)
        for key in ('original', 'history', 'attributes'):
            row[key] = _json(row[key])
        attrs = annotation.attributes
        spatial, affect = _dict(attrs.get('spatial_relation')), _dict(attrs.get('affect'))
        primary = _string(attrs.get('object_id'))
        secondary = active_secondary_object_id(project, annotation)
        obj, other = objects.get(primary), objects.get(secondary)
        track = tracks.get(annotation.track_id)
        directional = (annotation.category == 'Object Spatial Relation'
                       and spatial_label_name(project, annotation) in OBJECT_DIRECTIONAL_LABELS)
        row.update({
            'workspace': track.workspace if track is not None else category_workspace(annotation.category),
            'track_name': track.name if track is not None else '',
            'annotation_fields_version': _scalar(attrs.get('annotation_fields_version')),
            'object_id': primary, 'object_name': obj.name if obj is not None else '',
            'object_class': obj.object_class if obj is not None else '',
            'secondary_object_id': secondary,
            'secondary_object_name': other.name if other is not None else '',
            'spatial_reference_frame': _string(spatial.get('reference_frame')) if directional else '',
            'effector': _scalar(attrs.get('effector')),
            'target_role': _scalar(attrs.get('target_role')),
            'affect_mode': _scalar(affect.get('annotation_mode')),
            'affect_intensity': _scalar(affect.get('intensity')),
            'affect_valence': _scalar(affect.get('valence')),
            'affect_arousal': _scalar(affect.get('arousal')),
        })
        rows.append(row)
        reference_counts.update(annotation_object_ids(annotation))
    object_rows = []
    for object_id in sorted(reference_counts):
        obj = objects.get(object_id)
        if obj is not None:
            obj.validate()
        object_rows.append({
            'object_id': object_id,
            'object_name': obj.name if obj is not None else '',
            'object_class': obj.object_class if obj is not None else '',
            'notes': obj.notes if obj is not None else '',
            'retired': obj.retired if obj is not None else '',
            'missing': obj is None,
            'reference_count': reference_counts[object_id],
            'extra': _json(obj.extra if obj is not None else {}),
        })
    return rows, object_rows


def _csv_bytes(rows, fields):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8-sig')


def _path_identity(path):
    if os.name != 'nt' and PureWindowsPath(str(path)).is_absolute():
        return 'windows:' + str(PureWindowsPath(str(path))).casefold()
    return os.path.normcase(str(Path(path).resolve()))


def _protect_inputs(project, paths):
    protected = {_path_identity(asset.path) for asset in project.assets if asset.path}
    if project.path:
        protected.add(_path_identity(project.path))
    for path in paths:
        if _path_identity(path) in protected:
            raise ValueError('Choose a new export path; source media and the project file are read-only export inputs.')


def _write_bytes(path, payload):
    with Path(path).open('wb') as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def _path_units(path):
    return len(str(path).encode('utf-16-le', errors='surrogatepass')) // 2


def _bundle_directory_base(parent, stem, filenames, stamp, token, *, windows=False):
    """Budget final leaf paths, not just the shorter staging directory.

    A Windows directory rename can succeed while its resulting file paths
    exceed MAX_PATH. Keep bundles readable by ordinary Windows tools without
    requiring a machine policy change or extended-path prefixes.
    """
    suffix = f'_exports_{stamp}_{token}'
    if windows:
        # Two separators plus a normal collision suffix (_02) need room too.
        budget = 259 - _path_units(parent) - 2 - _path_units(suffix) - 3
        budget -= max(_path_units(name) for name in filenames)
        while stem and _path_units(stem) > budget:
            stem = stem[:-1]
        if not stem:
            raise ValueError('The Windows export folder is too deep. Choose a shorter parent folder; no export bundle was published.')
    return stem + suffix


def _summary(rows, review_state, categories):
    counts = Counter(row['category'] for row in rows)
    return {'annotation_count': len(rows), 'category_count': len(counts),
            'type_counts': {category: counts[category] for category in sorted(counts, key=_type_order)},
            'review_state': review_state,
            'categories': sorted(counts, key=_type_order),
            'requested_categories': None if categories is None else list(categories)}


def export_annotation_csv(project, path, *, review_state='accepted', categories=None):
    """Write one enriched, re-importable CSV atomically at an explicit path."""
    categories = _categories(categories)
    rows, _ = _prepare(project, review_state, categories)
    payload = _csv_bytes(rows, CSV_COLUMNS)
    target = Path(path).resolve()
    _protect_inputs(project, [target])
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        descriptor, filename = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
        os.close(descriptor)
        temporary = Path(filename)
        _write_bytes(temporary, payload)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return dict(_summary(rows, review_state, categories), path=str(target),
                paths=[str(target)], csv_paths=[str(target)], layout='combined')


def export_annotation_bundle(project, parent_directory, *, review_state='accepted',
                             categories=None, layout='by_type'):
    """Create a fresh folder with partitioned CSVs and metadata sidecars.

    Every payload is prepared before touching the destination. Files are
    written in a private sibling staging directory, then the complete bundle
    is renamed into a new, randomly named directory. Existing exports are
    never selected as destinations or removed by cleanup.
    """
    if layout not in {'by_type', 'both'}:
        raise ValueError('A CSV bundle layout must be by_type or both.')
    categories = _categories(categories)
    rows, object_rows = _prepare(project, review_state, categories)
    summary = _summary(rows, review_state, categories)
    stem = suggested_export_stem(project)
    filenames = _category_filenames(summary['categories'], stem)
    payloads, tables = {}, []
    if layout == 'both':
        filename = f'{stem}_annotations.csv'
        payloads[filename] = _csv_bytes(rows, CSV_COLUMNS)
        tables.append({'kind': 'combined', 'filename': filename, 'row_count': len(rows)})
    for category, filename in filenames.items():
        subset = [row for row in rows if row['category'] == category]
        payloads[filename] = _csv_bytes(subset, CSV_COLUMNS)
        tables.append({'kind': 'annotation_type', 'category': category,
                       'filename': filename, 'row_count': len(subset)})
    objects_filename = f'{stem}_objects.csv'
    payloads[objects_filename] = _csv_bytes(object_rows, OBJECT_COLUMNS)
    inventory = available_export_types(project, review_state)
    requested = {item['category'] for item in inventory} if categories is None else set(categories)
    manifest = {
        'schema': 'annotationstudio.annotation_export', 'version': 1,
        'application_version': __version__,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_project': {'name': project.name, 'schema': SCHEMA, 'version': SCHEMA_VERSION,
                           'filename': Path(project.path).name if project.path else None},
        'layout': layout, **summary,
        'skipped_empty_categories': sorted(requested - set(summary['categories']), key=_type_order),
        'time_basis': {'clock': 'project_master', 'unit': 'seconds',
                       'interval': '[start_s, end_s)', 'point': 'start_s == end_s; temporal_kind=point',
                       'source_offsets_reapplied': False},
        'csv_encoding': 'UTF-8 with BOM', 'native_columns': list(NATIVE_COLUMNS),
        'derived_columns': list(DERIVED_COLUMNS), 'tables': tables,
        'objects': {'filename': objects_filename, 'row_count': len(object_rows),
                    'scope': 'References in exported records, including retained inactive secondary references.',
                    'missing': 'A missing row is an unresolved reference, not a newly registered object.'},
        'interpretation': {
            'category': 'The annotation category defines each partition, including custom and historical types.',
            'workspace': 'Authored track workspace when known; category fallback for orphan records.',
            'spatial': 'Flat second targets and direction frames are active-relation views; all retained values remain in attributes.',
            'affect': 'Stored scalar values are copied without normalization. Unknown is blank; zero remains zero. The stored mode governs active ratings; retained inactive scores may also be present.',
            'round_trip': 'Native fields are authoritative. Extra columns are convenience views and are ignored on annotation CSV import.',
            'complete_project': 'Use Save project for the complete registry, vocabulary, tracks, settings and media references.',
        },
        'files': [{'filename': filename, 'bytes': len(payload),
                   'sha256': hashlib.sha256(payload).hexdigest()}
                  for filename, payload in payloads.items()],
    }
    manifest_filename = f'{stem}_export_manifest.json'
    payloads[manifest_filename] = (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    parent = Path(parent_directory).resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    token = uuid.uuid4().hex[:12]
    base = _bundle_directory_base(parent, stem, payloads, stamp, token, windows=os.name == 'nt')
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.annotation_export_', dir=parent))
    destination = None
    try:
        for filename, payload in payloads.items():
            _write_bytes(staging / filename, payload)
        index = 1
        while True:
            candidate = parent / (base if index == 1 else f'{base}_{index:02d}')
            if not candidate.exists():
                if os.name == 'nt' and any(_path_units(candidate / name) > 259 for name in payloads):
                    raise ValueError('The Windows export path is too long. Choose a shorter parent folder; no export bundle was published.')
                _protect_inputs(project, [candidate / filename for filename in payloads])
                # A random destination prevents normal concurrent export races;
                # all already-existing paths, even empty directories, are skipped.
                os.rename(staging, candidate)
                destination = candidate
                break
            index += 1
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    paths = [str(destination / filename) for filename in payloads]
    return dict(summary, layout=layout, directory=str(destination), paths=paths,
                csv_paths=[str(destination / table['filename']) for table in tables],
                objects_path=str(destination / objects_filename),
                manifest_path=str(destination / manifest_filename),
                tables=tables)
