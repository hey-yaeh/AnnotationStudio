"""Two simple Affect workflows, with authored identities and hidden data intact."""
from copy import deepcopy
from dataclasses import asdict

import pytest
from PySide6.QtWidgets import QMessageBox
from PySide6.QtTest import QTest

from annotationstudio.affect_display import DIMENSIONAL_AFFECT_LABEL_ID, DIMENSIONAL_AFFECT_LABEL_NAME, affect_adjective
from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.models import Annotation, Project, export_csv, import_annotation_csv
from annotationstudio.ontology import label_spec
from annotationstudio.ui import MainWindow


@pytest.fixture
def window(qapp,monkeypatch,tmp_path):
    messages=[]
    for method in ('warning','critical','information'):
        monkeypatch.setattr(QMessageBox,method,
            lambda parent,title,text,*args,**kwargs:messages.append((title,text)) or QMessageBox.Ok)
    monkeypatch.setattr(MainWindow,'recovery_path',lambda self:tmp_path/'recovery.json')
    widget=MainWindow(recover=False)
    widget.timer.stop(); widget.autosave_timer.stop(); widget.show()
    qapp.processEvents(); widget.qa_messages=messages
    yield widget
    widget.session.cancel(); widget._preview_invalid=False
    widget.history.mark_saved(widget.project); widget.close(); widget.deleteLater()
    qapp.processEvents()


def choose(combo,value):
    index=combo.findData(value)
    assert index>=0,value
    combo.setCurrentIndex(index)


def affect_track(project,role='R01',**extra):
    return project.add_track(name=f'{role} affect',role=role,
        category='Perceived Affect',channel='Emotion',extra=extra)


def assert_roundtrip(project,record,tmp_path):
    project.save(tmp_path/'affect.json')
    loaded=Project.load(tmp_path/'affect.json')
    export_csv(project.annotations,tmp_path/'affect.csv')
    imported=import_annotation_csv(tmp_path/'affect.csv')
    assert asdict(loaded.annotations[0])==asdict(record)==asdict(imported[0])


def test_gemep_core_has_all_seventeen_selectable_manual_categories():
    project = Project()
    track = affect_track(project)
    expected = {
        'Admiration': 'Admiring', 'Amusement': 'Amused', 'Tenderness': 'Tender',
        'Hot anger (rage)': 'Enraged', 'Disgust': 'Disgusted', 'Despair': 'Despairing',
        'Pride': 'Proud', 'Anxiety': 'Anxious', 'Interest': 'Interested',
        'Irritation (cold anger)': 'Irritated', 'Elated joy': 'Elated',
        'Contempt': 'Contemptuous', 'Fear (panic)': 'Panicked', 'Pleasure': 'Pleased',
        'Relief': 'Relieved', 'Surprise': 'Surprised', 'Sadness': 'Sad',
    }
    selectable = project.labels_for_track(track)
    references = {label.extra['gemep_category']: label for label in selectable
                  if 'gemep_category' in label.extra}
    assert len(selectable) == 34  # 32 adjective choices, the dimensional rating and Unlabeled.
    assert {reference: affect_adjective(label) for reference, label in references.items()} == expected
    for label in references.values():
        spec = label_spec(label.category, label.name)
        assert spec['implementation_status'] == 'manual'
        assert spec['description_zh'] and spec['boundary_rule_zh'] and spec['evidence_mode']
        assert project.resolve_label(label.extra['gemep_category'], label.category) is label
    assert {'Angry', 'Joyful', 'Fearful / apprehensive', 'Tense / nervous'} <= {
        affect_adjective(label) for label in selectable}


