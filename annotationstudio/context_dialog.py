"""Read-only co-occurrence query UI for speech, posture and object relations."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox)
from .context_relations import intersect_tracks, export_context_csv
from .annotation_fields import active_secondary_object_id


class ContextQueryDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.rows = None
        self.summary = None
        self.setWindowTitle('Context Query')
        self.resize(1020, 640)
        self.setMinimumSize(760, 500)
        layout = QVBoxLayout(self)
        title = QLabel('WHEN DO THESE STATES OVERLAP?')
        title.setObjectName('Subhead')
        layout.addWidget(title)
        help_text = QLabel('For example: Speaking × sitting on a sofa, or Speaking × a hand resting on a table. '
                           'Source annotations keep their own boundaries. This query creates no compound labels.')
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QFormLayout()
        self.track_a, self.track_b = QComboBox(), QComboBox()
        self.label_a, self.label_b = QComboBox(), QComboBox()
        self.object_a, self.object_b = QComboBox(), QComboBox()
        for picker in (self.object_a, self.object_b):
            picker.setToolTip('Match the primary object or either target of between objects.')
        for track in sorted(project.tracks, key=lambda t: t.order):
            text = f'{track.role}  ·  {track.category}  ·  {track.name}'
            self.track_a.addItem(text, track.id)
            self.track_b.addItem(text, track.id)
        for caption, track, label, object_box in (
                ('Track A', self.track_a, self.label_a, self.object_a),
                ('Track B', self.track_b, self.label_b, self.object_b)):
            row = QHBoxLayout()
            row.addWidget(track, 2)
            row.addWidget(label, 1)
            row.addWidget(object_box, 1)
            form.addRow(caption, row)
        layout.addLayout(form)
        options = QHBoxLayout()
        self.same_actor = QCheckBox('Same known actor only (R01 / R02)')
        self.same_actor.setChecked(True)
        self.approved_only = QCheckBox('Accepted annotations only')
        options.addWidget(self.same_actor)
        options.addWidget(self.approved_only)
        options.addStretch()
        self.run_button = QPushButton('Calculate overlap')
        self.run_button.setObjectName('PrimaryButton')
        options.addWidget(self.run_button)
        layout.addLayout(options)
        self.summary_label = QLabel('Choose two tracks. Point markers and rejected annotations are excluded.')
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['Start', 'End', 'Duration', 'Actors', 'A label / object', 'B label / object', 'Review'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        for column in (4, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)
        note = QLabel('Totals use the union of elapsed time, so overlapping pair rows are not double-counted. '
                      'Temporal co-occurrence does not establish gesture meaning, attention or causality.')
        note.setWordWrap(True)
        layout.addWidget(note)
        bottom = QHBoxLayout()
        self.export_button = QPushButton('Export result CSV…')
        self.export_button.setEnabled(False)
        bottom.addWidget(self.export_button)
        bottom.addStretch()
        close = QPushButton('Close')
        bottom.addWidget(close)
        layout.addLayout(bottom)
        self.track_a.currentIndexChanged.connect(lambda: self._track_changed('a'))
        self.track_b.currentIndexChanged.connect(lambda: self._track_changed('b'))
        for control in (self.label_a, self.label_b, self.object_a, self.object_b):
            control.currentIndexChanged.connect(self.invalidate)
        self.same_actor.toggled.connect(self.invalidate)
        self.approved_only.toggled.connect(self.invalidate)
        self.run_button.clicked.connect(self.calculate)
        self.export_button.clicked.connect(self.export_csv)
        close.clicked.connect(self.accept)
        # Prefer useful defaults without asserting any relationship.
        for index, track in enumerate(sorted(project.tracks, key=lambda t: t.order)):
            if track.category == 'Speaking':
                self.track_a.setCurrentIndex(index)
                break
        selected_role = project.get_track(self.track_a.currentData()).role if self.track_a.currentData() else None
        for index, track in enumerate(sorted(project.tracks, key=lambda t: t.order)):
            if track.role == selected_role and track.category in ('Action / HOI', 'Body Posture'):
                self.track_b.setCurrentIndex(index)
                break
        if self.track_b.currentData() == self.track_a.currentData() and self.track_b.count() > 1:
            self.track_b.setCurrentIndex((self.track_a.currentIndex()+1) % self.track_b.count())
        self._track_changed('a')
        self._track_changed('b')

    def invalidate(self, *_):
        self.rows = self.summary = None
        self.export_button.setEnabled(False)
        self.table.setRowCount(0)
        self.summary_label.setText('Calculate again after changing the filters. Source annotations are never modified.')
        self.run_button.setEnabled(self.track_a.currentIndex() >= 0 and self.track_b.currentIndex() >= 0
                                   and self.track_a.currentData() != self.track_b.currentData())

    def _track_changed(self, side):
        track_box, label_box, object_box = getattr(self, f'track_{side}'), getattr(self, f'label_{side}'), getattr(self, f'object_{side}')
        records = [x for x in self.project.annotations if x.track_id == track_box.currentData()
                   and x.status != 'rejected' and getattr(x, 'temporal_kind', 'interval') == 'interval']
        label_box.blockSignals(True)
        object_box.blockSignals(True)
        label_box.clear()
        label_box.addItem('All labels', None)
        for label in sorted({x.label for x in records}):
            label_box.addItem(label, label)
        object_box.clear()
        object_box.addItem('Any object', None)
        object_ids = {value for record in records for value in (
            record.attributes.get('object_id'), active_secondary_object_id(self.project, record))
            if isinstance(value, str) and value}
        for object_id in sorted(object_ids):
            known = self.project.get_object(object_id) if hasattr(self.project, 'get_object') else None
            object_box.addItem(f'{known.name} ({object_id})' if known else object_id, object_id)
        label_box.blockSignals(False)
        object_box.blockSignals(False)
        self.invalidate()

    def calculate(self):
        try:
            rows, summary = intersect_tracks(
                self.project, self.track_a.currentData(), self.track_b.currentData(),
                same_actor=self.same_actor.isChecked(), approved_only=self.approved_only.isChecked(),
                label_a=self.label_a.currentData(), label_b=self.label_b.currentData(),
                object_a=self.object_a.currentData(), object_b=self.object_b.currentData())
        except (ValueError, TypeError) as error:
            QMessageBox.warning(self, 'Context query', str(error))
            return
        self.rows, self.summary = rows, summary
        coverage = '—' if summary['coverage_of_a'] is None else f"{100*summary['coverage_of_a']:.1f}%"
        self.summary_label.setText(
            f"Overlap union: {summary['overlap_union_s']:.3f} s · Track A coverage: {coverage} · "
            f"{summary['pair_rows']} matching pairs · Fully reviewed overlap: {summary['reviewed_overlap_union_s']:.3f} s"
            + (' · Showing first 500 rows; CSV includes all rows.' if len(rows) > 500 else ''))
        self.table.setRowCount(min(500, len(rows)))
        for index, row in enumerate(rows[:500]):
            objects_a = ' / '.join(value for value in (row['object_a'], row.get('secondary_object_a')) if value)
            objects_b = ' / '.join(value for value in (row['object_b'], row.get('secondary_object_b')) if value)
            values = [f"{row['start_s']:.3f}", f"{row['end_s']:.3f}", f"{row['duration_s']:.3f}",
                      row['role_a'] if row['role_a'] == row['role_b'] else f"{row['role_a']} / {row['role_b']}",
                      row['label_a'] + (f" · {objects_a}" if objects_a else ''),
                      row['label_b'] + (f" · {objects_b}" if objects_b else ''),
                      'Both accepted' if row['both_reviewed'] else 'Contains candidates']
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(f"{value}\nSources: {row['source_a_id']} / {row['source_b_id']}")
                self.table.setItem(index, column, item)
        self.export_button.setEnabled(True)

    def export_csv(self):
        if self.rows is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export co-occurrence results', 'context_query.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            export_context_csv(path, self.rows)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Export failed', str(error))
