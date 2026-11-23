"""Manual label-list workflows, including historical records and draft safety."""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtTest import QTest

from annotationstudio.dialogs import LabelDialog
from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.editor import SegmentEditor
from annotationstudio.label_palette import LabelPalette
from annotationstudio.models import Annotation, Project
from annotationstudio.ontology import INTERACTION_EVENT_CORE_GROUPS, label_spec


@pytest.fixture
def vocabulary():
    """A small real project with intentionally different scopes and types."""
    project = Project('Label-list QA')
    project.tracks.clear()
    project.labels.clear()
    hold = project.add_label(
        'hands touching', 'Hand Behavior', scope='core', aliases=['hand contact'],
        definition='The two hands remain in physical contact.',
        boundary_rule='Start at first contact; end when contact breaks.',
        extra={'zh': '双手接触', 'group': 'Hand contact', 'auto_mode': 'manual'},
    )
    clasp = project.add_label(
        'fingers interlaced', 'Hand Behavior', scope='core', aliases=['interlocking fingers'],
        definition='Fingers from opposite hands interleave.',
        boundary_rule='Start when fingers interleave; end when they separate.',
        extra={'zh': '十指交叉', 'group': 'Hand contact', 'auto_mode': 'manual'},
    )
    custom = project.add_label('thumb circle', 'Hand Behavior', scope='project',
                               extra={'group': 'Project labels'})
    temporary = project.add_label('uncertain hand pose', 'Hand Behavior', scope='temporary')
    other = project.add_label('sitting', 'Body Posture', scope='core')
    retired = project.add_label('retired clasp wording', 'Hand Behavior', scope='core', deprecated=True)
    track = project.add_track(name='Hands', role='R01', category='Hand Behavior',
                              workspace='Motion', channel='Hands')
    return project, track, {'hold': hold, 'clasp': clasp, 'custom': custom,
                            'temporary': temporary, 'other': other, 'retired': retired}


@pytest.fixture
def make_widget(qapp):
    widgets = []

    def make(cls, *args, **kwargs):
        widget = cls(*args, **kwargs)
        widgets.append(widget)
        return widget

    yield make
    for widget in widgets:
        widget.hide()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents()


def draft_for(track, **kwargs):
    values = dict(id='draft-test', start_s=1., end_s=3., role=track.role,
                  category=track.category, channel=track.channel, track_id=track.id)
    values.update(kwargs)
    return Annotation(**values)


def item_named(palette, name):
    for index in range(palette.tree.topLevelItemCount()):
        group = palette.tree.topLevelItem(index)
        for child_index in range(group.childCount()):
            item = group.child(child_index)
            if item.data(0, Qt.UserRole) == name:
                return item
    raise AssertionError(f'No visible list item: {name}')


def click_label(palette, name, qapp):
    item = item_named(palette, name)
    palette.tree.scrollToItem(item)
    qapp.processEvents()
    QTest.mouseClick(palette.tree.viewport(), Qt.LeftButton,
                     pos=palette.tree.visualItemRect(item).center())
    qapp.processEvents()


