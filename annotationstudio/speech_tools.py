"""Preview dialog for locally derived speech structure; no model download."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QListWidget, QListWidgetItem, QCheckBox, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)

from .speech_structure import build_speech_structure


class SpeechStructureDialog(QDialog):
    """Inspect ``annotations`` and ``report`` after Accepted, then apply once.

    This dialog never modifies the project. The main controller settles any
    active draft, checkpoints history, and calls apply_speech_structure().
    """
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.annotations = None
        self.report = None
        self.setWindowTitle('Build Speech Structure')
        self.resize(940, 720)
        self.setMinimumSize(720, 570)
        layout = QVBoxLayout(self)
        title = QLabel('SPEECH TURNS & TIMING')
        title.setObjectName('Subhead')
        layout.addWidget(title)
        description = QLabel('Build turn candidates from existing R01 / R02 Speaking intervals. '
                             'The source speech stays unchanged. This tool does not separate speakers or transcribe audio.')
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addWidget(QLabel('Speaking tracks'))
        self.tracks = QListWidget()
        self.tracks.setMaximumHeight(115)
        counts = {}
        for annotation in project.annotations:
            if (annotation.category == 'Speaking' and annotation.label.casefold() == 'speaking'
                    and annotation.role in ('R01', 'R02') and annotation.status != 'rejected'
                    and getattr(annotation, 'temporal_kind', 'interval') == 'interval'):
                counts[annotation.track_id] = counts.get(annotation.track_id, 0) + 1
        for track_id, count in counts.items():
            track = project.get_track(track_id)
            if not track:
                continue
            item = QListWidgetItem(f'{track.role}  ·  {track.name}  ·  {count} speech intervals')
            item.setData(Qt.UserRole, track_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.tracks.addItem(item)
        layout.addWidget(self.tracks)
        if not self.tracks.count():
            missing = QLabel('No Speaking intervals are available. Run VAD, import annotations or mark speech first.')
            missing.setWordWrap(True)
            layout.addWidget(missing)
        form = QFormLayout()
        self.merge_gap = QDoubleSpinBox()
        self.merge_gap.setRange(0, 5)
        self.merge_gap.setDecimals(3)
        self.merge_gap.setSingleStep(.05)
        self.merge_gap.setValue(.3)
        self.merge_gap.setSuffix(' s')
        self.merge_gap.setToolTip('Merge same-speaker segments across at most this pause, unless another non-backchannel speaker occupies the gap.')
        form.addRow('Maximum same-speaker pause', self.merge_gap)
        self.short_turn = QDoubleSpinBox()
        self.short_turn.setRange(0, 5)
        self.short_turn.setDecimals(3)
        self.short_turn.setSingleStep(.1)
        self.short_turn.setValue(.6)
        self.short_turn.setSuffix(' s')
        self.short_turn.setToolTip('Only flags short contributions for review. It does not classify them as backchannels.')
        form.addRow('Flag contributions shorter than', self.short_turn)
        layout.addLayout(form)
        self.approved_only = QCheckBox('Use only accepted Speaking intervals')
        self.confirm_attribution = QCheckBox('I have checked that the selected speech tracks belong to the correct R01 / R02.')
        self.confirm_attribution.setToolTip('A VAD result inherits its asset role; it has not identified the speaker.')
        self.replace_check = QCheckBox('Replace unedited candidates from this same track selection')
        self.replace_check.setChecked(True)
        layout.addWidget(self.approved_only)
        layout.addWidget(self.confirm_attribution)
        layout.addWidget(self.replace_check)
        self.summary = QLabel('Generate a preview to inspect proposed turns, timing intervals and point markers.')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.preview = QTableWidget(0, 6)
        self.preview.setHorizontalHeaderLabels(['Role', 'Type', 'Label', 'Start / Time', 'End', 'Review note'])
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.preview.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.preview.verticalHeader().setVisible(False)
        layout.addWidget(self.preview, 1)
        footer = QLabel('Reviewed backchannels are respected. Every new result remains a candidate; '
                        'a speaker-entry marker is not a confirmed handover.')
        footer.setWordWrap(True)
        layout.addWidget(footer)
        row = QHBoxLayout()
        self.generate_button = QPushButton('Generate preview')
        self.generate_button.setObjectName('PrimaryButton')
        row.addWidget(self.generate_button)
        row.addStretch()
        self.apply_button = QPushButton('Add to project')
        self.apply_button.setEnabled(False)
        cancel = QPushButton('Cancel')
        row.addWidget(self.apply_button)
        row.addWidget(cancel)
        layout.addLayout(row)
        self.generate_button.clicked.connect(self.generate_preview)
        self.apply_button.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        for control in (self.merge_gap, self.short_turn):
            control.valueChanged.connect(self.invalidate)
        self.tracks.itemChanged.connect(self.invalidate)
        self.approved_only.toggled.connect(self.invalidate)
        self.confirm_attribution.toggled.connect(self.invalidate)
        self.invalidate()

    @property
    def replace(self):
        return self.replace_check.isChecked()

    def selected_tracks(self):
        return [self.tracks.item(index).data(Qt.UserRole)
                for index in range(self.tracks.count())
                if self.tracks.item(index).checkState() == Qt.Checked]

    def invalidate(self, *_):
        self.annotations = None
        self.report = None
        self.apply_button.setEnabled(False)
        self.generate_button.setEnabled(bool(self.selected_tracks()) and self.confirm_attribution.isChecked())
        self.preview.setRowCount(0)
        self.summary.setText('Generate a preview after confirming the speaker assignments.')

    def generate_preview(self):
        try:
            annotations, report = build_speech_structure(
                self.project, attribution_confirmed=self.confirm_attribution.isChecked(),
                merge_gap_s=self.merge_gap.value(), short_turn_s=self.short_turn.value(),
                approved_only=self.approved_only.isChecked(), track_ids=self.selected_tracks())
        except (ValueError, TypeError) as error:
            QMessageBox.warning(self, 'Speech structure', str(error))
            return
        self.annotations, self.report = annotations, report
        self.summary.setText(
            f"{report['turn_candidates']} new turn candidates · {report['timing_intervals']} timing intervals · "
            f"{report['transition_points']} point markers · {report['curated_turns_retained']} curated turns retained. "
            f"{report['excluded_reviewed_backchannels']} speech intervals covered by reviewed backchannels. "
            f"{report['retained_dependency_turns']} turn anchors retained by reviewed relations; "
            f"{report['residual_turn_candidates']} unclaimed-speech candidates."
            + (' Preview shows the first 200 results; all results will be added.' if len(annotations) > 200 else ''))
        self.preview.setRowCount(min(200, len(annotations)))
        for row, annotation in enumerate(annotations[:200]):
            values = [annotation.role, annotation.temporal_kind, annotation.label,
                      f'{annotation.start_s:.3f}', '—' if annotation.temporal_kind == 'point' else f'{annotation.end_s:.3f}',
                      '; '.join(annotation.attributes.get('review_reasons', []))]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.preview.setItem(row, column, item)
        # An empty generation can still remove stale, unedited results in the
        # selected scope, e.g. when all contributions are reviewed backchannels.
        self.apply_button.setEnabled(True)
