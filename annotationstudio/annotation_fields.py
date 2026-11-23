"""Optional human interpretation fields, independent of detector scores.

New editors opt in with ``annotation_fields_version=1``. Old arbitrary
attributes and future-version payloads remain readable without normalization.
Unknown string choices and additional keys are deliberately retained.
"""
from __future__ import annotations
import uuid


DIRECTED_CATEGORIES = frozenset({
    'Proxemic Movement', 'Interaction Event', 'Dialogue Event',
    'Turn Transition', 'Physical Interaction', 'Cognitive State Expression',
})
PAIR_CATEGORIES = frozenset({'Spatial Configuration', 'Activity Relation'})
JUDGMENT_CATEGORIES = frozenset({
    'Physical Interaction', 'Cognitive State Expression', 'Perceived Affect',
})
OBJECT_SPATIAL_CATEGORIES = frozenset({
    'Object Spatial Relation', 'Object-relative Movement',
})
OBJECT_DIRECTIONAL_LABELS = frozenset({
    'in front of object', 'behind object', 'left of object', 'right of object',
})
SPATIAL_REFERENCE_CHOICES = (
    (None, 'Unspecified'),
    ('object_intrinsic', 'Object front'),
    ('scene_reference', 'Scene directions'),
)
_SPATIAL_UNCERTAINTY_LABELS = frozenset({
    'spatial relation uncertain', 'object-relative movement uncertain',
})


def annotation_object_ids(annotation_or_attributes):
    """Return all stored object references once, without changing metadata.

    This includes a retained, inactive second reference so the registry never
    incorrectly reports it unused. Active relation queries must separately
    check the annotation's label before interpreting that reference.
    """
    attrs = (annotation_or_attributes if isinstance(annotation_or_attributes, dict)
             else getattr(annotation_or_attributes, 'attributes', {}))
    if not isinstance(attrs, dict):
        return ()
    spatial = attrs.get('spatial_relation', {})
    values = [attrs.get('object_id')]
    if isinstance(spatial, dict):
        values.append(spatial.get('secondary_object_id'))
    return tuple(dict.fromkeys(value for value in values
                               if isinstance(value, str) and value.strip()))


def _spatial_values(annotation):
    attrs = annotation.attributes if isinstance(annotation.attributes, dict) else {}
    spatial = attrs.get('spatial_relation', {})
    spatial = spatial if isinstance(spatial, dict) else {}
    return attrs.get('object_id'), spatial.get('secondary_object_id'), spatial.get('reference_frame')


def spatial_label_name(project, annotation):
    """Resolve a rule name, preserving constraints after a core-label rename.

    This is never a display or serialization rewrite. Core identity retains
    its rule even if a user renamed the displayed label. Arbitrary custom
    names continue to use their authored interpretation.
    """
    from .models import _ID_NAMESPACE  # Lazy import: models imports this module.

    def rule_name(label):
        names = (OBJECT_DIRECTIONAL_LABELS | {'between objects', 'spatial relation uncertain'}
                 if label.category == 'Object Spatial Relation'
                 else {'object-relative movement uncertain'})
        for canonical in names:
            if label.id == str(uuid.uuid5(_ID_NAMESPACE, f'core:{label.category}:{canonical}')):
                return canonical
        return label.name

    name = str(annotation.label).strip()
    selected = project.get_label(annotation.label_id) if annotation.label_id else None
    if (selected is not None and selected.category == annotation.category
            and name.casefold() in {selected.name.casefold(),
                                   *(alias.casefold() for alias in selected.aliases)}):
        return rule_name(selected)
    resolved = project.resolve_label(name, annotation.category, include_deprecated=True)
    return rule_name(resolved) if resolved is not None else name


def active_secondary_object_id(project, annotation):
    """Second target participates only in an active between-objects relation."""
    if (annotation.category == 'Object Spatial Relation'
            and spatial_label_name(project, annotation) == 'between objects'):
        value = _spatial_values(annotation)[1]
        return value if isinstance(value, str) else ''
    return ''