def test_social_core_groups_and_search_work_on_a_saved_vocabulary(tmp_path, make_widget):
    project = Project('Existing Social vocabulary')
    track = project.add_track(name='Participants', role='Both', category='Interaction Event')
    acknowledgment = project.resolve_label('acknowledgment', track.category)
    acknowledgment.aliases.clear()
    acknowledgment.extra['group'] = 'Directed contribution'
    acknowledgment.definition = 'The study protocol for acknowledging receipt.'
    offer = project.resolve_label('offer', track.category)
    offer.extra['group'] = 'Directed contribution'
    agreement = project.resolve_label('agreement', track.category)
    agreement.extra['group'] = 'Our project grouping'
    path = tmp_path / 'old-social.studio.json'
    project.save(path)
    loaded = Project.load(path)
    before = deepcopy(loaded.to_dict())

    palette = make_widget(LabelPalette)
    palette.bind(loaded, loaded.get_track(track.id))
    expected = [name for names in INTERACTION_EVENT_CORE_GROUPS.values()
                for name in names if name != 'agreement']
    assert palette.visible_label_names()[:len(expected)] == expected
    assert len(palette.visible_label_names()) == 27
    assert item_named(palette, 'acknowledgment').parent().text(0) == 'Core · Responses'
    assert item_named(palette, 'agreement').parent().text(0) == 'Our project grouping'
    palette.search.setText('确认收到')
    assert palette.visible_label_names() == ['acknowledgment']
    assert acknowledgment.definition in palette.definition.toPlainText()
    palette.search.setText('greeting')
    assert palette.visible_label_names() == ['greeting']
    manager = make_widget(LabelDialog, loaded, track.category)
    manager.search.setText('acknowledgement')
    assert manager.list.count() == 1
    assert manager.current.id == acknowledgment.id
    assert loaded.to_dict() == before

    loaded.set_track_label_ids(track.id, [acknowledgment.id])
    palette.search.clear()
    palette.bind(loaded, loaded.get_track(track.id))
    assert palette.visible_label_names() == ['acknowledgment']


def test_list_respects_category_scope_and_per_track_subset(vocabulary, make_widget):
    project, track, labels = vocabulary
    palette = make_widget(LabelPalette)
    palette.bind(project, track)
    assert set(palette.visible_label_names()) == {'hands touching', 'fingers interlaced', 'thumb circle'}
    project.set_track_label_ids(track, [labels['clasp'].id, labels['custom'].id])
    palette.bind(project, track)
    assert set(palette.visible_label_names()) == {'fingers interlaced', 'thumb circle'}
    editor = make_widget(SegmentEditor)
    editor.bind(draft_for(track), project)
    assert [editor.label.itemText(i) for i in range(editor.label.count())] == [
        'fingers interlaced', 'thumb circle',
    ]
    track.extra['label_scope'] = 1
    palette.bind(project, track)
    assert palette.visible_label_names() == ['thumb circle']
    project.set_track_label_ids(track, [])
    palette.bind(project, track)
    assert palette.visible_label_names() == []
    assert 'No matching labels' in palette.hint.text()


def test_leaf_click_updates_draft_but_accept_is_separate(vocabulary, make_widget, qapp):
    project, track, labels = vocabulary
    session = EditSession(project, ProjectHistory())
    draft = session.create(1., 3., track.id)
    palette = make_widget(LabelPalette)
    editor = make_widget(SegmentEditor)
    editor.bind(draft, project)
    palette.bind(project, track, draft)
    chosen = []
    palette.labelChosen.connect(chosen.append)
    palette.labelChosen.connect(editor.label.setCurrentText)

    def update(values):
        session.update(**values)
        editor.current = session.draft

    editor.changed.connect(update)
    editor.acceptClicked.connect(session.accept)
    palette.resize(340, 520)
    palette.show()
    editor.show()
    qapp.processEvents()
    click_label(palette, labels['clasp'].name, qapp)
    assert chosen == ['fingers interlaced']
    assert session.draft.label == 'fingers interlaced'
    assert project.annotations == []
    assert session.draft.status == 'pending'
    assert 'Time boundaries' in palette.definition.toPlainText()
    assert labels['clasp'].boundary_rule in palette.definition.toPlainText()
    QTest.mouseClick(editor.accept, Qt.LeftButton)
    assert session.draft is None
    assert len(project.annotations) == 1
    saved = project.annotations[0]
    assert saved.status == 'approved'
    assert saved.label_id == labels['clasp'].id
    assert saved.start_s == 1. and saved.end_s == 3.


def test_browsing_without_interval_shows_definition_without_selecting(vocabulary, make_widget, qapp):
    project, track, labels = vocabulary
    palette = make_widget(LabelPalette)
    chosen = []
    palette.labelChosen.connect(chosen.append)
    palette.bind(project, track)
    palette.resize(340, 520)
    palette.show()
    qapp.processEvents()
    click_label(palette, labels['hold'].name, qapp)
    assert chosen == []
    assert project.annotations == []
    assert labels['hold'].definition in palette.definition.toPlainText()
    assert 'Select a proposal or drag an interval' in palette.hint.text()


