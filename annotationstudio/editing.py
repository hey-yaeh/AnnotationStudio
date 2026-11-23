"""Whole-project undo/redo; annotation drafts remain a UI concern."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import uuid

from .models import Annotation, label_search_aliases, track_relation_attributes, track_temporal_kind
from .ontology import LEGACY_MOTION_RELATION, RETIRED_PRIMITIVE_LABELS, is_legacy_category
from .annotation_fields import validate_annotation_fields, has_affect_rating, spatial_accept_error
from .affect_display import DIMENSIONAL_AFFECT_LABEL_ID


def _track_layer(track):
    return ('L1 · Kinematics' if track.workspace in ('Motion', 'Spatial') else
            'L3 · Interaction' if track.workspace == 'Social' else
            'QC / Notes' if track.workspace == 'Review' else 'L2 · Action / Gesture')


def motion_accept_error(prospective, existing):
    if (prospective.category == 'Motion Primitive'
            and prospective.label.strip().casefold() in RETIRED_PRIMITIVE_LABELS
            and not (existing and existing.status == 'approved'
                     and existing.category == prospective.category
                     and existing.track_id == prospective.track_id
                     and existing.label.strip() == prospective.label.strip()
                     and prospective.label_id in ('', existing.label_id))):
        return 'Choose a specific movement form before accepting, or keep this record as a candidate.'
    return ''


class ProjectHistory:
    """Checkpoint immediately BEFORE a committed user action.

    Restoring keeps the same Project instance and current file path, so widgets
    holding the project and Save As destinations remain valid. All persistent
    data (tracks, labels, annotations, objects, assets and settings) is undoable together.
    """
    def __init__(self, limit=80):
        self.limit = max(1, int(limit))
        self._undo = []
        self._redo = []
        self._saved = None

    @staticmethod
    def _state(project):
        return deepcopy({key: value for key, value in project.__dict__.items() if key != 'path'})

    @staticmethod
    def _restore(project, state):
        path = project.path
        project.__dict__.clear()
        project.__dict__.update(deepcopy(state))
        project.path = path

    @staticmethod
    def _fingerprint(project):
        # Absolute asset paths make the dirty flag independent of Save As.
        data = project.to_dict()
        data['assets'] = [vars(asset) for asset in project.assets]
        encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
        return hashlib.sha256(encoded).digest()

    def checkpoint(self, project):
        self._undo.append(self._state(project))
        self._undo = self._undo[-self.limit:]
        self._redo.clear()

    def undo(self, project):
        if not self._undo:
            return False
        self._redo.append(self._state(project))
        self._restore(project, self._undo.pop())
        return True

    def redo(self, project):
        if not self._redo:
            return False
        self._undo.append(self._state(project))
        self._restore(project, self._redo.pop())
        return True

    def mark_saved(self, project):
        self._saved = self._fingerprint(project)

    def is_dirty(self, project):
        return self._saved != self._fingerprint(project)

    def clear(self):
        self._undo.clear()
        self._redo.clear()

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)


class EditSession:
    """Isolated annotation draft; only accept/save_candidate writes the project.

    The view decides how to prompt before switching away from a dirty draft.
    Merely selecting, resizing or cancelling never changes saved annotations.
    """
    def __init__(self, project, history):
        self.project = project
        self.history = history
        self.draft: Annotation | None = None
        self.is_new = False
        self._base: Annotation | None = None
        self._annotation_id = None

    def begin(self, annotation_id):
        annotation = next((item for item in self.project.annotations if item.id == annotation_id), None)
        if annotation is None:
            raise ValueError('Annotation no longer exists')
        self._base = deepcopy(annotation)
        self.draft = deepcopy(annotation)
        self.is_new = False
        self._annotation_id = annotation.id
        return self.draft

    def create(self, start, end, track_id):
        track = self.project.get_track(track_id)
        if track is None:
            raise ValueError('Choose an existing annotation track')
        return self._create(start, end, track, track_temporal_kind(track))

    def create_point(self, time_s, track_id):
        """Create one timestamp, not a short artificial interval.

        A dedicated point track is the usual UI route. The explicit API also
        permits point markers on a mixed historical/custom track.
        """
        track = self.project.get_track(track_id)
        if track is None:
            raise ValueError('Choose an existing annotation track')
        return self._create(time_s, time_s, track, 'point')

    def _create(self, start, end, track, temporal_kind):
        if track.category == LEGACY_MOTION_RELATION:
            raise ValueError('Activity Relation is a historical track. Choose an active track to add an annotation.')
        candidate = Annotation(id=str(uuid.uuid4()), start_s=start, end_s=end,
                               role=track.role, channel=track.channel, category=track.category,
                               track_id=track.id, layer=_track_layer(track), source='manual',
                               temporal_kind=temporal_kind,
                               attributes={'body_parts': deepcopy(track.body_parts),
                                           **track_relation_attributes(track)})
        if not candidate.valid():
            raise ValueError('Draft requires finite times: interval 0 <= start < end, point 0 <= start = end')
        self.draft = candidate
        self._base = None
        self._annotation_id = candidate.id
        self.is_new = True
        return self.draft

    @property
    def dirty(self):
        return self.draft is not None and (
            self.is_new or self._base is None or self.draft.snapshot() != self._base.snapshot()
        )

    def update(self, **values):
        if self.draft is None:
            raise ValueError('No active annotation draft')
        protected = {'id', 'source', 'original', 'history', 'temporal_kind'}
        if protected.intersection(values):
            raise ValueError('Annotation identity, temporal type and original provenance cannot be edited')
        unknown = set(values) - set(Annotation.__dataclass_fields__)
        if unknown:
            raise ValueError(f'Unknown annotation fields: {", ".join(sorted(unknown))}')
        candidate = deepcopy(self.draft)
        for key, value in values.items():
            if key in ('start_s', 'end_s'):
                if isinstance(value, bool):
                    raise ValueError('Annotation boundaries must be numeric times')
                value = float(value)
            setattr(candidate, key, deepcopy(value))
        if candidate.is_point:
            # A point has one time. A single-boundary change moves it; two
            # supplied boundaries must agree, otherwise validation fails
            # atomically and the original draft is preserved.
            if 'start_s' in values and 'end_s' not in values:
                candidate.end_s = candidate.start_s
            elif 'end_s' in values and 'start_s' not in values:
                candidate.start_s = candidate.end_s
        if not isinstance(candidate.attributes, dict):
            raise ValueError('Annotation attributes must be a dictionary')
        validate_annotation_fields(candidate.attributes)
        if 'label' in values and 'label_id' not in values:
            candidate.label_id = ''
        if 'track_id' in values:
            track = self.project.get_track(candidate.track_id)
            if track is None:
                raise ValueError('Choose an existing annotation track')
            if track.id != self.draft.track_id:
                # Reassign only on an actual move. Re-sending the same track ID
                # must not normalize an old heterogeneous track's annotations.
                category_changed = candidate.category != track.category
                candidate.role, candidate.channel = track.role, track.channel
                candidate.category, candidate.layer = track.category, _track_layer(track)
                candidate.attributes['body_parts'] = deepcopy(track.body_parts)
                for key in ('target_role', 'participants'):
                    candidate.attributes.pop(key, None)
                candidate.attributes.update(track_relation_attributes(track))
                if category_changed:
                    candidate.label_id = ''
                    if 'label' not in values:
                        candidate.label = 'Unlabeled'
        if not candidate.valid():
            raise ValueError('Draft requires finite times: interval 0 <= start < end, point 0 <= start = end')
        self.draft = candidate

    def accept(self, reviewer=''):
        return self._commit('approved', reviewer)

    def save_candidate(self):
        return self._commit('pending', '')

    def _commit(self, status, reviewer):
        if self.draft is None:
            raise ValueError('No active annotation draft')
        candidate = deepcopy(self.draft)
        if candidate.id != self._annotation_id or not candidate.valid():
            raise ValueError('Draft identity or time span is invalid')
        validate_annotation_fields(candidate.attributes)
        label_name = str(candidate.label).strip()
        if status == 'approved' and label_name.casefold() in ('', 'unlabeled'):
            raise ValueError('Choose a label before accepting this annotation')
        candidate.label = label_name or 'Unlabeled'
        existing = next((item for item in self.project.annotations if item.id == candidate.id), None)
        if (self.is_new and existing is not None) or (not self.is_new and existing is None):
            raise ValueError('Annotation changed outside this edit session; reopen the segment')
        track = self.project.get_track(candidate.track_id)
        if track is None:
            raise ValueError('The annotation track no longer exists')
        if existing is not None and existing.snapshot() != self._base.snapshot():
            raise ValueError('Annotation changed outside this edit session; reopen the segment')
        if track.category == LEGACY_MOTION_RELATION and (existing is None or existing.track_id != track.id):
            raise ValueError('Activity Relation only supports edits to existing annotations.')

        unchanged_label = (existing is not None
                           and candidate.track_id == existing.track_id
                           and candidate.category == existing.category
                           and candidate.label == str(existing.label).strip()
                           and candidate.label_id in ('', existing.label_id))
        # Current labels can outlive their preset, be deliberately excluded from
        # a newly shortened list, or belong to a heterogeneous historical track.
        # Editing their boundaries must preserve their meaning and identity.
        preserve_mapping = (unchanged_label and (existing.label_id
                            or status != 'approved' or existing.status == 'approved'))
        create_label = False
        if preserve_mapping:
            label = self.project.get_label(existing.label_id)
            candidate.label, candidate.label_id = existing.label, existing.label_id
        else:
            selected = self.project.get_label(candidate.label_id)
            matches_selected = (selected is not None and selected.category == candidate.category
                                and candidate.label.casefold() in [selected.name.casefold(),
                                    *[alias.casefold() for alias in label_search_aliases(selected)]])
            if not matches_selected and candidate.category == track.category == 'Motion Primitive':
                available = self.project.labels_for_track(track)
                query = candidate.label.casefold()
                matches = [item for item in available if query == item.name.casefold()] or [
                    item for item in available if query in (alias.casefold() for alias in label_search_aliases(item))]
                if len(matches) > 1 and status == 'approved':
                    raise ValueError('Choose one of the matching movement forms from the label list.')
                if len(matches) == 1:
                    selected, matches_selected = matches[0], True
            label = selected if matches_selected else self.project.resolve_label(candidate.label, candidate.category)
            if label is None and status == 'approved':
                label = self.project.resolve_label(candidate.label, candidate.category, include_deprecated=True)
                create_label = label is None
            if label:
                candidate.label_id, candidate.label = label.id, label.name
            else:
                candidate.label_id = ''

        affect = candidate.attributes.get('affect', {})
        if (status == 'approved' and candidate.category == 'Perceived Affect'
                and (candidate.label_id == DIMENSIONAL_AFFECT_LABEL_ID
                     or candidate.label == 'valence / arousal rating'
                     or (isinstance(affect, dict) and affect.get('annotation_mode') == 'valence_arousal'))
                and not has_affect_rating(candidate.attributes)):
            # Check after resolving the prospective identity so aliases such
            # as V/A cannot bypass the same rule as the mode selector.
            raise ValueError('Choose at least one Valence or Arousal rating before accepting')

        if status == 'approved' and not unchanged_label:
            # Legacy-category tracks intentionally browse their original
            # vocabulary. Selecting another historical label is an explicit
            # human decision; current-category tracks still hide retired items.
            allowed_ids = {item.id for item in self.project.labels_for_track(
                track, include_deprecated=is_legacy_category(track.category))}
            if candidate.category != track.category:
                raise ValueError('Choose a label from the annotation track category')
            if label is not None and label.id not in allowed_ids:
                raise ValueError('This label is outside the track label list; choose an allowed label or edit the list')
        if status == 'approved':
            motion_error = motion_accept_error(candidate, existing)
            if motion_error:
                raise ValueError(motion_error)
            spatial_error = spatial_accept_error(self.project, candidate, existing)
            if spatial_error:
                raise ValueError(spatial_error)
        if create_label and candidate.category == track.category:
            # Validate the existing restriction before checkpointing or adding
            # anything, including the explicit empty-list case.
            self.project.labels_for_track(track)

        # One user action includes the new custom label, its optional list
        # membership, and the annotation. Cancelling or failing validation above
        # never changes any of them or consumes an undo checkpoint.
        self.history.checkpoint(self.project)
        if create_label:
            scope = 'temporary' if track.extra.get('label_scope') == 2 else 'project'
            label = self.project.add_label(candidate.label, candidate.category, scope=scope)
            candidate.label_id, candidate.label = label.id, label.name
            if candidate.category == track.category:
                self.project.allow_label_on_track(track, label)
        before = self._base.snapshot() if self._base is not None else self.draft.snapshot()
        if self._base is not None:
            candidate.source = self._base.source
            candidate.original = deepcopy(self._base.original)
            candidate.history = deepcopy(self._base.history)
        else:
            candidate.source = 'manual'
            candidate.original = {}
            candidate.history = []
        candidate.status = status
        if reviewer:
            candidate.reviewer = reviewer
        candidate.record_change(before, 'accept' if status == 'approved' else 'save candidate', reviewer)
        if existing is None:
            self.project.annotations.append(candidate)
            result = candidate
        else:
            existing.__dict__.update(deepcopy(candidate.__dict__))
            result = existing
        self.project._initialized_annotation_ids.add(result.id)
        self.cancel()
        return result

    def cancel(self):
        self.draft = None
        self.is_new = False
        self._base = None
        self._annotation_id = None
