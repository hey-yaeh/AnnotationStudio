"""Synchronized Qt video docks and the BVH world view."""
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QWidget,QMainWindow,QVBoxLayout,QHBoxLayout,QLabel,
    QStackedWidget,QDockWidget,QPushButton,QComboBox,QCheckBox)
from .scene import SkeletonCanvas


class VideoPanel(QWidget):
    importRequested=Signal()
    durationReady=Signal(str,int)
    failed=Signal(str)
    def __init__(self,title,parent=None):
        super().__init__(parent); self.asset=None; self._desired_ms=0
        self.player=QMediaPlayer(self); self.audio=QAudioOutput(self); self.audio.setMuted(True); self.player.setAudioOutput(self.audio)
        layout=QVBoxLayout(self); layout.setContentsMargins(3,3,3,3); layout.setSpacing(3)
        head=QHBoxLayout(); layout.addLayout(head)
        self.title=QLabel(title); self.title.setObjectName('Subhead'); head.addWidget(self.title,1)
        self.info=QLabel('NO SOURCE'); self.info.setStyleSheet('font-size:7pt;color:#9B8D7C;'); head.addWidget(self.info)
        self.stack=QStackedWidget(); layout.addWidget(self.stack,1)
        self.placeholder=QWidget(); self.placeholder.setStyleSheet('background:#36312A;border-radius:5px;')
        pl=QVBoxLayout(self.placeholder); pl.addStretch()
        self.empty=QLabel('VIDEO PREVIEW'); self.empty.setAlignment(Qt.AlignCenter); self.empty.setStyleSheet('color:#D8CABA;font-size:10pt;letter-spacing:1px;'); pl.addWidget(self.empty)
        self.hint=QLabel('Add a synchronized reference video'); self.hint.setAlignment(Qt.AlignCenter); self.hint.setStyleSheet('color:#AA9B86;font-size:8pt;'); pl.addWidget(self.hint)
        self.add=QPushButton('+ Add video'); self.add.setStyleSheet('background:#4B4034;color:#F2E6D6;border:1px solid #6D5946;'); self.add.clicked.connect(self.importRequested); pl.addWidget(self.add,0,Qt.AlignHCenter); pl.addStretch()
        self.stack.addWidget(self.placeholder)
        self.video=QVideoWidget(); self.video.setMinimumSize(180,80); self.video.setStyleSheet('background:#28231F;'); self.stack.addWidget(self.video); self.player.setVideoOutput(self.video)
        self.player.mediaStatusChanged.connect(self._loaded)
        self.player.errorOccurred.connect(self._error)
        self.player.durationChanged.connect(lambda ms:self.durationReady.emit(self.asset.id,ms) if self.asset and ms>0 else None)
    def bind(self,asset):
        self.asset=asset; self._desired_ms=0
        self.title.setText(f'{asset.role} · {asset.extra.get("view","Video")}')
        self.title.setToolTip(asset.path); self.info.setText(f'{asset.offset_s:+.3f}s')
        self.player.setSource(QUrl.fromLocalFile(asset.path)); self.stack.setCurrentWidget(self.video)
    def release(self):
        self.player.stop(); self.player.setSource(QUrl()); self.asset=None
        self.info.setText('NO SOURCE'); self.empty.setText('VIDEO PREVIEW'); self.hint.setText('Add a synchronized reference video'); self.add.show(); self.stack.setCurrentWidget(self.placeholder)
    def _loaded(self,status):
        if self.asset and status in (QMediaPlayer.LoadedMedia,QMediaPlayer.BufferedMedia):self.player.setPosition(self._desired_ms)
    def _error(self,*_):
        if not self.player.errorString():return
        name=self.asset.name if self.asset else 'Video'
        self.info.setText('UNAVAILABLE'); self.empty.setText('VIDEO UNAVAILABLE'); self.hint.setText(self.player.errorString()); self.hint.setWordWrap(True); self.add.hide(); self.stack.setCurrentWidget(self.placeholder)
        self.failed.emit(f'{name}: {self.player.errorString()}')
    def sync(self,t,play,force=False,rate=1.):
        if not self.asset:return
        target=t-self.asset.offset_s; duration=self.player.duration()/1000.
        if target<0 or (duration>0 and target>=duration):
            self.player.pause(); self.empty.setText('OUTSIDE SOURCE RANGE'); self.hint.setText(f'Offset {self.asset.offset_s:+.3f}s'); self.add.hide(); self.stack.setCurrentWidget(self.placeholder); return
        if self.player.error()!=QMediaPlayer.NoError:return
        self.stack.setCurrentWidget(self.video)
        ms=max(0,round(target*1000)); self._desired_ms=ms
        if abs(self.player.playbackRate()-rate)>.001:self.player.setPlaybackRate(rate)
        if force or abs(self.player.position()-ms)>120:self.player.setPosition(ms)
        if play:
            if self.player.playbackState()!=QMediaPlayer.PlayingState:self.player.play()
        else:self.player.pause()


