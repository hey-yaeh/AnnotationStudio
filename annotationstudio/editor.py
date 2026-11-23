"""The active interval editor lives directly BELOW the timeline."""
from copy import copy, deepcopy

from PySide6.QtCore import Qt, Signal, QSignalBlocker, QEvent
from PySide6.QtWidgets import (QFrame,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QLineEdit,
    QPushButton,QDoubleSpinBox,QCompleter,QSizePolicy,QToolButton,QMenu)
from .label_palette import eligible_labels, current_label
from .editing import motion_accept_error
from .models import label_search_aliases
from .ontology import ACTIVITY_EPISODE, RETIRED_PRIMITIVE_LABELS
from .object_registry import ObjectPicker
from .annotation_fields import (DIRECTED_CATEGORIES, PAIR_CATEGORIES,
    JUDGMENT_CATEGORIES, CERTAINTY_CHOICES, OUTCOME_CHOICES,
    EVIDENCE_ORIGIN_CHOICES, EVIDENCE_SOURCE_CHOICES, AFFECT_MODE_CHOICES,
    validate_annotation_fields, has_affect_rating, OBJECT_SPATIAL_CATEGORIES,
    OBJECT_DIRECTIONAL_LABELS, SPATIAL_REFERENCE_CHOICES, spatial_accept_error,
    spatial_label_name)
from .affect_display import (affect_adjective, DIMENSIONAL_AFFECT_LABEL_NAME,
    DIMENSIONAL_AFFECT_LABEL_ID)


class EvidencePicker(QToolButton):
    """Compact multiple selection; unknown recorded sources stay selectable."""
    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._actions = {}
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setMinimumWidth(155)
        self.setToolTip('Select the evidence actually used. Several sources may be selected.')
        self.set_sources([])

    def set_sources(self, sources):
        self._loading = True
        self._menu.clear(); self._actions = {}
        sources = list(sources) if isinstance(sources, (list, tuple)) else []
        known = dict(EVIDENCE_SOURCE_CHOICES)
        choices = [*EVIDENCE_SOURCE_CHOICES,
                   *((value, f'Recorded: {value}') for value in sources if value not in known)]
        for value, text in choices:
            if not isinstance(value, str) or value in self._actions:
                continue
            action = self._menu.addAction(text)
            action.setCheckable(True); action.setChecked(value in sources)
            action.toggled.connect(self._selection_changed)
            self._actions[value] = action
        self._menu.addSeparator()
        self._menu.addAction('Clear evidence selection', self.clear_selection)
        self._loading = False
        self._update_text()
        self.selectionChanged.emit()

    def selected_sources(self):
        return [value for value, action in self._actions.items() if action.isChecked()]

    def clear_selection(self):
        self._loading = True
        for action in self._actions.values():
            action.setChecked(False)
        self._loading = False
        self._selection_changed()

    def _update_text(self):
        count = len(self.selected_sources())
        self.setText(f'{count} evidence source' + ('s' if count != 1 else '')
                     if count else 'Choose evidence…')

    def _selection_changed(self, *_):
        if self._loading:
            return
        self._update_text(); self.selectionChanged.emit()


