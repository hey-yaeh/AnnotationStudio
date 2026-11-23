"""Layered annotation vocabulary and separately stated automation capabilities.

Review status, recommended workflow and implemented detector capability are
independent. Legacy categories and labels remain addressable without relabelling
saved records. Physical state, object relation and social function are separate.
Gaze and facial-action annotations are retired from new track creation; synchronized
media and Oculo references remain usable as evidence.
"""

ACTIVITY_EPISODE = 'Activity Episode'
ACTIVITY_CHANNEL = 'Activity'
INTERACTION_EVENT_CORE_GROUPS = {
    'Core · Attention': ('attention getting',),
    'Core · Requests and offers': ('request', 'offer', 'request assistance', 'offer assistance'),
    'Core · Responses': ('acknowledgment', 'acceptance', 'refusal', 'agreement', 'disagreement'),
    'Core · Joint action': ('joint activity coordination', 'object handover'),
    'Core · Uncertainty': ('interaction uncertain',),
}
WORKSPACES = ('Overview', 'Activity', 'Motion', 'Gesture', 'HOI', 'Speech', 'Spatial', 'Social', 'Affect', 'Review')
WORKSPACE_CATEGORIES = {
    'Activity': (ACTIVITY_EPISODE,),
    'Motion': ('Motion Primitive', 'Body Posture', 'Hand Behavior', 'Locomotion', 'Activity Relation'),
    'Gesture': ('Gesture Type', 'Gesture Phase', 'Speech-Gesture Relation'),
    'HOI': ('Action / HOI',),
    'Affect': ('Perceived Affect',),
    'Speech': ('Speaking', 'Speech Turn', 'Turn Transition', 'Speech Timing', 'Vocal Event', 'Audio Activity', 'Dialogue Event'),
    'Spatial': ('Proxemic Movement', 'Spatial Configuration'),
    'Social': ('Interaction Event',),
    'Review': ('QC / Notes',),
}
WORKSPACE_CATEGORIES['Overview'] = tuple(
    category for categories in WORKSPACE_CATEGORIES.values() for category in categories
)
BODY_PARTS = ('Head', 'Torso', 'Left Arm', 'Right Arm', 'Left Hand',
              'Right Hand', 'Left Leg', 'Right Leg', 'Root', 'Full Body')
LEGACY_MOTION_RELATION = 'Activity Relation'
UNCLASSIFIED_MOTION = 'unclassified motion candidate'
COARSE_MOTION_LABELS = frozenset({
    'movement', 'local arm movement (meaning uncertain)', 'arm movement (meaning uncertain)',
    'head / neck movement', 'torso movement', 'left leg movement', 'right leg movement',
    'left hand / finger movement', 'right hand / finger movement', 'hand / finger movement',
    'whole-body movement', 'pelvis translation / locomotion candidate',
    'step / locomotion candidate', 'head nod candidate', 'head shake candidate',
})
FINE_PRIMITIVE_AUTO_METHODS = {
    'head rotation': 'BVH torso-relative, yaw-dominant turn. Review the label and boundaries.',
    'head nod': 'BVH torso-relative, pitch-dominant movement and return. Review the label and boundaries.',
    'head shake': 'BVH torso-relative, yaw-dominant movement and return. Review the label and boundaries.',
    **{f'{verb} {side} elbow': 'BVH upper-arm / forearm angle change, split at stops or reversals. Review the result.'
       for verb in ('flex', 'extend') for side in ('left', 'right')},
    **{f'{verb} {side} knee': 'BVH thigh / shank angle change, split at stops or reversals. Review the result.'
       for verb in ('bend', 'straighten') for side in ('left', 'right')},
}
MOTION_CANDIDATE_LABELS = COARSE_MOTION_LABELS | {
    UNCLASSIFIED_MOTION, 'raise → hold → lower (candidate)', 'raise → lower (candidate)',
    'bilateral arm co-activity (not classified)', 'bilateral arm co-activity',
}
RETIRED_PRIMITIVE_LABELS = MOTION_CANDIDATE_LABELS | {'hold', 'rest'}
LEGACY_CATEGORY_WORKSPACES = {
    'Gesture': 'Gesture', 'Emotion': 'Affect', 'Gaze / Attention': 'Gaze',
    'Facial Expression': 'Face', 'Speech / Dialogue': 'Speech',
    'Social Interaction': 'Social', LEGACY_MOTION_RELATION: 'Motion',
}
LEGACY_CATEGORIES = tuple(LEGACY_CATEGORY_WORKSPACES)

# Exact original 187 (category, label) entries; do not normalize spelling or case.
LEGACY_LABEL_PRESETS = {'Motion Primitive': ['Unlabeled',
                      'raise right arm',
                      'lower right arm',
                      'raise left arm',
                      'lower left arm',
                      'extend right elbow',
                      'extend left elbow',
                      'flex right elbow',
                      'flex left elbow',
                      'reach forward (kinematic)',
                      'retract arm',
                      'head rotation',
                      'head nod candidate',
                      'head shake candidate',
                      'torso lean',
                      'turn body',
                      'step / locomotion candidate',
                      'arm movement (meaning uncertain)',
                      'bilateral arm co-activity',
                      'movement',
                      'hold',
                      'rest'],
 'Body Posture': ['Unlabeled',
                  'standing',
                  'sitting',
                  'leaning forward',
                  'leaning backward',
                  'arms crossed',
                  'legs crossed',
                  'right leg over left',
                  'left leg over right',
                  'ankles crossed',
                  'hands on hips',
                  'hands in lap',
                  'posture transition',
                  'posture uncertain',
                  'not visible'],
 'Hand Behavior': ['Unlabeled',
                   'fingers interlaced',
                   'hands clasped',
                   'palms together',
                   'hand rubbing',
                   'finger tapping',
                   'thumb twiddling',
                   'self-touch',
                   'hand to face',
                   'hand to hair',
                   'hand resting',
                   'hand behavior uncertain',
                   'not visible'],
 'Locomotion': ['Unlabeled',
                'walking',
                'stepping',
                'turning in place',
                'weight shift',
                'sit down',
                'stand up',
                'stationary',
                'locomotion uncertain'],
 'Gesture': ['Unlabeled',
             'gesture (unclassified)',
             'co-speech gesture',
             'deictic / pointing gesture',
             'iconic gesture',
             'metaphoric gesture',
             'beat gesture',
             'emblem',
             'greeting wave',
             'gesture preparation',
             'gesture stroke',
             'gesture hold',
             'gesture retraction',
             'non-gesture movement',
             'not visible'],
 'Action / HOI': ['Unlabeled',
                  'reaching toward object',
                  'grasp object',
                  'pick up object',
                  'put down object',
                  'hold object',
                  'release object',
                  'push object',
                  'pull object',
                  'handover object',
                  'receive object',
                  'touch object',
                  'use object',
                  'move furniture',
                  'other action',
                  'contact uncertain',
                  'not visible'],
 'Facial Expression': ['Unlabeled',
                       'smile',
                       'laugh face',
                       'brow raise',
                       'brow furrow',
                       'mouth open',
                       'lip press',
                       'blink',
                       'squint',
                       'neutral expression',
                       'other facial action',
                       'face not visible',
                       'face occluded'],
 'Emotion': ['Unlabeled',
             'emotion uncertain',
             'neutral / no reliable cue',
             'positive affect candidate',
             'negative affect candidate',
             'amusement candidate',
             'frustration candidate',
             'surprise candidate',
             'valence continuous (see notes)',
             'arousal continuous (see notes)',
             'insufficient evidence'],
 'Gaze / Attention': ['Unlabeled',
                      'partner face',
                      'partner head non-face',
                      'partner left hand',
                      'partner right hand',
                      'object AOI',
                      'gaze aversion',
                      'attention shift',
                      'mutual gaze candidate',
                      'joint attention candidate',
                      'looking away',
                      'uncertain target',
                      'eyes not visible',
                      'missing gaze data'],
 'Speaking': ['Unlabeled',
              'Speaking',
              'Overlapping speech',
              'Speaker unknown',
              'Unintelligible speech'],
 'Vocal Event': ['Unlabeled',
                 'Laughter',
                 'Sigh',
                 'Gasp',
                 'Cough',
                 'Throat clearing',
                 'Sneeze',
                 'Sniff',
                 'Breathing',
                 'Crying',
                 'Other vocal event',
                 'Vocal event uncertain'],
 'Audio Activity': ['Unlabeled', 'Audio activity (energy)', 'Audio unavailable'],
 'Speech / Dialogue': ['Unlabeled',
                       'speaker turn',
                       'speech activity',
                       'vocal backchannel',
                       'interruption candidate',
                       'overlapping speech',
                       'laughter',
                       'sigh',
                       'gasp',
                       'cough',
                       'throat clearing',
                       'silence (reviewed)',
                       'turn-taking transition',
                       'other vocal event',
                       'unknown speaker'],
 'Social Interaction': ['Unlabeled',
                        'interaction candidate',
                        'co-active arms (not response)',
                        'response candidate',
                        'imitation candidate',
                        'turn exchange',
                        'joint attention candidate',
                        'handover candidate',
                        'approach',
                        'withdrawal',
                        'synchronous posture candidate',
                        'other interaction',
                        'interaction uncertain'],
 'QC / Notes': ['Unlabeled',
                'BVH fit anomaly',
                'synchronization issue',
                'occlusion',
                'missing modality',
                'low-confidence gaze',
                'coordinate mapping issue',
                'video glitch',
                'annotation ambiguity',
                'other QC issue']}

# These v0.3 interval labels were replaced by explicit turn / point-event types.
# Their original category/name identities remain available to old projects;
# loading does not move or reinterpret their saved interval boundaries.
LEGACY_LABEL_PRESETS['Dialogue Event'] = ['speaker turn', 'turn handover']

_CATEGORY_ROWS = [
    (ACTIVITY_EPISODE, 'An observable activity performed by one actor over a meaningful interval. Record a reusable activity name, an optional named object, and an optional description of how the activity was performed.', ACTIVITY_CHANNEL, 'single', 'video or direct observation of the activity', 'Start at the first action that constitutes the named activity. End when it stops or changes to a different activity.'),
    ('Motion Primitive', 'Observable movement form or maintained state of a body part; communicative meaning is recorded separately.', 'Right Arm', 'single', 'video / BVH kinematics', 'Start at the first clear departure from the preceding pose; end when the movement stops or its form changes. Split reversals for directional primitives; repeated movement patterns use their own bout boundaries. Do not include unrelated preparation or rest.'),
    ('Body Posture', 'A sustained body configuration. The historical broad posture transition entry is retained as a process, with its own boundary rule; specific transitions belong in Locomotion.', 'Full Body', 'single', 'video / BVH posture', 'Start when the stated configuration is established; end when it clearly ceases. Exclude the transition into and out of the posture.'),
    ('Hand Behavior', 'Visible hand arrangement, self-contact or repetitive hand action, without inferred social intent.', 'Hands', 'single', 'close video; BVH only if fingers/contact are supported', 'Start when the stated hand arrangement or action is visible; end when it breaks or changes. Split repeated bouts at a clear pause and use not visible for missing evidence.'),
    ('Locomotion', 'Whole-body displacement, stepping, weight transfer and transitions between standing, sitting, squatting and kneeling.', 'Root', 'single', 'video / root and lower-body kinematics', 'Start at the first clear locomotor movement or weight transfer; end when it stops or another locomotor pattern begins. Annotate stationary as a sustained state, not a missing detection.'),
    ('Gesture Type', 'A contextual interpretation of an observable communicative gesture; phase and speech relation are separate types.', 'Hands', 'single', 'video with conversation context', 'Mark one gesture unit from visible preparation through its final retraction, when present. Split independently interpretable gestures; do not extend a unit across an unrelated pause.'),
    ('Gesture Phase', 'Temporal components within a gesture unit: preparation, expressive stroke, hold and retraction.', 'Hands', 'single', 'video / BVH, interpreted within a gesture unit', 'Use the onset and offset of the particular phase, not the entire gesture unit. Boundaries must follow visible changes of phase; do not manufacture phases that are absent.'),
    ('Speech-Gesture Relation', 'Whether a gesture is coordinated with speech by the same actor; no listener role is assigned.', 'Hands', 'single', 'synchronized audio and video', 'Use the gesture unit as the interval and inspect the surrounding speech. Temporal overlap alone is not sufficient for a semantic relation.'),
    ('Action / HOI', 'Observable object actions and sustained contact or support relations; identify the body part and stable object instance separately.', 'Hands', 'single', 'video with visible object/contact; optional calibrated body and object geometry', 'For an action, mark the operation from onset to completion. For a state, mark the full maintained relation from establishment to separation or change. Speech boundaries do not split an otherwise continuous state.'),
    ('Perceived Affect', 'A cautious observer impression from multimodal context, not a verified internal emotion or a facial-action classifier.', 'Emotion', 'single', 'multimodal context reviewed by a human', 'Mark only the interval with supporting cues. End when the impression changes or evidence becomes insufficient; record the cues and uncertainty in notes.'),
    ('Speaking', 'Audible speech activity and speech-quality qualifiers for an assigned actor or an unknown speaker.', 'Speech', 'either', 'audio; video may help assign an actor', 'Start at audible speech onset and end at speech offset. Keep overlaps where both actors are audible; do not assign an identity or listener status from silence.'),
    ('Speech Turn', 'An actor-specific conversational turn that may include short internal pauses; automatic grouping is a candidate based on attributed speech.', 'Speech', 'single', 'attributed speech intervals, audio and conversation context', 'Begin at the first contribution taking or claiming the turn; end when the turn is yielded or abandoned. Preserve a turn across its internal pauses and verified backchannels where supported by context.'),
    ('Turn Transition', 'A timestamped speaker-change candidate or reviewed floor-transfer relation, linked to the contributing turns when available.', 'Speech', 'either', 'source speech turns and conversational context', 'Place a point at the incoming contribution onset under this project convention. Preserve the outgoing end and source turn IDs separately; a point does not claim a measurable transition duration.'),
    ('Speech Timing', 'Positive-duration timing intervals derived from speech or turn boundaries; derived timing does not by itself establish conversational function.', 'Speech', 'either', 'attributed speech intervals and source turn intervals', 'Use the exact intersection or gap between the relevant source boundaries. Do not inflate zero-duration boundaries into spans; use a Turn Transition point for a boundary event.'),
    ('Vocal Event', 'Audible non-lexical vocal sounds, independent of dialogue function or inferred emotion.', 'Speech', 'either', 'audio', 'Start at the first audible part of the vocal event and end at its acoustic offset. Review short model windows by listening; do not include the surrounding silence.'),
    ('Audio Activity', 'Signal-energy activity or unavailable audio; this type does not classify speech or vocal events.', 'Speech', 'either', 'audio / waveform', 'Mark the interval of audible or detected activity, or the interval with missing usable audio. An energy event may contain noise rather than human vocalization.'),
    ('Dialogue Event', 'Contextual turn-taking actions and conversational functions, separate from acoustic sound classes.', 'Speech', 'either', 'audio and conversational context', 'Mark the utterance or brief exchange that performs the function. For directed events, assign initiator and target only when supported by context.'),
    ('Proxemic Movement', 'Actor-specific changes in distance or body orientation relative to a partner; no social intention is implied.', 'Root', 'single', 'video / calibrated root and torso motion', 'Start when the selected actor clearly begins the relative translation or turn; end when it stops or reverses. Pair distance alone cannot identify which actor moved.'),
    ('Spatial Configuration', 'A sustained relative position and body-facing arrangement of the pair, separate from movement and interaction function.', 'Dyadic', 'pair', 'video / calibrated positions and body orientation', 'Start when the arrangement is established; end when either participant changes it. Use a consistent project-specific orientation tolerance; do not infer eye gaze from body facing.'),
    ('Activity Relation', 'Observable temporal or postural relation between two actors without automatic inference of response, imitation or social function.', 'Dyadic', 'pair', 'synchronized video / two-actor kinematics', 'Mark the interval in which the stated relation is supported in both actors. Record the comparison and any lag/tolerance in notes; simultaneity alone is not synchrony or imitation.'),
    ('Interaction Event', 'A social action or exchange supported by context, distinct from proximity, simultaneous movement and dialogue acoustics.', 'Dyadic', 'either', 'multimodal interaction context', 'Start at the first action constituting the event; end when it resolves or clearly ceases. Separate initiative and response when actor direction matters; record target and supporting cues.'),
    ('QC / Notes', 'Data quality, visibility, alignment and annotation issues; these are not observed participant behaviors.', 'Notes', 'either', 'all available modalities / project metadata', 'Mark the interval affected by the problem. Start when evidence becomes unreliable and end when it recovers; describe the affected modality and uncertainty in notes.'),
]
CATEGORY_INFO = {name: dict(description=description, default_channel=channel,
                           actor_scope=scope, evidence_mode=evidence,
                           boundary_rule=boundary)
                 for name, description, channel, scope, evidence, boundary in _CATEGORY_ROWS}

