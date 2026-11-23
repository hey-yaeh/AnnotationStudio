"""Primary-part lists, legacy preservation and opt-in starter supplementation."""
import csv
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from annotationstudio.annotation_export import export_annotation_bundle, export_annotation_csv
from annotationstudio.dialogs import LabelDialog
from annotationstudio.models import Project, PRIMITIVE_CHANNELS, import_annotation_csv
from annotationstudio.ontology import ACTIVITY_EPISODE, RETIRED_PRIMITIVE_LABELS, UNCLASSIFIED_MOTION
from annotationstudio.track_setup import TrackDialog, TrackLabelDialog
from annotationstudio.ui import MainWindow


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    for method in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QMessageBox, method, lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(MainWindow, 'recovery_path', lambda self: tmp_path/'recovery.json')
    widget=MainWindow(recover=False)
    widget.timer.stop(); widget.autosave_timer.stop(); widget.show()
    qapp.processEvents()
    yield widget
    widget.session.cancel(); widget._preview_invalid=False
    widget.history.mark_saved(widget.project); widget.close(); widget.deleteLater()
    qapp.processEvents()


def names(options):
    return {options.list.item(i).text() for i in range(options.list.count())}


def test_add_track_preview_changes_with_primary_part(qapp):
    p=Project(); dialog=TrackDialog(project=p)
    dialog.channel.setCurrentText('Left Leg')
    assert {'hip flexion','bend left knee','kick left leg (kinematic)'} <= names(dialog.label_options)
    assert {'left leg movement','right leg movement','bend right knee'}.isdisjoint(names(dialog.label_options))
    assert 'wave right hand (kinematic)' not in names(dialog.label_options)
    for i in range(dialog.parts.count()):
        if dialog.parts.item(i).text()=='Right Arm':dialog.parts.item(i).setSelected(True)
    assert dialog.values()['body_parts']==['Left Leg','Right Arm']
    assert 'wave right hand (kinematic)' not in names(dialog.label_options)
    dialog.channel.setCurrentText('Right Hand')
    assert 'wave right hand (kinematic)' in names(dialog.label_options)
    assert 'wave left hand (kinematic)' not in names(dialog.label_options)
    dialog.channel.setCurrentText('Full Body')
    assert {'move legs apart','bring legs together','not visible'} == names(dialog.label_options)
    dialog.deleteLater()


def test_editing_part_filtered_list_keeps_hidden_saved_membership(qapp):
    p=Project(); track=next(t for t in p.tracks if t.role=='R01' and t.channel=='Left Leg')
    left=p.resolve_label('bend left knee','Motion Primitive')
    right=p.resolve_label('bend right knee','Motion Primitive')
    legacy=p.resolve_label('left leg movement','Motion Primitive',include_deprecated=True)
    p.set_track_label_ids(track,[left.id,right.id,legacy.id])
    before=deepcopy(track.extra)
    dialog=TrackLabelDialog(p,track)
    assert 'bend left knee' in names(dialog.options)
    assert {'bend right knee','left leg movement'}.isdisjoint(names(dialog.options))
    assert set(dialog.allowed_ids())=={left.id,right.id,legacy.id}
    assert track.extra==before
    dialog.deleteLater()


def test_current_historical_label_remains_editable_on_leg_track(window):
    p=window.project
    track=next(t for t in p.tracks if t.role=='R01' and t.channel=='Left Leg')
    a=p.add_annotation(1,2,track_id=track.id,role=track.role,category=track.category,
                       channel=track.channel,label='raise right arm',status='approved',source='manual')
    old_id=a.label_id
    window._refresh_annotations(); window.select_annotation(a.id)
    assert {'raise right arm','bend left knee'} <= set(window.label_palette.visible_label_names())
    assert 'Left Leg' in window.label_palette.context.text()
    window.editor.end.setValue(2.5)
    assert window.accept_edit()
    assert p.annotations[0].label_id==old_id
    assert p.annotations[0].label=='raise right arm'
    assert p.annotations[0].end_s==2.5


