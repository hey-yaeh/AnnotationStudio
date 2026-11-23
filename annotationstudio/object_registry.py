"""Stable, explicitly registered scene objects; no inferred geometry or contact."""
from __future__ import annotations

from copy import deepcopy
import re

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QComboBox, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialogButtonBox, QMessageBox,
)
from .models import Project
from .annotation_fields import annotation_object_ids


class ObjectPicker(QComboBox):
    """Display names while storing only stable IDs; retain unresolved old IDs."""
    def bind(self, project, value=''):
        with QSignalBlocker(self):
            self.clear()
            self.addItem('Unspecified object', '')
            if project is not None:
                for obj in sorted(project.objects, key=lambda x: (x.name.casefold(), x.id)):
                    if obj.extra.get('retired') and obj.id != value:
                        continue
                    suffix = ' · retired' if obj.extra.get('retired') else ''
                    self.addItem(f'{obj.name} · {obj.id}{suffix}', obj.id)
            self.setText(value)

    def setText(self, value):
        value = str(value or '')
        index = self.findData(value)
        if index < 0:
            self.addItem(f'Unregistered · {value}', value)
            index = self.count()-1
        self.setCurrentIndex(index)

    def text(self):
        return str(self.currentData() or '')


class ObjectRegistryDialog(QDialog):
    """All changes remain local until the main controller commits this dialog."""
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = deepcopy(project)
        self.setWindowTitle('Scene objects')
        self.resize(800, 570)
        layout = QVBoxLayout(self)
        note = QLabel('Enter an object or region name to use it in Spatial and HOI annotations. '
                      'Only a name is required; the ID is generated automatically. '
                      'No 3D model, prop track or geometry file is needed.')
        note.setWordWrap(True); layout.addWidget(note)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Object ID', 'Name', 'Class', 'References', 'State'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._select)
        layout.addWidget(self.table, 1)
        form = QFormLayout(); layout.addLayout(form)
        self.object_id = QLineEdit(); self.object_id.setPlaceholderText('Optional for a new object; e.g. sofa_01')
        self.name = QLineEdit(); self.name.setPlaceholderText('Counter / Sofa by the window / Waiting area')
        self.object_class = QLineEdit(); self.object_class.setPlaceholderText('Optional: counter / sofa / table / area')
        self.notes = QLineEdit(); self.notes.setPlaceholderText('Identification notes; geometry is not inferred.')
        form.addRow('Display name', self.name); form.addRow('Class (optional)', self.object_class)
        form.addRow('ID (automatic)', self.object_id); form.addRow('Notes (optional)', self.notes)
        buttons = QHBoxLayout(); layout.addLayout(buttons)
        new = QPushButton('New object'); new.clicked.connect(self._new); buttons.addWidget(new)
        self.store_button = QPushButton('Add object'); self.store_button.clicked.connect(self._store); buttons.addWidget(self.store_button)
        self.retire_button = QPushButton('Retire / restore'); self.retire_button.clicked.connect(self._retire); buttons.addWidget(self.retire_button)
        buttons.addStretch()
        self.message = QLabel(''); self.message.setWordWrap(True); layout.addWidget(self.message)
        done = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        done.accepted.connect(self._finish); done.rejected.connect(self.reject); layout.addWidget(done)
        self._selected_id = None
        self._refresh(); self._new()

    def _refresh(self, select_id=None):
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(self.project.objects))
            for row, obj in enumerate(self.project.objects):
                refs = sum(obj.id in annotation_object_ids(a) for a in self.project.annotations)
                values = [obj.id, obj.name, obj.object_class, str(refs),
                          'Retired' if obj.extra.get('retired') else 'Active']
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(value))
                if obj.id == select_id:
                    self.table.selectRow(row)

    def _new(self):
        self._selected_id = None
        with QSignalBlocker(self.table): self.table.clearSelection()
        for widget in (self.object_id, self.name, self.object_class, self.notes): widget.clear()
        self.object_id.setReadOnly(False)
        self.store_button.setText('Add object'); self.retire_button.setEnabled(False)
        self.name.setFocus()

    def _select(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0): return
        obj = self.project.get_object(self.table.item(row, 0).text())
        if obj is None: return
        self._selected_id = obj.id
        self.object_id.setText(obj.id); self.object_id.setReadOnly(True)
        self.name.setText(obj.name); self.object_class.setText(obj.object_class); self.notes.setText(obj.notes)
        self.store_button.setText('Update object'); self.retire_button.setEnabled(True)

    def _store(self):
        name = self.name.text().strip()
        if not name:
            self.message.setText('Enter a display name before adding or updating an object.')
            return False
        try:
            if self._selected_id:
                obj = self.project.update_object(self._selected_id, name=name,
                    object_class=self.object_class.text().strip(), notes=self.notes.text().strip())
            else:
                ident = self.object_id.text().strip()
                if not ident:
                    stem = re.sub(r'[^a-z0-9]+', '_', self.object_class.text().strip().lower()).strip('_') or 'object'
                    number = 1
                    while self.project.get_object(f'{stem}_{number:02d}'): number += 1
                    ident = f'{stem}_{number:02d}'
                obj = self.project.add_object(name, object_class=self.object_class.text().strip(),
                                              notes=self.notes.text().strip(), id=ident)
            self._selected_id = obj.id
            self.object_id.setText(obj.id); self.object_id.setReadOnly(True)
            self.store_button.setText('Update object'); self.retire_button.setEnabled(True)
            self._refresh(obj.id); self.message.setText('Object stored in this dialog. Save to apply to the project; Cancel discards changes.')
            return True
        except ValueError as exc:
            self.message.setText(str(exc)); return False

    def _retire(self):
        obj = self.project.get_object(self._selected_id)
        if obj is None: return
        extra = deepcopy(obj.extra); extra['retired'] = not bool(extra.get('retired'))
        self.project.update_object(obj.id, extra=extra)
        self._refresh(obj.id)
        self.message.setText('Existing annotations keep this ID. Retired objects are hidden from new selections.')

    def _finish(self):
        # Do not silently lose fields typed since the last Add / Update click.
        if any(w.text().strip() for w in (self.name,self.object_id,self.object_class,self.notes)) and not self._store(): return
        self.accept()

    def result_objects(self):
        return deepcopy(self.project.objects)
