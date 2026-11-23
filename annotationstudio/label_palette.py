"""A browsable label list for the selected timeline track.

Selecting a label changes an annotation draft only through ``labelChosen``.
This widget never creates a time interval or accepts an annotation itself.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSignalBlocker, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QSizePolicy,
)

from .ontology import (
    FINE_PRIMITIVE_AUTO_METHODS, INTERACTION_EVENT_CORE_GROUPS, LABEL_PRESETS, LEGACY_LABEL_PRESETS, category_info,
    interaction_event_menu_group, is_legacy_category, label_spec,
)
from .ontology_v51 import HAND_MENU_GROUPS, hand_menu_group
from .affect_display import affect_adjective
from .models import label_search_aliases

WORKFLOW_NAMES = {'automatic_primary':'Automatic first', 'automatic_derived':'Automatically derived',
                  'assisted':'Automatic assistance + review', 'manual_primary':'Contextual / manual'}
IMPLEMENTATION_NAMES = {'builtin':'Built in', 'optional_model':'Optional model',
                        'planned_rule':'Rule detector planned', 'planned_model':'Model integration planned',
                        'manual':'Manual input available'}

_INTERACTION_EVENT_LABEL_ORDER = {
    key: index for index, key in enumerate(
        (group, name) for group, names in INTERACTION_EVENT_CORE_GROUPS.items() for name in names)
}


_NAME_ROLE = Qt.UserRole
_ENTRY_ROLE = Qt.UserRole + 1


def eligible_labels(project, track):
    """Return the track's own list, preserving access to historical types.

    Current annotations are handled separately: a saved label remains visible
    even if the track list has since been narrowed or the label was retired.
    """
    if project is None or track is None:
        return []
    legacy = is_legacy_category(track.category)
    if hasattr(project, 'labels_for_track'):
        return list(project.labels_for_track(track, include_deprecated=legacy))
    labels = project.labels_for(track.category, include_deprecated=legacy)
    scope = track.extra.get('label_scope', 0)
    permitted = {0: ('core', 'project'), 1: ('project',),
                 2: ('temporary',)}.get(scope, ('core', 'project', 'temporary'))
    allowed = track.extra.get('allowed_label_ids')
    return [label for label in labels if label.scope in permitted
            and (allowed is None or label.id in allowed)]


def current_label(project, annotation):
    """Resolve a current record without changing its text or stable identity."""
    if project is None or annotation is None:
        return None
    label = project.get_label(annotation.label_id) if annotation.label_id else None
    if label is not None:
        return label
    return next((label for label in project.labels
                 if label.category == annotation.category
                 and label.name == annotation.label), None)


class LabelPalette(QWidget):
    labelChosen = Signal(str)
    configureTrackRequested = Signal()
    addLabelRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('LabelPalette')
        self.project = None
        self.track = None
        self.annotation = None
        self._context_key = None
        self._entries = []
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        heading = QHBoxLayout()
        self.title = QLabel('TRACK LABELS')
        self.title.setObjectName('Subhead')
        heading.addWidget(self.title, 1)
        self.configure_button = QPushButton('Edit list…')
        self.configure_button.setToolTip('Choose which labels belong to this track.')
        self.configure_button.clicked.connect(self.configureTrackRequested)
        heading.addWidget(self.configure_button)
        layout.addLayout(heading)

        self.context = QLabel('Select an annotation track.')
        self.context.setWordWrap(True)
        self.context.setStyleSheet('font-size:8pt; color:#735B49;')
        layout.addWidget(self.context)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText('Search this label list…')
        self.search.setToolTip('Search English names, aliases or Chinese meanings.')
        self.search.textChanged.connect(self._rebuild)
        search_row.addWidget(self.search, 1)
        self.add_button = QPushButton('+ Label')
        self.add_button.setToolTip('Add the search text as a custom label for this track.')
        self.add_button.clicked.connect(self._add_search_label)
        search_row.addWidget(self.add_button)
        layout.addLayout(search_row)

        self.hint = QLabel('Drag a time interval, then choose its label.')
        self.hint.setWordWrap(False)
        self.hint.setStyleSheet('font-size:8pt; color:#8B7968;')
        layout.addWidget(self.hint)
        self.tree = QTreeWidget()
        self.tree.setObjectName('TrackLabelList')
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.setIndentation(12)
        self.tree.setUniformRowHeights(False)
        self.tree.setWordWrap(True)
        self.tree.setMinimumHeight(80)
        self.tree.setStyleSheet('QTreeWidget::item { padding:3px 5px; }')
        self.tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        self.tree.itemClicked.connect(self._choose_item)
        self.tree.itemActivated.connect(self._choose_item)
        layout.addWidget(self.tree, 1)

        self.definition = QPlainTextEdit()
        self.definition.setReadOnly(True)
        self.definition.setFixedHeight(78)
        self.definition.setPlaceholderText('Select a label to see its meaning and time boundaries.')
        self.definition.setStyleSheet('font-size:8pt; background:#FBF9F5;')
        layout.addWidget(self.definition)
        self.capability = QLabel('')
        self.capability.setWordWrap(True)
        self.capability.setStyleSheet('font-size:8pt; color:#8B7968;')
        layout.addWidget(self.capability)
        self.bind(None, None)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'capability'):
            return
        # The main splitter is adjustable. Keep the list useful on a laptop;
        # the full definition remains scrollable when the upper pane is short.
        height = self.height()
        self.definition.setFixedHeight(58 if height < 300 else 78 if height < 430 else 116)
        self.capability.setVisible(height >= 400)
        QTimer.singleShot(0, self._ensure_current_visible)

    def _ensure_current_visible(self):
        item = self.tree.currentItem()
        if item is not None:
            self.tree.scrollToItem(item)

    @staticmethod
    def _entry(label, *, current=False):
        extra = label.extra or {}
        # Older core Label records are preserved verbatim by project migration.
        # Supply missing display guidance without rewriting their stored data.
        # A user-renamed core item must keep its project-specific interpretation.
        known_name = (label.name in LABEL_PRESETS.get(label.category, ()) or
                      label.name in LEGACY_LABEL_PRESETS.get(label.category, ()))
        fallback = label_spec(label.category, label.name) if label.scope == 'core' and known_name else {}
        current_detector = (fallback and label.category == 'Motion Primitive'
                            and label.name in FINE_PRIMITIVE_AUTO_METHODS)

        def metadata(key, default=''):
            if current_detector and key in ('auto_mode', 'auto_method', 'implementation_status'):
                return fallback[key]
            return extra.get(key) or fallback.get(key) or default

        group = str(metadata('group',
                    'Project labels' if label.scope == 'project' else
                    'Temporary labels' if label.scope == 'temporary' else 'Labels'))
        if label.scope == 'core' and known_name:
            if label.category == 'Hand Behavior':
                group = hand_menu_group(label.name, group)
            elif label.category == 'Interaction Event':
                group = interaction_event_menu_group(label.name, group)

        return {
            'name': label.name,
            'display_name': affect_adjective(label),
            'id': label.id,
            'aliases': label_search_aliases(label) or fallback.get('aliases', []),
            'zh': str(metadata('zh')),
            'group': 'Current / legacy' if current else group,
            'definition': label.definition or fallback.get('description', ''),
            'boundary_rule': label.boundary_rule or fallback.get('boundary_rule', ''),
            'auto_mode': str(metadata('auto_mode', 'manual')),
            'auto_method': str(metadata('auto_method')),
            'recommended_workflow': str(metadata('recommended_workflow', 'manual_primary')),
            'implementation_status': str(metadata('implementation_status', 'manual')),
            'temporal_kind': str(metadata('temporal_kind', 'interval')),
            'semantic_kind': str(metadata('semantic_kind')),
            'current': current,
            'deprecated': label.deprecated,
        }

    def bind(self, project, track, annotation=None):
        """Update list context without clearing a same-track search or draft."""
        key = (track.id, track.category, track.channel) if track is not None else None
        changed_track = key != self._context_key
        self.project, self.track, self.annotation = project, track, annotation
        self._context_key = key
        self._loading = True
        if changed_track:
            blocker = QSignalBlocker(self.search)
            self.search.clear()
            del blocker
        self._entries = []
        if track is not None and project is not None:
            labels = eligible_labels(project, track)
            # Unlabeled is an editing placeholder, not a selectable event.
            self._entries = [self._entry(label) for label in labels
                             if label.name.casefold() != 'unlabeled']
            current = current_label(project, annotation)
            current_name = annotation.label if annotation is not None else ''
            if current_name and current_name.casefold() != 'unlabeled':
                represented = any(entry['name'] == current_name for entry in self._entries)
                retired = (current is not None and
                           (project.label_is_deprecated(current)
                            if hasattr(project, 'label_is_deprecated') else current.deprecated))
                if not represented or retired or is_legacy_category(track.category):
                    self._entries = [entry for entry in self._entries if entry['name'] != current_name]
                    if current is not None and current.name == current_name:
                        entry = self._entry(current, current=True)
                    else:
                        entry = {
                            'name': current_name, 'id': annotation.label_id,
                            'aliases': [], 'zh': '', 'group': 'Current / legacy',
                            'definition': 'Current annotation text. It is retained exactly as saved; '
                                          'choose a listed label if you want to reclassify it.',
                            'boundary_rule': 'Review this interval against the available sources.',
                            'auto_mode': 'unmapped', 'auto_method': annotation.source,
                            'current': True, 'deprecated': False,
                        }
                    self._entries.insert(0, entry)
            suffix = ' · legacy type' if is_legacy_category(track.category) else ''
            primary_part = f' · {track.channel}' if track.category == 'Motion Primitive' else ''
            self.context.setText(f'{track.role}{primary_part} · {track.category}{suffix}')
            self.context.setToolTip(f'{track.role} / {track.workspace} / {track.category} / {track.name}')
        else:
            self.context.setText('Select an annotation track.')
            self.context.setToolTip('')
        self.configure_button.setEnabled(track is not None)
        self.search.setEnabled(track is not None)
        self._loading = False
        self._rebuild()

    def visible_label_names(self):
        """Visible leaf names, useful for keyboard integrations and QA."""
        result = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            result.extend(group.child(j).data(0, _NAME_ROLE)
                          for j in range(group.childCount()))
        return result

    def set_selected_label(self, name):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                item = group.child(j)
                if item.data(0, _NAME_ROLE) == name:
                    self.tree.setCurrentItem(item)
                    self.tree.scrollToItem(item)
                    return True
        return False

    def _rebuild(self, *_):
        if self._loading:
            return
        previous = self.tree.currentItem()
        previous_name = previous.data(0, _NAME_ROLE) if previous is not None else ''
        current_name = self.annotation.label if self.annotation is not None else previous_name
        query = self.search.text().strip().casefold()
        # Keep a record outside the active vocabulary visible while searching;
        # it must never look as though its historical text was silently mapped.
        filtered = [entry for entry in self._entries if entry['current'] or not query or query in ' '.join(
            [entry['name'], entry.get('display_name', entry['name']),
             entry['zh'], entry['group'], *entry['aliases']]).casefold()]
        if self.track is not None and self.track.category == 'Hand Behavior':
            group_order = {name: index for index, name in enumerate(HAND_MENU_GROUPS)}
            filtered.sort(key=lambda entry: -1 if entry['current'] else
                          group_order.get(entry['group'], len(group_order)))
        elif self.track is not None and self.track.category == 'Interaction Event':
            other = len(_INTERACTION_EVENT_LABEL_ORDER)
            filtered.sort(key=lambda entry: -1 if entry['current'] else
                          _INTERACTION_EVENT_LABEL_ORDER.get((entry['group'], entry['name']), other))
        blocker = QSignalBlocker(self.tree)
        self.tree.clear()
        groups = {}
        first = selected = None
        for entry in filtered:
            group_name = entry['group']
            if group_name not in groups:
                group = QTreeWidgetItem([group_name])
                group.setFlags(group.flags() & ~Qt.ItemIsSelectable)
                group.setFont(0, QFont(self.font().family(), 8, QFont.Bold))
                group.setForeground(0, Qt.darkGray)
                self.tree.addTopLevelItem(group)
                groups[group_name] = group
            item = QTreeWidgetItem([entry.get('display_name', entry['name'])])
            item.setData(0, _NAME_ROLE, entry['name'])
            item.setData(0, _ENTRY_ROLE, entry)
            tip = entry['definition'] or entry['name']
            if entry['zh']:
                tip = entry['zh'] + '\n' + tip
            item.setToolTip(0, tip)
            groups[group_name].addChild(item)
            first = first or item
            if entry['name'] == current_name:
                selected = item
        self.tree.expandAll()
        if selected is not None or first is not None:
            self.tree.setCurrentItem(selected or first)
            self.tree.scrollToItem(selected or first)
        del blocker
        self.add_button.setEnabled(self.track is not None and bool(self.search.text().strip()))
        count = f'{len(filtered)} of {len(self._entries)} labels' if query else f'{len(filtered)} labels'
        if self.track is None:
            self.hint.setText('Select a track to browse its label list.')
        elif self.annotation is None:
            point=category_info(self.track.category).get('temporal_kind')=='point'
            self.hint.setText(f'{count} · '+('Click a time point first.' if point else 'Select a proposal or drag an interval.'))
        else:
            self.hint.setText(f'{count} · Choose, then Accept below.')
        if not filtered and self.track is not None:
            self.hint.setText('No matching labels. Edit list or add a label.')
        self._selection_changed()

    def _selection_changed(self):
        item = self.tree.currentItem()
        entry = item.data(0, _ENTRY_ROLE) if item is not None else None
        if not entry:
            self.definition.clear()
            self.definition.setToolTip('')
            self.capability.clear()
            self.capability.setToolTip('')
            return
        definition = entry['definition'] or 'No definition is recorded for this label yet.'
        boundary = entry['boundary_rule'] or 'Review and set the interval boundaries for this event.'
        heading = entry['name'] + (f" · {entry['zh']}" if entry['zh'] else '')
        self.definition.setPlainText(f"{definition}\nTime boundaries: {boundary}")
        workflow=WORKFLOW_NAMES.get(entry.get('recommended_workflow'), 'Manual input / review')
        implementation=IMPLEMENTATION_NAMES.get(entry.get('implementation_status'), 'Unmapped label')
        capability=f'{workflow} · {implementation}'
        if entry['current'] or entry['deprecated']:
            capability = 'Current / legacy label. Original text is preserved.'
        self.capability.setText(capability)
        self.capability.setToolTip(f'{capability}\n{entry["auto_method"]}')
        self.definition.setToolTip(f"{heading}\n{capability}" +
                                   (f"\n{entry['auto_method']}" if entry['auto_method'] else ''))

    def _choose_item(self, item, _column=0):
        entry = item.data(0, _ENTRY_ROLE) if item is not None else None
        if not entry:
            return
        self._selection_changed()
        if self.annotation is None:
            point=bool(self.track and category_info(self.track.category).get('temporal_kind')=='point')
            self.hint.setText('Click a time point first. Preview only.' if point else 'Select a proposal or drag an interval. Preview only.')
            return
        self.labelChosen.emit(entry['name'])

    def _add_search_label(self):
        text = self.search.text().strip()
        if self.track is not None and text:
            self.addLabelRequested.emit(text)
