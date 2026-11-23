"""Track setup with a reviewable, category-specific manual label list."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QDialogButtonBox, QCheckBox, QPlainTextEdit, QMessageBox)

from .models import Project, Track, CHANNELS, ROLES, label_search_aliases
from .ontology import (ACTIVITY_CHANNEL, ACTIVITY_EPISODE, WORKSPACE_CATEGORIES, BODY_PARTS, category_info, is_legacy_category,
                       LABEL_INFO, LEGACY_LABEL_PRESETS, label_spec)
from .annotation_fields import DIRECTED_CATEGORIES


class TrackLabelOptions(QWidget):
    """Preview all labels, or select an explicit per-track subset without mutation."""
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self._labels = []
        self._category = ''
        self._retained_ids = []
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel('LABEL LIST'); title.setObjectName('Subhead'); layout.addWidget(title)
        self.restrict = QCheckBox('Use only checked labels on this track')
        layout.addWidget(self.restrict)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search labels or Chinese names…')
        layout.addWidget(self.search)
        self.list = QListWidget(); self.list.setMinimumWidth(320); layout.addWidget(self.list, 1)
        self.count = QLabel(); self.count.setWordWrap(True); layout.addWidget(self.count)
        self.definition = QPlainTextEdit(); self.definition.setReadOnly(True)
        self.definition.setPlaceholderText('Select a label to read its definition and boundary rule.')
        self.definition.setMaximumHeight(125); layout.addWidget(self.definition)
        self.restrict.toggled.connect(self._restriction_changed)
        self.search.textChanged.connect(self._filter)
        self.list.currentItemChanged.connect(self._describe)
        self.list.itemChanged.connect(self._count)

    def set_context(self, category, scope=0, allowed_ids=None, channel=None):
        self._category = category
        track = Track(id='preview', name='Preview', category=category,
                      channel=channel or 'Full Body',
                      extra={'label_scope': scope})
        self._labels = [label for label in self.project.labels_for_track(
            track, include_deprecated=is_legacy_category(category),
            match_body_part=channel is not None) if label.name != 'Unlabeled']
        visible_ids = {label.id for label in self._labels}
        # Opening a body-part-filtered view must not silently remove old or
        # retired list membership that is not shown by this view.
        self._retained_ids = [ident for ident in (allowed_ids or []) if ident not in visible_ids]
        with QSignalBlocker(self.list), QSignalBlocker(self.restrict):
            self.list.clear()
            self.restrict.setChecked(allowed_ids is not None)
            for label in self._labels:
                item = QListWidgetItem(label.name)
                item.setData(Qt.UserRole, label.id)
                item.setToolTip(label.definition or label.name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if allowed_ids is None or label.id in allowed_ids else Qt.Unchecked)
                self.list.addItem(item)
        self._restriction_changed()
        self._filter()
        self.definition.clear()

    def _restriction_changed(self, *_):
        with QSignalBlocker(self.list):
            for index in range(self.list.count()):
                item = self.list.item(index)
                flags = item.flags()
                item.setFlags(flags | Qt.ItemIsUserCheckable if self.restrict.isChecked()
                              else flags & ~Qt.ItemIsUserCheckable)
        self._count()

    def _filter(self, *_):
        query = self.search.text().strip().casefold()
        by_id = {label.id: label for label in self._labels}
        for index in range(self.list.count()):
            item = self.list.item(index); label = by_id[item.data(Qt.UserRole)]
            info = self._fallback(label)
            haystack = ' '.join([label.name, *label_search_aliases(label), str(label.extra.get('zh') or info.get('zh', '')),
                                str(label.extra.get('group') or info.get('group', ''))]).casefold()
            item.setHidden(bool(query and query not in haystack))

    @staticmethod
    def _fallback(label):
        known = ((label.category, label.name) in LABEL_INFO or
                 label.name in LEGACY_LABEL_PRESETS.get(label.category, ()))
        return label_spec(label.category, label.name) if label.scope == 'core' and known else {}

    def _count(self, *_):
        chosen = sum(self.list.item(i).checkState() == Qt.Checked for i in range(self.list.count()))
        retained = f'; {len(self._retained_ids)} saved IDs outside this view retained' if self._retained_ids else ''
        self.count.setText(f'{chosen} of {self.list.count()} visible labels selected{retained}' if self.restrict.isChecked()
                           else f'All {self.list.count()} matching labels; future compatible project labels are included.')

    def _describe(self, item, *_):
        if not item:
            self.definition.clear(); return
        label = self.project.get_label(item.data(Qt.UserRole))
        if label:
            info = self._fallback(label)
            definition = label.definition or info.get('description', 'No definition is recorded yet.')
            rule = label.boundary_rule or info.get('boundary_rule', 'Set boundaries from the available evidence.')
            self.definition.setPlainText(f'{label.name}\n\n{definition}\n\nBoundary: {rule}')

    def allowed_ids(self):
        if not self.restrict.isChecked():
            return None
        return list(dict.fromkeys([*self._retained_ids,
            *[self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
              if self.list.item(i).checkState() == Qt.Checked]]))

    def validate(self):
        if self.allowed_ids() == []:
            QMessageBox.warning(self, 'Choose labels', 'Check at least one label, or use the full label list.')
            return False
        return True


class TrackDialog(QDialog):
    def __init__(self, workspace='Motion', parent=None, project=None):
        super().__init__(parent)
        self.project = project if project is not None else Project()
        self.setWindowTitle('Add annotation track'); self.resize(880, 650)
        layout = QVBoxLayout(self)
        note = QLabel('One track answers one annotation question. For primitives, choose an actor and a primary body part.')
        note.setWordWrap(True); layout.addWidget(note)
        columns = QHBoxLayout(); layout.addLayout(columns, 1)
        left = QVBoxLayout(); columns.addLayout(left, 1)
        form = QFormLayout(); left.addLayout(form)
        self.name = QLineEdit(); form.addRow('Track name', self.name)
        self.workspace = QComboBox()
        self.workspace.addItems([x for x in WORKSPACE_CATEGORIES if x != 'Overview'])
        form.addRow('Workspace', self.workspace)
        self.category = QComboBox(); form.addRow('Annotation type', self.category)
        self.description = QLabel(); self.description.setWordWrap(True); left.addWidget(self.description)
        form2 = QFormLayout(); left.addLayout(form2)
        self.role = QComboBox(); self.role.addItems(['R01', 'R02', 'Unknown'])
        form2.addRow('Actor', self.role)
        self.target_role = QComboBox(); self.target_label = QLabel('Toward / responding to')
        form2.addRow(self.target_label, self.target_role)
        self.channel = QComboBox(); self.channel.addItems(CHANNELS)
        self.channel_label = QLabel('Channel / body part')
        form2.addRow(self.channel_label, self.channel)
        self.scope = QComboBox(); self.scope.addItems(['Core + project labels', 'Project labels', 'Temporary labels'])
        form2.addRow('Label source', self.scope)
        self.parts = QListWidget(); self.parts.setMaximumHeight(160)
        self.parts.setSelectionMode(QAbstractItemView.MultiSelection)
        self.parts.addItems(BODY_PARTS)
        self.parts_label = QLabel('Additional linked parts (do not change the primary label list)')
        left.addWidget(self.parts_label); left.addWidget(self.parts)
        self.role_note = QLabel(); self.role_note.setWordWrap(True); left.addWidget(self.role_note); left.addStretch()
        self.label_options = TrackLabelOptions(self.project); columns.addWidget(self.label_options, 1)
        self.workspace.currentTextChanged.connect(self._workspace_changed)
        self.category.currentTextChanged.connect(self._category_changed)
        self.role.currentTextChanged.connect(self._actor_changed)
        self.scope.currentIndexChanged.connect(self._labels_changed)
        self.channel.currentTextChanged.connect(self._channel_changed)
        self.workspace.setCurrentText(workspace if workspace in WORKSPACE_CATEGORIES and workspace != 'Overview' else 'Motion')
        self._workspace_changed(self.workspace.currentText())
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Add track')
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def _workspace_changed(self, workspace):
        with QSignalBlocker(self.category):
            self.category.clear(); self.category.addItems(WORKSPACE_CATEGORIES.get(workspace, ()))
        self._category_changed(self.category.currentText())

    def _category_changed(self, category):
        info = category_info(category)
        activity = category == ACTIVITY_EPISODE
        timing='Point event: click a time; there is no duration.' if info.get('temporal_kind')=='point' else 'Interval: edit start and end boundaries.'
        self.description.setText(info.get('description', category)+'\n\n'+timing)
        channels = (ACTIVITY_CHANNEL,) if activity else (BODY_PARTS if category == 'Motion Primitive' else CHANNELS)
        with QSignalBlocker(self.channel):
            self.channel.clear()
            self.channel.addItems(channels)
            self.channel.setCurrentText(info.get('default_channel', 'Right Arm'))
        for widget in (self.channel_label, self.channel, self.parts_label, self.parts):
            widget.setVisible(not activity)
        self.name.setPlaceholderText(self._default_track_name())
        old_role = self.role.currentText()
        scope = info.get('actor_scope', 'single')
        roles = ['Both'] if scope == 'pair' else (list(ROLES) if scope == 'either' else ['R01', 'R02', 'Unknown'])
        with QSignalBlocker(self.role):
            self.role.clear(); self.role.addItems(roles)
            if old_role in roles: self.role.setCurrentText(old_role)
        self.role.setEnabled(scope != 'pair')
        self.role_note.setText('A paired track describes R01 and R02 together.' if scope == 'pair'
                               else 'Create separate R01 and R02 tracks to annotate each person independently.')
        self._actor_changed(); self._labels_changed()

    def _actor_changed(self, *_):
        old_target = self.target_role.currentData()
        self.target_role.clear(); self.target_role.addItem('Unspecified', '')
        for role in ('R01', 'R02'):
            if role != self.role.currentText(): self.target_role.addItem(role, role)
        index = self.target_role.findData(old_target)
        if index >= 0: self.target_role.setCurrentIndex(index)
        enabled = self.category.currentText() in DIRECTED_CATEGORIES and self.role.currentText() in ('R01', 'R02')
        self.target_role.setEnabled(enabled)
        self.target_role.setVisible(enabled); self.target_label.setVisible(enabled)

    def _labels_changed(self, *_):
        self.label_options.set_context(self.category.currentText(), self.scope.currentIndex(),
                                       channel=self.channel.currentText())

    def _channel_changed(self, *_):
        self.name.setPlaceholderText(self._default_track_name())
        self._labels_changed()

    def _default_track_name(self):
        category = self.category.currentText()
        return category if category == ACTIVITY_EPISODE else f'{self.channel.currentText()} · {category}'

    def _accept(self):
        if self.label_options.validate(): self.accept()

    def values(self):
        extra = {'label_scope': self.scope.currentIndex()}
        extra['temporal_kind'] = category_info(self.category.currentText()).get('temporal_kind', 'interval')
        ids = self.label_options.allowed_ids()
        if ids is not None: extra['allowed_label_ids'] = ids
        if self.role.currentText() == 'Both': extra['participants'] = ['R01', 'R02']
        if self.target_role.isEnabled() and self.target_role.currentData():
            extra['target_role'] = self.target_role.currentData()
        linked_parts = [item.text() for item in self.parts.selectedItems()]
        if self.category.currentText() == 'Motion Primitive':
            linked_parts = list(dict.fromkeys([self.channel.currentText(), *linked_parts]))
        body_parts = [] if self.category.currentText() == ACTIVITY_EPISODE else (linked_parts or [self.channel.currentText()])
        return dict(name=self.name.text().strip() or self._default_track_name(),
                    role=self.role.currentText(), workspace=self.workspace.currentText(),
                    category=self.category.currentText(), channel=self.channel.currentText(),
                    body_parts=body_parts, extra=extra)


class TrackLabelDialog(QDialog):
    """Edit only suggestion membership; existing annotations keep their identity."""
    def __init__(self, project, track, parent=None):
        super().__init__(parent); self.setWindowTitle('Track label list'); self.resize(590, 600)
        layout = QVBoxLayout(self)
        title = QLabel(f'{track.role} / {track.name}\n{track.category}'); title.setWordWrap(True); layout.addWidget(title)
        note = QLabel('Choose which labels appear for this track. Saved annotations retain their labels and history.')
        note.setWordWrap(True); layout.addWidget(note)
        self.options = TrackLabelOptions(project); layout.addWidget(self.options, 1)
        self.options.set_context(track.category, track.extra.get('label_scope', 0),
                                 track.extra.get('allowed_label_ids'), channel=track.channel)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def _accept(self):
        if self.options.validate(): self.accept()

    def allowed_ids(self): return self.options.allowed_ids()
