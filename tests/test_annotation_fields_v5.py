"""Human interpretation fields, directed interaction and explicit lane setup."""
from copy import deepcopy
from dataclasses import asdict
import json
import uuid

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QMessageBox, QStyle, QStyleOptionComboBox

from annotationstudio.editing import EditSession, ProjectHistory
from annotationstudio.editor import SegmentEditor
from annotationstudio.models import Project, export_csv, import_annotation_csv
from annotationstudio.ontology import WORKSPACE_CATEGORIES, category_info
from annotationstudio.track_setup import TrackDialog
from annotationstudio.ui import MainWindow
from annotationstudio.theme import STYLE


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
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
    assert index>=0, value
    combo.setCurrentIndex(index)


def test_explicit_supplement_preserves_authored_lanes_and_does_not_run_on_load(tmp_path):
    project=Project()
    authored=project.add_track(name='Our hand-support lane',role='R01',
        category='Physical Interaction',channel='Right Hand',visible=False,
        extra={'allowed_label_ids':[],'target_role':'R02'})
    snapshot=asdict(authored)
    project.save(tmp_path/'before.json')
    loaded=Project.load(tmp_path/'before.json')
    assert [asdict(track) for track in loaded.tracks]==[asdict(track) for track in project.tracks]
    additions=loaded.ensure_annotation_tracks()
    assert additions and asdict(loaded.get_track(authored.id))==snapshot
    assert len([track for track in loaded.tracks
                if track.role=='R01' and track.category=='Physical Interaction'])==1
    for category in WORKSPACE_CATEGORIES['Overview']:
        if category in ('Motion Primitive','QC / Notes'):continue
        expected={'Both'} if category_info(category)['actor_scope']=='pair' else {'R01','R02'}
        assert expected<={track.role for track in loaded.tracks if track.category==category}
    assert not any(track.category in ('Facial Expression','Gaze / Attention','QC / Notes')
                   for track in additions)
    before=loaded.to_dict()
    assert loaded.ensure_annotation_tracks()==[]
    assert loaded.to_dict()==before


def test_supplement_invalid_roles_is_atomic_and_single_actor_has_no_pair_lanes():
    project=Project(); project.tracks.clear()
    for roles in ('R01',None,['R01','Both'],['R01',None]):
        with pytest.raises(ValueError):project.ensure_annotation_tracks(roles)
        assert project.tracks==[]
    assert project.ensure_annotation_tracks([])==[]
    additions=project.ensure_annotation_tracks(['R02','R02'])
    assert additions and all(track.role=='R02' for track in additions)
    assert not any(category_info(track.category)['actor_scope']=='pair' for track in additions)


@pytest.mark.parametrize('key,value',[
    ('valence',3),('valence',-3),('valence',True),('valence','0'),
    ('valence',0.5),('arousal',0),('arousal',6),('arousal',float('nan')),
])
def test_invalid_ratings_cannot_mutate_draft_project_or_history(key,value):
    project=Project()
    track=project.add_track(name='Affect',category='Perceived Affect',channel='Emotion')
    history=ProjectHistory(); session=EditSession(project,history)
    session.create(1,3,track.id)
    draft=deepcopy(session.draft)
    before=project.to_dict()
    with pytest.raises(ValueError,match='Affect'):
        session.update(attributes={'annotation_fields_version':1,'affect':{key:value}})
    assert session.draft==draft and project.to_dict()==before
    assert not history.can_undo
    # A backend cannot bypass this contract by adding an annotation directly.
    with pytest.raises(ValueError,match='Affect'):
        project.add_annotation(1,3,category='Perceived Affect',
            attributes={'annotation_fields_version':1,'affect':{key:value}})
    assert project.to_dict()==before


