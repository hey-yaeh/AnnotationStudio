"""Compact automation and review controls; model jobs run in the main controller.

Importing these panels does not load a neural model or download its weights.
All automation produces pending proposals. Review status is independent of
whether an annotation originally came from a model or a person.
"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QDoubleSpinBox, QPushButton, QToolButton,
    QLineEdit, QScrollArea, QTabWidget, QGroupBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy,
)
from .segmentation import SegmentationConfig, MOTION_CHANNELS, DEFAULT_CHANNELS


def _caption(text):
    label = QLabel(text)
    label.setObjectName('Subhead')
    return label


def _note(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet('color: #87786A; font-size: 8pt;')
    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    return label


def _spin(value, minimum, maximum, step=.1, decimals=2):
    widget = QDoubleSpinBox()
    widget.setDecimals(decimals)
    widget.setRange(minimum, maximum)
    widget.setSingleStep(step)
    widget.setValue(value)
    widget.setKeyboardTracking(False)
    return widget


def _form():
    layout = QFormLayout()
    layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    layout.setHorizontalSpacing(7)
    layout.setVerticalSpacing(7)
    return layout


def _scroll_page():
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    body = QWidget()
    body.setObjectName('AutomationBody')
    body.setStyleSheet('QWidget#AutomationBody { background: #FFFCF8; }')
    content = QVBoxLayout(body)
    content.setContentsMargins(10, 12, 10, 10)
    content.setSpacing(10)
    scroll.setWidget(body)
    outer.addWidget(scroll, 1)
    return page, outer, content


class AutoPanel(QWidget):
    runMotion = Signal()
    runAudio = Signal()
    runSpeechStructure = Signal()
    reviewLatest = Signal()
    cancelJob = Signal()
    importResults = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(270)
        self._busy = False
        self._motion_roles = set()
        self._statuses = {}
        self._active_audio_model = 'energy'
        self._thresholds = {'energy': -36., 'silero': .5, 'yamnet': .35}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        status = QFrame()
        status.setObjectName('Card')
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(12, 10, 12, 10)
        heading = QHBoxLayout()
        heading.addWidget(_caption('AUTOMATIC PROPOSALS'))
        heading.addStretch()
        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.setEnabled(False)
        self.cancel_button.setMaximumWidth(69)
        self.cancel_button.setStyleSheet('padding: 4px 7px;')
        self.cancel_button.clicked.connect(self.cancelJob.emit)
        heading.addWidget(self.cancel_button)
        status_layout.addLayout(heading)
        self.progress = QLabel('Ready. Run a detector, then review its proposals.')
        self.progress.setWordWrap(True)
        self.progress.setMinimumHeight(32)
        self.progress.setMaximumHeight(90)
        self.progress.setStyleSheet('font-size: 8pt; color: #776554;')
        status_layout.addWidget(self.progress)
        self.review_latest = QPushButton('Review latest candidates')
        self.review_latest.hide()
        self.review_latest.clicked.connect(self.reviewLatest.emit)
        status_layout.addWidget(self.review_latest)
        layout.addWidget(status)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs, 1)
        self._build_motion()
        self._build_audio()
        self.turn_button = QPushButton('Build speech turns / timing…')
        self.turn_button.setToolTip('Create turn proposals, timing intervals and point transitions from existing attributed Speaking intervals. No diarization is performed.')
        self.turn_button.clicked.connect(self.runSpeechStructure.emit)
        layout.addWidget(self.turn_button)

        self.import_button = QPushButton('Import existing results…')
        self.import_button.clicked.connect(self.importResults.emit)
        layout.addWidget(self.import_button)
        self._refresh_models()
        self.set_assets([])

    def _build_motion(self):
        page, outer, content = _scroll_page()
        self.tabs.addTab(page, 'Motion')
        self.motion_source = _note('')
        content.addWidget(self.motion_source)
        form = _form()
        content.addLayout(form)
        self.motion_role = QComboBox()
        self.motion_role.addItem('All loaded actors', 'all')
        self.motion_role.addItem('R01', 'R01')
        self.motion_role.addItem('R02', 'R02')
        self.motion_role.currentIndexChanged.connect(self._update_run_buttons)
        form.addRow('Actor', self.motion_role)
        self.mode = QComboBox()
        self.mode.addItem('Graph + multi-scale', 'graph')
        self.mode.addItem('Velocity baseline', 'velocity')
        self.mode.setToolTip('Graph mode is experimental; both methods return candidates with relative salience scores.')
        form.addRow('Method', self.mode)
        self.up_axis = QComboBox()
        self.up_axis.addItems(['Z', 'Y'])
        self.up_axis.setToolTip('Vertical axis for the fallback arm-height rule when a torso frame is unavailable.')
        form.addRow('Source up axis', self.up_axis)
        self.fine_primitives = QCheckBox('Classify head, elbow and knee motion')
        self.fine_primitives.setChecked(True)
        self.fine_primitives.setToolTip('Suggest nods, shakes, turns and elbow/knee flexion or extension. Review the proposed labels and boundaries.')
        content.addWidget(self.fine_primitives)

        parts = QGroupBox('Body parts')
        parts_layout = QVBoxLayout(parts)
        parts_layout.setContentsMargins(8, 13, 8, 8)
        tools = QHBoxLayout()
        tools.addWidget(_note('Select one or more'))
        tools.addStretch()
        all_button, none_button = QToolButton(), QToolButton()
        all_button.setText('All')
        none_button.setText('Clear')
        all_button.clicked.connect(lambda: self._select_parts(True))
        none_button.clicked.connect(lambda: self._select_parts(False))
        tools.addWidget(all_button)
        tools.addWidget(none_button)
        parts_layout.addLayout(tools)
        grid = QGridLayout()
        grid.setHorizontalSpacing(9)
        grid.setVerticalSpacing(5)
        self.parts = {}
        part_order = ('Head', 'Torso', 'Left Arm', 'Right Arm', 'Left Hand', 'Right Hand',
                      'Left Leg', 'Right Leg', 'Root', 'Full Body', 'Hands')
        for index, name in enumerate(part_order):
            checkbox = QCheckBox('Both hands' if name == 'Hands' else name)
            checkbox.setChecked(name in DEFAULT_CHANNELS)
            self.parts[name] = checkbox
            grid.addWidget(checkbox, index // 2, index % 2)
        parts_layout.addLayout(grid)
        content.addWidget(parts)

        range_form = _form()
        content.addLayout(range_form)
        self.scope = QComboBox()
        self.scope.addItem('Full recording', 'all')
        self.scope.addItem('Time range · master clock', 'range')
        self.scope.currentIndexChanged.connect(self._scope_changed)
        range_form.addRow('Range', self.scope)
        self.range_widget = QWidget()
        range_grid = QGridLayout(self.range_widget)
        range_grid.setContentsMargins(0, 0, 0, 0)
        range_grid.setSpacing(5)
        range_grid.addWidget(_note('Start (s)'), 0, 0)
        range_grid.addWidget(_note('End (0 = end)'), 0, 1)
        self.range_start = _spin(0., 0., 360000., .1, 3)
        self.range_end = _spin(0., 0., 360000., .1, 3)
        range_grid.addWidget(self.range_start, 1, 0)
        range_grid.addWidget(self.range_end, 1, 1)
        content.addWidget(self.range_widget)
        self._scope_changed()

        advanced_button = QToolButton()
        advanced_button.setText('Advanced parameters')
        advanced_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        advanced_button.setArrowType(Qt.RightArrow)
        advanced_button.setCheckable(True)
        content.addWidget(advanced_button)
        self.advanced = QWidget()
        advanced_form = _form()
        advanced_form.setContentsMargins(0, 0, 0, 0)
        self.advanced.setLayout(advanced_form)
        self.min_s = _spin(.35, .03, 30., .05)
        self.merge = _spin(.25, 0., 10., .05)
        self.threshold = _spin(.34, .01, .99, .01)
        self.smoothing = _spin(.10, 0., 2., .02)
        self.sample_hz = _spin(30., 1., 240., 5., 0)
        advanced_form.addRow('Activity min duration (s)', self.min_s)
        advanced_form.addRow('Merge gap (s)', self.merge)
        advanced_form.addRow('Onset fraction', self.threshold)
        advanced_form.addRow('Smoothing (s)', self.smoothing)
        advanced_form.addRow('Analysis Hz', self.sample_hz)
        self.advanced.hide()
        advanced_button.toggled.connect(self.advanced.setVisible)
        advanced_button.toggled.connect(lambda checked: advanced_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow))
        content.addWidget(self.advanced)

        self.structure = QCheckBox('Compose arm-phase candidates')
        self.structure.setChecked(True)
        self.structure.setToolTip('Combine adjacent raise/lower intervals or bilateral motion. A hold and gesture meaning still require review.')
        self.replace = QCheckBox('Update unedited candidates only')
        self.replace.setChecked(True)
        self.replace.setToolTip('Replace pending automatic outputs only within this run’s source, parts and time range. Accepted and edited segments are retained.')
        for widget in (self.structure, self.replace):
            content.addWidget(widget)
        self.world = QCheckBox('World coordinates verified')
        self.world.setToolTip('Confirm only after checking common origin, axes, scale and time. This switch does not calibrate data.')
        content.addWidget(self.world)
        content.addStretch(1)
        self.motion_run = QPushButton('Generate motion proposals')
        self.motion_run.setObjectName('PrimaryButton')
        self.motion_run.clicked.connect(self.runMotion.emit)
        run_layout = QVBoxLayout()
        run_layout.setContentsMargins(10, 8, 10, 10)
        run_layout.addWidget(self.motion_run)
        outer.addLayout(run_layout)

    def _build_audio(self):
        page, outer, content = _scroll_page()
        self.tabs.addTab(page, 'Audio')
        content.addWidget(_note('Speech activity and vocal events are separate tracks. Silence never automatically becomes a Listener label.'))
        form = _form()
        content.addLayout(form)
        self.audio_asset = QComboBox()
        self.audio_asset.setMinimumContentsLength(12)
        self.audio_asset.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.audio_asset.currentIndexChanged.connect(self._update_run_buttons)
        form.addRow('Asset', self.audio_asset)
        self.audio_channel = QComboBox()
        self.audio_channel.addItem('Automatic · mono only', None)
        self.audio_channel.addItem('Channel 1', 0)
        self.audio_channel.addItem('Channel 2', 1)
        self.audio_channel.addItem('Mix channels explicitly', 'mix')
        form.addRow('Channel', self.audio_channel)
        self.audio_model = QComboBox()
        self.audio_model.addItem('Audio activity · energy', 'energy')
        self.audio_model.addItem('Speaking · Silero VAD', 'silero')
        self.audio_model.addItem('Vocal events · YAMNet', 'yamnet')
        self.audio_model.setMinimumContentsLength(14)
        self.audio_model.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.audio_model.currentIndexChanged.connect(self._audio_model_changed)
        form.addRow('Detector', self.audio_model)

        self.model_badge = _caption('CHECKING DEPENDENCIES')
        content.addWidget(self.model_badge)
        self.model_detail = _note('')
        content.addWidget(self.model_detail)
        self.refresh_models = QPushButton('Refresh model availability')
        self.refresh_models.setStyleSheet('padding: 4px 7px; font-size: 8pt;')
        self.refresh_models.clicked.connect(self._refresh_models)
        content.addWidget(self.refresh_models)

        threshold_form = _form()
        self.threshold_label = QLabel('Threshold (dBFS)')
        self.audio_threshold = _spin(-36., -90., 0., 1., 1)
        threshold_form.addRow(self.threshold_label, self.audio_threshold)
        content.addLayout(threshold_form)
        self.audio_threshold_note = _note('RMS level threshold; background sounds may also trigger candidates.')
        content.addWidget(self.audio_threshold_note)

        self.yamnet_options = QWidget()
        yamnet_layout = QVBoxLayout(self.yamnet_options)
        yamnet_layout.setContentsMargins(0, 0, 0, 0)
        yamnet_layout.setSpacing(7)
        yamnet_layout.addWidget(_caption('YAMNET MODEL DIRECTORY'))
        path_row = QHBoxLayout()
        path_row.setSpacing(5)
        self.model_path = QLineEdit()
        self.model_path.setPlaceholderText('Local SavedModel directory')
        self.model_path.setToolTip('Select the folder containing saved_model.pb and the variables directory.')
        self.model_path.textChanged.connect(self._update_run_buttons)
        browse = QPushButton('…')
        browse.setMaximumWidth(32)
        browse.setToolTip('Choose YAMNet SavedModel directory')
        browse.clicked.connect(self._browse_model)
        path_row.addWidget(self.model_path, 1)
        path_row.addWidget(browse)
        yamnet_layout.addLayout(path_row)
        self.download = QCheckBox('Allow model download on Run')
        self.download.setChecked(False)
        self.download.setToolTip('Explicitly permits downloading the official YAMNet model through TensorFlow Hub when no local model is selected.')
        self.download.toggled.connect(self._update_run_buttons)
        yamnet_layout.addWidget(self.download)
        yamnet_layout.addWidget(_note('Candidate classes: laughter, sigh, gasp, cough, throat clearing, sneeze and sniff. Timing needs review.'))
        content.addWidget(self.yamnet_options)
        self.yamnet_options.hide()
        content.addWidget(_note('The chosen asset/channel supplies the actor assignment. Cross-talk and overlapping speech require manual review.'))
        content.addStretch(1)
        self.audio_run = QPushButton('Generate audio proposals')
        self.audio_run.setObjectName('PrimaryButton')
        self.audio_run.clicked.connect(self.runAudio.emit)
        run_layout = QVBoxLayout()
        run_layout.setContentsMargins(10, 8, 10, 10)
        run_layout.addWidget(self.audio_run)
        outer.addLayout(run_layout)

    def _select_parts(self, checked):
        for checkbox in self.parts.values():
            checkbox.setChecked(checked)

    def _scope_changed(self, *_):
        if hasattr(self, 'range_widget'):
            self.range_widget.setVisible(self.scope.currentData() == 'range')

    def set_marked_range(self, start_s, end_s):
        """Optional controller helper for the timeline's marked master range."""
        self.scope.setCurrentIndex(self.scope.findData('range'))
        self.range_start.setValue(max(0., float(start_s)))
        self.range_end.setValue(max(0., float(end_s)))

    def motion_options(self):
        high = self.threshold.value()
        cfg = SegmentationConfig(
            mode=self.mode.currentData(), sample_hz=self.sample_hz.value(),
            smoothing_s=self.smoothing.value(), high_fraction=high,
            low_fraction=min(.18, high * .6), min_duration_s=self.min_s.value(),
            merge_gap_s=self.merge.value(), up_axis=self.up_axis.currentText(),
            fine_primitives=self.fine_primitives.isChecked(),
            channels=[name for name, checkbox in self.parts.items() if checkbox.isChecked()],
        ).validate()
        selection = self.motion_role.currentData()
        roles = ['R01', 'R02'] if selection == 'all' else [selection]
        ranged = self.scope.currentData() == 'range'
        start = self.range_start.value() if ranged else 0.
        end = self.range_end.value() if ranged and self.range_end.value() > 0 else None
        if end is not None and end <= start:
            raise ValueError('The master end time must be greater than the start time, or 0 for recording end.')
        return {'cfg': cfg, 'roles': roles, 'master_start': start, 'master_end': end,
                'structure': self.structure.isChecked(),
                'replace': self.replace.isChecked()}

    def audio_options(self):
        model_id = self.audio_model.currentData()
        value = self.audio_threshold.value()
        options = {'model_id': model_id, 'channel': self.audio_channel.currentData(),
                   'model_path': self.model_path.text().strip(), 'threshold': value,
                   'download': self.download.isChecked() if model_id == 'yamnet' else False}
        if model_id == 'energy':
            options['db_threshold'] = value
        return options

    def set_assets(self, assets, motion_roles=()):
        self._motion_roles = {'R01', 'R02'}.intersection(motion_roles)
        selected = self.audio_asset.currentData()
        with QSignalBlocker(self.audio_asset):
            self.audio_asset.clear()
            for asset in assets:
                if asset.kind == 'audio' and asset.enabled:
                    self.audio_asset.addItem(f'{asset.role} · {asset.name or Path(asset.path).name}', asset.id)
            if self.audio_asset.count() == 0:
                self.audio_asset.addItem('Import a WAV / FLAC asset', None)
            else:
                index = self.audio_asset.findData(selected)
                self.audio_asset.setCurrentIndex(index if index >= 0 else 0)
        self._update_run_buttons()

    def _browse_model(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose YAMNet SavedModel directory', self.model_path.text())
        if path:
            self.model_path.setText(path)

    def _refresh_models(self):
        try:
            from .audio_models import model_status
            self._statuses = {record['id']: record for record in model_status()}
        except Exception as exc:
            self._statuses = {name: {'available': False, 'detail': f'Status unavailable: {type(exc).__name__}: {exc}'}
                              for name in ('energy', 'silero', 'yamnet')}
        self._audio_model_changed()

    def _audio_model_changed(self, *_):
        model_id = self.audio_model.currentData() or 'energy'
        if hasattr(self, 'audio_threshold'):
            self._thresholds[self._active_audio_model] = self.audio_threshold.value()
        self._active_audio_model = model_id
        if not hasattr(self, 'audio_threshold'):
            return
        energy = model_id == 'energy'
        self.threshold_label.setText('Threshold (dBFS)' if energy else 'Score threshold')
        with QSignalBlocker(self.audio_threshold):
            self.audio_threshold.setRange(-90., 0.) if energy else self.audio_threshold.setRange(.01, .99)
            self.audio_threshold.setDecimals(1 if energy else 2)
            self.audio_threshold.setSingleStep(1. if energy else .01)
            self.audio_threshold.setValue(self._thresholds[model_id])
        self.audio_threshold_note.setText('RMS level threshold; background sounds may also trigger candidates.' if energy else
                                         'Model score threshold. A higher score is not a calibrated measure of annotation accuracy.')
        self.yamnet_options.setVisible(model_id == 'yamnet')
        status = self._statuses.get(model_id, {})
        available = status.get('available', False)
        bundled = status.get('bundled_model_path')
        if model_id == 'yamnet':
            self.model_path.setPlaceholderText('Bundled YAMNet model' if bundled else 'Local SavedModel directory')
        if model_id == 'energy' and available:
            badge = 'AVAILABLE · ACTIVITY BASELINE'
        elif available and bundled:
            badge = 'BUNDLED MODEL · LOADS LOCALLY'
        elif available:
            badge = 'DEPENDENCIES FOUND · MODEL NOT CHECKED'
        else:
            badge = 'OPTIONAL DEPENDENCIES NEEDED'
        self.model_badge.setText(badge)
        self.model_detail.setText(status.get('detail', 'Refresh to check this detector.'))
        self.download.setEnabled(bool(status.get('can_download', False)) and not self._busy)
        self._update_run_buttons()

    def _update_run_buttons(self, *_):
        if not hasattr(self, 'audio_run'):
            return
        selected_role = self.motion_role.currentData()
        motion_ready = bool(self._motion_roles) if selected_role == 'all' else selected_role in self._motion_roles
        if motion_ready:
            roles = ' / '.join(sorted(self._motion_roles)) if selected_role == 'all' else selected_role
            motion_help = f'{roles} ready. Detect body-part activity and arm raises or lowers for review.'
        elif self._motion_roles:
            motion_help = f'Add or relink a BVH / pose source for {selected_role}, or select a loaded actor.'
        else:
            motion_help = 'Add or relink a BVH / pose source in Sources to run motion detection.'
        self.motion_source.setText(motion_help)
        self.motion_run.setEnabled(not self._busy and motion_ready)
        self.motion_run.setToolTip(motion_help)
        if hasattr(self,'turn_button'):self.turn_button.setEnabled(not self._busy)
        model_id = self.audio_model.currentData()
        status = self._statuses.get(model_id, {})
        has_asset = self.audio_asset.currentData() is not None
        can_run = bool(status.get('available', False)) and has_asset
        if model_id == 'yamnet':
            can_run = can_run and (bool(self.model_path.text().strip()) or
                                   bool(status.get('bundled_model_path')) or
                                   (self.download.isChecked() and bool(status.get('can_download', False))))
        self.audio_run.setEnabled(not self._busy and can_run)
        self.audio_run.setToolTip('' if can_run else 'Select an audio asset and install the chosen detector. YAMNet also needs a local model or explicit download permission.')
        self.cancel_button.setEnabled(self._busy)

    def set_busy(self, busy):
        self._busy = bool(busy)
        self.import_button.setEnabled(not self._busy)
        self.refresh_models.setEnabled(not self._busy)
        status = self._statuses.get(self.audio_model.currentData(), {})
        self.download.setEnabled(bool(status.get('can_download', False)) and not self._busy)
        self._update_run_buttons()

    def set_progress(self, message):
        self.progress.setText(str(message))
        self.progress.setToolTip(str(message))

    def set_latest_review_available(self, available):
        self.review_latest.setVisible(available)


class ReviewPanel(QWidget):
    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(270)
        self._annotations = []
        self._latest_ids = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(9)
        layout.addWidget(_caption('REVIEW QUEUE'))
        self.counts = _note('0 accepted · 0 pending')
        layout.addWidget(self.counts)
        self.filter = QComboBox()
        self.filter.addItem('Pending candidates', 'pending')
        self.filter.addItem('All segments', 'all')
        self.filter.addItem('Accepted', 'approved')
        self.filter.addItem('Rejected', 'rejected')
        self.filter.currentIndexChanged.connect(self._render)
        layout.addWidget(self.filter)
        self.latest_only = QCheckBox('Latest run only')
        self.latest_only.setEnabled(False)
        self.latest_only.toggled.connect(self._render)
        layout.addWidget(self.latest_only)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter label, actor or source…')
        self.search.textChanged.connect(self._render)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Start', 'Actor / part', 'Label'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(31)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.cellClicked.connect(self._select_row)
        layout.addWidget(self.table, 1)
        self.visible_count = _note('Select a segment to edit its label and timing.')
        layout.addWidget(self.visible_count)

    def populate(self, annotations):
        self._annotations = list(annotations)
        pending = sum(item.status == 'pending' for item in self._annotations)
        accepted = sum(item.status == 'approved' for item in self._annotations)
        rejected = sum(item.status == 'rejected' for item in self._annotations)
        self.counts.setText(f'{accepted} accepted · {pending} pending · {rejected} rejected')
        self._render()

    def set_latest_batch(self, ids):
        self._latest_ids = set(ids)
        self.latest_only.setEnabled(bool(self._latest_ids))
        if not self._latest_ids:
            with QSignalBlocker(self.latest_only):
                self.latest_only.setChecked(False)
        self._render()

    def latest_pending(self):
        return [item for item in self._annotations if item.id in self._latest_ids and item.status == 'pending']

    def show_latest_pending(self):
        with QSignalBlocker(self.filter), QSignalBlocker(self.search), QSignalBlocker(self.latest_only):
            self.filter.setCurrentIndex(self.filter.findData('pending'))
            self.search.clear()
            self.latest_only.setChecked(bool(self._latest_ids))
        self._render()

    def _render(self, *_):
        if not hasattr(self, 'table'):
            return
        active = self.table.item(self.table.currentRow(), 0)
        selected_id = active.data(Qt.UserRole) if active is not None else None
        status, query = self.filter.currentData(), self.search.text().strip().casefold()
        latest_only = self.latest_only.isChecked()
        visible = sorted([annotation for annotation in self._annotations
                          if (status == 'all' or annotation.status == status)
                          and (not latest_only or annotation.id in self._latest_ids)
                          and (not query or query in f'{annotation.label} {annotation.role} {annotation.source} {annotation.channel}'.casefold())],
                         key=lambda item: (item.start_s, item.role, item.end_s, item.id))
        with QSignalBlocker(self.table):
            self.table.clearContents()
            self.table.setRowCount(len(visible))
            selected_row = None
            for row, annotation in enumerate(visible):
                values = (f'{annotation.start_s:.2f}', f'{annotation.role} · {annotation.channel}', annotation.label)
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.UserRole, annotation.id)
                    item.setToolTip(f'{annotation.label}\n{annotation.start_s:.3f}–{annotation.end_s:.3f} s\n{annotation.source} · {annotation.status}')
                    if column == 0:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if column == 2:
                        item.setForeground(QBrush(QColor('#765E4A') if annotation.status == 'rejected' else QColor('#493B31')))
                    self.table.setItem(row, column, item)
                if annotation.id == selected_id:
                    selected_row = row
            if selected_row is not None:
                self.table.selectRow(selected_row)
            else:
                self.table.clearSelection()
        if not visible and latest_only and status == 'pending' and not query:
            self.visible_count.setText('No pending candidates from the latest run.')
        else:
            self.visible_count.setText(f'{len(visible)} shown · select a segment to review')

    def _select_row(self, row, _column):
        item = self.table.item(row, 0)
        if item is not None:
            self.selected.emit(str(item.data(Qt.UserRole)))