def test_old_affect_project_loads_new_choices_and_keeps_previous_records(window, tmp_path):
    project = window.project
    unlocked = affect_track(project, 'R02')
    old_label = project.resolve_label('amusement', 'Perceived Affect')
    old_label.definition = 'Authored definition before the GEMEP update'
    locked = affect_track(project, allowed_label_ids=[old_label.id])
    previous = project.add_annotation(1, 2, role='R01', channel='Emotion', category=locked.category,
        track_id=locked.id, label=old_label.name, label_id=old_label.id, status='approved',
        attributes={'affect': {'intensity': 3}}, original={'original_text': 'keep'}, history=[{'event': 'old'}])
    snapshot = asdict(previous)
    project.labels = [label for label in project.labels if label.extra.get('group') != 'GEMEP observer categories']
    for label in project.labels:
        label.extra.pop('gemep_category', None)
    old_path = tmp_path / 'pre-gemep.studio.json'
    project.save(old_path)
    old_bytes = old_path.read_bytes()
    loaded = Project.load(old_path)
    assert asdict(loaded.annotations[0]) == snapshot
    assert [label.id for label in loaded.labels_for_track(locked.id)] == [old_label.id]
    assert asdict(loaded.get_label(old_label.id)) == asdict(old_label)
    window._install_project(loaded)

    window.add_range(3, 4, unlocked.id)
    assert window.editor.affect_mode.currentData() == 'adjective_intensity'
    for query in ('cold anger', '冷怒', 'Irritated'):
        window.label_palette.search.setText(query)
        assert window.label_palette.visible_label_names() == ['irritation']
    window.choose_palette_label('irritation')
    assert window.editor.label.currentText() == 'Irritated'
    choose(window.editor.intensity, 2)
    assert window.accept_edit()
    added = loaded.annotations[-1]
    assert added.role == 'R02' and added.label == 'irritation'
    assert added.label_id == loaded.resolve_label('Irritated', 'Perceived Affect').id
    assert added.attributes['affect'] == {'annotation_mode': 'adjective_intensity', 'intensity': 2}

    new_path, csv_path = tmp_path / 'after.studio.json', tmp_path / 'affect.csv'
    loaded.save(new_path)
    export_csv(loaded.annotations, csv_path)
    expected = [snapshot, asdict(added)]
    assert [asdict(record) for record in Project.load(new_path).annotations] == expected
    assert [asdict(record) for record in import_annotation_csv(csv_path)] == expected
    assert old_path.read_bytes() == old_bytes
    assert not window.qa_messages


def test_adjective_intensity_draft_cancel_accept_identity_and_roundtrip(window,tmp_path):
    project=window.project; track=affect_track(project,'R02')
    label=project.resolve_label('joy','Perceived Affect')
    window.add_range(2,5,track.id)
    editor=window.editor
    assert editor.affect_mode.currentData()=='adjective_intensity'
    assert editor.intensity.currentData() is None
    assert not editor.more_details.isChecked()
    assert editor.evidence_fields.isHidden() and editor.judgment_certainty.isHidden()
    window.choose_palette_label('joy'); choose(editor.intensity,4)
    assert editor.label.currentText()=='Joyful'
    assert window.session.draft.label=='joy' and window.session.draft.label_id==label.id
    assert not project.annotations
    window.cancel_edit(); assert not project.annotations
    window.add_range(2,5,track.id)
    editor.choose_label('Joyful'); choose(editor.intensity,4)
    assert window.accept_edit()
    record=project.annotations[0]
    assert record.role=='R02' and record.label_id==label.id and record.label=='joy'
    assert record.attributes['affect']=={'annotation_mode':'adjective_intensity','intensity':4}
    assert 'human_judgment' not in record.attributes
    assert_roundtrip(project,record,tmp_path)
    window.undo(); assert not project.annotations
    window.redo(); assert project.annotations[0].label_id==label.id
    assert not window.qa_messages


def test_va_only_neutral_is_present_unknown_stays_null_and_accept_requires_rating(window,tmp_path):
    project=window.project; track=affect_track(project)
    window.add_range(1,3,track.id); editor=window.editor
    choose(editor.affect_mode,'valence_arousal')
    assert editor.label.isHidden() and editor.intensity.isHidden()
    assert editor.valence.isVisible() and editor.arousal.isVisible()
    assert editor.valence.currentData() is None and editor.arousal.currentData() is None
    assert not editor.accept.isEnabled() and editor.candidate.isEnabled()
    with pytest.raises(ValueError,match='at least one'):
        window.session.accept()
    assert not project.annotations
    choose(editor.valence,0)
    assert editor.accept.isEnabled() and window.accept_edit()
    record=project.annotations[0]
    assert record.label==DIMENSIONAL_AFFECT_LABEL_NAME
    assert record.label_id==DIMENSIONAL_AFFECT_LABEL_ID
    assert record.attributes['affect']=={'annotation_mode':'valence_arousal','valence':0}
    assert 'adjective_label' not in record.attributes['affect']
    assert_roundtrip(project,record,tmp_path)
    assert not window.qa_messages


