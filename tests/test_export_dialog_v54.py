"""Exercise explicit export selections and real files through the desktop UI."""
from copy import deepcopy
import csv
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from annotationstudio.dialogs import ExportDialog
from annotationstudio.models import Annotation, Project, import_annotation_csv
from annotationstudio.ui import MainWindow


def seed(project):
    project.name='Export UI demonstration'
    counter=project.add_object('柜台',object_class='counter',id='counter_01')
    project.annotations=[
        Annotation('primitive_accepted',1,2,category='Motion Primitive',role='R01',
                   channel='Right Arm',label='movement',status='approved'),
        Annotation('primitive_candidate',2,3,category='Motion Primitive',role='R02',
                   channel='Left Arm',label='movement',status='pending',source='test-rule'),
        Annotation('hoi_accepted',1,4,category='Action / HOI',role='R02',channel='Hands',
                   label='rest on object',status='approved',attributes={'object_id':counter.id}),
        Annotation('custom_accepted',5,6,category='My custom type',role='R01',channel='Root',
                   label='our event',status='approved'),
        Annotation('legacy_accepted',6,7,category='Gaze / Attention',role='R02',channel='Head',
                   label='historical label',status='approved'),
        Annotation('transition_candidate',4,4,category='Turn Transition',role='Both',
                   channel='Speech',label='turn handover',status='pending',temporal_kind='point'),
        Annotation('hoi_rejected',8,9,category='Action / HOI',role='R01',channel='Hands',
                   label='rest on object',status='rejected',attributes={'object_id':counter.id}),
    ]
    return project


def item_for(dialog,category):
    return next(dialog.types.item(i) for i in range(dialog.types.count())
                if dialog.types.item(i).data(Qt.UserRole)==category)


def choose_types(dialog,categories):
    dialog.type_mode.setCurrentIndex(1)
    dialog._set_all_types(False)
    for category in categories:item_for(dialog,category).setCheckState(Qt.Checked)


def choose_output(dialog,key):
    index=dialog.output.findData(key)
    assert index>=0
    dialog.output.setCurrentIndex(index)


@pytest.fixture
def dialog(qapp):
    widget=ExportDialog(project=seed(Project()))
    widget.show(); qapp.processEvents()
    yield widget
    widget.close(); widget.deleteLater(); qapp.processEvents()


@pytest.fixture
def window(qapp,monkeypatch,tmp_path):
    messages=[]
    for method in ('warning','critical','information'):
        monkeypatch.setattr(QMessageBox,method,
            lambda parent,title,text,*args,**kwargs:messages.append((title,text)) or QMessageBox.Ok)
    monkeypatch.setattr(MainWindow,'recovery_path',lambda self:tmp_path/'recovery.json')
    widget=MainWindow(recover=False)
    widget.timer.stop(); widget.autosave_timer.stop()
    seed(widget.project); widget.project.path=tmp_path/'Practice_Session.studio.json'
    widget.show(); qapp.processEvents(); widget.qa_messages=messages
    yield widget
    widget.session.cancel(); widget._preview_invalid=False
    widget.history.mark_saved(widget.project); widget.close(); widget.deleteLater()
    qapp.processEvents()


def scripted_dialog(monkeypatch,configure,result=QDialog.Accepted):
    class ScriptedExport(ExportDialog):
        def exec(self):
            configure(self)
            return result
    monkeypatch.setattr('annotationstudio.ui.ExportDialog',ScriptedExport)


def test_defaults_include_custom_and_legacy_types_without_modifying_project(dialog):
    before=deepcopy(dialog.project.to_dict())
    assert dialog.review_state()=='accepted'
    assert dialog.export_layout()=='both'
    assert dialog.selected_categories() is None
    assert dialog.type_panel.isHidden()
    assert '4 annotations' in dialog.summary.text() and '4 types' in dialog.summary.text()
    assert dialog.export_button.isEnabled()
    assert item_for(dialog,'My custom type') is not None
    assert item_for(dialog,'Gaze / Attention') is not None
    assert dialog.project.to_dict()==before