class SegmentEditor(QFrame):
    changed=Signal(dict)
    acceptClicked=Signal()
    cancelClicked=Signal()
    candidateClicked=Signal()
    addLabelClicked=Signal(str)
    splitClicked=Signal()
    mergeClicked=Signal()
    objectsRequested=Signal()

    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName('SegmentEditor')
        self._loading=False; self.current=None; self._field_dirty=set()
        self._project=None; self._dimensional_allowed=False
        self._adjective_selection=('', ''); self._label_options=[]
        self._object_dirty=set()
        self._syncing_height=False
        layout=QVBoxLayout(self); layout.setContentsMargins(13,6,13,6); layout.setSpacing(6)
        head=QHBoxLayout(); layout.addLayout(head)
        self.title=QLabel('SEGMENT EDITOR'); self.title.setObjectName('Subhead'); head.addWidget(self.title)
        self.context=QLabel('Click a block to edit, or drag an empty track to create a segment.'); self.context.setStyleSheet('color:#93816E;font-size:8pt;'); head.addWidget(self.context,1)
        self.source=QLabel(''); self.source.setStyleSheet('color:#9B8B77;font-size:8pt;'); head.addWidget(self.source)
        row=QHBoxLayout(); layout.addLayout(row)
        self.label_caption=QLabel('Label'); row.addWidget(self.label_caption)
        self.label=QComboBox(); self.label.setEditable(True); self.label.setInsertPolicy(QComboBox.NoInsert)
        self.label.setMinimumWidth(240); self.label.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); row.addWidget(self.label,1)
        self.label.lineEdit().setPlaceholderText('Search labels or type a custom label…')
        self.dimensional_summary=QLabel('Valence / Arousal rating')
        self.dimensional_summary.setVisible(False); row.addWidget(self.dimensional_summary,1)
        self.add_label=QPushButton('+ Label'); self.add_label.setToolTip('Add this text to the project label vocabulary.'); row.addWidget(self.add_label)
        row.addSpacing(12); self.start_label=QLabel('Start'); row.addWidget(self.start_label)
        self.start=self._spin(); row.addWidget(self.start)
        self.end_label=QLabel('End'); row.addWidget(self.end_label); self.end=self._spin(); row.addWidget(self.end)
        self.duration=QLabel('—'); self.duration.setMinimumWidth(65); self.duration.setStyleSheet('color:#8F785F;font-size:8pt;'); row.addWidget(self.duration)
        self.accept=QPushButton('✓  Accept'); self.accept.setObjectName('PrimaryButton'); self.accept.setMinimumWidth(98); row.addWidget(self.accept)
        self.cancel=QPushButton('Cancel'); row.addWidget(self.cancel)
        suggestions=QHBoxLayout(); layout.addLayout(suggestions)
        self.suggestion_label=QLabel('SUGGESTIONS'); self.suggestion_label.setObjectName('Subhead'); suggestions.addWidget(self.suggestion_label)
        self.chips=[]
        for _ in range(5):
            b=QPushButton(''); b.setObjectName('Chip'); b.setCheckable(True); b.setMaximumWidth(210)
            b.clicked.connect(lambda checked=False,b=b:self.choose_label(b.property('full_label') or b.text()))
            suggestions.addWidget(b); self.chips.append(b)
        suggestions.addStretch()
        self.candidate=QPushButton('Keep candidate'); self.candidate.setToolTip('Save an unfinished segment without accepting its label.'); suggestions.addWidget(self.candidate)
        self.split=QPushButton('Split'); suggestions.addWidget(self.split)
        self.merge=QPushButton('Merge next'); self.merge.setToolTip('Merge with the following event on the same track and label.'); suggestions.addWidget(self.merge)
        details=QHBoxLayout(); layout.addLayout(details)
        self.notes=QLineEdit(); self.notes.setPlaceholderText('Notes / uncertainty / boundary rationale…'); details.addWidget(self.notes,1)
        self.object_label=QLabel('Object'); details.addWidget(self.object_label)
        self.object_id=ObjectPicker(); self.object_id.setMinimumWidth(145); self.object_id.setMaximumWidth(225); details.addWidget(self.object_id)
        self.object_id.setToolTip('Choose a named object. Register a name with Objects…; a 3D model is not required.')
        self.secondary_object_label=QLabel('Object B'); details.addWidget(self.secondary_object_label)
        self.secondary_object_id=ObjectPicker(); self.secondary_object_id.setMinimumWidth(145)
        self.secondary_object_id.setMaximumWidth(225); details.addWidget(self.secondary_object_id)
        self.secondary_object_id.setToolTip('The second named object defining the space between. Choose a different object.')
        self.objects=QPushButton('Objects…'); self.objects.clicked.connect(self.objectsRequested); details.addWidget(self.objects)
        self.spatial_reference_label=QLabel('Reference'); details.addWidget(self.spatial_reference_label)
        self.spatial_reference=self._choice(SPATIAL_REFERENCE_CHOICES)
        self.spatial_reference.setMinimumContentsLength(16); self.spatial_reference.setMaximumWidth(180)
        self.spatial_reference.setToolTip('Use the object\'s own front/left/right, or fixed scene directions. Define the convention once in object or project notes; no 3D model is needed.')
        details.addWidget(self.spatial_reference)
        self.hand=QComboBox(); self.hand.addItems(['Unspecified hand','Left hand','Right hand','Both hands','Other body part',
            'Pelvis / seat','Back / torso','Left foot','Right foot','Both feet','Full body']); self.hand.setMaximumWidth(145); details.addWidget(self.hand)
        self.hand.setToolTip('Body part involved in the object action or sustained state.')
        self.target_label=QLabel('Target'); details.addWidget(self.target_label)
        self.target_role=QComboBox(); self.target_role.setMaximumWidth(110); details.addWidget(self.target_role)
        self.target_role.setToolTip('Who this action is directed toward. Unknown means the target is not established.')
        details.addWidget(QLabel('Reviewer'))
        self.reviewer=QLineEdit(); self.reviewer.setPlaceholderText('Your initials'); self.reviewer.setMaximumWidth(110); details.addWidget(self.reviewer)
        self.more_details=QToolButton(); self.more_details.setText('More details')
        self.more_details.setCheckable(True); self.more_details.setArrowType(Qt.RightArrow)
        self.more_details.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.more_details.setToolTip('Optional evidence, origin and judgment. Existing values are retained when hidden.')
        details.addWidget(self.more_details)
        self.domain_fields=QFrame(); domain=QHBoxLayout(self.domain_fields)
        domain.setContentsMargins(0,0,0,0); domain.setSpacing(8); layout.addWidget(self.domain_fields)
        self.affect_mode_label=QLabel('Mode'); domain.addWidget(self.affect_mode_label)
        self.affect_mode=self._choice(AFFECT_MODE_CHOICES)
        self.affect_mode.setMinimumContentsLength(20); domain.addWidget(self.affect_mode)
        self.intensity_label=QLabel('Intensity'); domain.addWidget(self.intensity_label)
        self.intensity=self._choice(((None,'Unknown'),(1,'1  Very weak'),(2,'2  Weak'),
                                    (3,'3  Moderate'),(4,'4  Strong'),(5,'5  Very strong')))
        self.intensity.setToolTip('Strength of the selected adjective; separate from activation (Arousal) and confidence.')
        domain.addWidget(self.intensity)
        self.valence_label=QLabel('Valence'); domain.addWidget(self.valence_label)
        self.valence=self._choice(((None,'Unknown'),(-2,'−2  Very negative'),(-1,'−1  Negative'),
                                   (0,'0  Near neutral'),(1,'+1  Positive'),(2,'+2  Very positive')))
        self.valence.setToolTip('Perceived positive/negative affect. Unknown is distinct from neutral (0).')
        domain.addWidget(self.valence)
        self.arousal_label=QLabel('Arousal'); domain.addWidget(self.arousal_label)
        self.arousal=self._choice(((None,'Unknown'),(1,'1  Very low'),(2,'2  Low'),
                                   (3,'3  Moderate'),(4,'4  High'),(5,'5  Very high')))
        self.arousal.setToolTip('Perceived activation. This is not body speed or a physiological measurement.')
        domain.addWidget(self.arousal)
        self.outcome_label=QLabel('Outcome'); domain.addWidget(self.outcome_label)
        self.physical_outcome=self._choice(OUTCOME_CHOICES); domain.addWidget(self.physical_outcome)
        self.physical_outcome.setMinimumContentsLength(18)
        self.physical_outcome.setToolTip('Record the observed result; an attempt does not imply completion.')
        self.judgment_label=QLabel('Judgment'); domain.addWidget(self.judgment_label)
        self.judgment_certainty=self._choice(CERTAINTY_CHOICES); domain.addWidget(self.judgment_certainty)
        self.judgment_certainty.setToolTip('Human certainty about the interpretation, separate from model score and review status.')
        domain.addStretch()
        self.evidence_fields=QFrame(); evidence=QHBoxLayout(self.evidence_fields)
        evidence.setContentsMargins(0,0,0,0); evidence.setSpacing(8); layout.addWidget(self.evidence_fields)
        evidence.addWidget(QLabel('Evidence'))
        self.evidence_sources=EvidencePicker(); evidence.addWidget(self.evidence_sources)
        evidence.addWidget(QLabel('Origin'))
        self.evidence_origin=self._choice(EVIDENCE_ORIGIN_CHOICES); evidence.addWidget(self.evidence_origin)
        self.evidence_origin.setMinimumContentsLength(22)
        self.evidence_origin.setToolTip('Keep observed expression, a scenario instruction, and participant report distinct. No origin is inferred automatically.')
        self.interpretation_hint=QLabel(); self.interpretation_hint.setWordWrap(True)
        self.interpretation_hint.setStyleSheet('color:#93816E;font-size:8pt;')
        evidence.addWidget(self.interpretation_hint,1)
        self._field_widgets={
            'valence':self.valence, 'arousal':self.arousal, 'intensity':self.intensity,
            'outcome':self.physical_outcome, 'certainty':self.judgment_certainty,
            'evidence_origin':self.evidence_origin,
        }
        for key, widget in self._field_widgets.items():
            widget.currentIndexChanged.connect(lambda _index,key=key:self._field_changed(key))
        self.evidence_sources.selectionChanged.connect(lambda:self._field_changed('evidence_sources'))
        self.label.currentTextChanged.connect(self._label_changed)
        self.label.activated.connect(lambda index:self.choose_label(
            self.label.itemData(index)[0] if self.label.itemData(index) else self.label.itemText(index)))
        self.label.lineEdit().editingFinished.connect(self._finish_label_edit)
        self.affect_mode.currentIndexChanged.connect(self._mode_changed)
        self.more_details.toggled.connect(self._toggle_details)
        self.start.valueChanged.connect(self._changed); self.end.valueChanged.connect(self._changed)
        self.notes.textChanged.connect(self._changed); self.reviewer.textChanged.connect(self._changed)
        self.object_id.currentTextChanged.connect(lambda:self._object_changed('object_id'))
        self.secondary_object_id.currentTextChanged.connect(lambda:self._object_changed('secondary_object_id'))
        self.spatial_reference.currentIndexChanged.connect(lambda:self._object_changed('reference_frame'))
        self.hand.currentIndexChanged.connect(self._changed)
        self.target_role.currentIndexChanged.connect(self._changed)
        self.accept.clicked.connect(self.acceptClicked); self.cancel.clicked.connect(self.cancelClicked)
        self.candidate.clicked.connect(self.candidateClicked)
        self.add_label.clicked.connect(lambda:self.addLabelClicked.emit(self._label_value()[0]))
        self.split.clicked.connect(self.splitClicked); self.merge.clicked.connect(self.mergeClicked)
        self.bind(None,None)

    @staticmethod
    def _spin():
        s=QDoubleSpinBox(); s.setRange(0,1e8); s.setDecimals(6); s.setSingleStep(1/120); s.setMinimumWidth(105); s.setMaximumWidth(115); return s

    def _sync_minimum_height(self):
        """Reserve actual styled row heights in the containing splitter.

        A fixed editor floor lets a short window compress every input row.
        The minimum must follow currently visible rows, and decrease again
        when the optional interpretation fields are hidden. Width remains
        controlled by the surrounding application layout.
        """
        if getattr(self,'_syncing_height',False) or not hasattr(self,'evidence_fields'):
            return
        self._syncing_height=True
        try:
            self.ensurePolished()
            # Qt already invalidates the layout when visibility, fonts or
            # styles change. Invalidating it again from LayoutRequest would
            # continually post more layout events and starve job completion.
            minimum=max(132,self.minimumSizeHint().height())
            if self.minimumHeight()!=minimum:
                self.setMinimumHeight(minimum)
                self.updateGeometry()
        finally:
            self._syncing_height=False

    def event(self,event):
        handled=super().event(event)
        if event.type() in (QEvent.LayoutRequest,QEvent.StyleChange,QEvent.FontChange):
            self._sync_minimum_height()
        return handled

    @staticmethod
    def _choice(choices):
        combo=QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(12)
        for value,text in choices:combo.addItem(text,value)
        return combo

    @staticmethod
    def _select_recorded(combo,value):
        # Remove values added by a previously bound record, then preserve the
        # current recorded value even when a newer vocabulary does not know it.
        for index in range(combo.count()-1,-1,-1):
            if combo.itemData(index,Qt.UserRole+1):combo.removeItem(index)
        index=combo.findData(value)
        if index<0:
            combo.addItem(f'Recorded: {value}',value); index=combo.count()-1
            combo.setItemData(index,True,Qt.UserRole+1)
        combo.setCurrentIndex(index)

    def _is_affect(self):
        return bool(self.current and self.current.category=='Perceived Affect')

    def _is_dimensional(self):
        return self._is_affect() and self.affect_mode.currentData()=='valence_arousal'

    def _is_object_spatial(self):
        return bool(self.current and self.current.category in OBJECT_SPATIAL_CATEGORIES)

    def _spatial_label_name(self):
        name,label_id=self._label_value()
        if not self._is_object_spatial() or self._project is None:return name
        prospective=copy(self.current); prospective.label=name; prospective.label_id=label_id
        return spatial_label_name(self._project,prospective)

    def _update_object_visibility(self):
        active=self.current is not None
        hoi=bool(active and self.current.category=='Action / HOI')
        activity=bool(active and self.current.category==ACTIVITY_EPISODE)
        spatial=self._is_object_spatial()
        name=self._spatial_label_name() if spatial else ''
        between=spatial and name=='between objects'
        directional=spatial and name in OBJECT_DIRECTIONAL_LABELS
        for widget in (self.object_label,self.object_id,self.objects):widget.setVisible(hoi or spatial or activity)
        self.object_label.setText('Optional object' if activity else ('Object A' if between else 'Object'))
        self.hand.setVisible(hoi)
        for widget in (self.secondary_object_label,self.secondary_object_id):widget.setVisible(between)
        for widget in (self.spatial_reference_label,self.spatial_reference):widget.setVisible(directional)
        self._sync_minimum_height()

    def _object_changed(self,key):
        if self._loading or self.current is None:return
        if self._is_object_spatial() or self.current.category == ACTIVITY_EPISODE:self._object_dirty.add(key)
        self._changed()

    def refresh_objects(self,project):
        """Refresh names without rebinding or discarding an unfinished draft."""
        self._project=project
        for picker in (self.object_id,self.secondary_object_id):
            picker.bind(project,picker.text())
        if self.current:
            point=getattr(self.current,'temporal_kind','interval')=='point'
            valid=self.start.value()>=0 and (point or self.end.value()>self.start.value())
            self.accept.setEnabled(valid and self._accepts_label())

    def _label_value(self):
        """Return authored name/ID, independently of the friendly adjective."""
        text=self.label.currentText().strip()
        index=self.label.currentIndex()
        data=self.label.itemData(index) if index>=0 else None
        if data and text==self.label.itemText(index):return tuple(data)
        for label in self._label_options:
            if text.casefold() in (label.name.casefold(), affect_adjective(label).casefold()):
                return label.name,label.id
        matches = self._primitive_alias_matches(text)
        if len(matches) == 1:
            return matches[0].name, matches[0].id
        return text,''

    def _primitive_alias_matches(self, text):
        if self.current is None or self.current.category != 'Motion Primitive':
            return []
        return [label for label in self._label_options
                if text.casefold() in (alias.casefold() for alias in label_search_aliases(label))]

    def _set_label_selection(self,name,label_id=''):
        with QSignalBlocker(self.label):
            for index in range(self.label.count()):
                data=self.label.itemData(index)
                if data and data[0]==name and (not label_id or data[1]==label_id):
                    self.label.setCurrentIndex(index); return
            # An authored/retired selection may be outside the track's current
            # menu. Keeping it inspectable does not widen the track whitelist.
            if label_id:
                label=self._project.get_label(label_id) if self._project else None
                display=affect_adjective(label) if self._is_affect() and label and label.name==name else name
                self.label.addItem(display,(name,label_id)); self.label.setCurrentIndex(self.label.count()-1)
            else:self.label.setEditText(name)

    def choose_label(self,name):
        """One mode-aware path for the palette, quick chips and typed labels."""
        if not self.current:return False
        text=str(name).strip(); selected=None
        for label in self._label_options:
            if text.casefold() in (label.name.casefold(),affect_adjective(label).casefold()):
                selected=label; break
        if selected is None:
            matches = self._primitive_alias_matches(text)
            if len(matches) == 1:
                selected = matches[0]
        name=selected.name if selected else text
        label_id=selected.id if selected else ''
        if self._is_affect():
            dimensional=(label_id==DIMENSIONAL_AFFECT_LABEL_ID or name==DIMENSIONAL_AFFECT_LABEL_NAME)
            if dimensional:
                if not self._dimensional_allowed:return False
                if not self._is_dimensional():
                    self.affect_mode.setCurrentIndex(self.affect_mode.findData('valence_arousal'))
                else:self._mode_changed()
                return True
            with QSignalBlocker(self.affect_mode):
                self.affect_mode.setCurrentIndex(self.affect_mode.findData('adjective_intensity'))
            self._adjective_selection=(name,label_id)
            self._field_dirty.add('annotation_mode')
            previous=self.current.attributes.get('affect',{})
            if 'adjective_label' in self._field_dirty or (isinstance(previous,dict) and previous.get('adjective_label')):
                self._field_dirty.add('adjective_label')
        self._set_label_selection(name,label_id)
        self._update_affect_visibility(); self._update_object_visibility(); self._changed()
        return True

    def _label_changed(self,*_):
        if self._loading or not self.current:return
        if self._is_affect():
            name,label_id=self._label_value()
            dimensional=(label_id==DIMENSIONAL_AFFECT_LABEL_ID or name==DIMENSIONAL_AFFECT_LABEL_NAME)
            if dimensional:
                self._changed(); return
            # Typing must not replace a matching prefix (joy -> Joyful) or
            # move the caret. Friendly display is applied only by an explicit
            # palette/menu/completer selection; canonical identity is a value.
            with QSignalBlocker(self.affect_mode):
                self.affect_mode.setCurrentIndex(self.affect_mode.findData('adjective_intensity'))
            self._adjective_selection=(name,label_id)
            self._field_dirty.add('annotation_mode')
            previous=self.current.attributes.get('affect',{})
            if 'adjective_label' in self._field_dirty or (isinstance(previous,dict) and previous.get('adjective_label')):
                self._field_dirty.add('adjective_label')
            self._update_affect_visibility()
        self._update_object_visibility(); self._changed()

    def _finish_label_edit(self):
        if self._loading or not self._is_affect():return
        name,label_id=self._label_value()
        resolved=self._project.resolve_label(name,'Perceived Affect')
        if label_id==DIMENSIONAL_AFFECT_LABEL_ID or (resolved and resolved.id==DIMENSIONAL_AFFECT_LABEL_ID):
            self.choose_label(resolved.name if resolved else name)

    def _mode_changed(self,*_):
        if self._loading or not self._is_affect():return
        if self._is_dimensional():
            if not self._dimensional_allowed:
                with QSignalBlocker(self.affect_mode):
                    self.affect_mode.setCurrentIndex(self.affect_mode.findData('adjective_intensity'))
                self._update_affect_visibility(); return
            name,label_id=self._label_value()
            if name and name.casefold()!='unlabeled' and label_id!=DIMENSIONAL_AFFECT_LABEL_ID and name!=DIMENSIONAL_AFFECT_LABEL_NAME:
                self._adjective_selection=(name,label_id)
            saved_name,saved_id=self._adjective_selection
            if saved_name and saved_name.casefold()!='unlabeled' and saved_id!=DIMENSIONAL_AFFECT_LABEL_ID:
                self._field_dirty.add('adjective_label')
            structural=self._project.get_label(DIMENSIONAL_AFFECT_LABEL_ID)
            self._set_label_selection(structural.name if structural else DIMENSIONAL_AFFECT_LABEL_NAME,
                                      DIMENSIONAL_AFFECT_LABEL_ID)
        else:
            name,label_id=self._label_value()
            if label_id==DIMENSIONAL_AFFECT_LABEL_ID or name==DIMENSIONAL_AFFECT_LABEL_NAME:
                name,label_id=self._adjective_selection
                restored=self._project.get_label(label_id) if label_id else None
                if restored is not None and restored.category=='Perceived Affect':name=restored.name
                self._set_label_selection(name or 'Unlabeled',label_id)
        self._field_dirty.add('annotation_mode')
        self._update_affect_visibility(); self._changed()

    def _toggle_details(self,*_):
        self.more_details.setArrowType(Qt.DownArrow if self.more_details.isChecked() else Qt.RightArrow)
        self._update_affect_visibility()

    def _update_affect_visibility(self):
        affect=self._is_affect(); dimensional=self._is_dimensional()
        judgment=bool(self.current and self.current.category in JUDGMENT_CATEGORIES)
        advanced=judgment and (not affect or self.more_details.isChecked())
        self.more_details.setVisible(affect)
        self.domain_fields.setVisible(judgment)
        for widget in (self.affect_mode_label,self.affect_mode):widget.setVisible(affect)
        for widget in (self.intensity_label,self.intensity):widget.setVisible(affect and not dimensional)
        for widget in (self.valence_label,self.valence,self.arousal_label,self.arousal):widget.setVisible(dimensional)
        for widget in (self.judgment_label,self.judgment_certainty):widget.setVisible(advanced)
        self.evidence_fields.setVisible(advanced)
        self.label_caption.setText('Adjective' if affect else 'Label')
        for widget in (self.label_caption,self.label,self.add_label):widget.setVisible(not dimensional)
        self.dimensional_summary.setVisible(dimensional)
        self.suggestion_label.setVisible(not dimensional)
        for chip in self.chips:
            chip.setVisible(bool(chip.property('full_label')) and not dimensional)
        self._sync_minimum_height()

    def _field_changed(self,key):
        if self._loading or self.current is None:return
        self._field_dirty.add(key)
        if key=='intensity' and self._is_affect():self._field_dirty.add('annotation_mode')
        self._update_interpretation_hint()
        self._changed()

    def _update_interpretation_hint(self):
        origin=self.evidence_origin.currentData()
        if origin=='scenario_prompt':
            text='Scenario information describes intended portrayal; it does not establish observed behavior.'
        elif origin=='participant_report':
            text='Participant report is retained as its own source, separate from observer judgments.'
        elif self.current and self.current.category=='Physical Interaction':
            text='Actor acts toward Target. A shared Both record does not identify who supports whom.'
        elif self.current and self.current.category=='Perceived Affect':
            text='Rate expressed affect; unknown ratings remain empty, not neutral.'
        else:
            text='Record the expressed content and its evidence, rather than an assumed internal belief.'
        self.interpretation_hint.setText(text)

    def bind(self,annotation,project):
        self._loading=True; self.current=annotation; self._field_dirty.clear(); self._object_dirty.clear()
        self._project=project; self._label_options=[]; self._adjective_selection=('', '')
        self._dimensional_allowed=False
        with QSignalBlocker(self.more_details):self.more_details.setChecked(False)
        self.more_details.setArrowType(Qt.RightArrow)
        active=annotation is not None
        activity=bool(active and annotation.category==ACTIVITY_EPISODE)
        self.notes.setPlaceholderText('Describe the activity briefly…' if activity else 'Notes / uncertainty / boundary rationale…')
        self.setProperty('active',active); self.style().unpolish(self); self.style().polish(self)
        for w in (self.label,self.start,self.end,self.accept,self.cancel,self.notes,self.reviewer,self.candidate,self.add_label,self.split,self.merge,self.object_id,self.secondary_object_id,self.spatial_reference,self.hand,self.target_role): w.setEnabled(active)
        for chip in self.chips:chip.setVisible(False); chip.setProperty('full_label','')
        point=bool(active and getattr(annotation,'temporal_kind','interval')=='point')
        self.start_label.setText('Time' if point else 'Start')
        self.end_label.setVisible(not point); self.end.setVisible(not point)
        self.split.setEnabled(active and not point); self.merge.setEnabled(active and not point)
        directed=bool(active and annotation.role in ('R01','R02') and annotation.category in DIRECTED_CATEGORIES)
        for w in (self.target_label,self.target_role):w.setVisible(directed)
        judgment=bool(active and annotation.category in JUDGMENT_CATEGORIES)
        affect=bool(active and annotation.category=='Perceived Affect')
        physical=bool(active and annotation.category=='Physical Interaction')
        for widget in (self.outcome_label,self.physical_outcome):widget.setVisible(physical)
        for widget in (*self._field_widgets.values(),self.evidence_sources):widget.setEnabled(judgment)
        self.affect_mode.setEnabled(affect)
        if not active:
            self.context.setText('Click a block to edit, or drag an empty track to create a segment.')
            self.source.clear(); self.label.clear(); self.notes.clear(); self.duration.setText('—'); self.title.setText('SEGMENT EDITOR')
            self.suggestion_label.setText('Labels, timing and notes are committed together when you accept.')
            self._update_affect_visibility()
            self._update_object_visibility()
            self._loading=False; self._sync_minimum_height(); return
        track=project.get_track(annotation.track_id)
        self.title.setText('EDITING POINT' if point else 'EDITING SEGMENT')
        self.context.setText(f'{annotation.role}  /  {track.name if track else annotation.channel}  /  {annotation.category}')
        evidence = (annotation.attributes or {}).get('primitive_evidence')
        if isinstance(evidence, dict) and 'onset_speed_deg_s' in evidence:
            hint = ('Torso-relative ' + str(evidence.get('axis', ''))
                    if evidence.get('rule') == 'torso_relative_head_rotation' else 'Adjacent-bone angle change')
            excursion = evidence.get('excursions_deg', evidence.get('excursion_deg', ''))
            original_label = (annotation.original or {}).get('label', annotation.label)
            self.source.setText(f'{annotation.source}  ·  BVH rule')
            self.source.setToolTip(f'Original proposal · {original_label}\n{hint}\nMeasured excursion (°) {excursion}')
        else:
            self.source.setText(annotation.source + (f'  ·  score {annotation.confidence:.2f}' if annotation.confidence is not None else ''))
            self.source.setToolTip('Model scores are not validated accuracy. Original prediction and edit history are retained.')
        labels=eligible_labels(project,track) if track else project.labels_for(annotation.category)
        self._dimensional_allowed=any(label.id==DIMENSIONAL_AFFECT_LABEL_ID for label in labels)
        saved_label=current_label(project,annotation)
        if saved_label is not None and all(l.id!=saved_label.id for l in labels):labels=[saved_label,*labels]
        if annotation.label_id==DIMENSIONAL_AFFECT_LABEL_ID:self._dimensional_allowed=True
        self._label_options=labels
        self.label.clear()
        for label in labels:
            self.label.addItem(affect_adjective(label) if affect else label.name,(label.name,label.id))
        self._set_label_selection(annotation.label,annotation.label_id)
        completions=list(dict.fromkeys([*(x.name for x in labels),
            *(affect_adjective(x) for x in labels if affect),
            *(alias for x in labels if annotation.category == 'Motion Primitive'
              for alias in label_search_aliases(x) if len(self._primitive_alias_matches(alias)) == 1)]))
        comp=QCompleter(completions,self.label); comp.setCaseSensitivity(Qt.CaseInsensitive); comp.setFilterMode(Qt.MatchContains); self.label.setCompleter(comp)
        comp.activated[str].connect(self.choose_label)
        self.start.setValue(annotation.start_s); self.end.setValue(annotation.end_s)
        self.duration.setText('Point' if point else f'{annotation.end_s-annotation.start_s:.3f}s')
        self.notes.setText(annotation.notes); self.reviewer.setText(annotation.reviewer)
        self.object_id.bind(project,str(annotation.attributes.get('object_id','')))
        spatial_values=annotation.attributes.get('spatial_relation',{})
        spatial_values=spatial_values if isinstance(spatial_values,dict) else {}
        self.secondary_object_id.bind(project,str(spatial_values.get('secondary_object_id','') or ''))
        self._select_recorded(self.spatial_reference,spatial_values.get('reference_frame'))
        effector=annotation.attributes.get('effector','Unspecified hand')
        if self.hand.findText(effector)<0:self.hand.addItem(effector)
        self.hand.setCurrentText(effector)
        self.target_role.clear()
        if directed:
            self.target_role.addItems(['Unknown',*[role for role in ('R01','R02') if role!=annotation.role]])
            target=annotation.attributes.get('target_role',track.extra.get('target_role','Unknown') if track else 'Unknown')
            self.target_role.setCurrentText(target if target in ('R01','R02') and target!=annotation.role else 'Unknown')
        if judgment:
            attrs=annotation.attributes
            human=attrs.get('human_judgment',{})
            affect_values=attrs.get('affect',{})
            physical_values=attrs.get('physical_interaction',{})
            human=human if isinstance(human,dict) else {}
            affect_values=affect_values if isinstance(affect_values,dict) else {}
            physical_values=physical_values if isinstance(physical_values,dict) else {}
            for combo,value in ((self.valence,affect_values.get('valence')),
                (self.arousal,affect_values.get('arousal')),
                (self.intensity,affect_values.get('intensity')),
                (self.physical_outcome,physical_values.get('outcome')),
                (self.judgment_certainty,human.get('certainty')),
                (self.evidence_origin,human.get('evidence_origin'))):
                self._select_recorded(combo,value)
            self.evidence_sources.set_sources(human.get('evidence_sources',[]))
            self._update_interpretation_hint()
            if affect:
                dimensional=(annotation.label_id==DIMENSIONAL_AFFECT_LABEL_ID or
                             annotation.label==DIMENSIONAL_AFFECT_LABEL_NAME)
                mode=affect_values.get('annotation_mode')
                if mode not in dict(AFFECT_MODE_CHOICES):
                    mode='valence_arousal' if dimensional else 'adjective_intensity'
                self.affect_mode.setCurrentIndex(self.affect_mode.findData(mode))
                if dimensional:
                    name=affect_values.get('adjective_label',''); label_id=affect_values.get('adjective_label_id','')
                    self._adjective_selection=(name if isinstance(name,str) else '',label_id if isinstance(label_id,str) else '')
                else:self._adjective_selection=(annotation.label,annotation.label_id)
                item=self.affect_mode.model().item(self.affect_mode.findData('valence_arousal'))
                item.setEnabled(self._dimensional_allowed)
                self.affect_mode.setToolTip('Choose one annotation mode. Hidden values are retained.' if self._dimensional_allowed else
                    'Valence / Arousal requires its rating label in this track\'s label list.')
        self.suggestion_label.setText('QUICK LABELS')
        names=[x.name for x in labels if x.name!='Unlabeled' and x.id!=DIMENSIONAL_AFFECT_LABEL_ID
               and not (x.category=='Motion Primitive' and x.name.casefold() in RETIRED_PRIMITIVE_LABELS)]
        # Prefer anatomically relevant arm suggestions, without restricting custom labels.
        if annotation.channel in ('Left Arm','Right Arm'):
            side=annotation.channel.split()[0].lower()
            names=sorted(names,key=lambda n: (side not in n.lower(),n != annotation.label))
        for b,name in zip(self.chips,names):
            label=next(x for x in labels if x.name==name)
            b.setText(affect_adjective(label) if affect else name); b.setProperty('full_label',name); b.setToolTip(name); b.setChecked(name==annotation.label); b.setVisible(True)
        valid=annotation.valid()
        self.accept.setEnabled(valid and self._accepts_label())
        self.candidate.setEnabled(valid)
        self._update_affect_visibility()
        self._update_object_visibility()
        self._loading=False
        self._sync_minimum_height()

    def update_span(self,start,end):
        point=bool(self.current and getattr(self.current,'temporal_kind','interval')=='point')
        self._loading=True; self.start.setValue(start); self.end.setValue(end); self.duration.setText('Point' if point else f'{end-start:.3f}s'); self._loading=False

    def values(self):
        name,label_id=self._label_value()
        values={'start_s':self.start.value(),'end_s':self.end.value(), 'label':name,'label_id':label_id,
                'notes':self.notes.text(),'reviewer':self.reviewer.text().strip()}
        if self.current:
            if getattr(self.current,'temporal_kind','interval')=='point':values['end_s']=values['start_s']
            attrs=deepcopy(self.current.attributes)
            if self.current.category=='Action / HOI':
                attrs.update(object_id=self.object_id.text().strip(),effector=self.hand.currentText()); values['attributes']=attrs
            if self.current.category == ACTIVITY_EPISODE and 'object_id' in self._object_dirty:
                object_id = self.object_id.text().strip()
                if object_id:
                    attrs['object_id'] = object_id
                else:
                    attrs.pop('object_id', None)
                values['attributes'] = attrs
            if self._is_object_spatial() and self._object_dirty:
                if 'object_id' in self._object_dirty:attrs['object_id']=self.object_id.text().strip()
                spatial_keys=self._object_dirty & {'secondary_object_id','reference_frame'}
                if spatial_keys:
                    spatial=attrs.get('spatial_relation',{})
                    spatial=deepcopy(spatial) if isinstance(spatial,dict) else {}
                    if 'secondary_object_id' in spatial_keys:spatial['secondary_object_id']=self.secondary_object_id.text().strip()
                    if 'reference_frame' in spatial_keys:spatial['reference_frame']=self.spatial_reference.currentData()
                    attrs['spatial_relation']=spatial
                if 'annotation_fields_version' not in attrs:
                    proposed={**attrs,'annotation_fields_version':1}
                    try:validate_annotation_fields(proposed)
                    except ValueError:pass
                    else:attrs['annotation_fields_version']=1
                values['attributes']=attrs
            if self.current.category in DIRECTED_CATEGORIES and self.current.role in ('R01','R02'):
                attrs['target_role']=self.target_role.currentText() or 'Unknown'
                values['attributes']=attrs
            elif self.current.category in DIRECTED_CATEGORIES|PAIR_CATEGORIES and self.current.role=='Both':
                attrs.pop('target_role',None)
                attrs['participants']=['R01','R02']
                values['attributes']=attrs
            if self.current.category in JUDGMENT_CATEGORIES and self._field_dirty:
                human_keys=self._field_dirty & {'certainty','evidence_origin','evidence_sources'}
                if human_keys:
                    human=attrs.get('human_judgment',{})
                    human=deepcopy(human) if isinstance(human,dict) else {}
                    for key in human_keys:
                        human[key]=(self.evidence_sources.selected_sources() if key=='evidence_sources'
                                    else self._field_widgets[key].currentData())
                    attrs['human_judgment']=human
                affect_keys=self._field_dirty & {'valence','arousal','intensity','annotation_mode','adjective_label'}
                if self.current.category=='Perceived Affect' and affect_keys:
                    affect=attrs.get('affect',{})
                    affect=deepcopy(affect) if isinstance(affect,dict) else {}
                    for key in affect_keys & {'valence','arousal','intensity'}:
                        affect[key]=self._field_widgets[key].currentData()
                    if 'annotation_mode' in affect_keys:affect['annotation_mode']=self.affect_mode.currentData()
                    if 'adjective_label' in affect_keys:
                        affect['adjective_label'],affect['adjective_label_id']=self._adjective_selection
                    attrs['affect']=affect
                if self.current.category=='Physical Interaction' and 'outcome' in self._field_dirty:
                    physical=attrs.get('physical_interaction',{})
                    physical=deepcopy(physical) if isinstance(physical,dict) else {}
                    physical['outcome']=self.physical_outcome.currentData()
                    attrs['physical_interaction']=physical
                if 'annotation_fields_version' not in attrs:
                    # A legacy payload may use another rating scale. Editing
                    # certainty must not silently reinterpret that whole
                    # payload as our ordinal v1 contract or block its save.
                    proposed={**attrs,'annotation_fields_version':1}
                    try:validate_annotation_fields(proposed)
                    except ValueError:pass
                    else:attrs['annotation_fields_version']=1
                values['attributes']=attrs
        return values

    def _accepts_label(self):
        name,label_id=self._label_value()
        if name.casefold() in ('','unlabeled'):return False
        if self.current.category == 'Motion Primitive':
            prospective = copy(self.current)
            prospective.label, prospective.label_id = name, label_id
            existing = next((a for a in self._project.annotations if a.id == prospective.id), None)
            error = motion_accept_error(prospective, existing)
            if not error and not label_id and len(self._primitive_alias_matches(name)) > 1:
                error = 'Choose one of the matching movement forms from the label list.'
            self.accept.setToolTip(error or 'Accept this annotation.')
            return not error
        if self._is_object_spatial():
            prospective=copy(self.current)
            for key,value in self.values().items():setattr(prospective,key,value)
            existing=next((a for a in self._project.annotations if a.id==prospective.id),None)
            error=spatial_accept_error(self._project,prospective,existing)
            self.accept.setToolTip(error or 'Accept this annotation.')
            return not error
        self.accept.setToolTip('Accept this annotation.')
        resolved=self._project.resolve_label(name,'Perceived Affect') if self._is_affect() else None
        if self._is_dimensional() or (self._is_affect() and
                (label_id==DIMENSIONAL_AFFECT_LABEL_ID or (resolved and resolved.id==DIMENSIONAL_AFFECT_LABEL_ID))):
            values=self.values()
            return has_affect_rating(values.get('attributes',self.current.attributes))
        return True

    def _changed(self,*_):
        if self._loading or not self.current:return
        point=getattr(self.current,'temporal_kind','interval')=='point'
        if point:
            with QSignalBlocker(self.end):self.end.setValue(self.start.value())
        self.duration.setText('Point' if point else f'{self.end.value()-self.start.value():.3f}s')
        valid=self.start.value()>=0 and (point or self.end.value()>self.start.value())
        self.accept.setEnabled(valid and self._accepts_label())
        self.candidate.setEnabled(valid)
        name,_=self._label_value()
        for b in self.chips:b.setChecked(b.property('full_label')==name)
        self.changed.emit(self.values())
