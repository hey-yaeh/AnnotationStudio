"""User-facing access to the expanded vocabulary without rewriting old work."""
from copy import deepcopy
from dataclasses import asdict

import pytest
from PySide6.QtWidgets import QMessageBox

from annotationstudio.models import Project
from annotationstudio.ui import MainWindow


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    for method in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QMessageBox, method, lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(MainWindow, 'recovery_path', lambda self: tmp_path / 'recovery.json')
    widget = MainWindow(recover=False)
    widget.timer.stop(); widget.autosave_timer.stop(); widget.show()
    qapp.processEvents()
    yield widget
    widget.session.cancel(); widget._preview_invalid = False
    widget.history.mark_saved(widget.project); widget.close(); widget.deleteLater()
    qapp.processEvents()


def test_supplement_categories_keeps_authored_data_and_single_undo(window):
    p = window.project
    authored = p.add_track(name='My reviewed posture', category='Body Posture',
                           role='R01', channel='Full Body', visible=False,
                           extra={'allowed_label_ids': [], 'custom_note': 'retain'})
    p.add_annotation(2, 4, track_id=authored.id, category='Body Posture',
                     role='R01', channel='Full Body', label='sitting', status='approved')
    before_tracks = [asdict(t) for t in p.tracks]
    before_annotations = [asdict(a) for a in p.annotations]
    before_labels = [asdict(l) for l in p.labels]
    window._refresh_annotations()
    window.add_missing_annotation_tracks()
    assert [asdict(a) for a in p.annotations] == before_annotations
    assert [asdict(l) for l in p.labels] == before_labels
    assert asdict(p.get_track(authored.id)) == before_tracks[-1]
    for category in ('Whole-body Action', 'Gait Pattern', 'Physical Interaction',
                     'Cognitive State Expression', 'Speech Disfluency'):
        assert {t.role for t in p.tracks if t.category == category} == {'R01', 'R02'}
    assert not any(t.category in ('Facial Expression', 'Gaze / Attention') for t in p.tracks)
    after = [asdict(t) for t in p.tracks]
    window.add_missing_annotation_tracks()
    assert [asdict(t) for t in p.tracks] == after
    window.undo()
    assert [asdict(t) for t in window.project.tracks] == before_tracks
    assert [asdict(a) for a in window.project.annotations] == before_annotations
    window.redo()
    assert [asdict(t) for t in window.project.tracks] == after


@pytest.mark.parametrize('workspace,category,label', [
    ('Motion', 'Whole-body Action', 'fall down'),
    ('Motion', 'Gait Pattern', 'staggering gait'),
    ('Social', 'Physical Interaction', 'assist partner to rise'),
    ('Social', 'Interaction Event', 'request assistance'),
    ('Affect', 'Perceived Affect', 'perceived neutral'),
    ('Motion', 'Hand Behavior', 'hand under chin'),
    ('Motion', 'Hand Behavior', 'hand to chin'),
    ('Motion', 'Hand Behavior', 'hand to cheek'),
    ('Motion', 'Hand Behavior', 'chin resting on hand'),
    ('Motion', 'Hand Behavior', 'cheek resting on hand'),
])
def test_new_label_access_draw_choose_cancel_and_accept(window, workspace, category, label):
    p = window.project
    track = p.add_track(name=category, category=category, role='R01')
    window.set_workflow(workspace, force=True)
    window._refresh_annotations(); window._track_selected(track.id)
    assert category in {window.submodule.itemText(i) for i in range(window.submodule.count())}
    assert label in window.label_palette.visible_label_names()
    before = deepcopy(p.to_dict())
    window.add_range(1, 3, track.id)
    window.choose_palette_label(label)
    assert window.session.draft.label == label and not p.annotations
    window.cancel_edit()
    assert p.to_dict() == before
    window.add_range(1, 3, track.id); window.choose_palette_label(label)
    assert window.accept_edit()
    assert len(p.annotations) == 1
    assert p.annotations[0].label == label and p.annotations[0].status == 'approved'
    assert p.annotations[0].role == 'R01'