@pytest.mark.parametrize('query,expected', [
    ('FINGERS', ['fingers interlaced']),
    ('hand contact', ['hands touching', 'fingers interlaced']),
    ('interlocking', ['fingers interlaced']),
    ('十指', ['fingers interlaced']),
    ('双手', ['hands touching']),
])
def test_search_supports_names_aliases_groups_and_chinese(vocabulary, make_widget, query, expected):
    project, track, _ = vocabulary
    palette = make_widget(LabelPalette)
    palette.bind(project, track)
    palette.search.setText(query)
    assert palette.visible_label_names() == expected


def test_refresh_preserves_search_cursor_and_focus_but_new_track_resets(vocabulary, make_widget, qapp):
    project, track, _ = vocabulary
    palette = make_widget(LabelPalette)
    palette.bind(project, track, draft_for(track))
    palette.resize(340, 520)
    palette.show()
    palette.activateWindow()
    palette.search.setFocus()
    QTest.keyClicks(palette.search, 'finger')
    palette.search.setCursorPosition(3)
    qapp.processEvents()
    assert palette.search.hasFocus()
    chosen = []
    palette.labelChosen.connect(chosen.append)
    palette.bind(project, track, draft_for(track, start_s=1.2))
    assert palette.search.text() == 'finger'
    assert palette.search.cursorPosition() == 3
    assert palette.search.hasFocus()
    assert chosen == []
    second = project.add_track(name='Posture', category='Body Posture', channel='Full Body')
    palette.bind(project, second)
    assert palette.search.text() == ''
    assert palette.visible_label_names() == ['sitting']


def test_compact_palette_keeps_selected_label_visible_without_overlap(make_widget, qapp):
    project = Project()
    track = project.add_track(name='Posture', category='Body Posture', channel='Full Body')
    label = project.resolve_label('legs crossed', track.category)
    palette = make_widget(LabelPalette)
    palette.bind(project, track, draft_for(track, label=label.name, label_id=label.id))
    palette.resize(336, 473)
    palette.show()
    qapp.processEvents()
    palette.resize(313, 269)
    qapp.processEvents()
    item = item_named(palette, label.name)
    assert palette.tree.currentItem() is item
    assert palette.tree.viewport().rect().contains(palette.tree.visualItemRect(item))
    assert not palette.tree.geometry().intersects(palette.definition.geometry())
    assert palette.tree.height() >= 80
    assert palette.definition.height() >= 58


@pytest.mark.parametrize('kind', ['outside_subset', 'retired', 'unknown'])
def test_current_record_stays_visible_without_remapping(vocabulary, make_widget, kind):
    project, track, labels = vocabulary
    project.set_track_label_ids(track, [labels['hold'].id])
    if kind == 'outside_subset':
        annotation = draft_for(track, label=labels['clasp'].name, label_id=labels['clasp'].id)
    elif kind == 'retired':
        annotation = draft_for(track, label=labels['retired'].name, label_id=labels['retired'].id)
    else:
        annotation = draft_for(track, label='R01 candidate 17 / unknown', source='auto:graph')
    before = deepcopy(annotation.snapshot())
    count = len(project.labels)
    palette = make_widget(LabelPalette)
    palette.bind(project, track, annotation)
    current = item_named(palette, annotation.label)
    assert current.parent().text(0) == 'Current / legacy'
    assert palette.tree.currentItem() is current
    assert palette.visible_label_names() == [annotation.label, 'hands touching']
    assert annotation.snapshot() == before
    assert len(project.labels) == count
    palette.search.setText('no matching search term')
    assert palette.visible_label_names() == [annotation.label]
    editor = make_widget(SegmentEditor)
    editor.bind(annotation, project)
    assert editor.label.currentText() == annotation.label
    assert editor.values()['label'] == annotation.label


