"""One QApplication for the full GUI test session, with explicit Qt cleanup."""
import os
import sys
import gc
from pathlib import Path
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
if sys.platform.startswith('linux') and os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
    # Headless test containers may have no configured PipeWire client/server.
    # This is a test setting only, never a Windows application default.
    os.environ.setdefault('QT_AUDIO_BACKEND', 'pulseaudio')

_QT_APPLICATION = None


@pytest.fixture(scope='session')
def qapp():
    global _QT_APPLICATION
    QtWidgets = pytest.importorskip('PySide6.QtWidgets')
    from PySide6.QtCore import QCoreApplication, QEvent
    _QT_APPLICATION = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _QT_APPLICATION.setQuitOnLastWindowClosed(False)
    _QT_APPLICATION.setApplicationName('Annotation Studio QA')
    _QT_APPLICATION.setOrganizationName('AnnotationStudioTests')
    yield _QT_APPLICATION
    # Qt does not support repeatedly destroying/recreating QApplication in one
    # process. Delete remaining widget trees before the one app is finalized.
    for widget in list(_QT_APPLICATION.topLevelWidgets()):
        widget.hide()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    _QT_APPLICATION.processEvents()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    _QT_APPLICATION.processEvents()


@pytest.fixture(scope='session')
def private_samples():
    examples = Path(__file__).resolve().parents[1] / 'examples'

    def require(*names):
        paths = tuple(examples / name for name in names)
        missing = [path.name for path in paths if not path.is_file()]
        if missing:
            pytest.skip('Original research fixtures unavailable: ' + ', '.join(missing))
        return paths

    return require