# These fields describe intended use, not whether an arbitrary label already has
# a trained classifier. Label-level overrides below refine the category defaults.
_CATEGORY_POLICIES = {
    ACTIVITY_EPISODE: ('manual_primary', 'manual', 'activity_episode'),
    'Motion Primitive': ('automatic_primary', 'planned_rule', 'motion'),
    'Body Posture': ('automatic_primary', 'planned_rule', 'state'),
    'Hand Behavior': ('assisted', 'planned_model', 'body_behavior'),
    'Locomotion': ('automatic_primary', 'planned_rule', 'motion'),
    'Activity Relation': ('automatic_derived', 'planned_rule', 'physical_relation'),
    'Gesture Type': ('manual_primary', 'manual', 'communicative_function'),
    'Gesture Phase': ('assisted', 'planned_model', 'gesture_phase'),
    'Speech-Gesture Relation': ('manual_primary', 'manual', 'communicative_relation'),
    'Action / HOI': ('assisted', 'planned_model', 'object_action'),
    'Perceived Affect': ('manual_primary', 'manual', 'interpretation'),
    'Speaking': ('automatic_primary', 'optional_model', 'speech_activity'),
    'Speech Turn': ('automatic_primary', 'builtin', 'turn'),
    'Turn Transition': ('automatic_derived', 'builtin', 'temporal_relation'),
    'Speech Timing': ('automatic_derived', 'builtin', 'timing'),
    'Vocal Event': ('automatic_primary', 'optional_model', 'vocal_event'),
    'Audio Activity': ('automatic_derived', 'builtin', 'signal_activity'),
    'Dialogue Event': ('manual_primary', 'manual', 'conversational_function'),
    'Proxemic Movement': ('automatic_primary', 'planned_rule', 'spatial_motion'),
    'Spatial Configuration': ('automatic_primary', 'planned_rule', 'spatial_state'),
    'Interaction Event': ('manual_primary', 'manual', 'social_function'),
    'QC / Notes': ('assisted', 'planned_rule', 'quality_issue'),
}
for _category, (_workflow, _implementation, _semantic) in _CATEGORY_POLICIES.items():
    CATEGORY_INFO[_category].update(
        recommended_workflow=_workflow, implementation_status=_implementation,
        temporal_kind='point' if _category == 'Turn Transition' else 'interval',
        semantic_kind=_semantic,
    )
LABEL_PRESETS = {category: [] for category in WORKSPACE_CATEGORIES['Overview']}
LABEL_INFO = {}


def _add(category, name, zh, description, *, group='Other', parts=(),
         rule=None, auto_mode='manual', auto_method='', evidence=None, aliases=(),
         recommended_workflow=None, implementation_status=None, semantic_kind=None):
    if name in LABEL_PRESETS[category]:
        raise ValueError(f'Duplicate label: {category} / {name}')
    LABEL_PRESETS[category].append(name)
    LABEL_INFO[(category, name)] = {
        'description': description,
        'boundary_rule': rule or CATEGORY_INFO[category]['boundary_rule'],
        'zh': zh, 'group': group, 'body_parts': list(parts),
        'auto_mode': auto_mode, 'auto_method': auto_method,
        'evidence_mode': evidence or CATEGORY_INFO[category]['evidence_mode'],
        'aliases': list(aliases),
        'recommended_workflow': recommended_workflow or CATEGORY_INFO[category]['recommended_workflow'],
        'implementation_status': implementation_status or (
            'builtin' if auto_mode == 'builtin_candidate' else
            'optional_model' if auto_mode == 'optional_model' else
            CATEGORY_INFO[category]['implementation_status']),
        'temporal_kind': CATEGORY_INFO[category]['temporal_kind'],
        'semantic_kind': semantic_kind or CATEGORY_INFO[category]['semantic_kind'],
    }


def _rows(category, group, parts, rows):
    for row in rows:
        name, zh, description, *boundary = row
        _add(category, name, zh, description, group=group, parts=parts,
             rule=boundary[0] if boundary else None)


for _category in LABEL_PRESETS:
    _add(_category, 'Unlabeled', '未选择标签',
         'An unfinished annotation with no semantic label selected; it does not mean the behavior is absent.',
         group='Uncertainty', rule='Keep the provisional interval or point while editing. Choose a meaningful label, including a specific uncertainty label where appropriate, before Accept.',
         recommended_workflow='manual_primary', implementation_status='manual', semantic_kind='placeholder')


def category_workspace(category: str) -> str:
    for workspace, categories in WORKSPACE_CATEGORIES.items():
        if workspace != 'Overview' and category in categories:
            return workspace
    return LEGACY_CATEGORY_WORKSPACES.get(category, 'Review')


def is_legacy_category(category: str) -> bool:
    return category in LEGACY_CATEGORIES


def is_motion_candidate(category, name):
    return category == 'Motion Primitive' and str(name).strip().casefold() in MOTION_CANDIDATE_LABELS


def interaction_event_menu_group(name, saved_group):
    """Update former preset groups for display while retaining authored group names."""
    previous_group = _INTERACTION_EVENT_PREVIOUS_GROUPS.get(name)
    if previous_group is not None and saved_group == previous_group:
        return LABEL_INFO['Interaction Event', name]['group']
    return saved_group


def category_info(category: str) -> dict:
    info = dict(CATEGORY_INFO.get(category, {
        'description': 'Legacy or project-defined type. Keep its original interpretation and review project notes before editing.',
        'default_channel': 'Notes', 'actor_scope': 'either',
        'evidence_mode': 'original annotation and project notes',
        'boundary_rule': 'Preserve the original interval unless evidence supports an explicit human edit.',
        'recommended_workflow': 'manual_primary', 'implementation_status': 'manual',
        'temporal_kind': 'interval', 'semantic_kind': 'legacy_or_custom',
    }))
    info['workspace'] = category_workspace(category)
    info['legacy'] = is_legacy_category(category)
    return info


def label_spec(category: str, name: str) -> dict:
    info = LABEL_INFO.get((category, name))
    if info is None:
        legacy = name in LEGACY_LABEL_PRESETS.get(category, ())
        info = {
            'description': ('Preserved historical label: ' if legacy else 'Project-defined label: ') + name + '. Consult the original project definition; no automatic semantic conversion is applied.',
            'boundary_rule': 'Preserve the original interval unless review provides evidence for an explicit edit. Document any interpretation change in notes.',
            'zh': name, 'group': 'Legacy' if legacy else 'Project labels',
            'body_parts': [], 'auto_mode': 'manual', 'auto_method': '',
            'evidence_mode': 'original annotation and project notes', 'aliases': [],
            'recommended_workflow': 'manual_primary', 'implementation_status': 'manual',
            'temporal_kind': 'interval', 'semantic_kind': 'legacy_or_custom',
        }
    result = dict(info)
    result['body_parts'] = list(result.get('body_parts', ()))
    result['aliases'] = list(result.get('aliases', ()))
    return result


WORKFLOWS = {
    'Activity': ('R01', ACTIVITY_CHANNEL, 'L2 · Action / Gesture', ACTIVITY_EPISODE),
    'Motion': ('R01', 'Right Arm', 'L1 · Kinematics', 'Motion Primitive'),
    'Gesture': ('R01', 'Hands', 'L2 · Action / Gesture', 'Gesture Type'),
    'HOI': ('R01', 'Hands', 'L2 · Action / Gesture', 'Action / HOI'),
    'Affect': ('R01', 'Emotion', 'L2 · Action / Gesture', 'Perceived Affect'),
    'Speech': ('R01', 'Speech', 'L2 · Action / Gesture', 'Speaking'),
    'Spatial': ('R01', 'Root', 'L1 · Kinematics', 'Proxemic Movement'),
    'Social': ('R01', 'Dyadic', 'L3 · Interaction', 'Interaction Event'),
    'Review': ('Scene', 'Notes', 'QC / Notes', 'QC / Notes'),
}

# Active, grouped choices follow. Exact automatic-output names are retained
# where an existing module already emits them; review status remains independent.

_add(ACTIVITY_EPISODE, 'push cart', '推车',
     'The actor visibly pushes a wheeled cart. Record posture, direction or other observable details in the description.',
     group='Object activities', aliases=('pushing cart', 'push trolley', '推车', '推手推车'),
     rule='Start when the actor begins pushing the cart. End when the push stops or the actor changes to another activity.')

for _side, _zh_side, _part in [('right', '右', 'Right Arm'), ('left', '左', 'Left Arm')]:
    for _verb, _zh_verb, _direction in [('raise', '抬起', 'upward'), ('lower', '放下', 'downward')]:
        _add('Motion Primitive', f'{_verb} {_side} arm', f'{_zh_verb}{_zh_side}臂',
             f'The {_side} arm moves {_direction} relative to the torso; this describes movement, not communicative function.',
             group='Arm movement', parts=[_part], auto_mode='builtin_candidate',
             auto_method='Graph / Velocity candidates with arm-height change heuristic; human boundary and meaning review required.')
    _rows('Motion Primitive', 'Arm movement', [_part], [
        (f'extend {_side} elbow', f'伸展{_zh_side}肘', f'The {_side} elbow straightens; distinguish elbow extension from translation of the entire arm.'),
        (f'flex {_side} elbow', f'弯曲{_zh_side}肘', f'The {_side} elbow bends; distinguish elbow flexion from translation of the entire arm.'),
    ])
_rows('Motion Primitive', 'Arm movement', ['Left Arm', 'Right Arm'], [
    ('reach forward (kinematic)', '向前伸出（运动学）', 'An arm extends forward relative to the torso; an object target or intention is not implied.'),
    ('retract arm', '收回手臂', 'An arm moves back toward the body or its preceding resting region; a gesture phase is recorded separately.'),
])
for _side, _zh_side in [('right', '右'), ('left', '左')]:
    _add('Motion Primitive', f'wave {_side} hand (kinematic)', f'{_zh_side}手往复挥动（运动学）',
         f'The {_side} hand shows an observable back-and-forth waving pattern in position or orientation, '
         'with alternating sweeps and direction reversals. The wrist, forearm or whole arm may contribute. '
         'This describes movement form only; greeting, farewell, refusal or intended recipient are not inferred.',
         group='Hand waving', parts=[f'{_side.title()} Hand', f'{_side.title()} Arm'],
         rule='Start at the first sweep belonging to the observed back-and-forth bout; end at the last sweep '
              'before a clear stop or change of movement form. A single unidirectional reach is not this pattern. '
              'Choose the primary observed moving part (hand or same-side arm) for one annotation; do not '
              'duplicate the same bout merely because both parts participate.',
         recommended_workflow='automatic_primary', implementation_status='planned_rule',
         auto_method='No waving detector is implemented in this release. A future rule may use body-relative '
                     'hand trajectory/orientation and repeated reversals with explicit amplitude, duration and '
                     'repetition criteria. Current generic arm/hand movement proposals do not classify waving.',
         aliases=[f'waving {_side} hand', f'{_side} hand wave', f'{_zh_side}手挥动', f'{_zh_side}手摆动'])
_rows('Motion Primitive', 'Head movement', ['Head'], [
    ('head rotation', '头部转动', 'A visible head orientation change that is not assigned a more specific nod or shake pattern; no gaze target is inferred.'),
    ('head nod', '点头运动', 'A visible head pitch movement or repeated vertical oscillation; agreement and acknowledgment require separate contextual evidence.'),
    ('head shake', '摇头运动', 'A visible head yaw movement or repeated lateral oscillation; disagreement and refusal are not implied.'),
])
_rows('Motion Primitive', 'Torso movement', ['Torso', 'Root'], [
    ('torso lean', '躯干倾斜运动', 'The torso changes inclination; mark the movement rather than the subsequent sustained leaning posture.'),
    ('turn body', '身体转向', 'The torso or whole body changes heading; a turn toward another person is a separate proxemic interpretation.'),
])
# A finite finer-grained vocabulary complements existing broad movement labels.
# Left/right in a direction is actor-relative. Unqualified limb names take their
# anatomical side from the selected track; no duplicate left/right labels are added.
for _name, _zh, _description, _aliases in [
    ('head flexion', '头部前屈',
     'The head pitches forward relative to the upper torso or neck, such as lowering the chin. '
     'This directional movement is separate from a repeated nod and does not identify an eye-gaze target.',
     ['lower head', 'bend head forward', '低头过程']),
    ('head extension', '头部后伸',
     'The head pitches backward relative to the upper torso or neck, including returning from a flexed '
     'position. This movement does not establish eye gaze or a subsequently held head posture.',
     ['raise head', 'extend neck', '抬头过程']),
    ('turn head left', '向左转头',
     'The head changes yaw toward the actor left relative to the torso. Whole-body turning with the '
     'head fixed to the torso is insufficient, and eye gaze is not inferred.',
     ['head rotation left', '左转头']),
    ('turn head right', '向右转头',
     'The head changes yaw toward the actor right relative to the torso. Whole-body turning with the '
     'head fixed to the torso is insufficient, and eye gaze is not inferred.',
     ['head rotation right', '右转头']),
    ('tilt head left', '头部向左侧倾',
     'The head bends laterally toward the actor left shoulder relative to the torso; distinguish this '
     'from yaw rotation or camera tilt. Eye gaze is not inferred.',
     ['head lateral flexion left', '左侧歪头过程']),
    ('tilt head right', '头部向右侧倾',
     'The head bends laterally toward the actor right shoulder relative to the torso; distinguish this '
     'from yaw rotation or camera tilt. Eye gaze is not inferred.',
     ['head lateral flexion right', '右侧歪头过程']),
]:
    _add('Motion Primitive', _name, _zh, _description, group='Head movement', parts=['Head'],
         rule='Mark the directional head movement from its first clear departure until it stops or reverses. '
              'Use actor-relative head-to-torso orientation, not screen direction; exclude the subsequent '
              'held posture. Use the broad head label when the direction cannot be resolved.',
         auto_method='No directional head-motion detector is implemented in this release. A future rule '
                     'requires validated head/torso axes and movement thresholds; broad head activity is '
                     'not this classification.', aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('bend torso forward', '躯干向前弯曲',
     'The torso inclines or bends forward relative to the pelvis and actor anatomical frame. '
     'This is the movement into flexion, not a maintained forward-leaning posture.', ['torso flexion', 'bend forward']),
    ('straighten torso', '躯干回正',
     'The torso moves from a visibly bent or leaned configuration toward a more upright, aligned '
     'configuration relative to the pelvis. The prior bend and the subsequent held posture remain separate.',
     ['return torso upright', 'straighten back', '躯干恢复直立']),
    ('lean torso backward', '躯干向后倾',
     'The torso moves into a backward inclination relative to the pelvis and actor anatomical frame. '
     'This is motion toward a back lean, not the subsequent maintained posture.', ['bend torso backward', '后仰过程']),
    ('bend torso left', '躯干向左侧弯',
     'The torso bends laterally toward the actor left relative to the pelvis. Distinguish lateral '
     'bending from axial rotation or translation of the whole body.', ['torso lateral flexion left', '向左弯腰']),
    ('bend torso right', '躯干向右侧弯',
     'The torso bends laterally toward the actor right relative to the pelvis. Distinguish lateral '
     'bending from axial rotation or translation of the whole body.', ['torso lateral flexion right', '向右弯腰']),
    ('rotate torso left', '躯干向左扭转',
     'The upper torso rotates toward the actor left relative to the pelvis. A whole body heading '
     'change with no torso-pelvis twist is recorded with a broader turning label.', ['torso rotation left', '向左扭身']),
    ('rotate torso right', '躯干向右扭转',
     'The upper torso rotates toward the actor right relative to the pelvis. A whole body heading '
     'change with no torso-pelvis twist is recorded with a broader turning label.', ['torso rotation right', '向右扭身']),
]:
    _add('Motion Primitive', _name, _zh, _description, group='Torso movement', parts=['Torso', 'Root'],
         rule='Start at the first clear torso movement of the selected form; end when it stops, reverses '
              'or changes form. Judge direction relative to the actor pelvis and calibrated body axes, '
              'not the camera. Exclude the maintained posture; choose a broader torso label if axes are unreliable.',
         auto_method='No fine torso-motion detector is implemented in this release. A future rule needs '
                     'validated torso/pelvis orientation and temporal thresholds; generic torso activity '
                     'does not classify a bend or twist.', aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('move arm outward', '手臂向外展开',
     'The selected upper arm moves laterally away from the torso in the actor body frame. '
     'Elbow extension moving only the hand outward is insufficient for this shoulder-level form.',
     ['arm abduction', 'spread arm', '手臂外展']),
    ('move arm inward', '手臂向内收拢',
     'The selected upper arm moves back toward the torso or body midline from a lateral position. '
     'Elbow flexion without this upper-arm change is insufficient.',
     ['arm adduction', 'bring arm inward', '手臂内收']),
]:
    _add('Motion Primitive', _name, _zh, _description, group='Arm movement', parts=['Left Arm', 'Right Arm'],
         rule='Select the moving arm track. Start at the first lateral upper-arm change and end when it '
              'stops or reverses; exclude the held end position. Use actor-relative direction, and do not '
              'duplicate the same movement under a broad arm label when a specific label is sufficient.',
         auto_method='No arm outward/inward detector is implemented in this release. A future rule needs '
                     'validated shoulder, upper-arm and torso geometry; current arm activity is not this classification.',
         aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('open hand', '张开手',
     'The selected hand changes from a more closed or curled configuration toward visibly unfolded '
     'digits. This is a shape-change process; it does not by itself prove release of an object.',
     ['hand opening', 'unclench hand', '张手']),
    ('close hand', '闭合手',
     'The selected hand changes toward curled or closed digits. A full fist is not required, and '
     'the movement alone does not establish a grasp or contact with an object.',
     ['hand closing', 'clench hand', '合手指']),
    ('flex wrist', '手腕屈曲',
     'The hand bends at the wrist toward its palm side relative to the forearm. Translation or '
     'rotation of the whole forearm without this wrist-angle change is insufficient.',
     ['wrist flexion', 'bend wrist', '屈腕']),
    ('extend wrist', '手腕伸展',
     'The hand bends at the wrist toward its back-of-hand side relative to the forearm, including '
     'returning from wrist flexion. Whole-forearm movement alone is insufficient.',
     ['wrist extension', '伸腕']),
]:
    _add('Motion Primitive', _name, _zh, _description, group='Hand and wrist movement',
         parts=['Left Hand', 'Right Hand'],
         rule='Select the moving hand track. Start at the first clear hand-shape or wrist-angle change '
              'of the specified form; end when it stops or reverses. Exclude the maintained configuration. '
              'Use sufficiently detailed video or validated finger/wrist joints; a wrist-position trace alone is insufficient.',
         evidence='close video or validated finger / wrist / forearm kinematics',
         auto_method='No hand-opening/closing or wrist flexion/extension detector is implemented in this release. '
                     'Finger shape or wrist orientation requires reliable corresponding joint data; coarse hand '
                     'movement does not classify these forms.', aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('raise leg', '抬腿（粗运动）',
     'The selected leg visibly lifts upward from its previous level in an actor-centred frame with a '
     'known up direction. The joint mechanism is unspecified: this coarse form does not establish hip '
     'flexion or knee extension. Whole-body upward translation alone is insufficient.',
     ['leg lift', 'lift leg', 'raising leg', '抬起腿']),
    ('lower leg', '放下腿（粗运动）',
     'The selected leg visibly moves down from a raised level toward a lower position relative to '
     'the actor. The joint mechanism is unspecified; movement of the entire body alone is insufficient.',
     ['leg lowering', 'lowering leg', '放腿']),
    ('hip flexion', '髋关节屈曲',
     'The selected thigh moves anteriorly relative to the pelvis through hip flexion. Knee bend may '
     'change independently. This is a joint-specific form, not any upward movement of the leg or foot.',
     ['raise thigh', 'thigh raise', 'lift thigh', 'hip flexion movement', '抬大腿', '屈髋']),
    ('hip extension', '髋关节伸展',
     'The selected thigh moves posteriorly relative to the pelvis, including returning from a flexed '
     'hip toward neutral. This does not mean knee straightening or generic lowering of the leg.',
     ['thigh extension', 'extend hip', '伸髋']),
    ('move leg outward', '腿向外展开',
     'The selected thigh or leg moves laterally away from the actor midline relative to the pelvis. '
     'Distinguish this hip-level outward form from whole-body translation or rotation of the camera.',
     ['hip abduction', 'leg abduction', '腿外展']),
    ('move leg inward', '腿向内收拢',
     'The selected thigh or leg moves toward the actor midline relative to the pelvis from a lateral '
     'position. The movement need not end in contact with the other leg.',
     ['hip adduction', 'leg adduction', '腿内收']),
]:
    _add('Motion Primitive', _name, _zh, _description, group='Leg movement', parts=['Left Leg', 'Right Leg'],
         rule='Select the moving leg track. Start at the first clear movement of the specified form; end '
              'when it stops or reverses. Exclude the maintained end posture. Use actor-relative pelvis/leg '
              'geometry; select the most specific supported label instead of duplicating its broad alternative.',
         auto_method='No leg-lift, hip flexion/extension or outward/inward leg detector is implemented in '
                     'this release. Future rules require validated pelvis/leg axes and joint geometry; '
                     'existing coarse leg activity cannot establish the mechanism.', aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('move legs apart', '分开双腿（过程）',
     'The spatial separation of the legs increases through movement of one or both legs. This coarse '
     'bilateral pattern does not establish a front split, middle split, pure hip abduction or contact.',
     ['split legs', 'split leg', 'spread legs', 'separate legs', '分腿']),
    ('bring legs together', '并拢双腿（过程）',
     'The spatial separation of the legs decreases through movement of one or both legs. Contact '
     'between legs is not required, and the maintained legs-together posture is a separate state.',
     ['close legs', 'join legs', '并腿']),
]:
    _add('Motion Primitive', _name, _zh, _description, group='Leg movement patterns',
         parts=['Full Body', 'Left Leg', 'Right Leg'],
         rule='Use Full Body for the combined bilateral observation, or the primarily moving leg when '
              'only that side is being analysed. Mark separation change from onset to cessation. Do not '
              'duplicate the same bout on both legs and Full Body; do not include the held configuration.',
         auto_method='No bilateral leg-separation detector is implemented in this release. A future rule '
                     'may measure validated body-relative leg separation, but cannot infer a split posture '
                     'from separation alone.', aliases=_aliases)