class MediaWorkspace(QMainWindow):
    importVideo=Signal()
    durationReady=Signal(str,int)
    failed=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setDockOptions(QMainWindow.AllowNestedDocks|QMainWindow.AllowTabbedDocks)
        center=QWidget(); layout=QVBoxLayout(center); layout.setContentsMargins(4,4,4,4); layout.setSpacing(4)
        row=QHBoxLayout(); layout.addLayout(row)
        title=QLabel('3D MOTION VIEW'); title.setObjectName('Subhead'); row.addWidget(title); row.addStretch()
        self.view=QComboBox(); self.view.addItems(['Perspective','Front','Side','Top']); self.view.setMaximumWidth(110); row.addWidget(self.view)
        self.axis=QComboBox(); self.axis.addItems(['Z up','Y up']); self.axis.setMaximumWidth(70); row.addWidget(self.axis)
        reset=QPushButton('Reset'); reset.setMaximumWidth(65); row.addWidget(reset)
        self.canvas=SkeletonCanvas(); self.canvas.setMinimumSize(290,170); layout.addWidget(self.canvas,1)
        self.arm_labels=QCheckBox('L/R')
        self.arm_labels.setAccessibleName('Arm labels')
        self.arm_labels.setToolTip('Show Left Arm and Right Arm on the 3D skeletons.')
        self.arm_labels.setChecked(self.canvas.show_arm_labels)
        self.arm_labels.toggled.connect(self.canvas.set_arm_labels_visible)
        row.addWidget(self.arm_labels)
        self.setCentralWidget(center)
        reset.clicked.connect(self.canvas.reset_camera)
        self.view.currentTextChanged.connect(lambda v:self.canvas.set_view(v.lower()) if hasattr(self.canvas,'set_view') else None)
        self.axis.currentTextChanged.connect(lambda v:self.canvas.set_up_axis(v[0]) if hasattr(self.canvas,'set_up_axis') else None)
        self.panels=[]; self.add_panel('CONTEXT VIDEO')
        self.resizeDocks([self.panels[0][0]],[270],Qt.Horizontal)
        self.setMinimumHeight(220)
    def add_panel(self,title):
        panel=VideoPanel(title); dock=QDockWidget(title,self); dock.setObjectName(f'VideoDock{len(self.panels)}')
        dock.setFeatures(QDockWidget.DockWidgetMovable|QDockWidget.DockWidgetFloatable|QDockWidget.DockWidgetClosable); dock.setAllowedAreas(Qt.AllDockWidgetAreas); dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea,dock)
        if self.panels:self.splitDockWidget(self.panels[-1][0],dock,Qt.Vertical)
        self.panels.append((dock,panel)); panel.importRequested.connect(self.importVideo); panel.durationReady.connect(self.durationReady); panel.failed.connect(self.failed)
        return panel
    def videos(self):return [p for _,p in self.panels]
    def clear(self):
        self.canvas.clear_assets()
        for i,(dock,panel) in enumerate(self.panels):
            panel.release(); dock.setVisible(i==0)
            dock.setWindowTitle('CONTEXT VIDEO' if i==0 else 'REFERENCE VIDEO')
    def bind_video(self,asset):
        existing=next((p for p in self.videos() if p.asset and p.asset.id==asset.id),None)
        if existing:return existing
        free=next((p for p in self.videos() if p.asset is None),None)
        panel=free or self.add_panel(f'{asset.role} VIDEO'); panel.bind(asset)
        for dock,p in self.panels:
            if p is panel:dock.setWindowTitle(f'{asset.role} · {asset.extra.get("view","VIDEO").upper()}'); dock.show()
        return panel
    def sync(self,t,play,force=False,rate=1.):
        self.canvas.set_time(t)
        for p in self.videos():p.sync(t,play,force,rate)
    def restore_panels(self):
        for i,(dock,panel) in enumerate(self.panels):
            if panel.asset or i==0:dock.show()