def test_affect_unknown_neutral_model_score_cancel_and_roundtrip(window,tmp_path):
    project=window.project
    track=project.add_track(name='R02 affect',role='R02',category='Perceived Affect',channel='Emotion')
    record=project.add_annotation(1,4,role='R02',track_id=track.id,category=track.category,
        channel='Emotion',label='surprise',source='auto:external-example',confidence=.78,
        attributes={'future_annotation_metadata':{'retain':True}})
    original=deepcopy(asdict(record))
    window.select_annotation(record.id)
    assert window.editor.valence.currentData() is None
    assert window.editor.arousal.currentData() is None
    choose(window.editor.valence,0)
    choose(window.editor.arousal,4)
    choose(window.editor.judgment_certainty,'low')
    choose(window.editor.evidence_origin,'observed_expression')
    window.editor.evidence_sources.set_sources(['voice','reference_video'])
    assert record.attributes==original['attributes']
    assert window.session.draft.attributes['affect']=={'valence':0,'arousal':4}
    window.cancel_edit()
    assert asdict(record)==original
    window.select_annotation(record.id)
    choose(window.editor.valence,0)
    choose(window.editor.arousal,4)
    choose(window.editor.arousal,None)
    choose(window.editor.judgment_certainty,'high')
    choose(window.editor.evidence_origin,'observed_expression')
    window.editor.evidence_sources.set_sources(['voice','body_motion'])
    assert window.accept_edit()
    assert record.status=='approved' and record.confidence==.78
    assert record.source=='auto:external-example'
    assert record.attributes['affect']=={'valence':0,'arousal':None}
    assert record.attributes['human_judgment']=={
        'certainty':'high','evidence_origin':'observed_expression',
        'evidence_sources':['voice','body_motion']}
    assert record.attributes['future_annotation_metadata']=={'retain':True}
    assert record.original==original['original']
    assert len(record.history)==len(original['history'])+1
    project.save(tmp_path/'affect.json')
    reloaded=Project.load(tmp_path/'affect.json').annotations[0]
    export_csv(project.annotations,tmp_path/'affect.csv')
    imported=import_annotation_csv(tmp_path/'affect.csv')[0]
    assert asdict(reloaded)==asdict(record)==asdict(imported)
    window.undo()
    assert asdict(project.annotations[0])==original
    window.redo()
    assert project.annotations[0].attributes['affect']['arousal'] is None
    assert not window.qa_messages


def test_physical_interaction_target_and_outcome_are_committed_together(window):
    project=window.project
    track=project.add_track(name='Assistance',category='Physical Interaction',
        channel='Full Body',role='R01')
    window.add_range(3,7,track.id)
    window.editor.label.setEditText('assist partner to rise')
    assert not window.editor.target_role.isHidden()
    assert window.editor.object_id.isHidden()
    window.editor.target_role.setCurrentText('R02')
    choose(window.editor.physical_outcome,'partial')
    choose(window.editor.judgment_certainty,'medium')
    window.editor.evidence_sources.set_sources(['reference_video'])
    assert not project.annotations
    assert window.accept_edit()
    record=project.annotations[0]
    assert record.role=='R01' and record.attributes['target_role']=='R02'
    assert record.attributes['physical_interaction']=={'outcome':'partial'}
    assert 'object_id' not in record.attributes
    window.undo(); assert not project.annotations
    window.redo()
    assert project.annotations[0].attributes['target_role']=='R02'
    assert not window.qa_messages


def test_cognitive_source_is_explicit_and_unknown_future_fields_survive(window):
    project=window.project
    track=project.add_track(name='Recognition',category='Cognitive State Expression',
        channel='Dyadic',role='R02')
    original_fields={'annotation_fields_version':1,
        'human_judgment':{'certainty':'future-certainty','evidence_origin':'future-origin',
            'evidence_sources':['future_sensor'],'future_field':{'raw':17}},
        'physical_interaction':{'future_contact_metadata':'retain'},'target_role':'R01'}
    record=project.add_annotation(2,3,role='R02',category=track.category,track_id=track.id,
        label='recognition uncertainty expressed',attributes=deepcopy(original_fields))
    window.select_annotation(record.id)
    assert window.editor.evidence_origin.currentData()=='future-origin'
    assert window.editor.judgment_certainty.currentData()=='future-certainty'
    assert window.editor.evidence_sources.selected_sources()==['future_sensor']
    window.editor.end.setValue(3.5)
    assert window.accept_edit()
    assert record.attributes==original_fields
    window.select_annotation(record.id)
    choose(window.editor.evidence_origin,'scenario_prompt')
    assert 'does not establish observed' in window.editor.interpretation_hint.text()
    assert window.accept_edit()
    human=record.attributes['human_judgment']
    assert human['evidence_origin']=='scenario_prompt'
    assert human['certainty']=='future-certainty'
    assert human['future_field']=={'raw':17}
    assert human['evidence_sources']==['future_sensor']
    assert record.attributes['physical_interaction']==original_fields['physical_interaction']
    assert not window.qa_messages


