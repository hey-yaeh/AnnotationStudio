"""Read-only Affect names and compact captions; saved labels stay canonical."""
from __future__ import annotations

from numbers import Real
import math
import uuid

from .models import _ID_NAMESPACE
from .ontology import label_spec


DIMENSIONAL_AFFECT_LABEL_NAME = 'valence / arousal rating'
DIMENSIONAL_AFFECT_LABEL_ID = str(uuid.uuid5(
    _ID_NAMESPACE, f'core:Perceived Affect:{DIMENSIONAL_AFFECT_LABEL_NAME}'))


def affect_adjective(label):
    """Return an optional display alias without reinterpreting renamed labels.

    Old projects keep their saved label metadata. A canonical core identity may
    borrow current display guidance, while a renamed core or arbitrary custom
    name is left alone. Project labels may explicitly supply their own alias.
    """
    name = label.name
    if label.category != 'Perceived Affect':
        return name
    extra = label.extra if isinstance(label.extra, dict) else {}
    if label.scope == 'core':
        identity = str(uuid.uuid5(_ID_NAMESPACE, f'core:{label.category}:{name}'))
        if label.id != identity:
            return name
        fallback = label_spec(label.category, name) or {}
    else:
        fallback = {}
    alias = extra.get('affect_adjective') or fallback.get('affect_adjective')
    return alias.strip() if isinstance(alias, str) and alias.strip() else name


def _annotation_adjective(annotation, project=None):
    if project is not None:
        label = project.get_label(annotation.label_id)
        if label is not None and label.name == annotation.label:
            return affect_adjective(label)
    name = annotation.label
    identity = str(uuid.uuid5(_ID_NAMESPACE, f'core:Perceived Affect:{name}'))
    if annotation.label_id != identity:
        return name
    alias = (label_spec('Perceived Affect', name) or {}).get('affect_adjective')
    return alias.strip() if isinstance(alias, str) and alias.strip() else name


def _score(value, *, signed=False):
    if value is None:
        return '—'
    # Legacy scales remain visible as recorded; a display must not round or
    # convert them to the current ordinal scale or invent a zero for missing.
    if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value):
        return format(value, '+g' if signed else 'g')
    return str(value)


def annotation_caption(annotation, project=None):
    """Display only the selected mode's scores, preserving all stored fields."""
    if annotation.category != 'Perceived Affect':
        return annotation.label
    attrs = annotation.attributes if isinstance(annotation.attributes, dict) else {}
    affect = attrs.get('affect', {})
    if not isinstance(affect, dict):
        return annotation.label
    mode = affect.get('annotation_mode')
    dimensional = mode == 'valence_arousal' or (
        mode is None and annotation.label_id == DIMENSIONAL_AFFECT_LABEL_ID
        and annotation.label == DIMENSIONAL_AFFECT_LABEL_NAME)
    if dimensional:
        return (f"V:{_score(affect.get('valence'), signed=True)} · "
                f"A:{_score(affect.get('arousal'))}")
    if mode not in (None, 'adjective_intensity'):
        return annotation.label
    text = _annotation_adjective(annotation, project)
    if mode == 'adjective_intensity' or 'intensity' in affect:
        text += f" · I:{_score(affect.get('intensity'))}"
    return text