for _side, _zh_side in [('right', '右'), ('left', '左')]:
    for _verb, _zh_verb, _joint_action in [('bend', '弯曲', 'flexion'), ('straighten', '伸直', 'extension')]:
        _add('Motion Primitive', f'{_verb} {_side} knee', f'{_zh_verb}{_zh_side}膝',
             f'The {_side} knee undergoes {_joint_action}, changing the relative angle of the thigh and shank. '
             'Translation or rotation of the entire leg without this knee-angle change is insufficient. '
             'This local joint movement may occur within a larger action such as squatting or kicking.',
             group='Knee movement', parts=[f'{_side.title()} Leg'],
             rule=f'Start at the first clear {_joint_action} of the selected knee; end when it stops or reverses. '
                  'Exclude a subsequent held bent or straight position. Use a valid hip-knee-ankle mapping or '
                  'visible joint movement, not a raw Euler-channel sign or whole-leg displacement.',
             evidence='visible knee movement or validated hip / knee / ankle kinematics',
             recommended_workflow='automatic_primary',
             aliases=[f'{_verb} knee', f'{_side} knee {_joint_action}', f'knee {_joint_action}',
                      f'{_zh_side}膝' + ('屈曲' if _verb == 'bend' else '伸展')])
    _add('Motion Primitive', f'kick {_side} leg (kinematic)', f'{_zh_side}腿踢动（运动学）',
         f'The {_side} leg or foot makes a distinct projecting swing or thrust. This is a coarser movement '
         'pattern that may combine hip and knee motion, not a strictly atomic joint primitive. '
         'A target, contact, aggression or communicative intention is not inferred; ordinary stepping '
         'or undifferentiated leg motion is insufficient.',
         group='Leg movement patterns', parts=[f'{_side.title()} Leg'],
         rule='Start at the first movement belonging to the distinct projecting bout; end when the thrust '
              'and any immediately connected retraction finish. Split separate kicks at a clear pause or '
              'new bout. Do not extend the event through a subsequently held leg posture.',
         recommended_workflow='automatic_primary', implementation_status='planned_rule',
         auto_method='No kicking detector is implemented in this release. A future kinematic rule needs '
                     'body-relative leg/foot trajectory and validated joint motion; coarse leg activity is '
                     'not a kicking classification and cannot establish an object strike.',
         aliases=[f'kick {_side} leg', f'kicking {_side} leg', f'{_side} leg kick', 'kick', f'{_zh_side}腿踢腿'])
for _name, _zh, _description, _boundary, _aliases in [
    ('cross legs', '交叉双腿（过程）',
     'One or both legs move across the other leg into a crossed arrangement. This is the crossing movement, '
     'not the maintained legs-crossed posture or an ordinary passing of the legs during walking.',
     'Start when the moving leg departs toward the crossing; end when the crossed arrangement is established '
     'or the crossing movement clearly stops.', ['cross leg', 'crossing legs', 'leg crossing', '翘腿过程', '交叉腿']),
    ('uncross legs', '解开双腿交叉（过程）',
     'One or both legs move out of an established crossed arrangement. This is the release movement, '
     'not the subsequent uncrossed posture.',
     'Start when a leg leaves the established crossed arrangement; end when the uncrossing movement stops '
     'or reaches the next maintained posture.', ['uncross leg', 'uncrossing legs', 'leg uncrossing', '放开交叉腿']),
]:
    _add('Motion Primitive', _name, _zh, _description, group='Leg movement patterns',
         parts=['Left Leg', 'Right Leg'],
         rule=_boundary + ' Select the primarily moving leg. Do not duplicate the same bout on both leg '
              'tracks merely because both legs define the relation; use Full Body for a combined observation when appropriate.',
         recommended_workflow='automatic_primary', implementation_status='planned_rule',
         auto_method='No leg crossing/uncrossing detector is implemented in this release. A future rule requires '
                     'body-relative leg trajectories and configuration evidence. Existing leg activity '
                     'does not establish crossing, sustained posture or physical contact.', aliases=_aliases)
for _name, _zh, _parts, _desc in [
    ('local arm movement (meaning uncertain)', '局部手臂运动（含义不确定）', ['Left Arm', 'Right Arm'], 'Movement of the selected arm whose form or meaning is not classified.'),
    ('head / neck movement', '头颈运动', ['Head'], 'Movement in the head or neck region without a specific nod, shake or rotation classification.'),
    ('torso movement', '躯干运动', ['Torso'], 'Movement in the torso region without a more specific movement classification.'),
    ('left leg movement', '左腿运动', ['Left Leg'], 'Movement of the left leg without a specific stepping or locomotion interpretation.'),
    ('right leg movement', '右腿运动', ['Right Leg'], 'Movement of the right leg without a specific stepping or locomotion interpretation.'),
    ('left hand / finger movement', '左手或手指运动', ['Left Hand'], 'Movement of the left hand or fingers without a specific configuration or contact interpretation.'),
    ('right hand / finger movement', '右手或手指运动', ['Right Hand'], 'Movement of the right hand or fingers without a specific configuration or contact interpretation.'),
    ('hand / finger movement', '手或手指运动', ['Left Hand', 'Right Hand'], 'Movement of a hand or fingers where laterality is unspecified by the output.'),
    ('whole-body movement', '全身运动', ['Full Body'], 'Broad movement involving the body without a classified action or social meaning.'),
    ('pelvis translation / locomotion candidate', '骨盆平移／位移候选', ['Root'], 'Root or pelvis translation proposed from kinematics; walking, stepping and actor intent remain unclassified.'),
]:
    _add('Motion Primitive', _name, _zh, _desc, group='Broad movement', parts=_parts,
         auto_mode='builtin_candidate', auto_method='Graph / Velocity region activity proposal; selected body-part mapping and BVH quality affect the output.')
for _name, _zh, _desc, _rule in [
    ('raise → hold → lower (candidate)', '抬起—保持—放下序列候选', 'A proposed arm sequence containing a raise, a quiet high-pose interval and a lowering movement; a quiet signal is not proof of a deliberate hold.', 'Mark the sequence from raise onset to lower offset. Inspect the proposed hold against the visible pose; annotate individual movements separately when that detail is needed.'),
    ('raise → lower (candidate)', '抬起—放下序列候选', 'A proposed arm raise followed by lowering without a confirmed intervening hold.', 'Mark the sequence from raise onset to lower offset. Split the component phases onto separate tracks if the task requires phase-level timing.'),
    ('bilateral arm co-activity (not classified)', '双臂共同活动（未分类）', 'Both arms of the same actor are active in overlapping time; this is not a two-person interaction label.', 'Mark only the interval or proposed group containing activity in both arms. Check the actual overlap and do not infer symmetry or coordination from timing alone.'),
]:
    _add('Motion Primitive', _name, _zh, _desc, group='Motion sequences', parts=['Left Arm', 'Right Arm'],
         rule=_rule, auto_mode='builtin_candidate', auto_method='Phase structure proposal from earlier movement candidates; human sequence review required.')
_rows('Motion Primitive', 'Other', ['Full Body'], [
    ('movement', '运动（未细分）', 'Visible movement is present but a more specific movement form is not selected.'),
])
_rows('Motion Primitive', 'Stillness', ['Full Body'], [
    ('hold', '保持姿势', 'A visibly maintained pose after or between movements; low velocity alone does not establish a hold.', 'Start when the pose is established and maintained; end at the first clear departure. Exclude the approach and release movements.'),
    ('rest', '休止', 'The selected body part visibly remains in a resting configuration; missing detections do not establish rest.', 'Start when the resting configuration is established; end when the body part begins a new movement. Do not fill unreviewed gaps automatically.'),
])
_add('Motion Primitive', 'not visible', '不可见', 'The relevant body part cannot be assessed from the available evidence.', group='Uncertainty',
     rule='Mark only the period with unusable visibility or kinematics; stop when sufficient evidence resumes.')

_rows('Body Posture', 'Whole-body posture', ['Full Body'], [
    ('standing', '站立', 'The actor maintains an upright posture supported primarily by the feet.'),
    ('sitting', '坐姿', 'The actor maintains a seated posture with support under the pelvis.'),
])
_add('Body Posture', 'squatting', '蹲姿',
     'The actor maintains a lowered body configuration with flexed hips and knees and support primarily '
     'through the feet. Distinguish it from seated or kneeling support; the movement into or out of the '
     'configuration is a separate transition.', group='Whole-body posture',
     parts=['Root', 'Full Body', 'Left Leg', 'Right Leg'],
     rule='Start when the squat configuration is established and maintained; end when the actor clearly '
          'leaves it. Exclude lowering into the squat and rising from it. Use posture uncertain when '
          'support or configuration cannot be distinguished.',
     auto_method='No squatting-posture detector is implemented in this release. A future rule needs '
                 'validated lower-body joint geometry and support evidence; root height alone is insufficient.',
     aliases=['squat posture', 'squat', 'squatted posture', '蹲着'])
_add('Body Posture', 'kneeling', '跪姿',
     'The actor maintains a posture with one or both knees visibly contacting a support surface in a '
     'kneeling support configuration. Knee-to-floor proximity in BVH alone does not establish contact, '
     'support or force. Record uncertainty when the support relation is not observable.',
     group='Whole-body posture', parts=['Root', 'Full Body', 'Left Leg', 'Right Leg'],
     recommended_workflow='assisted', implementation_status='planned_rule',
     rule='Start when the kneeling configuration and knee support/contact are established; end when that '
          'configuration ceases. Exclude kneeling down and rising. If knee contact is occluded or unsupported '
          'by reliable evidence, use posture uncertain rather than assuming contact from joint height.',
     evidence='video showing knee/support relation; BVH geometry alone cannot establish contact',
     auto_method='No kneeling-posture detector is implemented in this release. A future rule may propose '
                 'candidates from validated lower-body geometry; visible or independently established '
                 'knee support/contact must be checked, without inferring force.',
     aliases=['kneel posture', 'kneel', 'one-knee kneeling', 'two-knee kneeling', '跪着'])
for _name, _zh, _description, _aliases in [
    ('lying', '躺卧姿态',
     'The actor maintains a recumbent configuration with the torso broadly supported rather than '
     'upright. Use this broad label when lying is clear but the more specific supported body side is '
     'not classified. Sleeping, comfort and the identity of a support object are not inferred.',
     ['lie', 'lying down posture', 'recumbent posture', '躺着']),
    ('lying supine', '仰卧',
     'The actor maintains a lying posture with the back side of the torso facing the support surface '
     'and the front side facing away. Judge body orientation relative to support, not the camera; '
     'do not infer sleep.', ['supine', 'lying on back', '平躺朝上']),
    ('lying prone', '俯卧',
     'The actor maintains a lying posture with the front side of the torso facing the support surface. '
     'Head rotation can differ and is recorded separately; do not infer sleep or discomfort.',
     ['prone', 'lying on stomach', '趴着']),
    ('lying on left side', '左侧卧',
     'The actor maintains a lying posture with the left side of the trunk toward the supporting '
     'surface. Left is anatomical, not screen-left; use the broad lying label if the supported side '
     'is not observable.', ['left side lying', 'left lateral lying', '左侧躺']),
    ('lying on right side', '右侧卧',
     'The actor maintains a lying posture with the right side of the trunk toward the supporting '
     'surface. Right is anatomical, not screen-right; use the broad lying label if the supported '
     'side is not observable.', ['right side lying', 'right lateral lying', '右侧躺']),
]:
    _add('Body Posture', _name, _zh, _description, group='Lying posture',
         parts=['Full Body', 'Root', 'Torso'], recommended_workflow='assisted',
         implementation_status='planned_rule',
         rule='Start when the maintained lying configuration is established; end when it ceases or '
              'changes to a different classified orientation. Exclude lying down, getting up and rolling '
              'transitions. Prefer a supported specific lying label over also recording generic lying '
              'for the same phenomenon. The identified support object belongs in HOI.',
         evidence='video showing recumbent body configuration and support; calibrated body geometry as an aid',
         auto_method='No lying-posture detector is implemented in this release. A future geometry rule '
                     'can propose candidates, but support/orientation evidence must be reviewed; low root '
                     'height alone does not establish lying.', aliases=_aliases)
_add('Body Posture', 'half-kneeling', '半跪姿',
     'The actor maintains one knee on a support surface while the opposite leg is placed forward with '
     'its foot on a support surface. This specific kneeling configuration requires observable knee '
     'and foot support relations; low joint height alone is insufficient.',
     group='Whole-body posture', parts=['Full Body', 'Root', 'Left Leg', 'Right Leg'],
     recommended_workflow='assisted', implementation_status='planned_rule',
     rule='Start when the one-knee/other-foot configuration is established; end when it changes. Exclude '
          'the transition into or out of the posture. Prefer this specific label over generic kneeling '
          'for the same configuration; record the grounded knee side in the track or notes when known.',
     evidence='visible knee and opposite-foot support relations; validated geometry may aid review',
     auto_method='No half-kneeling detector is implemented in this release. Geometry can only suggest '
                 'the configuration; reliable contact/support evidence is needed and forces are not measured.',
     aliases=['half kneeling', 'one knee forward posture', '单膝半跪'])
for _side, _zh_side in [('left', '左'), ('right', '右')]:
    _add('Body Posture', f'standing on {_side} leg', f'{_zh_side}腿单腿站立',
         f'The actor maintains an upright posture with primary foot support through the {_side} leg '
         'while the other foot is visibly off the supporting surface. Additional hand or object support '
         'may be recorded separately; balance ability, load and force are not inferred.',
         group='Whole-body posture', parts=['Full Body', 'Root', f'{_side.title()} Leg'],
         recommended_workflow='assisted', implementation_status='planned_rule',
         rule='Start when the single-leg standing configuration is established; end when it changes or '
              'the other foot returns to support. Exclude weight-transfer transitions. Prefer this '
              'specific posture over also recording generic standing for the same phenomenon.',
         evidence='video showing foot/support relationship; calibrated whole-body geometry as an aid',
         auto_method='No single-leg-standing detector is implemented in this release. A future rule '
                     'requires posture and foot/support evidence; foot height alone cannot determine '
                     'actual load bearing.', aliases=[f'stand on {_side} leg', f'{_side} single-leg stance', f'{_zh_side}脚单脚站立'])