def test_new_directed_types_can_select_partner_without_invented_default(qapp):
    dialog=TrackDialog(workspace='Social',project=Project())
    for category in ('Physical Interaction','Cognitive State Expression'):
        dialog.category.setCurrentText(category)
        assert dialog.category.currentText()==category
        dialog.role.setCurrentText('R01')
        assert dialog.target_role.isEnabled()
        assert 'target_role' not in dialog.values()['extra']
        choose(dialog.target_role,'R02')
        assert dialog.values()['extra']['target_role']=='R02'
        assert dialog.target_role.findData('R01')<0
        dialog.role.setCurrentText('R02')
        assert 'target_role' not in dialog.values()['extra']
    dialog.close(); dialog.deleteLater()


def test_editing_certainty_preserves_legacy_unversioned_affect_scale(window):
    project=window.project
    track=project.add_track(name='Legacy affect scale',category='Perceived Affect',channel='Emotion')
    legacy={'valence':.5,'arousal':'unrated in old protocol','scale':'continuous legacy'}
    record=project.add_annotation(1,3,track_id=track.id,category=track.category,
        label='surprise',attributes={'affect':deepcopy(legacy),'custom_record':17})
    window.select_annotation(record.id)
    assert window.editor.valence.currentData()==.5
    choose(window.editor.judgment_certainty,'high')
    assert window.accept_edit()
    assert record.attributes['affect']==legacy
    assert 'annotation_fields_version' not in record.attributes
    assert record.attributes['human_judgment']['certainty']=='high'
    window.select_annotation(record.id)
    choose(window.editor.valence,1)
    assert window.accept_edit()
    assert record.attributes['affect']=={**legacy,'valence':1}
    assert 'annotation_fields_version' not in record.attributes
    assert record.attributes['custom_record']==17
    assert not window.qa_messages


def test_old_neutral_id_is_hidden_for_new_labels_but_existing_record_is_editable(qapp,tmp_path):
    project=Project()
    category='Perceived Affect'; name='neutral / no reliable cue'
    label_id=str(uuid.uuid5(uuid.UUID('f9ee1185-2f20-5d88-bafd-9413131745c5'),
                           f'core:{category}:{name}'))
    old=project.get_label(label_id)
    assert old is not None
    old.deprecated=False; old.definition='Our saved v0.4 definition'
    track=project.add_track(name='Original affect lane',category=category,channel='Emotion')
    record=project.add_annotation(1,2,track_id=track.id,category=category,channel='Emotion',
        label=name,label_id=label_id,status='approved',attributes={'legacy':'retain'})
    original_label=asdict(old)
    path=tmp_path/'legacy.json'; path.write_text(json.dumps(project.to_dict()))
    loaded=Project.load(path)
    old=loaded.get_label(label_id)
    assert asdict(old)==original_label
    assert old not in loaded.labels_for_track(track.id)
    assert old in loaded.labels_for_track(track.id,include_deprecated=True)
    session=EditSession(loaded,ProjectHistory()); session.begin(record.id)
    editor=SegmentEditor(); editor.bind(session.draft,loaded)
    assert editor.label.currentText()==name
    editor.end.setValue(2.5)
    session.update(**editor.values()); saved=session.accept()
    assert saved.label_id==label_id and saved.label==name
    assert saved.attributes=={'legacy':'retain'}
    assert asdict(loaded.get_label(label_id))==original_label
    editor.deleteLater()