def test_new_track_types_and_search_are_scoped_to_the_active_ontology(window):
    project = window.project
    project.ensure_annotation_tracks()
    assert {track.role for track in project.tracks if track.workspace == 'Motion'} == {'R01', 'R02'}
    dialog = TrackDialog(project=project)
    assert dialog.category.findText('Activity Relation') == -1
    dialog.workspace.setCurrentText('Spatial')
    dialog.category.setCurrentText('Spatial Configuration')
    assert dialog.role.currentText() == 'Both'
    dialog.workspace.setCurrentText('Social')
    dialog.category.setCurrentText('Interaction Event')
    assert dialog.role.findText('Both') >= 0
    dialog.workspace.setCurrentText('Motion')
    dialog.channel.setCurrentText('Right Hand')
    dialog.label_options.search.setText('wave hand')
    assert [dialog.label_options.list.item(i).text() for i in range(dialog.label_options.list.count())
            if not dialog.label_options.list.item(i).isHidden()] == ['wave right hand (kinematic)']
    assert RETIRED_PRIMITIVE_LABELS.isdisjoint(names(dialog.label_options))
    dialog.deleteLater()

    wave = project.resolve_label('wave right hand (kinematic)', 'Motion Primitive')
    wave.aliases = ['my authored alias']
    manager = LabelDialog(project, 'Motion Primitive')
    manager.search.setText('wave hand')
    assert manager.list.count() == 2
    manager.search.setText('未分类运动候选')
    assert manager.list.count() == 1 and '[Candidate only]' in manager.list.item(0).text()
    assert wave.aliases == ['my authored alias']
    manager.deleteLater()


def test_unclassified_candidates_need_a_specific_label_and_review_is_undoable(window):
    project = window.project
    track = next(t for t in project.tracks if t.role == 'R02' and t.channel == 'Right Hand')
    proposal = project.add_annotation(1, 2, track_id=track.id, role=track.role, channel=track.channel,
                                      label=UNCLASSIFIED_MOTION, source='auto:graph')
    before = asdict(proposal)
    window.select_annotation(proposal.id)
    assert not window.editor.accept.isEnabled()
    assert not window.accept_edit()
    assert asdict(proposal) == before and not window.history.can_undo
    window.label_palette.search.setText('wave hand')
    assert window.label_palette.visible_label_names() == [UNCLASSIFIED_MOTION, 'wave right hand (kinematic)']
    window.editor.choose_label('wave hand')
    assert window.editor.accept.isEnabled()
    window.cancel_edit()
    assert asdict(proposal) == before
    window.select_annotation(proposal.id)
    window.editor.choose_label('wave hand')
    assert window.accept_edit()
    assert proposal.status == 'approved' and proposal.label == 'wave right hand (kinematic)'
    assert proposal.original == before['original'] and proposal.label_id != before['label_id']
    window.undo()
    assert asdict(project.annotations[0]) == before
    window.redo()
    assert project.annotations[0].label == 'wave right hand (kinematic)'


def test_historical_motion_rows_survive_json_bundle_and_reversible_view_filter(window, tmp_path):
    project = window.project
    pair = project.add_track(name='Old both', role='Both', category='Activity Relation', channel='Dyadic')
    local = next(t for t in project.tracks if t.role == 'R01' and t.channel == 'Left Leg')
    for i, (track, name, status) in enumerate((
        (pair, 'simultaneous movement', 'approved'),
        (local, 'left leg movement', 'approved'),
        (local, 'movement', 'pending'),
    )):
        label = project.resolve_label(name, track.category, include_deprecated=True)
        label.deprecated = False
        project.add_annotation(i + 1, i + 2, track_id=track.id, role=track.role, channel=track.channel,
                               category=track.category, label=name, label_id=label.id, status=status,
                               source='auto:graph', original={'label': name}, history=[{'original_event': i}])
    before = [asdict(a) for a in project.annotations]
    project.save(tmp_path / 'historical.studio.json')
    loaded = Project.load(tmp_path / 'historical.studio.json')
    assert [asdict(a) for a in loaded.annotations] == before
    loaded.save(tmp_path / 'roundtrip.studio.json')
    assert [asdict(a) for a in Project.load(tmp_path / 'roundtrip.studio.json').annotations] == before

    window._refresh_annotations()
    action = window.actions['Hide legacy tracks']
    assert pair in window.timeline.canvas.visible_tracks()
    action.trigger()
    assert pair not in window.timeline.canvas.visible_tracks() and pair.visible
    bundle = export_annotation_bundle(project, tmp_path, review_state='candidates_accepted', layout='both')
    paths = [Path(p) for p in bundle['csv_paths']]
    rows = [[asdict(a) for a in import_annotation_csv(path)] for path in paths]
    assert {row['id']: row for row in rows[0]} == {row['id']: row for row in before}
    assert {row['id']: row for group in rows[1:] for row in group} == {row['id']: row for row in before}
    assert bundle['type_counts'] == {'Motion Primitive': 2, 'Activity Relation': 1}
    action.trigger()
    assert pair in window.timeline.canvas.visible_tracks()
    with pytest.raises(ValueError, match='historical track'):
        window.session.create(8, 9, pair.id)
    window.select_annotation(before[1]['id'])
    window.editor.end.setValue(3.5)
    assert window.accept_edit()
    assert project.annotations[1].label_id == before[1]['label_id']