for _name, _zh, _description, _aliases in [
    ('legs apart', '双腿分开姿态',
     'The actor maintains visibly separated legs relative to the pelvis under the project spacing '
     'criterion. This broad configuration can occur while sitting or standing and does not establish '
     'a front split, middle split or a particular social meaning.', ['legs spread posture', '双腿张开']),
    ('legs together', '双腿并拢姿态',
     'The actor maintains the legs close together relative to the pelvis under the project spacing '
     'criterion. Physical contact is not required or inferred; this describes configuration rather '
     'than the movement of bringing the legs together.', ['legs closed posture', '双腿合拢']),
]:
    _add('Body Posture', _name, _zh, _description, group='Leg posture',
         parts=['Full Body', 'Left Leg', 'Right Leg'],
         rule='Start when the specified spacing configuration is established and maintained; end when '
              'it changes. Exclude the separating or closing motion. Use a consistent body-scaled '
              'spacing criterion, not image pixel distance; choose a specific split label when supported.',
         auto_method='No leg-spacing posture detector is implemented in this release. A future rule '
                     'requires calibrated body-relative configuration and project-specific spacing criteria.',
         aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('front split', '前后劈叉姿态',
     'The actor maintains a low split configuration with one leg extended forward and the other '
     'backward relative to the pelvis, approaching opposed alignment in the actor sagittal plane. '
     'Ordinary separated legs, a step or a bent-knee lunge are insufficient; do not infer flexibility '
     'limits or support force.', ['front splits', 'sagittal split', '纵叉', '前后叉']),
    ('middle split', '左右横叉姿态',
     'The actor maintains a low split configuration with both legs extended laterally to opposite '
     'sides of the pelvis, approaching opposed alignment in the actor frontal plane. An ordinary '
     'wide stance or separated seated knees are insufficient; do not infer flexibility limits or force.',
     ['side split', 'middle splits', 'straddle split', '横叉']),
]:
    _add('Body Posture', _name, _zh, _description, group='Leg posture',
         parts=['Full Body', 'Root', 'Left Leg', 'Right Leg'],
         rule='Start when the specified maintained split configuration is established; end when it '
              'ceases. Exclude entering or leaving the split. Apply the project-defined hip/knee geometry '
              'tolerance; if only leg separation is supported, use legs apart rather than claiming a split.',
         auto_method='No front/middle-split posture detector is implemented in this release. A future rule '
                     'requires reliable pelvis/leg geometry, knee configuration and explicit posture '
                     'criteria; leg distance alone is insufficient.', aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('head upright', '头部中立保持',
     'The head remains near neutral alignment relative to the upper torso without a marked forward/back '
     'tilt, lateral tilt or turn under the project tolerance. This body-relative state does not determine '
     'world-vertical orientation or eye gaze.', ['neutral head posture', 'head neutral', '头部回正姿态']),
    ('head lowered', '低头保持',
     'The head remains flexed forward relative to the upper torso. This is a maintained configuration '
     'after head flexion; it does not establish looking downward or attention to an object.', ['head down posture', '低着头']),
    ('head tilted back', '头部后仰保持',
     'The head remains extended backward relative to the upper torso. It does not establish upward '
     'eye gaze, attention or a particular emotion.', ['head back posture', '仰头保持']),
    ('head turned left', '头部左转保持',
     'The head remains yawed toward the actor left relative to the torso. A gaze target or recipient '
     'is not inferred from this head orientation.', ['head facing left posture', '头朝左保持']),
    ('head turned right', '头部右转保持',
     'The head remains yawed toward the actor right relative to the torso. A gaze target or recipient '
     'is not inferred from this head orientation.', ['head facing right posture', '头朝右保持']),
    ('head tilted left', '头部左倾保持',
     'The head remains laterally inclined toward the actor left shoulder relative to the torso, '
     'distinct from yaw rotation. Eye gaze and affect are not inferred.', ['head left tilt posture', '头向左歪保持']),
    ('head tilted right', '头部右倾保持',
     'The head remains laterally inclined toward the actor right shoulder relative to the torso, '
     'distinct from yaw rotation. Eye gaze and affect are not inferred.', ['head right tilt posture', '头向右歪保持']),
]:
    _add('Body Posture', _name, _zh, _description, group='Head posture', parts=['Head'],
         rule='Start when the head configuration is established and maintained; end when it leaves '
              'the project-defined orientation tolerance. Exclude the movement into and out of it. '
              'Judge head-to-torso axes in the actor frame, not camera direction; do not infer gaze.',
         auto_method='No specific head-posture detector is implemented in this release. A future rule '
                     'requires validated head/torso axes and an explicit sustained-orientation tolerance.',
         aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('torso upright', '躯干中立保持',
     'The torso remains near neutral alignment relative to the pelvis without marked forward, backward '
     'or lateral lean or axial twist under the project tolerance. This does not by itself classify '
     'standing, sitting or lying.', ['torso neutral', 'upright torso', '躯干回正姿态']),
    ('torso leaned left', '躯干左倾保持',
     'The torso remains laterally bent toward the actor left relative to the pelvis. This is maintained '
     'inclination, not motion or body translation.', ['torso left lean', '身体左侧倾']),
    ('torso leaned right', '躯干右倾保持',
     'The torso remains laterally bent toward the actor right relative to the pelvis. This is maintained '
     'inclination, not motion or body translation.', ['torso right lean', '身体右侧倾']),
    ('torso rotated left', '躯干左扭保持',
     'The upper torso remains rotated toward the actor left relative to the pelvis. Whole-body '
     'heading alone does not establish this twist.', ['torso left twist posture', '躯干向左扭转保持']),
    ('torso rotated right', '躯干右扭保持',
     'The upper torso remains rotated toward the actor right relative to the pelvis. Whole-body '
     'heading alone does not establish this twist.', ['torso right twist posture', '躯干向右扭转保持']),
]:
    _add('Body Posture', _name, _zh, _description, group='Torso posture', parts=['Torso', 'Root'],
         rule='Start when the torso configuration is established and maintained; end when it leaves '
              'the project orientation tolerance. Exclude the bending, straightening or rotation '
              'process. Judge upper-torso orientation relative to the pelvis, not the camera.',
         auto_method='No specific torso-posture detector is implemented in this release. A future rule '
                     'requires validated torso/pelvis geometry and sustained-configuration criteria.',
         aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('arm raised', '手臂抬起保持',
     'The selected arm remains elevated relative to its torso reference under the project criterion. '
     'This is a held arm configuration, not the raising movement or a communicative gesture.',
     ['raised arm posture', 'arm held up', '举臂保持']),
    ('arm extended forward', '手臂前伸保持',
     'The selected arm remains projected forward relative to the torso. The elbow may be partly bent; '
     'full elbow extension, pointing intent and an object target are not implied.',
     ['forward arm posture', 'arm held forward', '伸臂保持']),
    ('arm hanging down', '手臂自然下垂姿态',
     'The selected arm remains alongside the torso toward the lower body in a non-elevated alignment. '
     'The label describes body-relative configuration without inferring relaxation, muscle activity '
     'or absence of support.', ['arm down posture', 'arm by side', '垂臂']),
    ('elbow bent', '屈肘保持',
     'The selected elbow remains flexed, with a maintained angle between upper arm and forearm under '
     'the project criterion. Arm position and hand target are separate attributes.',
     ['bent elbow posture', 'flexed elbow', '弯肘姿态']),
    ('elbow straight', '肘伸直保持',
     'The selected upper arm and forearm remain near straight alignment at the elbow under the project '
     'tolerance. Do not require exact zero flexion or infer force or joint locking.',
     ['straight elbow posture', 'extended elbow', '直肘姿态']),
]:
    _add('Body Posture', _name, _zh, _description, group='Arm posture', parts=['Left Arm', 'Right Arm'],
         rule='Select the relevant arm track. Start when the stated arm or elbow configuration is '
              'established and maintained; end when it changes. Exclude movement into or out of it. '
              'Use validated body-relative geometry and choose the level of detail required by the study.',
         auto_method='No specific arm/elbow-posture detector is implemented in this release. A future '
                     'rule requires valid shoulder/elbow/wrist mapping and explicit posture tolerances; '
                     'a quiet motion signal alone does not classify the pose.', aliases=_aliases)
for _name, _zh, _description, _aliases in [
    ('leg raised', '抬腿保持',
     'The selected leg remains visibly lifted relative to the actor pelvis and known up direction. '
     'This maintained coarse configuration does not determine which joint created it, whether the '
     'leg is externally supported or whether the actor stands on the other leg.',
     ['raised leg posture', 'leg held up', '举腿保持']),
    ('knee bent', '屈膝保持',
     'The selected knee remains flexed, with a maintained angle between thigh and shank under the '
     'project criterion. A bent knee alone does not establish squatting or kneeling.',
     ['bent knee posture', 'flexed knee', '弯膝姿态']),
    ('knee straight', '膝伸直保持',
     'The selected thigh and shank remain near straight alignment at the knee under the project '
     'tolerance. Do not require exact zero flexion or infer force, support or joint locking.',
     ['straight knee posture', 'extended knee', '直膝姿态']),
]:
    _add('Body Posture', _name, _zh, _description, group='Leg posture', parts=['Left Leg', 'Right Leg'],
         rule='Select the relevant leg track. Start when the stated leg or knee configuration is '
              'established and maintained; end when it changes. Exclude the raising, lowering, bending '
              'or straightening process. Use actor-relative geometry and study-defined angle tolerances.',
         auto_method='No specific raised-leg or knee-posture detector is implemented in this release. '
                     'A future rule requires validated pelvis/hip/knee/ankle mapping and posture criteria; '
                     'low motion does not determine joint configuration.', aliases=_aliases)
_rows('Body Posture', 'Torso posture', ['Torso'], [
    ('leaning forward', '身体前倾', 'The torso is held inclined forward relative to the actor and support surface.'),
    ('leaning backward', '身体后仰', 'The torso is held inclined backward relative to the actor and support surface.'),
])
_rows('Body Posture', 'Arm and hand posture', ['Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
    ('arms crossed', '双臂交叉', 'The arms are held crossed across the front of the torso; defensiveness or other attitude is not implied.'),
    ('hands on hips', '双手放在髋部', 'Both hands are held at the hips or waist.'),
    ('hands in lap', '双手放在腿上', 'Both hands are held or supported in the lap while seated.'),
])
_rows('Body Posture', 'Leg posture', ['Left Leg', 'Right Leg'], [
    ('legs crossed', '双腿交叉', 'The legs are held crossed; use a more specific side label when the crossing direction is clear.'),
    ('right leg over left', '右腿搭在左腿上', 'The right thigh or leg is held over the left leg; record the established posture rather than the crossing movement.'),
    ('left leg over right', '左腿搭在右腿上', 'The left thigh or leg is held over the right leg; record the established posture rather than the crossing movement.'),
    ('ankles crossed', '脚踝交叉', 'The legs are held crossed at or near the ankles.'),
])
_add('Body Posture', 'posture transition', '姿势转换（兼容通用项）',
     'A historical broad process label for visible movement between sustained postures, retained with its '
     'original identity for compatibility. It is not a maintained state; prefer a specific Locomotion '
     'posture-transition label when the process can be resolved.',
     group='Transition', parts=['Full Body'], semantic_kind='posture_transition',
     rule='Start at departure from the previous posture; end when the next posture is established. '
          'Do not include the sustained postures at either end. Do not automatically relabel historical records.')
_rows('Body Posture', 'Uncertainty', ['Full Body'], [
    ('posture uncertain', '姿势不确定', 'Evidence is present but does not support a reliable posture classification.'),
    ('not visible', '不可见', 'The relevant body region cannot be assessed for posture.'),
])

_rows('Hand Behavior', 'Hand configuration', ['Left Hand', 'Right Hand'], [
    ('fingers interlaced', '十指交叉相扣', 'Fingers of the two hands visibly interweave; distinguish this from hands simply clasped together.'),
    ('hands clasped', '双手握合', 'The two hands are held together in a clasp without requiring interlaced fingers.'),
    ('palms together', '双掌相合', 'The palms are held against one another without requiring a clasp or interlaced fingers.'),
    ('hand resting', '手部静置', 'One or both hands remain supported or still in a resting position; select the relevant hand channel.'),
])
_rows('Hand Behavior', 'Repetitive action', ['Left Hand', 'Right Hand'], [
    ('hand rubbing', '双手揉搓', 'The hands move against each other with repeated rubbing contact.'),
    ('finger tapping', '手指敲击', 'A finger repeatedly taps a surface, the body or another finger; note the target when known.'),
    ('thumb twiddling', '拇指绕动', 'The thumbs make repeated alternating or circular motions, usually while the other fingers are held together.'),
])
_rows('Hand Behavior', 'Self-contact', ['Left Hand', 'Right Hand'], [
    ('self-touch', '自我触碰', 'A hand visibly contacts the same actor body; this does not imply self-soothing or discomfort.'),
    ('hand to face', '手部触脸', 'A hand visibly touches or remains against the face; approaching the face alone is insufficient.'),
    ('hand to hair', '手部触碰头发', 'A hand visibly contacts or manipulates the hair; use the relevant hand channel.'),
])
_rows('Hand Behavior', 'Uncertainty', ['Left Hand', 'Right Hand'], [
    ('hand behavior uncertain', '手部行为不确定', 'Visible hand activity or configuration cannot be classified reliably from the available detail.'),
    ('not visible', '不可见', 'Hand shape or contact is not visible well enough to annotate.'),
])

_rows('Locomotion', 'Displacement', ['Root', 'Left Leg', 'Right Leg'], [
    ('walking', '行走', 'A sequence of alternating steps moves the actor through the scene.'),
    ('stepping', '迈步', 'One or a few discrete steps occur without requiring a sustained walking sequence.'),
    ('other locomotion', '其他位移方式', 'A visible locomotor action is outside the listed types; describe the action in notes.'),
])
_rows('Locomotion', 'In-place movement', ['Root', 'Left Leg', 'Right Leg'], [
    ('turning in place', '原地转身', 'Body heading changes while the actor remains approximately in the same location.'),
    ('weight shift', '重心转移', 'Body support visibly shifts between feet or support regions without a distinct locomotor step.'),
])
_rows('Locomotion', 'Posture transition', ['Root', 'Left Leg', 'Right Leg'], [
    ('sit down', '坐下', 'The actor lowers from standing or another elevated posture into a seated support.', 'Start with the movement toward the seat; end when the seated posture is established.'),
    ('stand up', '起立', 'The actor rises from a seated or lower support into standing.', 'Start with the preparatory rise or weight transfer; end when standing support is established.'),
])
for _name, _zh, _description, _boundary, _aliases in [
    ('lower into squat', '下蹲（进入蹲姿）',
     'The actor lowers the body through coordinated hip and knee motion into a squat with support primarily '
     'through the feet. This whole-body transition is separate from local knee flexion and from the maintained squat.',
     'Start at departure from the preceding posture toward the squat; end when the squat is established. '
     'Do not extend the transition through the subsequent held squat.', ['squat down', 'squatting down', '下蹲']),
    ('rise from squat', '从蹲姿起身',
     'The actor rises out of an established squat toward a higher posture. Record the transition, '
     'not the preceding squat or the following maintained posture.',
     'Start at departure from the squat; end when the next posture is established or the rise clearly stops.',
     ['stand from squat', 'stand up from squat', 'rising from squat', '蹲起']),
    ('kneel down', '跪下（进入跪姿）',
     'The actor lowers into a kneeling configuration with one or both knees establishing visible contact/support '
     'with a surface. Knee bending or low knee height alone does not establish this transition.',
     'Start at departure from the preceding posture toward kneeling; end when the kneeling support/configuration '
     'is established. Review knee contact; when it cannot be established use locomotion uncertain.',
     ['kneeling down', 'lower into kneeling', '跪下']),
    ('rise from kneeling', '从跪姿起身',
     'The actor rises out of an established kneeling support/configuration, leaving knee support for a higher '
     'posture. Do not infer the starting support relation solely from knee height in BVH.',
     'Start at departure from the kneeling configuration; end when the next posture is established or the rise '
     'clearly stops. Exclude the held postures at either end.',
     ['stand from kneeling', 'stand up from kneeling', 'rising from kneeling', '跪姿起身']),
]:
    _add('Locomotion', _name, _zh, _description, group='Posture transition',
         parts=['Root', 'Full Body', 'Left Leg', 'Right Leg'], rule=_boundary,
         recommended_workflow='automatic_primary', implementation_status='planned_rule',
         auto_method='No squat/kneel transition detector is implemented in this release. A future rule requires '
                     'validated joint geometry, posture change and support evidence; kneeling additionally '
                     'requires reliable knee contact/support evidence. Coarse leg motion is not this classification.',
         aliases=_aliases)
_add('Locomotion', 'stationary', '位置稳定', 'The actor remains in approximately the same scene location; arms or other body parts may still move.', group='State', parts=['Root'],
     rule='Mark the reviewed interval without meaningful root displacement under the project criterion; end when a locomotor displacement begins.')
_rows('Locomotion', 'Uncertainty', ['Root', 'Left Leg', 'Right Leg'], [
    ('locomotion uncertain', '位移类型不确定', 'Body displacement or support movement is evident but cannot be classified reliably.'),
    ('not visible', '不可见', 'The lower body or root motion cannot be assessed from the available evidence.'),
])