def test_explicit_types_empty_selection_and_review_changes_preserve_choices(dialog):
    choose_types(dialog,[])
    assert dialog.selected_categories()==[]
    assert not dialog.export_button.isEnabled()
    assert '0 annotations' in dialog.summary.text()
    item_for(dialog,'My custom type').setCheckState(Qt.Checked)
    item_for(dialog,'Motion Primitive').setCheckState(Qt.Checked)
    assert '2 annotations' in dialog.summary.text()
    dialog.scope.setCurrentIndex(1)
    assert dialog.review_state()=='candidates_accepted'
    assert set(dialog.selected_categories())=={'My custom type','Motion Primitive'}
    assert '3 annotations' in dialog.summary.text()
    assert item_for(dialog,'Motion Primitive').text().endswith('·   2')
    dialog.type_mode.setCurrentIndex(0)
    assert dialog.selected_categories() is None and '6 annotations' in dialog.summary.text()
    dialog.type_mode.setCurrentIndex(1)
    assert set(dialog.selected_categories())=={'My custom type','Motion Primitive'}
    dialog._set_all_types(True)
    dialog.scope.setCurrentIndex(2)
    assert dialog.review_state()=='all' and '7 annotations' in dialog.summary.text()


def test_eaf_keeps_type_filter_and_explains_point_limit_without_silent_dropping(dialog):
    choose_output(dialog,'by_type')
    dialog.scope.setCurrentIndex(1)
    dialog.format.setCurrentIndex(1)
    assert dialog.output.isHidden() and dialog.output_label.isHidden()
    assert dialog.export_layout()=='combined'
    assert not dialog.export_button.isEnabled()
    assert '1 point event' in dialog.note.text()
    assert '6 annotations' in dialog.summary.text()
    choose_types(dialog,['Action / HOI'])
    assert dialog.export_button.isEnabled() and '1 annotations' in dialog.summary.text()
    assert 'One EAF file' in dialog.note.text()
    dialog.format.setCurrentIndex(0)
    assert dialog.output.isVisible() and dialog.export_layout()=='by_type'
    assert dialog.selected_categories()==['Action / HOI']


def test_empty_project_cannot_export(qapp):
    dialog=ExportDialog(project=Project())
    try:
        assert not dialog.export_button.isEnabled()
        assert 'No annotations match' in dialog.note.text()
        dialog.type_mode.setCurrentIndex(1)
        dialog._set_all_types(True)
        assert not dialog.export_button.isEnabled()
    finally:dialog.deleteLater()


def test_single_type_csv_uses_selected_records_and_object_name(window,monkeypatch,tmp_path):
    before=deepcopy(window.project.to_dict())
    defaults=[]
    def configure(dialog):
        choose_output(dialog,'combined'); choose_types(dialog,['Action / HOI'])
    scripted_dialog(monkeypatch,configure)
    def save(parent,title,default,file_filter):
        defaults.append(default)
        return str(tmp_path/'only_hoi'),file_filter
    monkeypatch.setattr(QFileDialog,'getSaveFileName',save)
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:pytest.fail('Single CSV must ask for a file'))
    window.export_annotations()
    path=tmp_path/'only_hoi.csv'
    with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==1 and rows[0]['id']=='hoi_accepted'
    assert rows[0]['object_name']=='柜台' and rows[0]['role']=='R02'
    assert rows[0]['category']=='Action / HOI'
    assert Path(defaults[0]).name=='Practice_Session_hoi.csv'
    assert import_annotation_csv(path)[0].attributes=={'object_id':'counter_01'}
    assert window.project.to_dict()==before and not window.qa_messages


def annotation_tables(parent):
    tables={}
    for path in parent.rglob('*.csv'):
        with path.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream)
            if reader.fieldnames and 'category' in reader.fieldnames:tables[path.name]=list(reader)
    return tables


