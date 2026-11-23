"""Controller contracts and non-destructive review filtering for side panels."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from annotationstudio.models import Annotation, Asset
from annotationstudio.panels import AutoPanel, ReviewPanel

_APP = None


@pytest.fixture(scope='module')
def app(qapp):
    global _APP
    _APP = qapp
    return _APP


@pytest.fixture
def panel(app, monkeypatch):
    from annotationstudio import audio_models
    monkeypatch.setattr(audio_models, 'model_status', lambda: [
        {'id': 'energy', 'available': True, 'detail': 'Activity baseline'},
        {'id': 'silero', 'available': False, 'detail': 'Install optional dependencies'},
        {'id': 'yamnet', 'available': True, 'can_download': False, 'detail': 'Local model required'},
    ])
    widget = AutoPanel()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_motion_scope_contract_and_low_threshold(panel):
    assert not panel.motion_run.isEnabled()
    assert 'BVH / pose source' in panel.motion_source.text()
    panel.set_assets([], motion_roles=['R01'])
    assert panel.motion_run.isEnabled()
    panel.motion_role.setCurrentIndex(panel.motion_role.findData('R02'))
    assert not panel.motion_run.isEnabled()
    panel.motion_role.setCurrentIndex(panel.motion_role.findData('all'))
    panel.threshold.setValue(.05)
    panel.set_marked_range(4.25, 7.75)
    result = panel.motion_options()
    assert result['master_start'] == 4.25
    assert result['master_end'] == 7.75
    assert result['cfg'].start_s == 0.  # Controller converts per asset offset.
    assert result['cfg'].low_fraction <= result['cfg'].high_fraction
    assert result['cfg'].fine_primitives
    panel.fine_primitives.setChecked(False)
    assert not panel.motion_options()['cfg'].fine_primitives
    assert set(result['roles']) == {'R01', 'R02'}
    panel._select_parts(False)
    with pytest.raises(ValueError, match='at least one'):
        panel.motion_options()


def test_audio_selection_explicit_channels_and_busy_state(panel):
    assets = [Asset('audio-id', 'audio', 'R01', '/unused.wav', name='Lavalier'),
              Asset('disabled-id', 'audio', 'R02', '/disabled.wav', enabled=False),
              Asset('video-id', 'video', 'R01', '/video.mp4')]
    panel.set_assets(assets, motion_roles=['R01'])
    assert panel.audio_asset.count() == 1
    assert panel.audio_asset.currentData() == 'audio-id'
    assert panel.audio_options()['channel'] is None
    assert panel.audio_options()['db_threshold'] == -36.
    assert panel.audio_run.isEnabled()
    panel.audio_channel.setCurrentIndex(panel.audio_channel.findData(1))
    assert panel.audio_options()['channel'] == 1  # Channel 2 is zero based.
    panel.audio_model.setCurrentIndex(panel.audio_model.findData('yamnet'))
    assert not panel.audio_run.isEnabled()
    assert not panel.audio_options()['download']
    panel.model_path.setText('/local/savedmodel')
    assert panel.audio_run.isEnabled()
    assert panel.audio_options()['threshold'] == pytest.approx(.35)
    assert panel.motion_run.isEnabled()
    panel.set_busy(True)
    assert not panel.motion_run.isEnabled()
    assert not panel.audio_run.isEnabled()
    assert panel.cancel_button.isEnabled()
    panel.set_busy(False)
    assert panel.audio_run.isEnabled()
    assert not panel.cancel_button.isEnabled()

    panel._statuses['yamnet']['bundled_model_path'] = '/bundled/model'
    panel.model_path.clear()
    assert panel.audio_run.isEnabled()
    assert not panel.audio_options()['download']


def test_review_population_does_not_select_and_click_emits_id(app):
    panel = ReviewPanel()
    candidates = [Annotation('candidate', 1., 2., label='hand motion'),
                  Annotation('accepted', 3., 4., label='smile', status='approved'),
                  Annotation('rejected', 5., 6., label='noise', status='rejected')]
    spy = QSignalSpy(panel.selected)
    panel.populate(candidates)
    assert panel.table.rowCount() == 1
    assert spy.count() == 0
    panel.filter.setCurrentIndex(panel.filter.findData('all'))
    assert panel.table.rowCount() == 3
    panel.resize(320, 600)
    panel.show()
    app.processEvents()
    target = panel.table.visualItemRect(panel.table.item(1, 2)).center()
    QTest.mouseClick(panel.table.viewport(), Qt.LeftButton, pos=target)
    assert spy.count() == 1
    assert spy.at(0) == ['accepted']
    panel.populate(candidates)
    assert spy.count() == 1
    panel.search.setText('hand motion')
    assert panel.table.rowCount() == 1
    assert spy.count() == 1
    assert [item.status for item in candidates] == ['pending', 'approved', 'rejected']
    panel.set_latest_batch({'candidate'})
    panel.show_latest_pending()
    assert panel.table.rowCount() == 1 and panel.search.text() == ''
    assert panel.table.item(0, 0).data(Qt.UserRole) == 'candidate'
    panel.filter.setCurrentIndex(panel.filter.findData('all'))
    assert panel.table.rowCount() == 1
    panel.latest_only.setChecked(False)
    assert panel.table.rowCount() == 3
    assert spy.count() == 1
    panel.close()
    panel.deleteLater()
    app.processEvents()