_rows('Gesture Type', 'Gesture form and function', ['Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
    ('gesture (unclassified)', '手势（未细分）', 'A communicative gesture is supported by context, but its more specific type is not assigned.'),
    ('deictic / pointing gesture', '指示／指向手势', 'A gesture visibly indicates a person, object, place or direction; record the referent in notes when known.'),
    ('iconic gesture', '形象手势', 'A gesture depicts a concrete shape, action or spatial property of a referent in context.'),
    ('metaphoric gesture', '隐喻手势', 'A gesture represents an abstract concept through a spatial or physical form, supported by accompanying context.'),
    ('beat gesture', '节拍手势', 'A rhythmic gesture marks discourse emphasis or timing without a clear depictive or pointing content.'),
    ('emblem', '约定俗成手势', 'A conventional gesture has a locally established meaning that can be interpreted without the spoken words; record the intended convention.'),
    ('greeting wave', '招呼挥手', 'A visible wave functions as a greeting or farewell in the interaction context; social event timing can be annotated separately.'),
    ('non-gesture movement', '非交际性运动', 'The reviewed movement has an observable practical or bodily role and is not treated as a communicative gesture; do not use this for uncertainty.'),
])
_rows('Gesture Type', 'Uncertainty', ['Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
    ('gesture type uncertain', '手势类型不确定', 'The available movement and context do not support a reliable gesture-type decision.'),
    ('not visible', '不可见', 'The relevant movement is not visible well enough to judge gesture type.'),
])
_rows('Gesture Phase', 'Gesture phases', ['Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
    ('gesture preparation', '手势准备', 'Movement brings the effector from its preceding position into position for the expressive part of a gesture.', 'Start at departure from the previous position; end at the onset of the expressive stroke. Do not force a preparation phase when the gesture starts directly with a stroke.'),
    ('gesture stroke', '手势表达核心', 'The part of the gesture carrying its principal expressive movement or effort.', 'Start at the onset of the expressive movement; end when that expressive movement is complete, before a subsequent hold or retraction. Use context as well as speed.'),
    ('gesture hold', '手势停顿保持', 'A gesture-related pose is maintained before or after a stroke; a low-velocity signal alone does not establish this phase.', 'Start when the gesture pose becomes maintained; end when the next stroke or retraction begins. Include only the gesture-related hold, not unrelated rest.'),
    ('gesture retraction', '手势回收', 'Movement returns the effector from the gesture to a resting or less expressive position.', 'Start when the expressive stroke or hold is released; end when the return is complete or another gesture begins.'),
])
_rows('Gesture Phase', 'Uncertainty', ['Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
    ('gesture phase uncertain', '手势阶段不确定', 'A gesture unit is visible but the phase cannot be assigned reliably.'),
    ('not visible', '不可见', 'The effector or relevant phase transition cannot be seen.'),
])
_rows('Speech-Gesture Relation', 'Speech relation', ['Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
    ('co-speech gesture', '伴随言语的手势', 'The gesture is coordinated with speech by the same actor in timing or meaning; inspect synchronized audio and context.'),
    ('speech-independent gesture', '独立于言语的手势', 'The gesture is interpretable without accompanying speech by the actor, supported by the visible interaction context.'),
])
_rows('Speech-Gesture Relation', 'Uncertainty', [], [
    ('speech-gesture relation uncertain', '言语—手势关系不确定', 'A gesture is visible but the evidence does not establish its relation to the speech.'),
    ('audio unavailable', '音频不可用', 'Usable synchronized audio is absent, preventing a speech-gesture relation decision.', 'Mark the gesture interval for which the required audio is unavailable; do not infer speech independence from missing sound.'),
])

_rows('Action / HOI', 'Actions · Acquire and release', ['Left Hand', 'Right Hand', 'Left Arm', 'Right Arm'], [
    ('reaching toward object', '伸手接近物体', 'The hand or arm moves toward an identifiable object, without requiring contact.', 'Start at directed movement toward the object; end at first contact, a clear stop or abandonment of the reach.'),
    ('grasp object', '抓握物体', 'The hand visibly forms or establishes a grip on an object.', 'Start when fingers or the hand begin closing into the object grip; end when the grasp is established. Mark sustained holding separately.'),
    ('pick up object', '拿起物体', 'The actor lifts an object from its previous supporting surface or support.', 'Start when the object begins leaving its support under actor control; end when the lift is complete or transitions to transport or holding.'),
    ('put down object', '放下物体', 'The actor moves an object onto a supporting surface or another stable support.', 'Start at movement toward the support; end when the object is supported there and the placement movement ends. Release can be a separate operation.'),
    ('release object', '松开物体', 'The actor relinquishes an established grip or physical control of the object.', 'Start at visible opening or release of the established grip; end when grip or support by that hand ceases.'),
])
_rows('Action / HOI', 'States · Contact and control', ['Left Hand', 'Right Hand'], [
    ('hold object', '持有物体', 'A hand maintains a grasp or supporting control of an object.', 'Start when holding control is established; end when the actor releases it or control is lost. Object movement may overlap with holding.'),
    ('touch object', '触碰物体', 'A body part visibly contacts an object without requiring a grasp, lift or manipulation.', 'Start at visible contact and end at separation. Mere spatial proximity or BVH overlap is insufficient evidence of contact.'),
])
for _name, _zh, _desc, _parts, _rule in [
    ('rest on object', '搁置在物体上',
     'The selected body part remains visibly placed on an object surface, such as a hand resting on a table. This state does not imply emotional relaxation or a measured contact force.',
     ['Left Hand', 'Right Hand', 'Left Arm', 'Right Arm', 'Head', 'Torso', 'Left Leg', 'Right Leg'],
     'Start when the body part establishes a sustained placement on the surface; end when it separates or changes relation. Include the whole maintained state regardless of speech boundaries.'),
    ('sit on object', '坐在物体上',
     'The actor maintains a seated posture on an identified object such as a sofa or chair. Identify the supporting object; this is the seated state, not the sit-down movement.',
     ['Root', 'Full Body'],
     'Start when seated support on the object is established; end when the actor rises, leaves the support or changes to another relation. The sitting posture may be linked without drawing the same interval twice.'),
    ('lean against object', '倚靠物体',
     'The selected body region remains visibly leaned against an identified object, such as a torso against a sofa back. Record the maintained relation without estimating force.',
     ['Torso', 'Head', 'Left Arm', 'Right Arm', 'Full Body'],
     'Start when the visible leaning relation is established; end when contact or the leaning configuration clearly ceases. Mark approach and departure movements separately when needed.'),
    ('lie on object', '躺在物体上',
     'The actor maintains a lying or reclined body configuration on an identified supporting object. Sleep, comfort and intention are not inferred.',
     ['Full Body', 'Torso'],
     'Start when the lying relation to the object is established; end when the actor rises, leaves it or changes to another posture. Exclude the transition into or out of the state.'),
    ('stand on object', '站在物体上',
     'The actor stands on an identified object or support surface such as a platform. Record the object instance rather than inferring it from body height alone.',
     ['Left Leg', 'Right Leg', 'Full Body'],
     'Start when standing support on the identified object is established; end when the actor steps away or changes to another support or posture.'),
    ('support body on object', '借物体支撑身体',
     'Visible posture and contact support that the actor uses the selected body part against an object for bodily support, such as bracing the hands on a table. Mere proximity does not establish load bearing; exact force is not measured.',
     ['Left Hand', 'Right Hand', 'Left Arm', 'Right Arm', 'Torso', 'Full Body'],
     'Start when a supported or braced body configuration is visibly established; end when that support is released or its configuration changes. If support cannot be distinguished from touch, use touch object or contact uncertain.'),
]:
    _add('Action / HOI', _name, _zh, _desc, parts=_parts,
         group='States · Support and placement', rule=_rule,
         recommended_workflow='assisted', implementation_status='planned_rule',
         semantic_kind='object_state',
         auto_method='No automatic relation detector is implemented. Future candidates require visible contact or calibrated body/object geometry; a centroid or joint proximity alone is insufficient.')
_rows('Action / HOI', 'Actions · Manipulate', ['Left Hand', 'Right Hand', 'Left Arm', 'Right Arm'], [
    ('push object', '推动物体', 'The actor applies visible contact that moves or attempts to move an object away along a direction.', 'Start at the visible pushing effort or resulting displacement; end when the effort or directed movement stops.'),
    ('pull object', '拉动物体', 'The actor draws an object toward the body or along a pulling direction through an established contact or grasp.', 'Start at the visible pulling effort or resulting displacement; end when that effort or directed movement stops.'),
    ('use object', '使用物体', 'The actor performs an identifiable operation with an object, beyond simply holding it; describe the operation in notes.', 'Mark the active operation from first functional manipulation to its completion; do not include unrelated holding before or after.'),
    ('move furniture', '移动家具', 'The actor repositions a chair, table or other furniture item.', 'Start at the first controlled furniture displacement; end when the item stops in its new position or the actor abandons the move.'),
])
_rows('Action / HOI', 'Actions · Transfer', ['Left Hand', 'Right Hand', 'Left Arm', 'Right Arm'], [
    ('handover object', '递交物体', 'The selected actor presents and transfers an object to another person; an offer without transfer can be recorded as an Interaction Event.', 'Start at presentation of the object for transfer; end when the receiver has control and the giver releases, or the attempted transfer clearly stops.'),
    ('receive object', '接收物体', 'The selected actor acquires an object from another person.', 'Start at reaching or contact that visibly participates in the receipt; end when receiving control is established or the attempt stops.'),
])
_rows('Action / HOI', 'Other and uncertainty', list(BODY_PARTS), [
    ('other action', '其他物体操作', 'A visible object-related action is outside this list; describe the object and action in notes.'),
    ('contact uncertain', '接触状态不确定', 'Available evidence cannot establish whether the body and object are in contact.', 'Mark only the interval with unresolved contact evidence; end when contact or separation becomes clear.'),
    ('not visible', '不可见', 'The body-object interaction is hidden or lacks the visual detail required for assessment.', 'Mark the interval with unusable visibility; end when the relevant action can again be observed.'),
])

_rows('Perceived Affect', 'Perceived valence', [], [
    ('neutral / no reliable cue', '中性／无可靠情感线索', 'The reviewed interval contains no reliable cue for a more specific perceived affect; this is not proof of an emotionally neutral internal state.'),
    ('positive affect', '可感知的积极情感', 'Multimodal cues support a broad positive-affect impression without requiring a specific emotion label.'),
    ('negative affect', '可感知的消极情感', 'Multimodal cues support a broad negative-affect impression without requiring a specific emotion label.'),
])
_rows('Perceived Affect', 'Perceived emotion', [], [
    ('amusement', '可感知的愉悦或被逗乐', 'Context and observable cues support an impression of amusement; laughter alone is not conclusive.'),
    ('frustration', '可感知的挫败', 'Context and observable cues support an impression of frustration; movement or a sigh alone is not conclusive.'),
    ('surprise', '可感知的惊讶', 'Context and observable cues support an impression of surprise; a single facial or vocal event alone is not conclusive.'),
    ('other perceived affect', '其他可感知情感', 'An observer affect judgment outside the listed types is supported by stated cues; describe the interpretation in notes.'),
])
_rows('Perceived Affect', 'Uncertainty', [], [
    ('affect uncertain', '情感判断不确定', 'Available cues are ambiguous or conflicting, preventing a reliable perceived-affect judgment.'),
    ('insufficient evidence', '证据不足', 'The usable evidence is insufficient for an affect assessment; do not infer a state from absent modalities.'),
])

_add('Speaking', 'Speaking', '说话', 'Audible speech is present; speech activity detection does not identify the speaker or conversational role.',
     group='Speech activity', auto_mode='optional_model',
     auto_method='Optional Silero VAD. Linux real-model smoke test completed; OCUMO accuracy and Windows real-model behavior are not established. Actor identity requires human assignment.')
_rows('Speaking', 'Speech qualifiers', [], [
    ('Speaker unknown', '说话人未知', 'Speech is audible but the source person cannot be reliably assigned.', 'Mark the speech interval with unresolved speaker identity; stop when the identity becomes established or speech ends.'),
    ('Unintelligible speech', '无法听清的言语', 'Speech is audible but its words cannot be reliably understood.', 'Mark the unintelligible portion of speech; do not extend across intelligible material or non-speech noise.'),
])
_add('Speaking', 'silence (reviewed)', '静默（已人工核查）', 'No audible vocalization from the selected actor is present in the reviewed interval; this is not a listener or disengagement label.',
     group='Reviewed absence', rule='Mark only an interval listened to with usable audio and adequate speaker attribution. End at the next audible vocalization; missing or muted audio is not silence.')

for _name, _zh, _desc, _mode in [
    ('Laughter', '笑声', 'Audible laugh-like vocalization; amusement or agreement requires separate contextual evidence.', 'optional_model'),
    ('Sigh', '叹息声', 'A distinct audible sigh-like exhalation; tiredness, relief or frustration is not inferred from the sound alone.', 'optional_model'),
    ('Gasp', '吸气声／倒吸气', 'A distinct abrupt inhalation or gasp-like sound; its cause or emotional meaning is not inferred.', 'optional_model'),
    ('Cough', '咳嗽声', 'A cough-like vocal burst, without a health interpretation.', 'optional_model'),
    ('Throat clearing', '清嗓声', 'A brief throat-clearing vocal sound, separate from speech and a cough when distinguishable.', 'optional_model'),
    ('Sneeze', '喷嚏声', 'An audible sneeze-like event, without a health interpretation.', 'optional_model'),
    ('Sniff', '吸鼻声', 'An audible short nasal inhalation or sniff-like sound, without inferred cause.', 'optional_model'),
    ('Breathing', '呼吸声', 'Audible breathing that is the event of interest; silent respiration is not annotated from audio.', 'interface_only'),
    ('Crying', '哭泣声', 'Audible crying or sobbing-like vocalization; an internal emotional state is not established by the sound alone.', 'interface_only'),
]:
    _method = ('Optional YAMNet adapter, enabled target in the audio dialog. Adapter/postprocessing tested; real YAMNet weights and OCUMO detection accuracy were not validated in the audited build.'
               if _mode == 'optional_model' else
               'YAMNet class supported only by the lower-level adapter; not enabled by the current GUI target list. Use manual annotation in the current workflow.')
    _add('Vocal Event', _name, _zh, _desc, group='Vocal sounds', auto_mode=_mode, auto_method=_method)
_rows('Vocal Event', 'Other and uncertainty', [], [
    ('Other vocal event', '其他发声事件', 'An audible human vocal sound falls outside the named event types; describe the sound in notes.'),
    ('Vocal event uncertain', '发声类型不确定', 'A vocal event is audible but its sound class cannot be assigned reliably.'),
])
_add('Audio Activity', 'Audio activity (energy)', '音频能量活动', 'Signal energy crosses the activity criterion; speech, vocal class and speaker identity are not determined.',
     group='Signal activity', auto_mode='builtin_candidate', auto_method='RMS energy threshold. Environmental noise may trigger activity; listen before assigning a speech or vocal label.')
_add('Audio Activity', 'Audio unavailable', '音频不可用', 'The required audio is absent, corrupt, muted or otherwise unusable; this is different from reviewed silence.',
     group='Uncertainty', rule='Mark the interval without usable audio; end when a usable source resumes.')

_add('Speech Turn', 'speaker turn', '说话轮次',
     'An actor holds or claims a conversational turn, which may include internal pauses. Automatic grouping of attributed speech is a proposal and does not resolve every backchannel or floor-competition case.',
     group='Turn interval', auto_mode='builtin_candidate',
     auto_method='Built-in rule-based grouping of existing actor-attributed Speaking intervals. Identity mapping must already be established; there is no built-in diarization or ASR. Review short responses, overlaps and turn boundaries.',
     aliases=['speech turn', 'conversational turn', '话轮'])
_add('Speech Turn', 'turn uncertain', '话轮边界或归属不确定',
     'Speech is observable but the turn boundary, holder or grouping remains unresolved.',
     group='Uncertainty', recommended_workflow='manual_primary', implementation_status='manual')

_add('Turn Transition', 'speaker change candidate', '说话人切换候选点',
     'A candidate boundary at the incoming turn onset when the adjacent attributed turns change actor. A backchannel or simultaneous entry may not constitute a conversational floor transfer.',
     group='Automatic boundary', auto_mode='builtin_candidate',
     auto_method='Built-in derivation from attributed turn candidates. The point convention is the incoming start; outgoing end, source IDs and signed gap are retained as relation evidence. No social handover classifier is claimed.',
     aliases=['speaker change', 'turn transition candidate', '切换点'])
_add('Turn Transition', 'turn handover', '话轮交接点',
     'A reviewed conversational floor transfer from one actor to another. Link the outgoing and incoming turns when known, and keep any gap or overlap as a separate timing value.',
     group='Reviewed floor transfer', recommended_workflow='assisted', implementation_status='manual',
     auto_method='An acoustic speaker-change candidate can locate a review opportunity. Its conversational meaning requires context; no automatic handover classifier is implemented.')
_add('Turn Transition', 'transition uncertain', '交接性质不确定',
     'The incoming contribution onset is observable, but whether the floor transfers remains unresolved.',
     group='Uncertainty', recommended_workflow='manual_primary', implementation_status='manual')

for _name, _zh, _desc, _rule in [
    ('overlapping speech', '重叠说话区间',
     'Attributed speech by R01 and R02 occurs simultaneously. The intersection is a timing relation, not proof of interruption.',
     'Use the positive-duration intersection of the two actors speech intervals; exclude one-sided speech. Source attribution and missed speech affect the result.'),
    ('within-turn pause', '话轮内部停顿',
     'A gap between attributed speech segments lies within the same retained turn. Absence of detected speech is not absence of all sound or vocalization.',
     'Use the gap between successive same-actor speech segments within the turn. Do not create a pause over another segment of that actor or across a true turn transfer.'),
    ('between-turn gap', '话轮之间的间隔',
     'The incoming turn begins after the preceding relevant turn ends. A positive time difference is represented as an interval; zero or negative differences are not positive gaps.',
     'Start at the outgoing turn end and end at the incoming turn start only when the latter is later. Preserve the source turn relation; uncertainty in turn grouping propagates to this interval.'),
]:
    _add('Speech Timing', _name, _zh, _desc, group='Derived intervals', rule=_rule,
         auto_mode='builtin_candidate', recommended_workflow='automatic_derived',
         auto_method='Built-in interval arithmetic over source Speaking / Speech Turn records. Derived records retain source references and remain predictions unless their evidence has been reviewed.')

_rows('Dialogue Event', 'Turn organization', [], [
    ('interruption', '打断', 'An incoming contribution competes with or displaces an ongoing turn in context; speech overlap alone does not establish interruption.', 'Start at the incoming turn entry; end when the floor competition resolves or the interrupting attempt stops.'),
])
_rows('Dialogue Event', 'Conversational function', [], [
    ('vocal backchannel', '言语性反馈', 'A short vocal response acknowledges or supports the ongoing contribution without normally taking the conversational floor; do not infer a stable listener role.', 'Mark the feedback utterance itself from acoustic onset to offset; do not label the full silent period before or after it.'),
    ('repair request', '澄清或修复请求', 'A contribution requests repetition, clarification or correction of the preceding interaction.', 'Mark the utterance or gesture that requests the repair; the subsequent repair response is a separate event.'),
    ('other dialogue event', '其他会话事件', 'A contextual conversational function outside the list is observed; describe it in notes.'),
])
_add('Dialogue Event', 'dialogue event uncertain', '会话事件不确定', 'An exchange is observable but its turn-taking or communicative function cannot be assigned reliably.', group='Uncertainty')