def test_combined_and_split_export_uses_explicit_types_across_workspaces(window,monkeypatch,tmp_path):
    window.set_workflow('Affect',force=True)
    before=deepcopy(window.project.to_dict())
    def configure(dialog):
        choose_output(dialog,'both'); dialog.scope.setCurrentIndex(1)
        choose_types(dialog,['Motion Primitive','Action / HOI'])
    scripted_dialog(monkeypatch,configure)
    destination=tmp_path/'exports'; destination.mkdir()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(destination))
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:pytest.fail('Bundle must ask for a parent folder'))
    window.export_annotations()
    tables=annotation_tables(destination)
    assert len(tables)==3
    groups=[{row['id'] for row in rows} for rows in tables.values()]
    expected={'primitive_accepted','primitive_candidate','hoi_accepted'}
    assert expected in groups
    partials=[group for group in groups if group!=expected]
    assert len(partials)==2 and set.union(*partials)==expected
    assert not set.intersection(*partials)
    assert len(list(destination.iterdir()))==1
    assert window.project.to_dict()==before and not window.qa_messages


def test_separate_only_exports_selected_custom_type_without_combined_copy(window,monkeypatch,tmp_path):
    def configure(dialog):
        choose_output(dialog,'by_type'); choose_types(dialog,['My custom type'])
    scripted_dialog(monkeypatch,configure)
    destination=tmp_path/'exports'; destination.mkdir()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(destination))
    window.export_annotations()
    tables=annotation_tables(destination)
    assert len(tables)==1
    assert [row['id'] for row in next(iter(tables.values()))]==['custom_accepted']
    assert not window.qa_messages


@pytest.mark.parametrize('layout',['combined','both'])
def test_cancel_destination_has_no_files_or_project_edits(window,monkeypatch,tmp_path,layout):
    before=deepcopy(window.project.to_dict()); files=set(tmp_path.rglob('*'))
    scripted_dialog(monkeypatch,lambda dialog:choose_output(dialog,layout))
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:'')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:('',''))
    monkeypatch.setattr('annotationstudio.ui.export_annotation_csv',lambda *a,**k:pytest.fail('Cancelled'))
    monkeypatch.setattr('annotationstudio.ui.export_annotation_bundle',lambda *a,**k:pytest.fail('Cancelled'))
    window.export_annotations()
    assert set(tmp_path.rglob('*'))==files and window.project.to_dict()==before
    assert not window.qa_messages


def test_cancel_export_dialog_does_not_open_destination_or_modify_project(window,monkeypatch):
    before=deepcopy(window.project.to_dict())
    scripted_dialog(monkeypatch,lambda dialog:choose_types(dialog,['Action / HOI']),QDialog.Rejected)
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:pytest.fail('Cancelled dialog'))
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:pytest.fail('Cancelled dialog'))
    window.export_annotations()
    assert window.project.to_dict()==before


def test_eaf_selection_preserves_type_and_review_filters(window,monkeypatch,tmp_path):
    def configure(dialog):
        dialog.format.setCurrentIndex(1); dialog.scope.setCurrentIndex(2)
        choose_types(dialog,['Action / HOI'])
    scripted_dialog(monkeypatch,configure)
    path=tmp_path/'hoi.eaf'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(path),''))
    window.export_annotations()
    root=ET.parse(path).getroot()
    assert len(root.findall('.//ALIGNABLE_ANNOTATION'))==2
    assert {tier.attrib['PARTICIPANT'] for tier in root.findall('TIER')}=={'R01','R02'}
    assert all('Action / HOI' in tier.attrib['TIER_ID'] for tier in root.findall('TIER'))
    assert not window.qa_messages


def test_eaf_controller_still_rejects_points_before_overwriting_file(window,monkeypatch,tmp_path):
    def configure(dialog):
        dialog.format.setCurrentIndex(1); dialog.scope.setCurrentIndex(1)
        choose_types(dialog,['Turn Transition'])
        assert not dialog.export_button.isEnabled()
    # Simulate a stale/programmatic dialog result: backend safety must remain.
    scripted_dialog(monkeypatch,configure)
    path=tmp_path/'points.eaf'; path.write_text('existing contents')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(path),''))
    window.export_annotations()
    assert path.read_text()=='existing contents'
    assert window.qa_messages and window.qa_messages[-1][0]=='Export failed'
    assert 'Point events' in window.qa_messages[-1][1]
