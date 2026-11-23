"""Track, vocabulary, source and export configuration dialogs."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,
    QComboBox,QListWidget,QListWidgetItem,QAbstractItemView,QDialogButtonBox,QPushButton,
    QMessageBox,QPlainTextEdit,QCheckBox,QDoubleSpinBox,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QWidget)
from .models import CHANNELS, ROLES, Project, label_search_aliases
from .ontology import (WORKSPACE_CATEGORIES, BODY_PARTS, LEGACY_MOTION_RELATION,
                       RETIRED_PRIMITIVE_LABELS, is_motion_candidate, label_spec)
from .annotation_export import available_export_types, select_annotations


from .track_setup import TrackDialog, TrackLabelDialog


class TracksDialog(QDialog):
    def __init__(self,project,parent=None):
        super().__init__(parent); self.setWindowTitle('Track manager'); self.resize(600,490)
        self.tracks=deepcopy(sorted(project.tracks,key=lambda t:t.order)); self.removed=set()
        self.counts={t.id:sum(a.track_id==t.id for a in project.annotations) for t in self.tracks}
        layout=QVBoxLayout(self); layout.addWidget(QLabel('Drag to reorder. Uncheck to hide a track without removing its annotations.'))
        self.list=QListWidget(); self.list.setDragDropMode(QAbstractItemView.InternalMove); layout.addWidget(self.list,1)
        for t in self.tracks:
            item=QListWidgetItem(f'{t.role}   /   {t.workspace}   /   {t.name}   ({self.counts[t.id]})')
            item.setData(Qt.UserRole,t.id); item.setFlags(item.flags()|Qt.ItemIsUserCheckable); item.setCheckState(Qt.Checked if t.visible else Qt.Unchecked); self.list.addItem(item)
        row=QHBoxLayout(); layout.addLayout(row)
        delete=QPushButton('Delete selected track…'); delete.clicked.connect(self._delete); row.addWidget(delete); row.addStretch()
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); row.addWidget(buttons)
    def _delete(self):
        item=self.list.currentItem()
        if not item:return
        ident=item.data(Qt.UserRole); count=self.counts[ident]
        if count and QMessageBox.question(self,'Delete track',f'Delete this track and its {count} annotations? You can undo after closing this dialog.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self.removed.add(ident); self.list.takeItem(self.list.row(item))
    def result_tracks(self):
        result=[]
        for i in range(self.list.count()):
            item=self.list.item(i); track=next(t for t in self.tracks if t.id==item.data(Qt.UserRole)); track.order=i; track.visible=item.checkState()==Qt.Checked; result.append(track)
        return result


class LabelDialog(QDialog):
    def __init__(self,project,category=None,parent=None):
        super().__init__(parent); self.setWindowTitle('Label vocabulary'); self.resize(850,570)
        self.project=deepcopy(project); self.current=None; self._loading=False
        layout=QVBoxLayout(self)
        top=QHBoxLayout(); layout.addLayout(top)
        self.category=QComboBox(); self.category.addItems(list(dict.fromkeys([*WORKSPACE_CATEGORIES['Overview'], *[label.category for label in project.labels]]))); top.addWidget(self.category)
        self.search=QLineEdit(); self.search.setPlaceholderText('Search labels, aliases or Chinese names…'); top.addWidget(self.search,1)
        add=QPushButton('+ Project label'); add.clicked.connect(self._add); top.addWidget(add)
        body=QHBoxLayout(); layout.addLayout(body,1)
        self.list=QListWidget(); self.list.setMinimumWidth(300); body.addWidget(self.list,1)
        form=QFormLayout(); body.addLayout(form,1)
        self.name=QLineEdit(); form.addRow('Display name',self.name)
        self.scope=QComboBox(); self.scope.addItems(['core','project','temporary']); form.addRow('Scope',self.scope)
        self.aliases=QLineEdit(); self.aliases.setPlaceholderText('Separate with commas'); form.addRow('Aliases',self.aliases)
        self.definition=QPlainTextEdit(); self.definition.setMaximumHeight(105); form.addRow('Definition',self.definition)
        self.rule=QPlainTextEdit(); self.rule.setMaximumHeight(105); form.addRow('Boundary rule',self.rule)
        self.deprecated=QCheckBox('Retired (keep historical references)'); form.addRow('',self.deprecated)
        self.identity=QLabel(''); self.identity.setWordWrap(True); self.identity.setStyleSheet('font-size:8pt;color:#93816D;'); form.addRow('Stable ID',self.identity)
        apply=QPushButton('Apply label changes'); apply.clicked.connect(self._apply); form.addRow('',apply)
        merge=QPushButton('Merge into another label…'); merge.clicked.connect(self._merge); form.addRow('',merge)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.category.currentTextChanged.connect(self._populate); self.search.textChanged.connect(self._populate); self.list.currentItemChanged.connect(self._select)
        if category:self.category.setCurrentText(category)
        self._populate()
    def _populate(self,*_):
        self.list.clear(); self.current=None
        query=self.search.text().strip().casefold()
        for label in self.project.labels_for(self.category.currentText(),include_deprecated=True):
            zh=label.extra.get('zh') or (label_spec(label.category,label.name)['zh'] if label.scope=='core' else '')
            if not any(query in str(term).casefold() for term in (label.name,zh,*label_search_aliases(label))):continue
            item=QListWidgetItem(self._caption(label)); item.setData(Qt.UserRole,label.id); self.list.addItem(item)
        if self.list.count():self.list.setCurrentRow(0)
    def _caption(self,label):
        state = ('Candidate only' if is_motion_candidate(label.category,label.name) else
                 'Legacy' if label.category==LEGACY_MOTION_RELATION or self.project.label_is_deprecated(label)
                 else label.scope)
        return f'{label.name}   [{state}]'
    def _select(self,item,previous=None):
        if not item:return
        self.current=self.project.get_label(item.data(Qt.UserRole))
        a=self.current; self.name.setText(a.name); self.scope.setCurrentText(a.scope); self.aliases.setText(', '.join(a.aliases)); self.definition.setPlainText(a.definition); self.rule.setPlainText(a.boundary_rule); self.deprecated.setChecked(a.deprecated); self.identity.setText(f'{a.id}\nVersion {a.version}')
    def _apply(self):
        if not self.current:return True
        try:
            a=self.project.rename_label(self.current.id,self.name.text().strip())
            changes=dict(scope=self.scope.currentText(),aliases=[x.strip() for x in self.aliases.text().split(',') if x.strip()],definition=self.definition.toPlainText(),boundary_rule=self.rule.toPlainText(),deprecated=self.deprecated.isChecked())
            # Retain the old display name recorded by rename_label as an alias.
            changes['aliases']=list(dict.fromkeys([*a.aliases,*changes['aliases']]))
            if any(getattr(a,k)!=v for k,v in changes.items()):a.version+=1
            for k,v in changes.items():setattr(a,k,v)
            item=self.list.currentItem()
            if item:item.setText(self._caption(a))
            return True
        except ValueError as exc:QMessageBox.warning(self,'Label conflict',str(exc)); return False
    def _add(self):
        from PySide6.QtWidgets import QInputDialog
        name,ok=QInputDialog.getText(self,'New project label','Display name')
        if not ok or not name.strip():return
        category=self.category.currentText()
        if category==LEGACY_MOTION_RELATION or (
                category=='Motion Primitive' and name.strip().casefold() in RETIRED_PRIMITIVE_LABELS):
            QMessageBox.warning(self,'Historical vocabulary','Choose a specific label in an active type.'); return
        self.project.add_label(name,category,'project'); self.search.clear(); self._populate()
    def _merge(self):
        from PySide6.QtWidgets import QInputDialog
        if not self.current:return
        target=[l for l in self.project.labels_for(self.current.category) if l.id!=self.current.id]
        if not target:return
        name,ok=QInputDialog.getItem(self,'Merge label',f'Move all uses of “{self.current.name}” to:',[l.name for l in target],0,False)
        if ok:
            self.project.merge_labels(self.current.id,next(l.id for l in target if l.name==name)); self._populate()
    def _save(self):
        if self._apply():self.accept()


class AssetDialog(QDialog):
    def __init__(self,asset,parent=None):
        super().__init__(parent); self.setWindowTitle('Source timing & mapping'); self.resize(580,290)
        layout=QVBoxLayout(self); form=QFormLayout(); layout.addLayout(form)
        self.path=QLineEdit(asset.path); row=QHBoxLayout(); row.addWidget(self.path,1)
        browse=QPushButton('Relink…'); browse.clicked.connect(self._browse); row.addWidget(browse); form.addRow('File',row)
        self.name=QLineEdit(asset.name); form.addRow('Display name',self.name)
        self.role=QComboBox(); self.role.addItems(ROLES); self.role.setCurrentText(asset.role); form.addRow('Actor mapping',self.role)
        self.offset=QDoubleSpinBox(); self.offset.setRange(-1e6,1e6); self.offset.setDecimals(6); self.offset.setValue(asset.offset_s); form.addRow('Master offset (s)',self.offset)
        self.enabled=QCheckBox('Load and play this source'); self.enabled.setChecked(asset.enabled); form.addRow('',self.enabled)
        note=QLabel('Master time = source-local time + offset. Changing this mapping does not move existing annotations; review them against the new alignment.'); note.setWordWrap(True); layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def _browse(self):
        p,_=QFileDialog.getOpenFileName(self,'Relink source',str(Path(self.path.text()).parent))
        if p:self.path.setText(p)
    def values(self):return dict(path=self.path.text().strip(),name=self.name.text().strip(),role=self.role.currentText(),offset_s=self.offset.value(),enabled=self.enabled.isChecked())


class ExportDialog(QDialog):
    """Choose CSV output files and explicit type/review filters without editing data."""

    REVIEW_STATES=('accepted','candidates_accepted','all')

    def __init__(self,parent=None,project=None):
        super().__init__(parent)
        self.project=project if project is not None else getattr(parent,'project',None)
        if self.project is None:self.project=Project()
        self.setWindowTitle('Export annotations'); self.resize(680,330)
        layout=QVBoxLayout(self); layout.setSpacing(12)
        heading=QLabel('Choose the annotations and files to save.'); layout.addWidget(heading)
        form=QFormLayout(); form.setSpacing(9)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        layout.addLayout(form)
        self.format=QComboBox()
        self.format.addItems(['CSV · annotation tables','ELAN EAF · time-aligned subtiers'])
        form.addRow('Format',self.format)
        self.output=QComboBox()
        for title,key in [('Combined table','combined'),('Separate tables by type','by_type'),
                          ('Combined + separate tables','both')]:
            self.output.addItem(title,key)
        self.output.setCurrentIndex(2)
        self.output_label=QLabel('Output'); form.addRow(self.output_label,self.output)
        self.scope=QComboBox()
        self.scope.addItems(['Accepted only','Candidates + accepted','All including rejected'])
        form.addRow('Review state',self.scope)
        self.type_mode=QComboBox(); self.type_mode.addItems(['All types','Choose types…'])
        form.addRow('Annotation types',self.type_mode)

        self.type_panel=QWidget(); panel=QVBoxLayout(self.type_panel)
        panel.setContentsMargins(0,0,0,0); panel.setSpacing(6)
        actions=QHBoxLayout(); actions.addWidget(QLabel('Types in this project')); actions.addStretch()
        self.select_all=QPushButton('All'); self.select_none=QPushButton('None')
        actions.addWidget(self.select_all); actions.addWidget(self.select_none); panel.addLayout(actions)
        self.types=QListWidget(); self.types.setSelectionMode(QAbstractItemView.NoSelection)
        self.types.setMinimumHeight(160); self.types.setMaximumHeight(230)
        self.types.setAccessibleName('Annotation types to export')
        panel.addWidget(self.types)
        layout.addWidget(self.type_panel)

        self.summary=QLabel(); self.summary.setTextFormat(Qt.PlainText)
        self.summary.setWordWrap(True); self.summary.setStyleSheet('font-weight:600;')
        layout.addWidget(self.summary)
        self.note=QLabel(); self.note.setTextFormat(Qt.PlainText); self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        self.export_button=self.buttons.button(QDialogButtonBox.Save)
        self.export_button.setText('Export…')
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.format.currentIndexChanged.connect(self._update_format)
        self.output.currentIndexChanged.connect(self._update_summary)
        self.scope.currentIndexChanged.connect(self._refresh_types)
        self.type_mode.currentIndexChanged.connect(self._update_type_mode)
        self.types.itemChanged.connect(self._update_summary)
        self.select_all.clicked.connect(lambda:self._set_all_types(True))
        self.select_none.clicked.connect(lambda:self._set_all_types(False))
        self._refresh_types(); self._update_type_mode(); self._update_format()

    def review_state(self):
        return self.REVIEW_STATES[self.scope.currentIndex()]

    def selected_categories(self):
        if self.type_mode.currentIndex()==0:return None
        return [self.types.item(i).data(Qt.UserRole) for i in range(self.types.count())
                if self.types.item(i).checkState()==Qt.Checked]

    def export_layout(self):
        return 'combined' if self.format.currentIndex()==1 else self.output.currentData()

    def _refresh_types(self,*_):
        previous={self.types.item(i).data(Qt.UserRole):self.types.item(i).checkState()
                  for i in range(self.types.count())}
        self.types.blockSignals(True)
        try:
            self.types.clear()
            for row in available_export_types(self.project,self.review_state()):
                category=row['category']; workspace=row.get('workspace') or 'Project / legacy'
                item=QListWidgetItem(f"{category}   ·   {workspace}   ·   {row['count']}")
                item.setData(Qt.UserRole,category)
                item.setFlags(item.flags()|Qt.ItemIsUserCheckable)
                item.setCheckState(previous.get(category,Qt.Checked))
                item.setToolTip(f"{row['count']} matching annotations; {row['total_count']} in all review states.")
                self.types.addItem(item)
        finally:self.types.blockSignals(False)
        self._update_summary()

    def _set_all_types(self,checked):
        self.types.blockSignals(True)
        try:
            for i in range(self.types.count()):
                self.types.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        finally:self.types.blockSignals(False)
        self._update_summary()

    def _update_type_mode(self,*_):
        self.type_panel.setVisible(self.type_mode.currentIndex()==1)
        self._update_summary()
        self.resize(self.width(),self.sizeHint().height())

    def _update_format(self,*_):
        csv=self.format.currentIndex()==0
        self.output.setVisible(csv); self.output_label.setVisible(csv)
        self._update_summary()

    def _update_summary(self,*_):
        annotations=select_annotations(self.project,self.review_state(),self.selected_categories())
        categories={annotation.category for annotation in annotations}
        self.summary.setText(f'{len(annotations)} annotations · {len(categories)} types · all matching actors and tracks')
        points=sum(annotation.is_point for annotation in annotations)
        eaf=self.format.currentIndex()==1
        self.export_button.setEnabled(bool(annotations) and not (eaf and points))
        if not annotations:
            text='No annotations match these types and review state. Change the selection to export.'
        elif eaf and points:
            text=(f'This selection contains {points} point event(s). Use CSV, or choose only interval types for EAF. '
                  'Point events will not be dropped or given an artificial duration.')
        elif eaf:
            text=('One EAF file with separate tiers. EAF contains interval labels; use CSV and the project JSON '
                  'to retain object details, Affect ratings and edit history.')
        elif self.export_layout()=='combined':
            text=('Save one CSV containing the selected annotations, including object names and review metadata. '
                  'Choose one type above to save only that type.')
        else:
            total='a combined CSV, ' if self.export_layout()=='both' else ''
            text=(f'A new folder will contain {total}one CSV per non-empty selected type, '
                  'an object list and an export summary. Keep your project JSON for continued editing.')
        self.note.setText(text)