def test_invalid_structured_csv_export_does_not_truncate_existing_destination(tmp_path):
    project=Project()
    record=project.add_annotation(1,2,label='movement')
    record.attributes={'annotation_fields_version':1,'affect':{'valence':9}}
    path=tmp_path/'existing.csv'; path.write_text('existing review data')
    with pytest.raises(ValueError,match='valence'):export_csv([record],path)
    assert path.read_text()=='existing review data'


def test_styled_minimum_window_reserves_readable_editor_rows(window,qapp):
    previous_style=qapp.styleSheet()
    qapp.setStyleSheet(STYLE)
    try:
        project=window.project
        track=project.add_track(name='Affect',category='Perceived Affect',channel='Emotion')
        record=project.add_annotation(1,4,track_id=track.id,category=track.category,
            channel=track.channel,label='surprise',attributes={
                'annotation_fields_version':1,'affect':{'valence':-1,'arousal':4},
                'human_judgment':{'evidence_origin':'observed_expression'}})
        window.resize(1220,800); window.select_annotation(record.id)
        window.main_split.setSizes([400,400])
        for _ in range(4):qapp.processEvents()
        assert (window.width(),window.height())==(1220,800)
        editor=window.editor
        assert editor.label.isVisible() and editor.intensity.isVisible()
        assert not editor.valence.isVisible() and not editor.evidence_fields.isVisible()
        collapsed_minimum=editor.minimumHeight()
        # The expanded optional view must remain usable; it is no longer the
        # initial Affect layout requested by the user.
        choose(editor.affect_mode,'valence_arousal')
        editor.more_details.setChecked(True)
        for _ in range(4):qapp.processEvents()
        structured_minimum=editor.minimumHeight()
        assert structured_minimum>collapsed_minimum
        assert editor.height()>=editor.minimumSizeHint().height()
        bounds=QRect(editor.mapTo(window.centralWidget(),QPoint(0,0)),editor.size())
        assert window.centralWidget().rect().contains(bounds)
        groups=[
            (editor.dimensional_summary,editor.start,editor.end,editor.accept),
            (editor.notes,editor.reviewer),
            (editor.affect_mode,editor.valence,editor.arousal,editor.judgment_certainty),
            (editor.evidence_sources,editor.evidence_origin),
        ]
        previous_bottom=-1
        for controls in groups:
            rectangles=[]
            for control in controls:
                assert control.isVisible()
                assert control.height()>=control.minimumSizeHint().height()
                rectangle=QRect(control.mapTo(editor,QPoint(0,0)),control.size())
                assert editor.rect().contains(rectangle)
                rectangles.append(rectangle)
            assert min(rectangle.top() for rectangle in rectangles)>previous_bottom
            previous_bottom=max(rectangle.bottom() for rectangle in rectangles)
        assert window.right_tabs_area.verticalScrollBar().maximum()>0
        option=QStyleOptionComboBox(); editor.evidence_origin.initStyleOption(option)
        text_rect=editor.evidence_origin.style().subControlRect(
            QStyle.CC_ComboBox,option,QStyle.SC_ComboBoxEditField,editor.evidence_origin)
        assert editor.evidence_origin.fontMetrics().horizontalAdvance(
            editor.evidence_origin.currentText())<=text_rect.width()
        # Switching to an ordinary type releases the two optional rows.
        window.cancel_edit()
        primitive=project.tracks[0]
        base=project.add_annotation(5,6,track_id=primitive.id,category=primitive.category,
            channel=primitive.channel,label='movement')
        window.select_annotation(base.id)
        for _ in range(4):qapp.processEvents()
        assert editor.domain_fields.isHidden() and editor.evidence_fields.isHidden()
        assert editor.minimumHeight()<structured_minimum
        assert (window.width(),window.height())==(1220,800)
    finally:
        qapp.setStyleSheet(previous_style)
        qapp.processEvents()