def test_retired_category_track_can_still_browse_its_old_vocabulary(vocabulary, make_widget):
    project, _, _ = vocabulary
    old = project.add_label('approach', 'Social Interaction', scope='core', deprecated=True)
    old_track = project.add_track(name='Original interaction', workspace='Social',
                                  category='Social Interaction', channel='Dyadic')
    palette = make_widget(LabelPalette)
    palette.bind(project, old_track)
    assert palette.visible_label_names() == [old.name]
    assert 'legacy type' in palette.context.text()
    palette.bind(project, old_track, draft_for(old_track, label=old.name, label_id=old.id))
    assert item_named(palette, old.name).parent().text(0) == 'Current / legacy'


def test_an_explicit_selection_from_legacy_list_can_be_accepted(vocabulary, make_widget, qapp):
    project, _, _ = vocabulary
    old = project.add_label('approach', 'Social Interaction', scope='core', deprecated=True)
    other = project.add_label('retreat', 'Social Interaction', scope='core', deprecated=True)
    track = project.add_track(name='Historical events', workspace='Social',
                              category='Social Interaction', channel='Dyadic')
    saved = draft_for(track, label=old.name, label_id=old.id, status='approved')
    project.annotations.append(saved)
    session = EditSession(project, ProjectHistory())
    session.begin(saved.id)
    palette = make_widget(LabelPalette)
    palette.bind(project, track, session.draft)
    palette.labelChosen.connect(lambda name: session.update(label=name))
    palette.resize(340, 520)
    palette.show()
    qapp.processEvents()
    click_label(palette, other.name, qapp)
    assert saved.label == old.name
    assert session.draft.label == other.name
    accepted = session.accept()
    assert accepted.label == other.name and accepted.label_id == other.id
    assert accepted.history[-1]['before']['label'] == old.name


def test_old_core_records_get_display_guidance_without_saved_data_changes(make_widget):
    project = Project()
    track = project.add_track(name='Posture', category='Body Posture', channel='Full Body')
    label = project.resolve_label('legs crossed', track.category)
    assert label is not None
    label.definition = ''
    label.boundary_rule = ''
    label.aliases = []
    label.extra = {}
    before = deepcopy(vars(label))
    project.set_track_label_ids(track, [label.id])
    palette = make_widget(LabelPalette)
    palette.bind(project, track)
    guidance = label_spec(track.category, label.name)
    assert guidance['description'] in palette.definition.toPlainText()
    assert guidance['boundary_rule'] in palette.definition.toPlainText()
    palette.search.setText(guidance['zh'])
    assert palette.visible_label_names() == [label.name]
    assert vars(label) == before
    label.definition = 'Our operational definition overrides the preset.'
    label.boundary_rule = 'Use our study-specific boundaries.'
    palette.bind(project, track)
    assert label.definition in palette.definition.toPlainText()
    assert label.boundary_rule in palette.definition.toPlainText()
    label.name = 'project-specific lower-body arrangement'
    label.definition = ''
    label.boundary_rule = ''
    palette.search.clear()
    palette.bind(project, track)
    assert 'No definition is recorded' in palette.definition.toPlainText()
    assert guidance['description'] not in palette.definition.toPlainText()


def test_custom_label_request_can_be_made_before_creating_interval(vocabulary, make_widget, qapp):
    project, track, _ = vocabulary
    palette = make_widget(LabelPalette)
    requests = []
    palette.addLabelRequested.connect(requests.append)
    palette.bind(project, track)
    palette.search.setText('  My precise label  ')
    palette.show()
    qapp.processEvents()
    QTest.mouseClick(palette.add_button, Qt.LeftButton)
    assert requests == ['My precise label']
    assert project.resolve_label('My precise label', track.category) is None


