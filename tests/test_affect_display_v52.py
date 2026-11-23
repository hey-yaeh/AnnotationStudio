"""Affect presentation keeps canonical identity and recorded values intact."""
from copy import deepcopy
from dataclasses import asdict

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

from annotationstudio.affect_display import affect_adjective, annotation_caption
from annotationstudio.label_palette import LabelPalette
from annotationstudio.models import Annotation, Project
from annotationstudio.timeline import TimelineCanvas


def _record(project, name='joy', **affect):
    label = project.resolve_label(name, 'Perceived Affect')
    return Annotation(id='affect-test', start_s=1, end_s=5, role='R01',
        category='Perceived Affect', channel='Emotion', label=label.name,
        label_id=label.id, attributes={'affect': affect})


def test_palette_shows_and_searches_adjective_but_selects_canonical_identity(qapp):
    project = Project()
    label = project.resolve_label('joy', 'Perceived Affect')
    # Simulate a 0.5.1 label whose authored metadata predates the display alias.
    label.extra = {}; label.aliases = []
    track = project.add_track(name='Affect', category=label.category, channel='Emotion')
    project.set_track_label_ids(track, [label.id])
    annotation = _record(project)
    annotation.track_id = track.id
    before = deepcopy(project.to_dict())
    palette = LabelPalette()
    chosen = []
    palette.labelChosen.connect(chosen.append)
    try:
        palette.bind(project, track, annotation)
        palette.resize(360, 520); palette.show(); qapp.processEvents()
        palette.search.setText('joyful')
        assert palette.visible_label_names() == ['joy']
        item = palette.tree.topLevelItem(0).child(0)
        assert item.text(0) == 'Joyful'
        assert label.definition in item.toolTip(0)
        QTest.mouseClick(palette.tree.viewport(), Qt.LeftButton,
                        pos=palette.tree.visualItemRect(item).center())
        qapp.processEvents()
        assert chosen == ['joy']
        palette.search.setText('joy')
        assert palette.visible_label_names() == ['joy']
        assert project.to_dict() == before
    finally:
        palette.hide(); palette.deleteLater(); qapp.processEvents()


def test_affect_alias_does_not_replace_renamed_or_custom_label():
    project = Project()
    original = project.resolve_label('joy', 'Perceived Affect')
    assert affect_adjective(original) == 'Joyful'
    renamed = deepcopy(original)
    renamed.name = 'Our study-specific joy description'
    assert affect_adjective(renamed) == renamed.name
    arbitrary = deepcopy(original)
    arbitrary.id = 'authored-core-id'; arbitrary.extra = {}
    assert affect_adjective(arbitrary) == 'joy'
    custom = deepcopy(original)
    custom.id = 'custom-id'; custom.scope = 'project'; custom.extra = {}
    assert affect_adjective(custom) == 'joy'
    original.category = 'Dialogue Event'
    assert affect_adjective(original) == original.name


def test_caption_uses_only_active_mode_and_does_not_mutate_metadata():
    project = Project()
    record = _record(project, annotation_mode='adjective_intensity', intensity=4,
                     valence=-1, arousal=2, future_field={'keep': True})
    before = deepcopy(asdict(record))
    assert annotation_caption(record) == 'Joyful · I:4'
    assert asdict(record) == before
    record.attributes['affect']['annotation_mode'] = 'valence_arousal'
    record.attributes['affect']['valence'] = 0
    record.attributes['affect']['arousal'] = None
    before = deepcopy(asdict(record))
    assert annotation_caption(record) == 'V:+0 · A:—'
    assert asdict(record) == before
    record.attributes['affect']['annotation_mode'] = 'future_mode'
    assert annotation_caption(record) == 'joy'
    record.category = 'Gesture Type'
    assert annotation_caption(record) == 'joy'


def test_caption_preserves_legacy_scale_and_missing_values():
    project = Project()
    record = _record(project, 'valence / arousal rating', valence=.5, arousal=None)
    before = deepcopy(asdict(record))
    assert annotation_caption(record) == 'V:+0.5 · A:—'
    assert asdict(record) == before
    record = _record(project, annotation_mode='adjective_intensity', intensity=None)
    assert annotation_caption(record) == 'Joyful · I:—'
    record.label_id = ''
    assert annotation_caption(record) == 'joy · I:—'


def test_timeline_tooltip_shows_scores_and_keeps_canonical_label(qapp):
    project = Project()
    track = project.add_track(name='Affect', category='Perceived Affect', channel='Emotion')
    record = _record(project, 'valence / arousal rating',
        annotation_mode='valence_arousal', valence=1, arousal=3)
    record.track_id = track.id
    before = deepcopy(asdict(record))
    canvas = TimelineCanvas()
    try:
        canvas.workspace = 'Affect'
        canvas.set_data([track], [record])
        canvas.resize(1000, 150); canvas.show(); qapp.processEvents()
        # Exercise hover content independently of native cursor delivery and
        # the placement of other windows on a multi-monitor Windows desktop.
        position = canvas.annotation_rect(record).center()
        qapp.sendEvent(canvas, QMouseEvent(
            QEvent.MouseMove, position, canvas.mapToGlobal(position.toPoint()),
            Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        qapp.processEvents()
        assert 'V:+1 · A:3' in canvas.toolTip()
        assert 'Label: valence / arousal rating' in canvas.toolTip()
        assert asdict(record) == before
    finally:
        canvas.hide(); canvas.deleteLater(); qapp.processEvents()