_rows('Proxemic Movement', 'Relative translation', ['Root', 'Full Body'], [
    ('move toward partner', '向对方接近', 'The selected actor moves in a way that reduces actor-partner separation, supported by actor-specific motion; interaction initiation is not implied.'),
    ('move away from partner', '远离对方', 'The selected actor moves in a way that increases actor-partner separation; refusal, avoidance or leaving an interaction is not implied.'),
    ('move alongside partner', '与对方并行移动', 'The selected actor moves alongside a moving partner while approximately maintaining their lateral relation; coordination or affiliation is not assumed.'),
])
_rows('Proxemic Movement', 'Relative orientation', ['Torso', 'Root'], [
    ('turn toward partner', '身体转向对方', 'The selected actor changes body heading toward the partner; this does not identify an eye-gaze target.'),
    ('turn away from partner', '身体转离对方', 'The selected actor changes body heading away from the partner; this is not by itself disengagement or gaze avoidance.'),
])
_rows('Proxemic Movement', 'Other and uncertainty', ['Root', 'Torso'], [
    ('other proxemic movement', '其他相对空间运动', 'A visible actor-partner spatial change is outside the listed types; describe the actor-specific motion in notes.'),
    ('proxemic movement uncertain', '相对空间运动不确定', 'A relative spatial change is visible but its actor attribution or movement type cannot be established reliably.'),
])

_rows('Spatial Configuration', 'Pair configuration', ['Root', 'Torso'], [
    ('face-to-face', '面对面', 'Both participants are positioned and bodily oriented toward one another; opposite headings alone are insufficient, and mutual eye gaze is not implied.'),
    ('side-by-side', '并排', 'The participants occupy neighboring lateral positions with approximately similar bodily headings.'),
    ('back-to-back', '背对背', 'The participants occupy a rearward relation and orient away from one another; verify both position and heading.'),
    ('angled arrangement', '斜向排列', 'The participants form a sustained angled spatial arrangement that is not face-to-face, side-by-side or back-to-back.'),
    ('one facing the other', '一方朝向另一方', 'One participant bodily faces the other without reciprocal body facing; identify which actor faces whom in notes.'),
])
_add('Spatial Configuration', 'configuration uncertain', '空间构型不确定', 'Positions or orientations do not support a reliable pair-configuration judgment.', group='Uncertainty', parts=['Root', 'Torso'])

_add('Activity Relation', 'co-active arms (relationship unverified)', '双人手臂同时活动（关系未证实）',
     'Arm-activity intervals overlap across two actors. A response, synchrony, imitation or other social relationship has not been established.',
     group='Temporal overlap', parts=['Left Arm', 'Right Arm'], auto_mode='builtin_candidate',
     auto_method='Dyadic overlap of existing arm-activity candidates. The overlap rule proposes co-activity only; social relationship requires human evidence.',
     rule='Mark the common interval in which both actors have arm activity. Check each actor track and do not extend to unrelated surrounding movements.')
_rows('Activity Relation', 'Temporal relation', ['Full Body'], [
    ('simultaneous movement', '同时运动', 'Both actors visibly move during a shared time interval; the movement need not have similar form, rhythm or function.', 'Mark the interval with movement in both actors. Exclude one-sided lead-in and trailing movement.'),
    ('movement synchrony', '运动同步', 'Repeated or sustained movements have a consistent temporal relation under a stated comparison criterion; one accidental overlap is insufficient.', 'Mark only the span with repeated or sustained timing correspondence. Record the compared body parts, lag and project tolerance in notes.'),
    ('delayed movement correspondence', '延迟运动对应', 'A later movement resembles or corresponds to an earlier movement by the other actor with an observable lag, without inferring causation.', 'Include the source movement and corresponding later movement as one reviewed relation interval; record both component times and lag in notes.'),
])
_rows('Activity Relation', 'Postural relation', ['Full Body'], [
    ('posture similarity', '姿势相似', 'The two participants maintain comparable visible body configurations; imitation, rapport or intent is not inferred.', 'Mark the span with the relevant similarity in both actors. Record the compared posture features and any left-right mirroring in notes.'),
])
_rows('Activity Relation', 'Uncertainty', [], [
    ('activity relation uncertain', '活动关系不确定', 'Both actors are observable but the proposed temporal or postural relation remains ambiguous.'),
    ('insufficient evidence', '证据不足', 'The synchronized evidence from one or both actors is inadequate to assess an activity relation.'),
])

_rows('Interaction Event', 'Opening and closing', [], [
    ('greeting', '问候或招呼', 'An action or utterance is directed as a greeting in context; a greeting attempt does not require a successful response.', 'Start at the first greeting action or utterance and end at its completion. A response can be separately marked on the responding actor track.'),
    ('interaction initiation', '发起互动', 'An actor visibly or audibly attempts to open an exchange with a partner; moving closer alone is insufficient.', 'Mark the initiating contribution from onset to completion or abandonment. Record the intended target when supported by evidence.'),
    ('farewell', '告别', 'An action or utterance functions as leave-taking or closing an encounter in context.', 'Mark the farewell contribution or exchange from its first closing action to its resolution; later physical departure can be a separate event.'),
    ('leaving an interaction', '退出互动', 'Context supports that an actor ends participation in the ongoing exchange; increasing distance alone is insufficient.', 'Start at the observable disengagement or departure that constitutes leaving; end when participation has clearly ceased or the departure action ends.'),
])
_rows('Interaction Event', 'Directed contribution', [], [
    ('response', '回应', 'An action or utterance is contextually linked to a preceding contribution by the partner; temporal succession alone is insufficient.', 'Mark the responding contribution itself. Record the preceding event or reference time in notes where possible.'),
    ('acknowledgment', '确认或应答', 'An action or utterance indicates receipt or recognition of a partner contribution; a nod or sound alone is not conclusive.', 'Mark the acknowledgment action or utterance from onset to offset, without extending across the whole preceding contribution.'),
    ('offer', '提议或提供', 'An actor proposes an action, resource or object to the partner; an unaccepted offer remains an offer.', 'Mark the offering contribution or presentation from onset to completion. Acceptance or transfer is recorded separately.'),
    ('request', '请求', 'An actor asks the partner for information, an action or an object in context.', 'Mark the requesting contribution from onset to completion; do not include the partner response in the same actor event.'),
    ('acceptance', '接受', 'An actor observably accepts an offer, proposal or request in context.', 'Mark the accepting contribution or action. Silence alone is not evidence of acceptance.'),
    ('refusal', '拒绝', 'An actor observably declines an offer, proposal or request in context.', 'Mark the declining contribution or action. Silence, looking away or moving away alone is not evidence of refusal.'),
])
_rows('Interaction Event', 'Joint and linked action', [], [
    ('imitation', '模仿', 'Context supports that one actor reproduces a partner action; similarity or a time lag alone is insufficient.', 'Mark the imitating action and record the model actor and source interval in notes. When the evidence supports only similarity or timing, retain the individual motion observations.'),
    ('object handover', '物品交接事件', 'A coordinated exchange transfers an object from one participant to another; physical giver and receiver actions can also be annotated in HOI.', 'Start at the presentation or receiving action that initiates the exchange; end when control transfers or the exchange attempt clearly stops. Identify giver and receiver.'),
])
_rows('Interaction Event', 'Other and uncertainty', [], [
    ('other interaction', '其他社交事件', 'An observable social action or exchange falls outside the listed types; describe its meaning and evidence in notes.'),
    ('interaction uncertain', '互动含义不确定', 'Observable contributions are present but the available context does not support a reliable social-event interpretation.'),
])

_rows('QC / Notes', 'Data quality', [], [
    ('BVH fit anomaly', 'BVH 拟合异常', 'The reconstructed pose or motion shows a suspected fitting, skeleton or tracking artifact.'),
    ('synchronization issue', '同步问题', 'Two or more modalities appear temporally misaligned; record the affected sources and estimated offset when known.'),
    ('occlusion', '遮挡', 'An observation needed for the task is visually blocked; identify the actor or body part in notes.'),
    ('missing modality', '模态缺失', 'A required source or modality is absent for the annotated interval.'),
    ('low-confidence gaze', '外部注视参考置信度低', 'An imported Oculo or gaze reference is unreliable or incomplete; this quality note does not introduce a gaze annotation track.'),
    ('coordinate mapping issue', '坐标映射问题', 'Positions or orientations appear inconsistent across sources because their coordinate mapping is unreliable.'),
    ('video glitch', '视频异常', 'Video contains corruption, dropped frames, freezing or another visible playback/data defect.'),
])
_rows('QC / Notes', 'Annotation review', [], [
    ('annotation ambiguity', '标注歧义', 'The evidence or project definitions allow competing annotation interpretations; describe the alternatives.'),
    ('other QC issue', '其他质量问题', 'A data or annotation-quality issue is outside the named types; describe its nature and impact.'),
])

# Uncertainty and visibility intervals follow the evidence gap, not the boundaries
# of a specific movement or configuration that cannot be reliably observed.
for (_category, _name), _info in LABEL_INFO.items():
    if _name == 'not visible':
        _info['boundary_rule'] = ('Start when the relevant body part or action can no longer be assessed; '
                                  'end when sufficient usable evidence returns. Do not infer behavior within the obscured interval.')
    elif _name.endswith('uncertain') and _info.get('temporal_kind') != 'point':
        _info['boundary_rule'] = ('Mark the interval for which available evidence supports competing or unresolved classifications. '
                                  'End when a specific interpretation becomes supported or the relevant event ends; state the uncertainty in notes.')
    elif _name == 'insufficient evidence':
        _info['boundary_rule'] = ('Start when the evidence needed for this type is absent or unusable; '
                                  'end when an assessment becomes possible. This interval does not establish absence of the behavior.')
for _name in ('movement', 'hold', 'rest', 'not visible'):
    LABEL_INFO[('Motion Primitive', _name)]['body_parts'] = list(BODY_PARTS)

# A detector capability must never be inherited by a manual qualifier merely
# because it belongs to a category containing an automatic detector.
for (_category, _name), _info in LABEL_INFO.items():
    _uncertain = (_info['group'] in ('Uncertainty', 'Other and uncertainty', 'Reviewed absence')
                  or _name.endswith('uncertain') or _name == 'insufficient evidence')
    if _uncertain and _info['auto_mode'] == 'manual':
        _info.update(recommended_workflow='manual_primary', implementation_status='manual')
    if _category == 'Action / HOI':
        _info['uses_object_reference'] = True
        if _info['group'].startswith('States'):
            _info['semantic_kind'] = 'object_state'
    if _category == 'Speaking' and _name != 'Speaking':
        _info.update(recommended_workflow='manual_primary', implementation_status='manual')
    if _category == 'Vocal Event' and _info['auto_mode'] == 'interface_only':
        _info.update(recommended_workflow='automatic_primary', implementation_status='planned_model')
    if _category == 'Vocal Event' and _name in ('Other vocal event', 'Vocal event uncertain'):
        _info.update(recommended_workflow='manual_primary', implementation_status='manual')
    if _category == 'QC / Notes' and _name != 'Unlabeled':
        _info['auto_method'] = ('The application validates some file structure, but has no complete automatic '
                                'QC annotation detector. This label is manually assigned; future detectors may '
                                'flag suspicious intervals for review, not prove the cause of a defect.')

for _name in ('hold', 'rest'):
    LABEL_INFO[('Motion Primitive', _name)].update(
        recommended_workflow='assisted', implementation_status='planned_rule', semantic_kind='state',
        auto_method='No independent hold/rest detector is implemented. Stable kinematics can provide a candidate, but missing detections must not be converted into rest.')
LABEL_INFO[('Hand Behavior', 'hand resting')].update(
    recommended_workflow='automatic_primary', implementation_status='planned_rule', semantic_kind='state',
    auto_method='No dedicated resting-hand classifier is implemented. Future candidates require a stable hand configuration and usable evidence; support on an object is a separate HOI relation.')
LABEL_INFO[('Locomotion', 'stationary')]['semantic_kind'] = 'state'
LABEL_INFO[('Body Posture', 'standing')]['aliases'] = ['stand', 'standing posture', '站着']
LABEL_INFO[('Action / HOI', 'touch object')]['body_parts'] = list(BODY_PARTS)
# The existing bilateral structure detector emits this candidate on Full Body.
# Keep its arm applicability as well as its actual output channel addressable.
LABEL_INFO[('Motion Primitive', 'bilateral arm co-activity (not classified)')]['body_parts'] = [
    'Left Arm', 'Right Arm', 'Full Body']
LABEL_INFO[('Turn Transition', 'transition uncertain')]['boundary_rule'] = (
    'Place a single point at the incoming contribution onset under the project convention. '
    'Record the unresolved interpretation in notes; do not expand the marker to an arbitrary duration.')