def spatial_accept_error(project, annotation, existing=None):
    """Return a concise review constraint, not a geometry/model prerequisite.

    Call for Accept only. An incomplete candidate can be saved. Existing
    accepted records keep unresolved, retired or future-format references when
    only their boundaries/notes are edited; reclassification or retargeting
    deliberately invokes the current contract. This helper is read-only and
    is shared by the editor and the transactional commit path.
    """
    if annotation.category not in OBJECT_SPATIAL_CATEGORIES:
        return ''
    if (existing is not None and existing.status == 'approved'
            and annotation.track_id == existing.track_id
            and annotation.role == existing.role
            and annotation.category == existing.category
            and annotation.label == existing.label
            and annotation.label_id in ('', existing.label_id)
            and _spatial_values(annotation) == _spatial_values(existing)):
        return ''
    name = spatial_label_name(project, annotation)
    primary, secondary, frame = _spatial_values(annotation)
    uncertain = name in _SPATIAL_UNCERTAINTY_LABELS
    if not primary and not uncertain:
        return 'Choose a named object. Objects… needs only a display name; no model is required.'
    if primary:
        obj = project.get_object(primary)
        if obj is None or obj.retired:
            return 'Choose a registered, active object or restore it in Objects….'
    if name == 'between objects':
        if not secondary:
            return 'Choose the second object for between objects.'
        if primary == secondary:
            return 'Between objects needs two different objects.'
        obj = project.get_object(secondary)
        if obj is None or obj.retired:
            return 'Choose a registered, active second object or restore it in Objects….'
    if name in OBJECT_DIRECTIONAL_LABELS and (
            not isinstance(frame, str) or frame not in {'object_intrinsic', 'scene_reference'}):
        return 'Choose Object front or Scene directions as the reference.'
    return ''

CERTAINTY_CHOICES = ((None, 'Unspecified'), ('low', 'Low'),
                     ('medium', 'Medium'), ('high', 'High'))
OUTCOME_CHOICES = ((None, 'Unspecified'), ('attempted', 'Attempt observed'),
                   ('completed', 'Completed'), ('partial', 'Partly completed'),
                   ('aborted', 'Aborted'), ('uncertain', 'Outcome uncertain'))
EVIDENCE_ORIGIN_CHOICES = (
    (None, 'Unspecified source'),
    ('observed_expression', 'Observed expression'),
    ('scenario_prompt', 'Scenario / role instruction'),
    ('participant_report', 'Participant report'),
)
EVIDENCE_SOURCE_CHOICES = (
    ('voice', 'Voice / prosody'),
    ('speech_content', 'Speech content'),
    ('body_motion', 'Body movement'),
    ('reference_video', 'Reference video'),
    ('interaction_context', 'Interaction context'),
    ('other', 'Other (describe in Notes)'),
)

AFFECT_MODE_CHOICES = (
    ('adjective_intensity', 'Adjective + intensity'),
    ('valence_arousal', 'Valence / Arousal'),
)


def has_affect_rating(attributes):
    """Whether a dimensional record contains an explicitly supplied rating.

    The v1 validator checks rating ranges. Unversioned/future data retain their
    authored scale; this helper must not rewrite those values or treat zero as
    missing.
    """
    affect = attributes.get('affect', {})
    return isinstance(affect, dict) and any(
        affect.get(key) is not None for key in ('valence', 'arousal'))


def validate_annotation_fields(attributes):
    """Validate only the declared v1 fields without changing any input.

Absent values are not zero. Version 1 ratings are optional ordinal integers;
booleans, strings, nonfinite numbers and values outside their scales are not
ratings. Future versions and unversioned legacy metadata are retained as-is.
"""
    if not isinstance(attributes, dict):
        raise ValueError('Annotation attributes must be a dictionary')
    version = attributes.get('annotation_fields_version')
    if type(version) is not int or version != 1:
        return
    for key in ('affect', 'human_judgment', 'physical_interaction', 'spatial_relation'):
        if key in attributes and not isinstance(attributes[key], dict):
            raise ValueError(f'{key} must be an object of annotation fields')
    affect = attributes.get('affect', {})
    for key, low, high in (('valence', -2, 2), ('arousal', 1, 5), ('intensity', 1, 5)):
        value = affect.get(key)
        if value is not None and (type(value) is not int or not low <= value <= high):
            raise ValueError(f'Affect {key} must be unknown (null) or an integer from {low} to {high}')
    for key in ('annotation_mode', 'adjective_label', 'adjective_label_id'):
        if affect.get(key) is not None and not isinstance(affect[key], str):
            raise ValueError(f'Affect {key} must be a string or null')
    judgment = attributes.get('human_judgment', {})
    for key in ('certainty', 'evidence_origin'):
        if judgment.get(key) is not None and not isinstance(judgment[key], str):
            raise ValueError(f'Human judgment {key} must be a string or null')
    if 'evidence_sources' in judgment:
        sources = judgment['evidence_sources']
        if not isinstance(sources, list) or any(not isinstance(item, str) for item in sources):
            raise ValueError('Human judgment evidence_sources must be a list of strings')
    outcome = attributes.get('physical_interaction', {}).get('outcome')
    if outcome is not None and not isinstance(outcome, str):
        raise ValueError('Physical interaction outcome must be a string or null')
    spatial = attributes.get('spatial_relation', {})
    for key in ('secondary_object_id', 'reference_frame'):
        if spatial.get(key) is not None and not isinstance(spatial[key], str):
            raise ValueError(f'Spatial relation {key} must be a string or null')
    if 'spatial_relation' in attributes:
        primary = attributes.get('object_id')
        if primary is not None and not isinstance(primary, str):
            raise ValueError('Spatial relation object_id must be a string or null')
