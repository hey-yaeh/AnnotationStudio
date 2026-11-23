"""Versioned projects, stable annotation IDs and portable annotation exports.

Raw media is only referenced. Saving writes a complete temporary file before an
atomic replacement, so a failed write does not truncate an existing project.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from copy import deepcopy
import csv
import json
import math
import os
import tempfile
import uuid
import xml.etree.ElementTree as ET

from .ontology import (LABEL_PRESETS, LEGACY_LABEL_PRESETS, WORKSPACE_CATEGORIES,
                       ACTIVITY_CHANNEL, ACTIVITY_EPISODE, LEGACY_MOTION_RELATION, RETIRED_PRIMITIVE_LABELS,
                       category_workspace, category_info, label_spec)
from .annotation_fields import validate_annotation_fields

CHANNELS = ('Head', 'Left Arm', 'Right Arm', 'Torso', 'Left Hand', 'Right Hand',
            'Left Leg', 'Right Leg', 'Root', 'Hands', 'Full Body', 'Face',
            'Emotion', 'Speech', 'Gaze', 'Props', 'Dyadic', 'Notes')
PRIMITIVE_CHANNELS = ('Left Arm', 'Right Arm', 'Head', 'Torso', 'Left Hand',
                      'Right Hand', 'Left Leg', 'Right Leg', 'Root', 'Full Body')
# Legacy categories remain available to vocabulary management and old projects.
# New-track menus use the active ontology instead of this compatibility list.
CATEGORIES = tuple(dict.fromkeys((*LABEL_PRESETS, *LEGACY_LABEL_PRESETS)))
LAYERS = ('L1 · Kinematics', 'L2 · Action / Gesture', 'L3 · Interaction', 'QC / Notes')
ROLES = ('R01', 'R02', 'Both', 'Scene', 'Unknown')
STATUSES = ('pending', 'approved', 'rejected')
TEMPORAL_KINDS = ('interval', 'point')
SCHEMA = 'annotationstudio.project'
SCHEMA_VERSION = 3
_ID_NAMESPACE = uuid.UUID('f9ee1185-2f20-5d88-bafd-9413131745c5')


def _new_id():
    return str(uuid.uuid4())


def _known_fields(cls, record):
    return {k: v for k, v in record.items() if k in cls.__dataclass_fields__}


def _finite(value):
    try:
        return not isinstance(value, bool) and math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def _check_unique(items, kind):
    ids = [item.id for item in items]
    if any(not isinstance(value, str) or not value for value in ids):
        raise ValueError(f'{kind} must have a nonempty string ID')
    if len(ids) != len(set(ids)):
        raise ValueError(f'Duplicate {kind} IDs; import each record only once')


@dataclass
class Asset:
    id: str
    kind: str
    role: str
    path: str
    offset_s: float = 0.0
    name: str = ''
    enabled: bool = True
    extra: dict = field(default_factory=dict)

    def serialize(self, base: Path) -> dict:
        record = asdict(self)
        # Do not accidentally turn an unavailable Windows absolute path into a
        # Linux relative path during cross-platform project inspection.
        if os.name != 'nt' and PureWindowsPath(self.path).is_absolute():
            record['relative_to_project'] = False
            return record
        target = Path(self.path).resolve()
        try:
            record['path'] = str(target.relative_to(base.resolve()))
            record['relative_to_project'] = True
        except ValueError:
            record['path'] = str(target)
            record['relative_to_project'] = False
        return record

    @classmethod
    def deserialize(cls, data: dict, base: Path):
        data = dict(data)
        relative = data.pop('relative_to_project', False)
        if relative:
            data['path'] = str((base / data['path'].replace('\\', '/')).resolve())
        return cls(**_known_fields(cls, data))


@dataclass
class Track:
    id: str
    name: str
    role: str = 'R01'
    workspace: str = 'Motion'
    category: str = 'Motion Primitive'
    channel: str = 'Right Arm'
    body_parts: list[str] = field(default_factory=list)
    visible: bool = True
    color: str | None = None
    order: int = 0
    extra: dict = field(default_factory=dict)


def track_temporal_kind(track: Track) -> str:
    """Return the creation default, without rewriting an existing annotation.

    An explicit track setting wins over ontology metadata. Historical tracks
    and custom categories without a setting continue to create intervals.
    An annotation's own ``temporal_kind`` remains authoritative when displayed.
    """
    kind = track.extra.get('temporal_kind', category_info(track.category).get('temporal_kind', 'interval'))
    if kind not in TEMPORAL_KINDS:
        raise ValueError('Track temporal_kind must be interval or point')
    return kind


@dataclass
class SceneObject:
    """A stable object instance, separate from a prop's geometry or trajectory.

    Annotation attributes refer to ``id``. Renaming or retiring this entry
    never changes those references or asserts that a contact was detected.
    ``extra['retired']`` hides an object from new suggestions, not history.
    """
    id: str
    name: str
    object_class: str = ''
    notes: str = ''
    extra: dict = field(default_factory=dict)

    @property
    def retired(self):
        return bool(self.extra.get('retired', False))

    def validate(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError('Scene object must have a nonempty string ID')
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('Scene object name cannot be empty')
        if not isinstance(self.object_class, str) or not isinstance(self.notes, str):
            raise ValueError('Scene object class and notes must be strings')
        if not isinstance(self.extra, dict):
            raise ValueError('Scene object extra must be a dictionary')
        if 'retired' in self.extra and not isinstance(self.extra['retired'], bool):
            raise ValueError('Scene object retired flag must be boolean')


@dataclass
class Label:
    id: str
    name: str
    category: str
    scope: str = 'project'
    aliases: list[str] = field(default_factory=list)
    definition: str = ''
    boundary_rule: str = ''
    deprecated: bool = False
    version: int = 1
    extra: dict = field(default_factory=dict)


def label_search_aliases(label):
    aliases = label.aliases
    if label.scope == 'core' and label.category in ('Motion Primitive', 'Interaction Event'):
        aliases = [*aliases, *label_spec(label.category, label.name)['aliases']]
    return list(dict.fromkeys(aliases))


def core_labels():
    """Build the current vocabulary plus stable historical label identities.

    Removing a preset from the active menu must not erase a label referenced by
    an old annotation. UUID5 inputs are the original v0.2 category/name pair.
    """
    result, seen = [], set()
    for presets, legacy in ((LABEL_PRESETS, False), (LEGACY_LABEL_PRESETS, True)):
        for category, names in presets.items():
            for name in names:
                key = (category, name)
                if key in seen:
                    continue
                seen.add(key)
                info = deepcopy(label_spec(category, name) or {})
                definition = info.pop('description', '')
                boundary_rule = info.pop('boundary_rule', '')
                aliases = list(info.pop('aliases', []))
                if legacy:
                    info['legacy'] = True
                result.append(Label(
                    id=str(uuid.uuid5(_ID_NAMESPACE, f'core:{category}:{name}')),
                    name=name, category=category, scope='core', aliases=aliases,
                    definition=definition, boundary_rule=boundary_rule,
                    deprecated=legacy, extra=info,
                ))
    return result


def track_relation_attributes(track: Track) -> dict:
    """Return explicit relation defaults for a new or reassigned annotation.

    ``role`` identifies an individual actor. A target is recorded only when the
    track explicitly supplies ``extra['target_role']``; R01 never implies R02.
    Both identifies the pair and records its participants rather than a target.
    The returned values are independent copies and never mutate the track.
    """
    if track.role == 'Both':
        return {'participants': ['R01', 'R02']}
    target = track.extra.get('target_role')
    return {'target_role': deepcopy(target)} if target else {}


@dataclass
class Annotation:
    id: str
    start_s: float
    end_s: float
    role: str = 'R01'
    channel: str = 'Right Arm'
    layer: str = 'L1 · Kinematics'
    label: str = 'Unlabeled'
    status: str = 'pending'
    source: str = 'manual'
    confidence: float | None = None
    reviewer: str = ''
    notes: str = ''
    tags: str = ''
    parent_id: str = ''
    category: str = 'Motion Primitive'
    track_id: str = ''
    label_id: str = ''
    original: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    # Appended so existing positional construction retains its v1/v2 meaning.
    temporal_kind: str = 'interval'

    def __post_init__(self):
        # Deserializers and plugin adapters may supply numeric strings or
        # NumPy scalars; normalize them before Qt/export arithmetic.
        if isinstance(self.start_s, bool) or isinstance(self.end_s, bool):
            raise ValueError('Annotation boundaries must be numeric times')
        self.start_s, self.end_s = float(self.start_s), float(self.end_s)

    def valid(self):
        if (self.temporal_kind not in TEMPORAL_KINDS or not _finite(self.start_s)
                or not _finite(self.end_s) or float(self.start_s) < 0):
            return False
        if self.is_point:
            return float(self.end_s) == float(self.start_s)
        return float(self.end_s) > float(self.start_s)

    @property
    def is_point(self):
        return self.temporal_kind == 'point'

    def snapshot(self):
        """State without recursively nesting provenance on every edit."""
        return {key: deepcopy(value) for key, value in asdict(self).items()
                if key not in ('original', 'history')}

    def record_change(self, before: dict, action='edit', reviewer=''):
        """Call after an edit; preserve the first observed state permanently."""
        before = {key: deepcopy(value) for key, value in before.items()
                  if key not in ('original', 'history')}
        if not self.original:
            self.original = before
        self.history.append({
            'at': datetime.now(timezone.utc).isoformat(),
            'action': action, 'reviewer': reviewer or self.reviewer,
            'before': before, 'after': self.snapshot(),
        })


class Project:
    def __init__(self, name='Untitled Interaction'):
        self.name = name
        self.assets: list[Asset] = []
        self.objects: list[SceneObject] = []
        self.annotations: list[Annotation] = []
        self.tracks: list[Track] = []
        self.labels: list[Label] = core_labels()
        # Mapping a model's previously unknown text becomes an explicit review
        # action. Refreshing the UI or adding vocabulary must not do it later.
        # This is session bookkeeping, reconstructed from saved v2 records.
        self._initialized_annotation_ids: set[str] = set()
        self.settings = {'duration_s': 120.0, 'world_frame_verified': False, 'project_note': ''}
        self.path: Path | None = None
        self.version = SCHEMA_VERSION
        # Starter tracks belong only to a newly created project. Migration and
        # saving must preserve a user's deliberate deletion of every track.
        self.ensure_primitive_tracks()
        self.ensure_activity_tracks()

    def add_asset(self, kind, role, path, **kwargs):
        kwargs.setdefault('name', Path(path).name)
        asset = Asset(id=kwargs.pop('id', _new_id()), kind=kind, role=role,
                      path=str(Path(path).resolve()), **kwargs)
        if any(item.id == asset.id for item in self.assets):
            raise ValueError('Duplicate asset ID')
        if not _finite(asset.offset_s):
            raise ValueError('Asset offset must be finite')
        self.assets.append(asset)
        return asset

    def add_track(self, **kwargs):
        if kwargs.get('category') == ACTIVITY_EPISODE:
            kwargs.setdefault('name', ACTIVITY_EPISODE)
            kwargs.setdefault('channel', ACTIVITY_CHANNEL)
            kwargs.setdefault('body_parts', [])
        kwargs.setdefault('id', _new_id())
        kwargs.setdefault('name', kwargs.get('channel', 'Right Arm'))
        kwargs.setdefault('order', max((track.order for track in self.tracks), default=-1) + 1)
        kwargs.setdefault('workspace', category_workspace(kwargs.get('category', 'Motion Primitive')))
        kwargs.setdefault('body_parts', [kwargs.get('channel', 'Right Arm')])
        track = Track(**kwargs)
        if self.get_track(track.id):
            raise ValueError('Duplicate track ID')
        # New tracks are explicit; loading does not normalize saved tracks.
        track.extra = deepcopy(track.extra)
        track.extra.setdefault('temporal_kind', track_temporal_kind(track))
        self.tracks.append(track)
        return track

    def ensure_primitive_tracks(self, roles=('R01', 'R02')):
        """Explicitly add missing anatomical primitive tracks, without repair.

        Matching uses actor/category/channel, so existing names, IDs, order,
        label subsets and visibility are untouched. Callers own the undo
        checkpoint. Loading/saving a project never invokes this helper to fill
        in intentionally absent tracks.
        """
        if isinstance(roles, (str, bytes)):
            raise ValueError('Pass a sequence of R01/R02 roles, not a string')
        try:
            selected = list(roles)
        except TypeError as error:
            raise ValueError('Pass a sequence of R01/R02 roles') from error
        if any(role not in ('R01', 'R02') for role in selected):
            raise ValueError('Primitive tracks are actor-specific: select R01 and/or R02')
        selected = list(dict.fromkeys(selected))
        existing = {(track.role, track.category, track.channel) for track in self.tracks}
        additions = []
        for role in selected:
            for channel in PRIMITIVE_CHANNELS:
                key = (role, 'Motion Primitive', channel)
                if key in existing:
                    continue
                additions.append(self.add_track(
                    name=channel, role=role, workspace='Motion',
                    category='Motion Primitive', channel=channel,
                    body_parts=[channel], extra={'label_scope': 0},
                ))
                existing.add(key)
        return additions

    def ensure_activity_tracks(self, roles=('R01', 'R02')):
        """Add missing whole-activity lanes while preserving authored tracks."""
        existing = {(track.role, track.category) for track in self.tracks}
        selected = tuple(dict.fromkeys(roles))
        if any(role not in ('R01', 'R02') for role in selected):
            raise ValueError('Select R01 and/or R02 for activity tracks')
        return [
            self.add_track(role=role, category=ACTIVITY_EPISODE, extra={'label_scope': 0})
            for role in selected if (role, ACTIVITY_EPISODE) not in existing
        ]

    def ensure_annotation_tracks(self, roles=('R01', 'R02')):
        """Explicitly supplement active annotation types without reorganizing.

        Existing role/type lanes count even when hidden, renamed, restricted,
        or assigned another channel. Primitives retain their part-specific
        helper. Pair types are added only when both actors are requested.
        QC lanes remain user-selected through Add track. Loading and saving
        never call this helper; the controller owns one undo checkpoint.
        """
        if isinstance(roles, (str, bytes)):
            raise ValueError('Pass a sequence of R01/R02 roles, not a string')
        try:
            selected = list(roles)
        except TypeError as error:
            raise ValueError('Pass a sequence of R01/R02 roles') from error
        if any(role not in ('R01', 'R02') for role in selected):
            raise ValueError('Select R01 and/or R02 for annotation tracks')
        selected = list(dict.fromkeys(selected))
        if not selected:
            return []
        additions = self.ensure_primitive_tracks(roles=selected)
        additions.extend(self.ensure_activity_tracks(roles=selected))
        existing = {(track.role, track.category) for track in self.tracks}
        for category in WORKSPACE_CATEGORIES['Overview']:
            if category in (ACTIVITY_EPISODE, 'Motion Primitive', 'QC / Notes'):
                continue
            info = category_info(category)
            if info.get('actor_scope') == 'pair':
                actors = ['Both'] if set(selected) == {'R01', 'R02'} else []
            else:
                actors = selected
            for role in actors:
                if (role, category) in existing:
                    continue
                channel = info.get('default_channel', 'Full Body')
                extra = {'label_scope': 0}
                if role == 'Both':
                    extra['participants'] = ['R01', 'R02']
                additions.append(self.add_track(
                    name=category, role=role, category=category, channel=channel,
                    body_parts=[channel], extra=extra,
                ))
                existing.add((role, category))
        return additions

    def add_object(self, name, object_class='', **kwargs):
        """Register an instance; callers own history checkpoints for the action."""
        obj = SceneObject(id=kwargs.pop('id', _new_id()), name=name,
                          object_class=object_class, **deepcopy(kwargs))
        obj.validate()
        if self.get_object(obj.id):
            raise ValueError('Duplicate scene object ID')
        self.objects.append(obj)
        return obj

    def get_object(self, object_id):
        return next((obj for obj in self.objects if obj.id == object_id), None)

    def update_object(self, object_id, **values):
        """Atomically edit display metadata; the persistent ID is immutable."""
        obj = self.get_object(object_id)
        if obj is None:
            raise ValueError('Unknown scene object ID')
        allowed = {'name', 'object_class', 'notes', 'extra'}
        if set(values) - allowed:
            raise ValueError('Only scene object name, class, notes and extra can be edited; ID is immutable')
        candidate = deepcopy(obj)
        for key, value in values.items():
            setattr(candidate, key, deepcopy(value))
        candidate.validate()
        obj.__dict__.update(deepcopy(candidate.__dict__))
        return obj

    def retire_object(self, object_id):
        obj = self.get_object(object_id)
        if obj is None:
            raise ValueError('Unknown scene object ID')
        return self.update_object(object_id, extra={**obj.extra, 'retired': True})

    def get_track(self, track_id):
        return next((track for track in self.tracks if track.id == track_id), None)

    def get_label(self, label_id):
        return next((label for label in self.labels if label.id == label_id), None)

    def labels_for(self, category, include_deprecated=False):
        return [label for label in self.labels if label.category == category
                and (include_deprecated or (
                    not self.label_is_deprecated(label)
                    and not (category == 'Motion Primitive'
                             and label.name.strip().casefold() in RETIRED_PRIMITIVE_LABELS)))]

    @staticmethod
    def label_is_deprecated(label):
        """Recognize retired presets without rewriting saved vocabulary records.

        A v0.2 project may contain its original ``deprecated=False`` value.
        Historical preset IDs are still hidden from new suggestions, while a
        user-renamed core label or a project custom label is not reclassified.
        """
        original_core_id = str(uuid.uuid5(_ID_NAMESPACE, f'core:{label.category}:{label.name}'))
        retired_preset = (label.scope == 'core' and label.id == original_core_id
                          and label.name in LEGACY_LABEL_PRESETS.get(label.category, ())
                          and label.name not in LABEL_PRESETS.get(label.category, ()))
        return label.deprecated or retired_preset

    @staticmethod
    def _label_scopes_for_track(track):
        return {0: ('core', 'project'), 1: ('project',), 2: ('temporary',)}.get(
            track.extra.get('label_scope', 0), ('core', 'project', 'temporary'))

    def _track_for_labels(self, track_or_id, require_saved=False):
        track = track_or_id if isinstance(track_or_id, Track) else self.get_track(track_or_id)
        if track is None:
            raise ValueError('Choose an existing annotation track')
        if require_saved:
            track = self.get_track(track.id)
            if track is None:
                raise ValueError('Choose an existing annotation track')
        return track

    @staticmethod
    def _matches_primitive_part(label, channel):
        """Read-only anatomical filtering, retaining unspecified custom text."""
        if channel in (None, ''):
            return True
        # Unknown/legacy channels remain browsable rather than losing all
        # suggestions because the current anatomy vocabulary is incomplete.
        if channel not in (*PRIMITIVE_CHANNELS, 'Hands'):
            return True
        extra = label.extra if isinstance(label.extra, dict) else {}
        parts = extra.get('body_parts')
        if not parts and label.scope == 'core':
            spec = label_spec(label.category, label.name)
            parts = spec.get('body_parts') if spec else None
        if not parts:
            return True
        if isinstance(parts, str):
            parts = [parts]
        if not isinstance(parts, (list, tuple, set, frozenset)):
            return True
        wanted = {'Left Hand', 'Right Hand', 'Hands'} if channel == 'Hands' else {channel}
        return any(part in wanted for part in parts if isinstance(part, str))

    def labels_for_track(self, track_or_id, include_deprecated=False, *, match_body_part=True):
        """Return the track's selectable Label objects in vocabulary order.

        Category and ``extra['label_scope']`` always apply. An absent
        ``allowed_label_ids`` means every permitted label; an explicit ``[]``
        means none. Deprecated labels are opt-in. The editor may separately
        show an annotation's existing label, so changing the list never hides
        its historical meaning. Motion Primitive suggestions also match the
        track channel unless ``match_body_part=False``; Full Body/unspecified
        channels browse all. A temporary Track is allowed for dialog previews.
        """
        track = self._track_for_labels(track_or_id)
        scopes = self._label_scopes_for_track(track)
        allowed = None
        if 'allowed_label_ids' in track.extra:
            values = track.extra['allowed_label_ids']
            if not isinstance(values, (list, tuple)) or any(not isinstance(i, str) for i in values):
                raise ValueError('Track allowed_label_ids must be a list of label IDs')
            allowed = set(values)
        return [label for label in self.labels_for(track.category, include_deprecated)
                if label.scope in scopes and (allowed is None or label.id in allowed)
                and (not match_body_part or track.category != 'Motion Primitive'
                     or self._matches_primitive_part(label, track.channel))]

    def set_track_label_ids(self, track_or_id, label_ids):
        """Set an explicit list atomically, or remove the restriction with None.

        IDs must already belong to this project and category. Scope/deprecation
        filtering still applies when the list is read. This helper does not add
        an undo checkpoint; its caller owns the complete user action.
        """
        track = self._track_for_labels(track_or_id, require_saved=True)
        if label_ids is None:
            track.extra.pop('allowed_label_ids', None)
            return track
        if isinstance(label_ids, (str, bytes)):
            raise ValueError('Pass a list of label IDs, not a label name')
        try:
            ids = list(label_ids)
        except TypeError as error:
            raise ValueError('Pass a list of label IDs or None') from error
        if any(not isinstance(label_id, str) for label_id in ids):
            raise ValueError('Label IDs must be strings')
        ids = list(dict.fromkeys(ids))
        for label_id in ids:
            label = self.get_label(label_id)
            if label is None or label.category != track.category:
                raise ValueError('Every allowed label must exist in the track category')
        track.extra['allowed_label_ids'] = ids
        return track

    def allow_label_on_track(self, track_or_id, label_or_id):
        """Add a project label to a restricted list; unrestricted stays full."""
        track = self._track_for_labels(track_or_id, require_saved=True)
        label_id = label_or_id.id if isinstance(label_or_id, Label) else label_or_id
        label = self.get_label(label_id)
        if label is None or label.category != track.category:
            raise ValueError('The label must exist in the track category')
        if 'allowed_label_ids' in track.extra:
            # Read before writing so a malformed setting cannot be half-mutated.
            self.labels_for_track(track, include_deprecated=True)
            ids = list(track.extra['allowed_label_ids'])
            if label.id not in ids:
                self.set_track_label_ids(track, [*ids, label.id])
        return label

    def resolve_label(self, name, category, include_deprecated=False):
        name = str(name).strip().casefold()
        return next((label for label in self.labels_for(category, include_deprecated)
                     if name in [label.name.casefold(), *[a.casefold() for a in label.aliases]]), None)

    def add_label(self, name, category, scope='project', **kwargs):
        name = str(name).strip()
        if not name:
            raise ValueError('Label name cannot be empty')
        if scope not in ('core', 'project', 'temporary'):
            raise ValueError('Label scope must be core, project or temporary')
        known = self.resolve_label(name, category)
        if known:
            return known
        label = Label(id=kwargs.pop('id', _new_id()), name=name,
                      category=category, scope=scope, **kwargs)
        if self.get_label(label.id):
            raise ValueError('Duplicate label ID')
        self.labels.append(label)
        return label

    def rename_label(self, label_id, name):
        label = self.get_label(label_id)
        if not label:
            raise ValueError('Unknown label ID')
        name = str(name).strip()
        if not name:
            raise ValueError('Label name cannot be empty')
        collision = self.resolve_label(name, label.category)
        if collision and collision.id != label_id:
            raise ValueError('This name or alias already belongs to another label')
        if name != label.name:
            old_name = label.name
            if old_name not in label.aliases:
                label.aliases.append(old_name)
            label.name = name
            label.version += 1
            for annotation in self.annotations:
                if annotation.label_id == label_id:
                    before = annotation.snapshot()
                    annotation.label = name
                    annotation.record_change(before, 'rename label')
        return label

    def merge_labels(self, source_id, target_id):
        source, target = self.get_label(source_id), self.get_label(target_id)
        if not source or not target or source_id == target_id:
            raise ValueError('Select two different existing labels')
        if source.category != target.category or self.label_is_deprecated(target):
            raise ValueError('Merge requires an active target in the same category')
        for alias in [source.name, *source.aliases]:
            if alias != target.name and alias not in target.aliases:
                target.aliases.append(alias)
        target.version += 1
        source.deprecated = True
        source.version += 1
        source.extra['replaced_by'] = target_id
        for track in self.tracks:
            allowed = track.extra.get('allowed_label_ids')
            if isinstance(allowed, list) and source_id in allowed:
                track.extra['allowed_label_ids'] = list(dict.fromkeys(
                    target_id if label_id == source_id else label_id for label_id in allowed))
        for annotation in self.annotations:
            if annotation.label_id == source_id:
                before = annotation.snapshot()
                annotation.label_id, annotation.label = target.id, target.name
                annotation.record_change(before, 'merge labels')
        return target

    def ensure_tracks(self):
        """Attach tracks and initialize new imports without reinterpreting history.

        Existing v2 records are registered on load, so their label mappings and
        original/history fields are not rewritten. New imports map known labels
        once; an unknown model output stays unmapped until explicit review.
        Track repair does not replace a heterogeneous legacy track's metadata.
        """
        for annotation in self.annotations:
            track = self.get_track(annotation.track_id)
            if track is None:
                track = next((item for item in self.tracks
                              if item.role == annotation.role
                              and item.category == annotation.category
                              and item.channel == annotation.channel), None)
                if track is None:
                    track = self.add_track(name=annotation.channel, role=annotation.role,
                                           category=annotation.category, channel=annotation.channel)
                annotation.track_id = track.id
            if annotation.id not in self._initialized_annotation_ids:
                if not annotation.label_id:
                    historical_motion = (annotation.category == LEGACY_MOTION_RELATION or
                                         (annotation.category == 'Motion Primitive' and
                                          str(annotation.label).strip().casefold() in RETIRED_PRIMITIVE_LABELS))
                    label = self.resolve_label(annotation.label, annotation.category,
                                               include_deprecated=historical_motion)
                    if label:
                        annotation.label_id = label.id
                if not annotation.original and annotation.source != 'manual':
                    annotation.original = annotation.snapshot()
                self._initialized_annotation_ids.add(annotation.id)
        return self.tracks

    def add_annotation(self, start_s, end_s, **kwargs):
        annotation = Annotation(id=kwargs.pop('id', _new_id()), start_s=start_s,
                                end_s=end_s, **kwargs)
        if not annotation.valid():
            raise ValueError('Annotation requires finite times: interval 0 <= start < end, point 0 <= start = end')
        if annotation.status not in STATUSES:
            raise ValueError('Editing is transient; save pending, approved or rejected')
        validate_annotation_fields(annotation.attributes)
        if any(item.id == annotation.id for item in self.annotations):
            raise ValueError('Duplicate annotation ID')
        self.annotations.append(annotation)
        self.ensure_tracks()
        return annotation

    def import_annotations(self, annotations, duplicate='skip'):
        """Preserve imported IDs and skip already-imported records by default."""
        if duplicate not in ('skip', 'error'):
            raise ValueError('duplicate must be skip or error')
        existing = {annotation.id for annotation in self.annotations}
        additions = []
        for annotation in annotations:
            if not annotation.valid():
                raise ValueError(f'Invalid annotation: {annotation.id}')
            validate_annotation_fields(annotation.attributes)
            if annotation.id in existing:
                if duplicate == 'error':
                    raise ValueError(f'Duplicate annotation ID: {annotation.id}')
                continue
            existing.add(annotation.id)
            additions.append(deepcopy(annotation))
        self.annotations.extend(additions)
        self.ensure_tracks()
        return additions

    def validate(self):
        for records, kind in ((self.annotations, 'annotation'), (self.assets, 'asset'),
                              (self.tracks, 'track'), (self.labels, 'label'),
                              (self.objects, 'scene object')):
            _check_unique(records, kind)
        for obj in self.objects:
            obj.validate()
        for annotation in self.annotations:
            if not annotation.valid():
                raise ValueError(f'Invalid times for annotation {annotation.id}')
            if annotation.status not in STATUSES:
                raise ValueError(f'Invalid saved state for annotation {annotation.id}')
            if annotation.confidence is not None and not _finite(annotation.confidence):
                raise ValueError(f'Nonfinite score for annotation {annotation.id}')
            validate_annotation_fields(annotation.attributes)
        for asset in self.assets:
            if not _finite(asset.offset_s):
                raise ValueError(f'Invalid offset for asset {asset.name}')

    def to_dict(self, project_path: Path | None = None):
        base = Path(project_path).parent if project_path else (self.path.parent if self.path else Path.cwd())
        return {'schema': SCHEMA, 'version': SCHEMA_VERSION, 'name': self.name,
                'assets': [asset.serialize(base) for asset in self.assets],
                'objects': [asdict(obj) for obj in self.objects],
                'annotations': [asdict(annotation) for annotation in self.annotations],
                'tracks': [asdict(track) for track in self.tracks],
                'labels': [asdict(label) for label in self.labels],
                'settings': deepcopy(self.settings)}

    def save(self, path: str | Path):
        self.ensure_tracks()
        self.validate()
        target = Path(path).resolve()
        payload = json.dumps(self.to_dict(target), ensure_ascii=False, indent=2, allow_nan=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            fd, filename = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
            temp_path = Path(filename)
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, target)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        self.path = target

    @classmethod
    def load(cls, path: str | Path):
        path = Path(path).resolve()
        obj = json.loads(path.read_text(encoding='utf-8-sig'))
        if obj.get('schema') not in (SCHEMA, 'ocumo.annotationstudio.project'):
            raise ValueError('Not an Annotation Studio project')
        version = obj.get('version', 1)
        if isinstance(version, bool) or not isinstance(version, int) or version > SCHEMA_VERSION or version < 1:
            raise ValueError(f'Unsupported project version: {version}')
        project = cls(obj.get('name', path.stem))
        project.settings.update(obj.get('settings', {}))
        project.assets = [Asset.deserialize(asset, path.parent) for asset in obj.get('assets', [])]
        project.objects = [SceneObject(**_known_fields(SceneObject, item)) for item in obj.get('objects', [])]
        project.annotations = [Annotation(**_known_fields(Annotation, annotation))
                               for annotation in obj.get('annotations', [])]
        if version >= 2:
            project._initialized_annotation_ids.update(annotation.id for annotation in project.annotations)
        project.tracks = [Track(**_known_fields(Track, track)) for track in obj.get('tracks', [])]
        if 'labels' in obj:
            project.labels = [Label(**_known_fields(Label, label)) for label in obj['labels']]
            present = {label.id for label in project.labels}
            project.labels.extend(label for label in core_labels() if label.id not in present)
        project.path = path
        project.ensure_tracks()
        project.validate()
        return project


def normalize_channel(text):
    text = str(text).lower().replace('_', ' ').strip()
    if 'head' in text or 'neck' in text: return 'Head'
    if 'left' in text and 'arm' in text: return 'Left Arm'
    if 'right' in text and 'arm' in text: return 'Right Arm'
    if 'left' in text and 'leg' in text: return 'Left Leg'
    if 'right' in text and 'leg' in text: return 'Right Leg'
    if 'left' in text and 'hand' in text: return 'Left Hand'
    if 'right' in text and 'hand' in text: return 'Right Hand'
    if 'torso' in text or 'spine' in text: return 'Torso'
    if 'root' in text or 'translation' in text or 'pelvis' in text: return 'Root'
    if 'dyadic' in text or 'interaction' in text: return 'Dyadic'
    if 'face' in text or 'expression' in text: return 'Face'
    if 'emotion' in text or 'affect' in text: return 'Emotion'
    if 'gaze' in text: return 'Gaze'
    if 'speech' in text or 'audio' in text or 'vocal' in text: return 'Speech'
    if 'prop' in text or 'object' in text: return 'Props'
    if 'hand' in text: return 'Hands'
    if 'note' in text: return 'Notes'
    return 'Full Body'


def _csv_json(row, key, expected, default):
    value = row.get(key)
    if not value:
        return default
    decoded = json.loads(value)
    if not isinstance(decoded, expected):
        raise ValueError(f'{key} must be JSON {expected.__name__}')
    return decoded


def import_annotation_csv(path: str | Path) -> list[Annotation]:
    """Read v2/v3 CSV or Stage2 review CSV. Corrected boundaries take precedence.

    Existing exported IDs survive round trips. Stage2 event IDs become stable
    IDs based on the CSV basename so importing a reviewed copy is deduplicable.
    Invalid rows raise an explicit error rather than silently losing records.
    """
    result, seen = [], set()
    with open(path, 'r', encoding='utf-8-sig', newline='') as source_file:
        for line, row in enumerate(csv.DictReader(source_file), 2):
            if not row or not any(value for value in row.values()):
                continue
            try:
                start = float(row.get('corrected_start_s') or row.get('start_s') or row.get('start') or 0)
                end = float(row.get('corrected_end_s') or row.get('end_s') or row.get('end') or 0)
                source = row.get('source') or 'imported-stage2'
                label = row.get('approved_L1_labels') or row.get('label') or row.get('kinematic_L1_labels') or 'Unlabeled'
                confidence = float(row['confidence']) if row.get('confidence') else None
                if confidence is not None and not _finite(confidence):
                    raise ValueError('confidence must be finite')
                status = row.get('status') or row.get('review_status') or 'pending'
                status = {'accepted': 'approved', 'candidate': 'pending', 'unreviewed': 'pending'}.get(status, status)
                if status not in STATUSES:
                    status = 'pending'
                annotation_id = row.get('id') or (
                    str(uuid.uuid5(_ID_NAMESPACE, f"csv:{Path(path).name}:{row['event_id']}"))
                    if row.get('event_id') else _new_id())
                if annotation_id in seen:
                    raise ValueError(f'duplicate annotation ID {annotation_id}')
                annotation = Annotation(
                    id=annotation_id, start_s=start, end_s=end,
                    role=row.get('role') or 'R01',
                    channel=row.get('channel') or normalize_channel(row.get('body_channel') or ''),
                    layer=row.get('layer') or 'L1 · Kinematics', label=label,
                    source=source, confidence=confidence, reviewer=row.get('reviewer') or '',
                    notes=row.get('notes') or '', status=status, tags=row.get('tags') or '',
                    parent_id=row.get('parent_id') or '', category=row.get('category') or 'Motion Primitive',
                    track_id=row.get('track_id') or '', label_id=row.get('label_id') or '',
                    original=_csv_json(row, 'original', dict, {}),
                    history=_csv_json(row, 'history', list, []),
                    attributes=_csv_json(row, 'attributes', dict, {}),
                    temporal_kind=row.get('temporal_kind') or 'interval',
                )
                if not annotation.valid():
                    raise ValueError('require finite times: interval 0 <= start < end, point 0 <= start = end')
                validate_annotation_fields(annotation.attributes)
                # An explicitly exported empty provenance object is meaningful
                # for a manual annotation. Only legacy/external rows synthesize it.
                if not annotation.original and not row.get('original'):
                    annotation.original = annotation.snapshot()
                    for key in ('start_s', 'end_s'):
                        if row.get(key):
                            original_time = float(row[key])
                            if _finite(original_time):
                                annotation.original[key] = original_time
                    annotation.original['label'] = row.get('label') or row.get('kinematic_L1_labels') or label
                if row.get('event_id'):
                    annotation.attributes.setdefault('import_event_id', row['event_id'])
                seen.add(annotation.id)
                result.append(annotation)
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError(f'CSV row {line}: {error}') from error
    return result


def export_csv(annotations: list[Annotation], path: str | Path):
    _check_unique(annotations, 'annotation')
    if any(not annotation.valid() for annotation in annotations):
        raise ValueError('Cannot export invalid annotation times')
    for annotation in annotations:
        validate_annotation_fields(annotation.attributes)
    fields = list(Annotation.__dataclass_fields__)
    with open(path, 'w', newline='', encoding='utf-8-sig') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for annotation in sorted(annotations, key=lambda item: (item.start_s, item.role, item.id)):
            record = asdict(annotation)
            for key in ('original', 'history', 'attributes'):
                record[key] = json.dumps(record[key], ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            writer.writerow(record)


def export_eaf(annotations: list[Annotation], path: str | Path):
    """Export non-overlapping ELAN tiers; overlaps occupy numbered subtiers.

    EAF is millisecond-resolution. A shorter positive interval becomes 1 ms;
    that quantization never changes the original project or CSV timings.
    Points have no duration and are rejected before touching the destination.
    """
    _check_unique(annotations, 'annotation')
    if any(not annotation.valid() for annotation in annotations):
        raise ValueError('Cannot export invalid annotation times')
    if any(annotation.is_point for annotation in annotations):
        raise ValueError('ELAN EAF export supports intervals only. Point events have no duration; '
                         'use JSON/CSV or export an interval-only selection.')
    quantized = []
    for annotation in annotations:
        start = max(0, int(round(annotation.start_s * 1000)))
        end = max(start + 1, int(round(annotation.end_s * 1000)))
        quantized.append((annotation, start, end))
    root = ET.Element('ANNOTATION_DOCUMENT', {
        'AUTHOR': 'Annotation Studio', 'DATE': datetime.now(timezone.utc).isoformat(),
        'FORMAT': '3.0', 'VERSION': '3.0',
    })
    ET.SubElement(root, 'HEADER', {'MEDIA_FILE': '', 'TIME_UNITS': 'milliseconds'})
    time_order = ET.SubElement(root, 'TIME_ORDER')
    times = sorted({time for _, start, end in quantized for time in (start, end)})
    slots = {time: f'ts{index + 1}' for index, time in enumerate(times)}
    for time in times:
        ET.SubElement(time_order, 'TIME_SLOT', {'TIME_SLOT_ID': slots[time], 'TIME_VALUE': str(time)})
    tiers, lane_ends = {}, {}
    for index, (annotation, start, end) in enumerate(sorted(quantized, key=lambda item: (item[1], item[2], item[0].id)), 1):
        base = f'{annotation.role} | {annotation.channel} | {annotation.category} | {annotation.track_id or annotation.layer}'
        ends = lane_ends.setdefault(base, [])
        lane = next((lane for lane, previous_end in enumerate(ends) if previous_end <= start), len(ends))
        if lane == len(ends):
            ends.append(end)
        else:
            ends[lane] = end
        tier_name = f'{base} | lane {lane + 1}'
        if tier_name not in tiers:
            tiers[tier_name] = ET.SubElement(root, 'TIER', {
                'TIER_ID': tier_name, 'PARTICIPANT': annotation.role,
                'LINGUISTIC_TYPE_REF': 'default-lt',
            })
        entry = ET.SubElement(tiers[tier_name], 'ANNOTATION')
        aligned = ET.SubElement(entry, 'ALIGNABLE_ANNOTATION', {
            'ANNOTATION_ID': f'a{index}', 'TIME_SLOT_REF1': slots[start], 'TIME_SLOT_REF2': slots[end],
        })
        ET.SubElement(aligned, 'ANNOTATION_VALUE').text = annotation.label
    ET.SubElement(root, 'LINGUISTIC_TYPE', {
        'LINGUISTIC_TYPE_ID': 'default-lt', 'TIME_ALIGNABLE': 'true', 'GRAPHIC_REFERENCES': 'false',
    })
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