def test_empty_va_can_be_saved_as_candidate_without_fake_neutral(window):
    project=window.project; track=affect_track(project)
    window.add_range(1,2,track.id)
    choose(window.editor.affect_mode,'valence_arousal')
    assert window.keep_candidate()
    record=project.annotations[0]
    assert record.status=='pending'
    assert record.attributes['affect']=={'annotation_mode':'valence_arousal'}
    window.select_annotation(record.id)
    assert not window.editor.accept.isEnabled()
    choose(window.editor.arousal,1)
    assert window.accept_edit()
    assert record.attributes['affect']['arousal']==1
    assert 'valence' not in record.attributes['affect']
    assert not window.qa_messages


def test_mode_switch_preserves_hidden_values_origin_score_and_cancel(window,tmp_path):
    project=window.project; track=affect_track(project)
    record=project.add_annotation(1,4,track_id=track.id,category=track.category,
        label='surprise',source='auto:external-example',confidence=.78,attributes={
            'annotation_fields_version':1,
            'affect':{'intensity':3,'valence':-1,'arousal':2,'future_key':{'keep':True}},
            'human_judgment':{'certainty':'medium','evidence_origin':'scenario_prompt',
                'evidence_sources':['voice','future_sensor']},'unrelated':17})
    original=deepcopy(asdict(record))
    window.select_annotation(record.id); editor=window.editor
    assert editor.affect_mode.currentData()=='adjective_intensity'
    editor.more_details.setChecked(True); editor.more_details.setChecked(False)
    assert asdict(window.session.draft)==original
    choose(editor.affect_mode,'valence_arousal'); choose(editor.valence,1)
    assert window.session.draft.attributes['affect']['adjective_label_id']==record.label_id
    window.cancel_edit(); assert asdict(record)==original
    window.select_annotation(record.id)
    choose(editor.affect_mode,'valence_arousal'); choose(editor.valence,1)
    choose(editor.affect_mode,'adjective_intensity')
    assert editor.values()['label_id']==record.label_id
    assert editor.intensity.currentData()==3
    assert window.accept_edit()
    assert record.label=='surprise' and record.source==original['source']
    assert record.confidence==.78 and record.original==original['original']
    assert record.attributes['affect']['valence']==1
    assert record.attributes['affect']['arousal']==2
    assert record.attributes['affect']['intensity']==3
    assert record.attributes['affect']['future_key']=={'keep':True}
    assert record.attributes['human_judgment']==original['attributes']['human_judgment']
    assert record.attributes['unrelated']==17
    assert_roundtrip(project,record,tmp_path)
    assert not window.qa_messages


def test_va_reopen_restores_adjective_by_identity_and_palette_switches_modes(window):
    project=window.project; track=affect_track(project)
    label=project.resolve_label('joy','Perceived Affect')
    window.add_range(1,3,track.id)
    window.choose_palette_label('joy'); choose(window.editor.intensity,2)
    choose(window.editor.affect_mode,'valence_arousal'); choose(window.editor.arousal,3)
    assert window.accept_edit()
    record=project.annotations[0]
    # The saved ID must survive an authored vocabulary rename between edits.
    label.name='Our joyful expression'
    window.select_annotation(record.id)
    choose(window.editor.affect_mode,'adjective_intensity')
    assert window.editor.values()['label']=='Our joyful expression'
    assert window.editor.values()['label_id']==label.id
    assert window.editor.intensity.currentData()==2
    choose(window.editor.affect_mode,'valence_arousal')
    window.choose_palette_label('anger')
    assert window.editor.affect_mode.currentData()=='adjective_intensity'
    assert window.editor.values()['label']=='anger'
    assert window.accept_edit()
    assert record.label=='anger' and record.attributes['affect']['arousal']==3
    assert not window.qa_messages