# The UI remains English. Chinese definitions are supplied for the catalog and
# bilingual search/help; they do not replace saved project-authored definitions.
_ZH_DESCRIPTIONS = {
    ACTIVITY_EPISODE: {
        'push cart': '人物可见地推动有轮手推车。描述可补充弯腰、直立、前推等可观察细节。',
    },
    'Motion Primitive': {
        'raise right arm': '右臂相对躯干向上运动；描述运动形式，不判断交际意义。',
        'lower right arm': '右臂相对躯干向下运动；描述运动形式，不判断交际意义。',
        'extend right elbow': '右肘逐渐伸直，区别于整条手臂的位置平移。',
        'flex right elbow': '右肘逐渐弯曲，区别于整条手臂的位置平移。',
        'raise left arm': '左臂相对躯干向上运动；描述运动形式，不判断交际意义。',
        'lower left arm': '左臂相对躯干向下运动；描述运动形式，不判断交际意义。',
        'extend left elbow': '左肘逐渐伸直，区别于整条手臂的位置平移。',
        'flex left elbow': '左肘逐渐弯曲，区别于整条手臂的位置平移。',
        'reach forward (kinematic)': '手臂相对躯干向前伸出，不据此推断目标物体或动作意图。',
        'retract arm': '手臂向身体或此前的静置区域回收；与交际手势的回收阶段分开。',
        'wave right hand (kinematic)': '右手的位置或朝向呈可见往复挥动，具有交替摆动和方向反转；腕、前臂或整臂可参与，不推断问候、告别、拒绝或对象。',
        'wave left hand (kinematic)': '左手的位置或朝向呈可见往复挥动，具有交替摆动和方向反转；腕、前臂或整臂可参与，不推断问候、告别、拒绝或对象。',
        'head rotation': '可见的头部朝向变化，尚未细分为点头或摇头；不据此判断注视目标。',
        'head nod': '头部俯仰或上下往返运动；赞同、确认等功能需要另有上下文证据。',
        'head shake': '头部偏航或左右往返运动；不同意、拒绝等功能需要另有上下文证据。',
        'torso lean': '躯干倾斜角发生变化，标注运动过程，而非之后持续的倾斜姿态。',
        'turn body': '躯干或全身朝向改变；是否转向某个人由空间关系层表达。',
        'bend right knee': '右膝发生屈曲，大腿与小腿的相对角度改变；整腿平移不能替代膝关节证据，可发生于下蹲或踢腿等较大动作之中。',
        'straighten right knee': '右膝逐渐伸直，大腿与小腿的相对角度改变；标注伸直过程，不包含之后保持伸直的姿态。',
        'bend left knee': '左膝发生屈曲，大腿与小腿的相对角度改变；整腿平移不能替代膝关节证据，可发生于下蹲或踢腿等较大动作之中。',
        'straighten left knee': '左膝逐渐伸直，大腿与小腿的相对角度改变；标注伸直过程，不包含之后保持伸直的姿态。',
        'kick right leg (kinematic)': '右腿或右脚呈明确的向外摆出或踢动模式；这是可含髋膝联合运动的较粗运动模式，不是严格单关节原子，不推断目标、碰撞、攻击或交际意图。',
        'kick left leg (kinematic)': '左腿或左脚呈明确的向外摆出或踢动模式；这是可含髋膝联合运动的较粗运动模式，不是严格单关节原子，不推断目标、碰撞、攻击或交际意图。',
        'cross legs': '一条或两条腿移入交叉配置的过程，区别于之后持续的双腿交叉姿态；选择主要运动腿，不因涉及双腿而自动重复标注。',
        'uncross legs': '一条或两条腿离开已建立交叉配置的过程，区别于之后不交叉的持续姿态；选择主要运动腿。',
        'head flexion': '头相对上躯干／颈部向前俯屈，如下颌降低；是单方向运动，与往复点头分开，不推断眼睛注视目标。',
        'head extension': '头相对上躯干／颈部向后伸展，也包括从低头回到中立的过程；不表示眼睛向上看或已经保持仰头。',
        'turn head left': '头相对躯干向本人左侧转动；整个人转身而头躯干相对方向未变不属于此项，不推断注视。',
        'turn head right': '头相对躯干向本人右侧转动；整个人转身而头躯干相对方向未变不属于此项，不推断注视。',
        'tilt head left': '头相对躯干向本人左肩侧倾；区别于左右转头或镜头倾斜，不推断注视。',
        'tilt head right': '头相对躯干向本人右肩侧倾；区别于左右转头或镜头倾斜，不推断注视。',
        'bend torso forward': '躯干相对骨盆和本人身体坐标向前弯曲／倾斜；标过程，与持续前倾姿态分开。',
        'straighten torso': '躯干从弯曲或倾斜配置回到相对骨盆更中立、直立的配置；转换前后保持姿态分别记录。',
        'lean torso backward': '躯干相对骨盆向后倾斜的过程；与已经保持后仰的姿态分开。',
        'bend torso left': '躯干相对骨盆向本人左侧弯曲；区别于轴向扭转和全身平移。',
        'bend torso right': '躯干相对骨盆向本人右侧弯曲；区别于轴向扭转和全身平移。',
        'rotate torso left': '上躯干相对骨盆向本人左侧扭转；全身共同改变朝向但躯干骨盆未相对扭转时选较粗转身项。',
        'rotate torso right': '上躯干相对骨盆向本人右侧扭转；全身共同改变朝向但躯干骨盆未相对扭转时选较粗转身项。',
        'move arm outward': '所选侧上臂相对躯干向外展开；只靠伸肘使手远离身体不足以证明这一肩部层级运动。',
        'move arm inward': '所选侧上臂从外侧向躯干或中线收拢；只弯肘但上臂方向不变不足以成立。',
        'open hand': '所选手从较闭合／手指蜷曲的配置变得更展开；标手型变化，不自动判断松开物体。',
        'close hand': '所选手的手指向蜷曲或闭合配置变化，不要求握成完整拳头；不自动判断抓住物体或发生接触。',
        'flex wrist': '手相对前臂在腕部朝掌侧弯曲；整条前臂平移或旋转而腕角不变不足以成立。',
        'extend wrist': '手相对前臂在腕部朝手背侧伸展，也包括从屈腕回正；整条前臂运动不能替代腕角变化。',
        'raise leg': '所选腿相对本人从原有高度向上抬起，是关节机制未细分的粗运动；不直接等于屈髋或伸膝，整个身体一起升高不足以成立。',
        'lower leg': '所选腿相对本人从抬起位置移向较低位置；不限定关节机制，不能仅凭全身下降判定。',
        'hip flexion': '所选侧大腿相对骨盆向前运动而发生屈髋；膝角可独立变化。raise thigh 是搜索别名，不与任意抬腿／抬脚等同。',
        'hip extension': '所选侧大腿相对骨盆向后运动，也包括从屈髋回到中立；不是伸膝，也不等于所有放腿动作。',
        'move leg outward': '所选侧大腿／腿相对骨盆向身体中线外侧移动；区别于全身平移、镜头变化或单纯转向。',
        'move leg inward': '所选侧大腿／腿从外侧向身体中线收回，不要求最终与另一条腿接触。',
        'move legs apart': '一条或两条腿运动使双腿间距增大；这是粗略双腿模式，不直接证明前后劈叉、横叉、纯髋外展或接触。',
        'bring legs together': '一条或两条腿运动使双腿间距减小，不要求腿部接触；与之后持续并腿姿态分开。',
        'local arm movement (meaning uncertain)': '选定手臂发生局部运动，具体形式或含义尚未确定。',
        'head / neck movement': '头颈区域发生运动，尚未细分为点头、摇头或其他转动。',
        'torso movement': '躯干区域发生运动，尚未确定更具体的运动形式。',
        'left leg movement': '左腿发生运动，尚未确定是迈步、行走还是其他形式。',
        'right leg movement': '右腿发生运动，尚未确定是迈步、行走还是其他形式。',
        'left hand / finger movement': '左手或手指发生运动，尚未确定具体手型或接触关系。',
        'right hand / finger movement': '右手或手指发生运动，尚未确定具体手型或接触关系。',
        'hand / finger movement': '手或手指发生运动，当前输出未区分左右侧。',
        'whole-body movement': '涉及全身的广义运动，尚未分类为具体动作或社会行为。',
        'pelvis translation / locomotion candidate': '从骨盆或根节点轨迹得到的平移候选，尚未确认步行、迈步或运动意图。',
        'raise → hold → lower (candidate)': '抬臂后接低运动量间隔再放下的结构候选；需要检查中间是否确实保持高位姿态。',
        'raise → lower (candidate)': '抬臂后接放下的结构候选，中间没有已确认的保持阶段。',
        'bilateral arm co-activity (not classified)': '同一个人的两臂在时间上共同活动；不表示双人互动，也不自动证明对称或协调。',
        'movement': '存在可见运动，但尚未选择更具体的运动形式。',
        'hold': '动作之间或之后维持一个可见姿态；仅有低速度不足以证明姿态保持。',
        'rest': '所选身体部位维持可观察的休止配置；不能把未检测到动作的空白直接补成休止。',
        'not visible': '所需身体部位或其运动缺少足够可用证据，无法判断。',
    },
    'Body Posture': {
        'standing': '身体保持直立，主要由双脚或单脚支撑。',
        'sitting': '身体保持坐姿，骨盆下方有支撑；具体支撑物体由 HOI 关系记录。',
        'squatting': '髋膝弯曲、身体降低且主要由脚支撑的持续蹲姿；区别于坐姿或跪姿，也区别于下蹲和起身的转换过程。',
        'kneeling': '一侧或双侧膝与支撑面有可见接触并形成跪姿支撑配置；BVH 中膝靠近地面不足以证明接触、承重或力值，证据不足时保留姿态不确定。',
        'lying': '身体保持躺卧、躯干得到较广泛支撑而非直立的配置；侧别未细分时用此项，不推断睡眠、舒适或具体支撑物。',
        'lying supine': '保持背侧朝向支撑面、身体前侧朝外的仰卧配置；按身体与支撑关系判断，不按镜头方向，也不推断睡眠。',
        'lying prone': '保持躯干前侧朝向支撑面的俯卧配置；头可另行转向，不推断睡眠或不适。',
        'lying on left side': '保持本人躯干左侧朝向支撑面的侧卧配置；左侧指解剖侧别，不能按画面左侧判断。',
        'lying on right side': '保持本人躯干右侧朝向支撑面的侧卧配置；右侧指解剖侧别，不能按画面右侧判断。',
        'half-kneeling': '一侧膝接触支撑面，另一侧腿在前且脚接触支撑面的持续半跪配置；需可观察接触／支撑，不能只看关节高度。',
        'standing on left leg': '保持直立，主要脚部支撑来自左腿，另一只脚明确离开支撑面；额外手部或物体支撑可另记，不推断平衡能力或力值。',
        'standing on right leg': '保持直立，主要脚部支撑来自右腿，另一只脚明确离开支撑面；额外手部或物体支撑可另记，不推断平衡能力或力值。',
        'legs apart': '双腿相对骨盆保持明显分开的配置，可出现在坐姿或站姿；不直接等于劈叉、横叉或某种社会含义。',
        'legs together': '双腿相对骨盆保持接近／并拢配置，按项目统一间距准则判断；不要求或推断双腿接触。',
        'front split': '保持一腿相对骨盆前伸、另一腿后伸，骨盆较低、双腿接近前后相反直线的劈叉配置；普通分腿、迈步或弯膝弓步不足以成立。',
        'middle split': '保持双腿相对骨盆向两侧伸展、骨盆较低、双腿接近左右相反直线的横叉配置；普通宽站姿或坐姿膝分开不足以成立。',
        'head upright': '头相对上躯干保持接近中立，无明显俯仰、侧倾或转头；这是身体相对配置，不要求世界坐标竖直，也不判断注视。',
        'head lowered': '头相对上躯干保持前屈；与低头过程分开，不据此认定眼睛向下看或注意某物。',
        'head tilted back': '头相对上躯干保持后伸／后仰；不据此判断眼睛向上看、注意或情绪。',
        'head turned left': '头相对躯干保持向本人左侧转动后的配置；不推断注视对象或交流对象。',
        'head turned right': '头相对躯干保持向本人右侧转动后的配置；不推断注视对象或交流对象。',
        'head tilted left': '头相对躯干保持向本人左肩侧倾，区别于水平转头；不推断注视或情感。',
        'head tilted right': '头相对躯干保持向本人右肩侧倾，区别于水平转头；不推断注视或情感。',
        'torso upright': '躯干相对骨盆保持中立，无明显前后侧倾或扭转；不能单凭此项判断正在站、坐还是躺。',
        'torso leaned left': '躯干相对骨盆保持向本人左侧弯曲；是持续倾斜配置，不是侧弯过程或身体平移。',
        'torso leaned right': '躯干相对骨盆保持向本人右侧弯曲；是持续倾斜配置，不是侧弯过程或身体平移。',
        'torso rotated left': '上躯干相对骨盆保持向本人左侧扭转；全身朝向本身不足以确定躯干扭转。',
        'torso rotated right': '上躯干相对骨盆保持向本人右侧扭转；全身朝向本身不足以确定躯干扭转。',
        'arm raised': '所选侧手臂相对躯干保持抬高配置；这是持续姿态，不是抬起过程，也不自动构成交际手势。',
        'arm extended forward': '所选侧手臂相对躯干保持前伸，肘可以略弯；不要求肘完全伸直，也不推断指向意图或物体目标。',
        'arm hanging down': '所选侧手臂沿躯干向身体下部保持未抬高的配置；描述身体相对位置，不推断放松、肌肉活动或是否受到支撑。',
        'elbow bent': '所选侧上臂与前臂在肘部保持弯曲夹角；手臂整体位置和手的目标另行描述。',
        'elbow straight': '所选侧上臂与前臂在肘部保持接近直线；使用项目容差，不要求精确零屈曲，也不推断力或关节锁定。',
        'leg raised': '所选腿相对骨盆与已知上方向保持抬起配置；不限定关节机制，也不据此判断外部支撑或是否由另一腿单脚站立。',
        'knee bent': '所选侧大腿与小腿在膝部保持弯曲夹角；弯膝本身不证明蹲姿或跪姿。',
        'knee straight': '所选侧大腿与小腿在膝部保持接近直线；使用项目容差，不要求精确零屈曲，不推断力、承重或关节锁定。',
        'leaning forward': '躯干相对身体及支撑环境持续前倾。',
        'leaning backward': '躯干相对身体及支撑环境持续后仰。',
        'arms crossed': '双臂保持交叉在躯干前方，不推断防御、紧张等态度。',
        'hands on hips': '双手放在髋部或腰部。',
        'hands in lap': '坐姿下双手放在或由腿部支撑。',
        'legs crossed': '双腿保持交叉；方向明确时可选择更具体的左右腿标签。',
        'right leg over left': '右侧大腿或腿搭在左腿上，标注建立后的姿态。',
        'left leg over right': '左侧大腿或腿搭在右腿上，标注建立后的姿态。',
        'ankles crossed': '双腿在脚踝附近保持交叉。',
        'posture transition': '兼容历史记录的通用姿势转换过程，不属于持续状态；明确时优先选 Locomotion 中具体转换类型，不自动改写旧记录。',
        'posture uncertain': '存在姿态证据，但不足以可靠确定姿态类型。',
        'not visible': '相关身体区域缺少足够可见或可用证据，无法判断姿态。',
    },
    'Hand Behavior': {
        'fingers interlaced': '双手手指明显互相穿插相扣，区别于仅把双手握在一起。',
        'hands clasped': '双手保持握合，不要求十指互相穿插。',
        'palms together': '双掌相对并合，未必形成握合或手指交叉。',
        'hand resting': '一只或两只手保持静置或由某处支撑；与具体物体的关系另记 HOI。',
        'hand rubbing': '双手接触并反复互相揉搓。',
        'finger tapping': '手指反复敲击表面、身体或其他手指；已知时记录敲击对象。',
        'thumb twiddling': '拇指反复交替或绕圈运动，其他手指通常保持相对固定。',
        'self-touch': '手部可见地接触自己的身体，不推断自我安抚或不适。',
        'hand to face': '手部接触或保持贴在脸上；仅靠近脸部不足以成立。',
        'hand to hair': '手部可见地接触或整理头发。',
        'hand behavior uncertain': '手部行为可见，但细节不足以确定具体类型。',
        'not visible': '手型或接触细节不可见，无法据此分类。',
    },
    'Locomotion': {
        'walking': '连续交替迈步，使身体在场景中发生位移。',
        'stepping': '一次或少量明确迈步，不要求形成持续步行。',
        'other locomotion': '存在身体位移，但形式不属于已列类型；在备注中描述。',
        'turning in place': '身体朝向改变，整体位置大致保持不变。',
        'weight shift': '身体支撑明显在脚或支撑区域之间转移，未形成明确迈步；BVH 本身不测足底压力。',
        'sit down': '身体从站立或较高姿势降低到坐姿支撑；与已经坐着分开。',
        'stand up': '身体从坐姿或较低支撑起身到站立。',
        'lower into squat': '身体通过髋膝联合运动降低并进入蹲姿；属于全身姿态转换，与局部弯膝和持续蹲姿分开。',
        'rise from squat': '身体离开已建立的蹲姿并上升到较高姿态；仅标起身过程。',
        'kneel down': '身体降低并进入一侧或双膝与支撑面建立可见接触／支撑的跪姿；仅弯膝或膝位置低不足以确认。',
        'rise from kneeling': '身体离开已建立的跪姿支撑并向较高姿态起身；起点跪姿关系需有可靠证据，不能只由 BVH 膝高度推出。',
        'stationary': '身体在场景中的位置大致稳定，手臂或其他部位仍可活动。',
        'locomotion uncertain': '身体位移或支撑变化可见，但具体类型不确定。',
        'not visible': '下肢或根节点运动缺少足够证据，无法判断。',
    },
    'Activity Relation': {
        'co-active arms (relationship unverified)': '两人的手臂活动区间重叠；尚未建立回应、同步或模仿等关系。',
        'simultaneous movement': '两人在同一时间段内都发生运动，不要求动作相似或有相同功能。',
        'movement synchrony': '重复或持续运动在明确定义的比较准则下具有稳定时间对应；偶然一次重叠不足以成立。',
        'delayed movement correspondence': '一人的较晚动作与另一人的较早动作相似或对应，记录时滞，不推断因果。',
        'posture similarity': '两人维持相似身体配置，需说明比较部位及是否按左右镜像比较；不自动解释为模仿。',
        'activity relation uncertain': '两人均可观察，但时间或姿态关系仍有歧义。',
        'insufficient evidence': '一人或两人的同步证据不足，无法判断活动关系。',
    },
    'Gesture Type': {
        'gesture (unclassified)': '上下文支持这是交际手势，但尚未细分类型。',
        'deictic / pointing gesture': '手势指示人物、物体、位置或方向；已知时记录指代对象。',
        'iconic gesture': '手势描绘具体对象、动作或空间特征，其解释需要上下文。',
        'metaphoric gesture': '手势通过空间或形态表达抽象概念，需要言语或互动上下文支持。',
        'beat gesture': '手势以节奏或时序突出话语重点，没有明确描绘或指向内容。',
        'emblem': '当地文化或情境中具有约定含义的手势，可不依赖同步言语理解；记录相关约定。',
        'greeting wave': '挥手在当前互动中具有问候或告别功能；仅见手臂摆动不足以确定。',
        'non-gesture movement': '经过上下文判断，所见运动没有当前研究所定义的交际手势功能。',
        'gesture type uncertain': '手势可见，但其交际形式或类型不确定。',
        'not visible': '相关动作缺少足够可见证据，无法判断手势类型。',
    },
    'Gesture Phase': {
        'gesture preparation': '身体部位从此前状态移向即将进行表达的配置；没有准备阶段时不强行补出。',
        'gesture stroke': '手势承担主要表达内容或表达性用力的阶段；不能仅以最大速度判定。',
        'gesture hold': '表达核心前后维持与手势有关的姿态；无关静置或低运动量不自动算此阶段。',
        'gesture retraction': '手势表达结束后，身体部位返回休止或较少表达性的配置。',
        'gesture phase uncertain': '手势单位已确定，但当前阶段或其边界仍不确定。',
        'not visible': '相关身体部位或阶段不可观察，无法判断。',
    },
    'Speech-Gesture Relation': {
        'co-speech gesture': '同一人的手势在时序或意义上与其言语协调；单纯时间重叠不足以建立此语义关系。',
        'speech-independent gesture': '结合情境，手势可在没有本人伴随言语时独立理解。',
        'speech-gesture relation uncertain': '手势可见，但证据不足以确定它与言语的关系。',
        'audio unavailable': '所需同步音频不可用，不能由缺少声音推断手势独立于言语。',
    },
    'Action / HOI': {
        'reaching toward object': '手或手臂向可识别物体移动，不要求已经接触。',
        'grasp object': '手部正在建立对物体的抓握，之后持续持有另记状态。',
        'pick up object': '物体在人的控制下离开原支撑面并被抬起。',
        'put down object': '人将物体移到新的支撑面或稳定支撑上，松手可以另行标注。',
        'release object': '人解除对物体的抓握或控制。',
        'hold object': '手持续抓握或支撑并控制物体；关系方向为人控制物体。',
        'touch object': '身体部位可见地接触物体，不要求抓握、抬起或操作；仅接近不足以成立。',
        'rest on object': '身体部位持续搁置在物体表面，如右手搁在桌面；不推断心理放松或准确受力。',
        'sit on object': '身体在指定物体上保持坐姿，如坐在 sofa_01；坐下过程另行标注。',
        'lean against object': '身体部位持续倚靠指定物体，如躯干靠在沙发靠背上；不估计接触力。',
        'lie on object': '身体在指定支撑物上保持躺卧或斜躺配置，不推断睡眠、舒适或意图。',
        'stand on object': '身体在指定物体或支撑面上站立；不能仅凭身体高度猜测物体。',
        'support body on object': '可见接触和姿态支持身体借物体支撑或撑住；仅接近不足以证明承重，准确力值未知。',
        'push object': '可见接触使物体向外移动或明显试图推动物体。',
        'pull object': '通过接触或抓握，将物体向身体或指定方向拉动。',
        'use object': '对物体实施可识别的功能操作，超出单纯持有；在备注中说明操作。',
        'move furniture': '重新放置椅子、桌子或其他家具。',
        'handover object': '将物体呈现并交给另一人，区分实际转移与仅发出提供意向。',
        'receive object': '从另一人处获得对物体的控制。',
        'other action': '存在可见物体相关动作，但不属于已列类型；记录物体和动作。',
        'contact uncertain': '证据不足以判断身体与物体是否接触。',
        'not visible': '物体交互被遮挡或缺少足够细节，无法判断。',
    },
    'Perceived Affect': {
        'neutral / no reliable cue': '已复核区间缺少明确情感线索，不证明参与者内心处于中性状态。',
        'positive affect': '多模态上下文支持积极情感印象，未细分具体情绪。',
        'negative affect': '多模态上下文支持消极情感印象，未细分具体情绪。',
        'amusement': '上下文支持愉悦或被逗乐的印象，笑声本身不足以确定。',
        'frustration': '上下文支持挫败的印象，动作或叹息本身不足以确定。',
        'surprise': '多模态上下文支持惊讶的印象，不由单个表情或发声直接决定。',
        'other perceived affect': '上下文支持其他未列出的情感印象，记录线索和解释，不把观察者印象当作已知内在状态。',
        'affect uncertain': '情感线索含混或相互冲突，无法可靠判断。',
        'insufficient evidence': '多模态证据不足，无法判断可感知情感。',
    },
    'Speaking': {
        'Speaking': '存在可听见的言语；VAD 检测有无语音，不自动确定身份或会话角色。',
        'Speaker unknown': '言语可听见，但其来源人物无法可靠确定。',
        'Unintelligible speech': '言语可听见，但具体词语无法可靠听清。',
        'silence (reviewed)': '已听取并核查的有效音频中没有该人的可听发声；缺失或静音文件不等于静默，也不表示倾听。',
    },
    'Speech Turn': {
        'speaker turn': '一人持有或尝试持有一个会话话轮，可包含内部短暂停顿；自动分组合并只是待核查候选。',
        'turn uncertain': '言语可观察，但话轮边界、持有人或分组仍未确定。',
    },
    'Turn Transition': {
        'speaker change candidate': '相邻的已归属话轮发生人物变化，以后一个贡献的起点作候选点；短反馈或同时开口不必然构成话轮交接。',
        'turn handover': '上下文确认会话话轮由一人交给另一人；按项目约定标在接入话轮起点，并记录前后话轮。',
        'transition uncertain': '接入贡献的起点可观察，但是否真正转移话轮尚不确定。',
    },
    'Speech Timing': {
        'overlapping speech': 'R01 与 R02 的语音区间在时间上相交；重叠本身不证明打断。',
        'within-turn pause': '同一保留话轮内部的语音片段之间有间隔；未检出言语不等于没有其他声音或发声。',
        'between-turn gap': '相关的后一个话轮在前一个结束后开始，形成正时长间隔；零或负时间差不生成间隔区间。',
    },
    'Vocal Event': {
        'Laughter': '可听见的笑声，愉悦、赞同等含义需要额外上下文。',
        'Sigh': '可听见的叹息样呼气，不直接判断疲惫、释然或挫败。',
        'Gasp': '可听见的突然吸气或倒吸气，不推断其原因或情绪意义。',
        'Cough': '可听见的咳嗽样发声，不作健康解释。',
        'Throat clearing': '短促清嗓声，能够区分时与言语、咳嗽分别记录。',
        'Sneeze': '可听见的喷嚏样声音，不作健康解释。',
        'Sniff': '短促鼻吸气或吸鼻声，不推断原因。',
        'Breathing': '当前任务关注的可听呼吸声；无法从音频标注无声呼吸。',
        'Crying': '可听见的哭泣或啜泣样发声，不能仅凭声音确定内在情绪。',
        'Other vocal event': '可听见的人类发声不属于已列类别，在备注中描述。',
        'Vocal event uncertain': '发声事件可听见，但声音类型无法可靠确定。',
    },
    'Audio Activity': {
        'Audio activity (energy)': '信号能量超过活动阈值；可能包含噪声，不确定语音类别或人物身份。',
        'Audio unavailable': '所需音频缺失、损坏、静音或不可用，区别于已经核查的静默。',
    },
    'Dialogue Event': {
        'interruption': '接入贡献在上下文中竞争或取代当前话轮；仅有语音重叠不足以认定打断。',
        'vocal backchannel': '短促发声对当前贡献提供反馈，通常不接过话轮；不推断持续的倾听者角色。',
        'repair request': '请求对方重复、澄清或修正此前互动内容。',
        'other dialogue event': '可观察的会话功能不属于已列类型，在备注中说明。',
        'dialogue event uncertain': '交谈可观察，但话轮组织或交际功能无法可靠确定。',
    },
    'Proxemic Movement': {
        'move toward partner': '选定人物自身向伙伴方向运动并减少双方距离；不自动解释为发起互动。',
        'move away from partner': '选定人物自身远离伙伴并增加双方距离；不自动解释为拒绝、回避或退出互动。',
        'move alongside partner': '选定人物在伙伴侧方同向移动，侧向关系大致保持；不自动解释为协调或亲近。',
        'turn toward partner': '选定人物的身体朝向转向伙伴，不代表眼睛注视对方。',
        'turn away from partner': '选定人物的身体朝向转离伙伴，不直接代表退出互动或回避注视。',
        'other proxemic movement': '存在其他人物—伙伴之间的空间变化，记录各自运动。',
        'proxemic movement uncertain': '空间变化可观察，但移动归属或具体类型不确定。',
    },
    'Spatial Configuration': {
        'face-to-face': '双方的位置和身体朝向都支持彼此相对；仅朝向相反不足以成立，也不等于互相注视。',
        'side-by-side': '双方在侧向相邻位置，身体朝向大致一致。',
        'back-to-back': '双方处于背部相邻的空间关系，身体分别朝向远离彼此的方向。',
        'angled arrangement': '双方保持某种斜向排列，未归入面对面、并排或背对背。',
        'one facing the other': '其中一人的身体朝向伙伴，但对方未相互朝向；记录是哪一人。',
        'configuration uncertain': '位置或朝向证据不足以可靠判断双方空间排列。',
    },
    'Interaction Event': {
        'greeting': '动作或话语在上下文中用于问候，问候尝试不要求对方已经回应。',
        'interaction initiation': '一人通过可见或可听贡献尝试开启与伙伴的互动；仅接近不充分。',
        'farewell': '动作或话语在上下文中用于告别或结束接触。',
        'leaving an interaction': '上下文支持一人结束参与当前交流；仅增加距离不足以成立。',
        'response': '动作或话语在上下文中回应伙伴此前的贡献；仅时间先后不充分。',
        'acknowledgment': '动作或话语表示已收到或识别伙伴贡献；仅点头或发声不充分。',
        'offer': '向伙伴提出行动、资源或物品的提供，即使未被接受仍可记录提供。',
        'request': '向伙伴请求信息、行动或物品。',
        'acceptance': '可观察地接受提议、提供或请求；静默本身不构成接受。',
        'refusal': '可观察地拒绝提议、提供或请求；静默、转头或远离本身不充分。',
        'imitation': '上下文支持一人复现伙伴动作；相似或时滞本身不证明模仿。',
        'object handover': '双方协调交换物品，控制权由给予者转到接收者；各人的物理动作可在 HOI 分别记录。',
        'other interaction': '存在可观察的社交动作或交流，但不属于已列类型。',
        'interaction uncertain': '互动贡献可观察，但上下文不足以可靠确定社会意义。',
    },
    'QC / Notes': {
        'BVH fit anomaly': '重建姿态或运动出现疑似拟合、骨架映射或跟踪伪影。',
        'synchronization issue': '两个或更多模态可能时间错位，记录涉及来源及已知偏移。',
        'occlusion': '任务所需观察被遮挡，记录人物或身体部位。',
        'missing modality': '所需来源或模态在该时间段缺失。',
        'low-confidence gaze': '外部 Oculo 或 gaze 参考不可靠或不完整，此标签不增加新的注视标注工作区。',
        'coordinate mapping issue': '跨来源的位置或朝向因坐标映射问题而不一致。',
        'video glitch': '视频有损坏、丢帧、冻结或其他可见数据／播放问题。',
        'annotation ambiguity': '证据或标注规则允许多种解释，需要记录分歧。',
        'other QC issue': '其他数据或标注质量问题，说明性质及影响。',
    },
}