def test_opt_in_missing_tracks_is_idempotent_and_undoable(window):
    p=window.project
    p.tracks=[t for t in p.tracks if t.channel=='Left Arm']
    t=p.tracks[0]
    p.add_annotation(1,2,track_id=t.id,role=t.role,channel=t.channel,
                     category=t.category,label='raise left arm',status='approved')
    before=[asdict(a) for a in p.annotations]
    before_tracks=[asdict(t) for t in p.tracks]
    window._refresh_annotations()
    window.add_missing_primitive_tracks()
    assert len(p.tracks)==2*len(PRIMITIVE_CHANNELS)
    assert [asdict(a) for a in p.annotations]==before
    ids=[t.id for t in p.tracks]
    window.add_missing_primitive_tracks()
    assert [t.id for t in p.tracks]==ids
    window.undo()
    assert [asdict(t) for t in window.project.tracks]==before_tracks
    assert [asdict(a) for a in window.project.annotations]==before
    window.redo()
    assert [t.id for t in window.project.tracks]==ids


def test_activity_episode_authoring_and_export(window, tmp_path):
    project = window.project
    window.set_workflow('Activity')
    tracks = {track.role: track for track in window.timeline.canvas.visible_tracks()}
    assert set(tracks) == {'R01', 'R02'}
    assert all(track.category == ACTIVITY_EPISODE and not track.body_parts for track in tracks.values())
    cart = project.add_object('手推车')
    window.add_range(2., 5., tracks['R01'].id)
    assert window.editor.object_id.isVisible() and not window.editor.hand.isVisible()
    window.label_palette.search.setText('推车')
    assert 'push cart' in window.label_palette.visible_label_names()
    window.choose_palette_label('push cart')
    window.editor.object_id.setText(cart.id)
    window.editor.notes.setText('弯着腰向前推车')
    window.cancel_edit()
    assert not project.annotations

    window.add_range(2., 5., tracks['R01'].id)
    window.choose_palette_label('push cart')
    window.editor.object_id.setText(cart.id)
    window.editor.notes.setText('弯着腰向前推车')
    assert window.accept_edit()
    episode = window._selected()
    assert (episode.role, episode.channel, episode.category) == ('R01', 'Activity', ACTIVITY_EPISODE)
    assert (episode.start_s, episode.end_s, episode.label) == (2., 5., 'push cart')
    assert episode.attributes == {'body_parts': [], 'object_id': cart.id}

    window.add_range(6., 8., tracks['R02'].id)
    window.editor.label.setEditText('arrange materials')
    assert window.accept_edit()
    assert window._selected().label == 'arrange materials'
    assert 'object_id' not in window._selected().attributes

    saved = tmp_path / 'activity.studio.json'
    project.save(saved)
    reloaded = Project.load(saved)
    assert [asdict(a) for a in reloaded.annotations] == [asdict(a) for a in project.annotations]
    output = tmp_path / 'activity.csv'
    export_annotation_csv(project, output, categories=[ACTIVITY_EPISODE])
    assert [asdict(a) for a in import_annotation_csv(output)] == [asdict(a) for a in project.annotations]
    with output.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]['workspace'] == 'Activity'
    assert rows[0]['object_name'] == '手推车' and rows[0]['notes'] == '弯着腰向前推车'
    assert rows[1]['object_id'] == ''


def test_activity_tracks_are_an_explicit_addition_for_existing_projects(qapp, private_samples):
    private_samples('S004_I02_manual.studio.json')
    saved_example = Path(__file__).resolve().parents[1] / 'examples' / 'S004_I02_manual.studio.json'
    project = Project.load(saved_example)
    before = [asdict(track) for track in project.tracks]
    assert not any(track.category == ACTIVITY_EPISODE for track in project.tracks)
    dialog = TrackDialog('Activity', project=project)
    assert dialog.channel.isHidden() and dialog.parts.isHidden()
    assert dialog.values()['category'] == ACTIVITY_EPISODE
    assert dialog.values()['channel'] == 'Activity' and not dialog.values()['body_parts']
    dialog.deleteLater()
    assert {track.role for track in project.ensure_activity_tracks()} == {'R01', 'R02'}
    assert not project.ensure_activity_tracks()
    assert [asdict(track) for track in project.tracks[:len(before)]] == before