def test_dimension_mode_obeys_track_whitelist_without_mutating_it(window):
    project=window.project
    joy=project.resolve_label('joy','Perceived Affect')
    track=affect_track(project,allowed_label_ids=[joy.id])
    before=deepcopy(track.extra)
    window.add_range(1,2,track.id)
    assert not window.editor.affect_mode.model().item(
        window.editor.affect_mode.findData('valence_arousal')).isEnabled()
    assert not window.editor.choose_label(DIMENSIONAL_AFFECT_LABEL_NAME)
    assert window.editor.affect_mode.currentData()=='adjective_intensity'
    assert track.extra==before
    window.session.update(label=DIMENSIONAL_AFFECT_LABEL_NAME,label_id=DIMENSIONAL_AFFECT_LABEL_ID,
        attributes={'annotation_fields_version':1,'affect':{'annotation_mode':'valence_arousal','valence':0}})
    with pytest.raises(ValueError,match='outside the track'):
        window.session.accept()
    assert not project.annotations and track.extra==before
    assert not window.qa_messages


def test_future_fields_stay_untouched_by_opening_collapsing_and_boundary_edit(window):
    project=window.project; track=affect_track(project)
    fields={'annotation_fields_version':99,
        'affect':{'annotation_mode':'future_mode','intensity':.125,'valence':.25,
            'arousal':'continuous legacy','future_scale':[0,1]},
        'human_judgment':{'certainty':'future certainty','evidence_origin':'future origin'}}
    record=project.add_annotation(1,3,track_id=track.id,category=track.category,
        label='anger',attributes=deepcopy(fields))
    window.select_annotation(record.id)
    window.editor.more_details.setChecked(True)
    window.editor.more_details.setChecked(False)
    window.editor.end.setValue(3.5)
    assert window.accept_edit()
    assert record.attributes==fields
    assert not window.qa_messages


def test_typing_custom_adjective_does_not_replace_a_known_prefix(window):
    project=window.project; track=affect_track(project)
    window.add_range(1,2,track.id)
    line=window.editor.label.lineEdit()
    line.setFocus(); line.selectAll(); QTest.keyClicks(line,'joyless')
    assert line.text()=='joyless' and line.cursorPosition()==len('joyless')
    choose(window.editor.intensity,2)
    assert window.accept_edit()
    assert project.annotations[0].label=='joyless'
    assert not window.qa_messages


def test_boundary_only_edit_retains_authored_label_wording_with_known_id(window):
    project=window.project; track=affect_track(project)
    joy=project.resolve_label('joy','Perceived Affect')
    # Historical files may carry authored annotation text alongside a mapped ID.
    record=Annotation(id='authored-affect',start_s=1,end_s=3,track_id=track.id,
        category=track.category,channel=track.channel,label='authored joy wording',label_id=joy.id,
        status='approved',attributes={'author_field':'keep'})
    project.annotations.append(record)
    window.select_annotation(record.id)
    assert window.editor.values()['label']=='authored joy wording'
    assert window.editor.values()['label_id']==joy.id
    window.editor.end.setValue(3.5)
    assert window.accept_edit()
    assert record.label=='authored joy wording' and record.label_id==joy.id
    assert record.attributes=={'author_field':'keep'}
    assert not window.qa_messages


def test_dimensional_alias_cannot_bypass_required_rating():
    project=Project(); track=affect_track(project)
    history=ProjectHistory(); session=EditSession(project,history)
    session.create(1,2,track.id); session.update(label='V/A')
    before=deepcopy(session.draft)
    with pytest.raises(ValueError,match='at least one'):
        session.accept()
    assert session.draft==before and not project.annotations and not history.can_undo
    session.update(attributes={'annotation_fields_version':1,'affect':{'valence':0}})
    record=session.accept()
    assert record.label_id==DIMENSIONAL_AFFECT_LABEL_ID


@pytest.mark.parametrize('value',[0,6,True,'3',.5,float('inf')])
def test_invalid_intensity_is_atomic(value):
    project=Project(); track=affect_track(project)
    history=ProjectHistory(); session=EditSession(project,history)
    session.create(1,2,track.id); original=deepcopy(session.draft)
    with pytest.raises(ValueError,match='intensity'):
        session.update(attributes={'annotation_fields_version':1,'affect':{'intensity':value}})
    assert session.draft==original and not project.annotations and not history.can_undo