_CATEGORY_BOUNDARIES_ZH = {
    ACTIVITY_EPISODE: '从构成活动的第一个动作开始，到活动停止或转为其他活动时结束。',
    'Motion Primitive': '从明显离开此前姿态开始，到运动停止或形式改变结束；单方向运动在反向时拆分，挥手等往复模式按各自完整段落规则标注。',
    'Body Posture': '从姿态建立到其明确结束，排除进入和离开姿态的转换过程；历史 posture transition 项仍为过程，使用其专用边界。',
    'Hand Behavior': '从手型、接触或重复动作成立开始，到其解除或改变结束；看不清时记录不可见。',
    'Locomotion': '从位移、迈步或支撑转换开始，到其停止或类型改变结束；位置稳定是持续状态。',
    'Activity Relation': '标注双方证据共同支持该关系的区间，记录比较部位、时滞与容差。',
    'Gesture Type': '按一个可解释手势单位标注，可包含其准备与回收；独立手势分开。',
    'Gesture Phase': '只标当前阶段的可见起止，不扩展为整个手势，不强行补全不存在的阶段。',
    'Speech-Gesture Relation': '以手势单位为区间，检查周围言语和情境，不仅依据时间交集。',
    'Action / HOI': '动作标操作过程；状态标关系从建立到解除的完整区间，不随每次说话而切碎。',
    'Perceived Affect': '仅标有支持线索的区间，线索改变或不足时结束，并记录判断依据。',
    'Speaking': '从语音可听起点到终点；保留真实重叠，不由静默分配倾听者身份。',
    'Speech Turn': '从取得或主张话轮的贡献开始，到让出或放弃话轮结束；短暂停顿可在话轮内部。',
    'Turn Transition': '按项目约定标在接入贡献的起点，是单个时间点；前一轮结束与前后源 ID 另存。',
    'Speech Timing': '严格取相关源区间的交集或正时间间隔；零时长边界不扩成区间。',
    'Vocal Event': '从声音事件的可听起点到终点，不把周围静默纳入事件。',
    'Audio Activity': '标可听／检测活动或音频不可用的实际区间；能量活动不等于言语。',
    'Dialogue Event': '标执行该会话功能的贡献或短交换本身，并仅在有依据时记录发起者与对象。',
    'Proxemic Movement': '从所选人物的相对移动或转向开始，到其停止或反向结束；两人距离变化不足以确定谁移动。',
    'Spatial Configuration': '从空间排列建立到任一人改变它，使用项目统一的位置和朝向容差。',
    'Interaction Event': '从构成事件的首个贡献开始，到事件解决或停止结束；需要时分别记录发起与回应。',
    'QC / Notes': '标证据受影响的区间，从可靠性下降到恢复，并说明相关模态和原因。',
}

for (_category, _name), _info in LABEL_INFO.items():
    if _name == 'Unlabeled':
        _info['description_zh'] = '尚未选择语义标签的草稿，不表示该行为不存在。'
    else:
        _info['description_zh'] = _ZH_DESCRIPTIONS[_category][_name]
    _info['boundary_rule_zh'] = _CATEGORY_BOUNDARIES_ZH[_category]
    if not _info['auto_method']:
        _info['auto_method'] = {
            'planned_rule': 'No detector for this label is implemented in this release. The intended workflow uses explicit geometric or signal rules, followed by task-appropriate review.',
            'planned_model': 'No end-to-end detector for this label is available in the current GUI. Additional model/data integration and evaluation are required.',
            'manual': 'This release provides manual annotation for this label. Interpret evidence using the definition and preserve uncertainty.',
        }.get(_info['implementation_status'], '')

# Additive release vocabulary is kept separate so the historical definitions
# above remain inspectable and saved category/name identities stay stable.
from .ontology_zh_boundaries import correct_retained_chinese_boundaries as _correct_zh_boundaries
_correct_zh_boundaries(LABEL_INFO)
LABEL_INFO[ACTIVITY_EPISODE, 'push cart']['boundary_rule_zh'] = (
    '从人物开始推动手推车，到停止推动或转为另一项活动。准备弯腰的时段可留在推车区间之外。'
)
from .ontology_v5 import extend_ontology as _extend_ontology
_extend_ontology(WORKSPACE_CATEGORIES, CATEGORY_INFO, LABEL_PRESETS, LABEL_INFO,
                 LEGACY_LABEL_PRESETS, _add)
_INTERACTION_EVENT_PREVIOUS_GROUPS = {}
for _group, _names in INTERACTION_EVENT_CORE_GROUPS.items():
    for _name in _names:
        _entry = LABEL_INFO['Interaction Event', _name]
        _INTERACTION_EVENT_PREVIOUS_GROUPS[_name] = _entry['group']
        _entry['group'] = _group

_interaction_events = LABEL_PRESETS['Interaction Event']
LABEL_PRESETS['Interaction Event'] = [
    'Unlabeled', *_INTERACTION_EVENT_PREVIOUS_GROUPS,
    *(_name for _name in _interaction_events
      if _name != 'Unlabeled' and _name not in _INTERACTION_EVENT_PREVIOUS_GROUPS),
]
LABEL_INFO['Interaction Event', 'acknowledgment']['aliases'].extend(['acknowledgement', '确认收到'])

from .ontology_v51 import extend_hand_relations as _extend_hand_relations
_extend_hand_relations(CATEGORY_INFO, LABEL_PRESETS, LABEL_INFO, _add)
from .ontology_v52 import extend_affect_modes as _extend_affect_modes
_extend_affect_modes(CATEGORY_INFO, LABEL_INFO, _add)
from .ontology_gemep import extend_gemep_affect as _extend_gemep_affect
_extend_gemep_affect(LABEL_INFO, _add)
from .ontology_v53 import extend_object_spatial as _extend_object_spatial
_extend_object_spatial(WORKSPACE_CATEGORIES, CATEGORY_INFO, LABEL_PRESETS, LABEL_INFO, _add)

# Retire menu entries after the original definitions have been initialized.
# The category/name pairs (and the UUIDs derived from them) remain addressable.
_primitive = 'Motion Primitive'
_add(_primitive, UNCLASSIFIED_MOTION, '未分类运动候选',
     'A coarse BVH segmentation detected activity in the selected body part. Its movement form is still unclassified.',
     group='Broad movement', auto_mode='builtin_candidate',
     semantic_kind='unclassified_motion_candidate',
     rule='Check the source and boundaries. Keep pending or reject when no concrete movement form can be supported.')
LABEL_INFO[_primitive, UNCLASSIFIED_MOTION].update(
    description_zh='BVH 粗分割检出该部位的活动，具体运动形式尚未分类。',
    boundary_rule_zh='核查来源与边界；证据不足以确定具体动作时保留候选或拒绝。')

for _name, _zh, _parts, _group, _aliases, _desc, _desc_zh, _rule, _rule_zh in (
    ('extend arm', '伸出手臂', ('Left Arm', 'Right Arm'), 'Arm movement', ('arm extension',),
     'The hand moves away from the torso as the arm extends in any direction.',
     '手臂伸展使手远离躯干，方向不限。',
     'Mark outward extension from departure to a stop or reversal. Use a specific forward reach when its direction is clear; mark isolated elbow straightening separately.',
     '从手开始远离躯干标到停下或反向。明确向前伸手时可用向前伸手；单独的肘伸展用伸直肘。'),
    ('wrist rotation', '转动手腕', ('Left Hand', 'Right Hand'), 'Hand movement', ('rotate wrist', 'wrist circle', '手腕绕环'),
     'The hand traces a circular path relative to the forearm through combined wrist flexion, extension and deviation.',
     '手相对前臂通过腕屈伸和侧偏做绕环运动。',
     'Mark the observable circle or continuous series. Exclude rotation of the whole forearm and isolated wrist flexion or deviation.',
     '从可见绕环开始标到该次或连续一组绕环结束；排除整段前臂旋转和单独的腕屈伸或侧偏。'),
    ('pelvis translation', '骨盆平移', ('Root',), 'Root movement', ('pelvis shift', '骨盆移位'),
     'The pelvis shifts relative to the actor’s established support during a local movement.',
     '在局部动作中，骨盆相对人物已建立的支撑位置发生平移。',
     'Mark the clear shift from onset to stop or reversal. Use Locomotion for travel or a change of support during stepping.',
     '从可辨识的骨盆平移开始标到停下或反向；行进或迈步时的支撑转换用 Locomotion。'),
):
    _add(_primitive, _name, _zh, _desc, group=_group, parts=_parts, aliases=_aliases,
         rule=_rule, implementation_status='manual', recommended_workflow='manual_primary')
    LABEL_INFO[_primitive, _name].update(description_zh=_desc_zh, boundary_rule_zh=_rule_zh)

for _name, _aliases in {
    'head rotation': ('turn head', '转头'), 'head nod': ('nod', '点头'),
    'head shake': ('shake head', '摇头'), 'head flexion': ('lower head', '低头'),
    'head extension': ('raise head', '抬头'), 'tilt head left': ('tilt head',),
    'tilt head right': ('tilt head',), 'hip flexion': ('raise thigh', '抬大腿'),
    'flex fingers': ('finger flexion',), 'extend fingers': ('finger extension',),
    **{f'{verb} {side} {part}': (alias,)
       for side in ('left', 'right')
       for verb, part, alias in (
           ('raise', 'arm', 'raise arm'), ('lower', 'arm', 'lower arm'),
           ('flex', 'elbow', 'bend elbow'), ('extend', 'elbow', 'straighten elbow'),
           ('wave', 'hand (kinematic)', 'wave hand'), ('bend', 'knee', 'bend knee'),
           ('straighten', 'knee', 'straighten knee'), ('kick', 'leg (kinematic)', 'kick leg'))},
}.items():
    _entry = LABEL_INFO[_primitive, _name]
    _entry['aliases'] = list(dict.fromkeys([*_entry['aliases'], *_aliases]))

for _name, _method in FINE_PRIMITIVE_AUTO_METHODS.items():
    LABEL_INFO[_primitive, _name].update(auto_mode='builtin_candidate', implementation_status='builtin',
                                         auto_method=_method)

for _name in tuple(LABEL_PRESETS[_primitive]):
    if _name in RETIRED_PRIMITIVE_LABELS:
        LABEL_PRESETS[_primitive].remove(_name)
        if _name not in LEGACY_LABEL_PRESETS[_primitive]:
            LEGACY_LABEL_PRESETS[_primitive].append(_name)
LEGACY_LABEL_PRESETS[LEGACY_MOTION_RELATION] = LABEL_PRESETS.pop(LEGACY_MOTION_RELATION)
for _workspace in ('Motion', 'Overview'):
    WORKSPACE_CATEGORIES[_workspace] = tuple(
        category for category in WORKSPACE_CATEGORIES[_workspace] if category != LEGACY_MOTION_RELATION)