@pytest.mark.parametrize('role,other', [('R01', 'R02'), ('R02', 'R01')])
def test_directed_editor_excludes_self_and_preserves_other_attributes(vocabulary, make_widget, role, other):
    project, _, _ = vocabulary
    track = project.add_track(name='Directed movement', role=role, workspace='Social',
                              category='Proxemic Movement', channel='Root',
                              extra={'target_role': other})
    attrs = {'body_parts': ['Root'], 'provenance': {'method': 'import', 'index': 4}, 'note_id': 'n-4'}
    annotation = draft_for(track, label='approach partner', attributes=deepcopy(attrs))
    editor = make_widget(SegmentEditor)
    emitted = []
    editor.changed.connect(emitted.append)
    editor.bind(annotation, project)
    assert emitted == []
    assert not editor.target_role.isHidden()
    options = [editor.target_role.itemText(i) for i in range(editor.target_role.count())]
    assert options == ['Unknown', other]
    assert role not in options
    assert editor.target_role.currentText() == other
    values = editor.values()
    assert values['attributes'] == dict(attrs, target_role=other)
    assert annotation.attributes == attrs
    editor.target_role.setCurrentText('Unknown')
    assert emitted[-1]['attributes'] == dict(attrs, target_role='Unknown')
    assert annotation.attributes == attrs


def test_target_is_unknown_without_explicit_evidence_and_saved_target_wins(vocabulary, make_widget):
    project, _, _ = vocabulary
    track = project.add_track(name='Response', role='R01', workspace='Speech',
                              category='Dialogue Event', channel='Speech')
    editor = make_widget(SegmentEditor)
    annotation = draft_for(track, label='response')
    editor.bind(annotation, project)
    assert editor.target_role.currentText() == 'Unknown'
    track.extra['target_role'] = 'R02'
    annotation.attributes['target_role'] = 'Unknown'
    editor.bind(annotation, project)
    assert editor.target_role.currentText() == 'Unknown'
    annotation.attributes['target_role'] = 'R01'
    editor.bind(annotation, project)
    assert editor.target_role.currentText() == 'Unknown'


@pytest.mark.parametrize('category', ['Interaction Event', 'Spatial Configuration', 'Activity Relation'])
def test_pair_events_use_participants_and_preserve_other_metadata(vocabulary, make_widget, category):
    project, _, _ = vocabulary
    track = project.add_track(name='Pair relation', role='Both', category=category,
                              workspace='Social', channel='Dyadic')
    attrs = {'target_role': 'R02', 'participants': ['R01', 'R02'], 'evidence': ['video', 'motion']}
    annotation = draft_for(track, label='pair observation', attributes=deepcopy(attrs))
    editor = make_widget(SegmentEditor)
    editor.bind(annotation, project)
    assert editor.target_role.isHidden()
    assert editor.values()['attributes'] == {
        'participants': ['R01', 'R02'], 'evidence': ['video', 'motion'],
    }
    assert annotation.attributes == attrs


def test_hoi_fields_and_typed_label_survive_time_preview(vocabulary, make_widget, qapp):
    project, _, _ = vocabulary
    track = project.add_track(name='Cup', role='R01', category='Action / HOI',
                              workspace='HOI', channel='Hands')
    annotation = draft_for(track, label='hold object', attributes={
        'object_id': 'cup_01', 'effector': 'Right hand', 'quality': {'occluded': False},
    })
    editor = make_widget(SegmentEditor)
    editor.bind(annotation, project)
    editor.show()
    editor.activateWindow()
    field = editor.label.lineEdit()
    field.setFocus()
    field.selectAll()
    QTest.keyClicks(field, 'custom cup adjustment')
    qapp.processEvents()
    editor.update_span(1.25, 3.5)
    assert editor.label.lineEdit() is field
    assert field.text() == 'custom cup adjustment'
    assert field.hasFocus()
    assert editor.target_role.isHidden()
    values = editor.values()
    assert values['start_s'] == 1.25 and values['end_s'] == 3.5
    assert values['attributes'] == annotation.attributes
    editor.hand.setCurrentText('Both hands')
    assert editor.values()['attributes']['quality'] == {'occluded': False}
    assert editor.values()['attributes']['effector'] == 'Both hands'
    assert annotation.attributes['effector'] == 'Right hand'
