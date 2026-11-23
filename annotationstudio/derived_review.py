"""Read-only inspection of derived annotations whose upstream evidence changed."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,
    QTableWidgetItem,QHeaderView,QPushButton,QAbstractItemView)
from .speech_structure import dependency_issues


class DerivedReviewDialog(QDialog):
    def __init__(self,project,parent=None):
        super().__init__(parent)
        self.annotation_id=None
        self.setWindowTitle('Recheck derived results'); self.resize(900,510)
        layout=QVBoxLayout(self)
        note=QLabel('Derived records keep the source IDs and snapshots used to create them. '
                    'Changes below do not overwrite an accepted result. Open a record to inspect it, '
                    'or rerun speech structure after reviewing the source tracks.')
        note.setWordWrap(True); layout.addWidget(note)
        self.table=QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(['Actor','Label','Time','Review state','Changed / missing sources','Annotation ID'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch)
        self.table.setColumnHidden(5,True)
        layout.addWidget(self.table,1)
        current={a.id:a for a in project.annotations}
        for a in project.annotations:
            issues=dependency_issues(project,a)
            if not issues:continue
            row=self.table.rowCount(); self.table.insertRow(row)
            descriptions=[f'{current[i].label} [{i}]' if i in current else f'Missing [{i}]' for i in issues]
            values=[a.role,a.label,f'{a.start_s:.3f}s' if a.is_point else f'{a.start_s:.3f}–{a.end_s:.3f}s',
                    a.status,'; '.join(descriptions),a.id]
            for col,value in enumerate(values):
                item=QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(row,col,item)
        self.summary=QLabel(f'{self.table.rowCount()} records need an upstream-evidence check. '
                           'No records or review states have been changed.')
        self.summary.setWordWrap(True); layout.addWidget(self.summary)
        actions=QHBoxLayout(); layout.addLayout(actions)
        open_button=QPushButton('Open selected'); open_button.clicked.connect(self._open)
        open_button.setEnabled(self.table.rowCount()>0); actions.addWidget(open_button)
        actions.addStretch(); close=QPushButton('Close'); close.clicked.connect(self.reject); actions.addWidget(close)
        self.table.itemDoubleClicked.connect(lambda _:self._open())
        if self.table.rowCount():self.table.selectRow(0)

    def _open(self):
        row=self.table.currentRow()
        if row<0:return
        self.annotation_id=self.table.item(row,5).text(); self.accept()
