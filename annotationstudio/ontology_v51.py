"""Hand relation refinements for v0.5.1, without prediction or data migration.

These are menu groups and observable interval labels. A maintained relation is
distinct from the movement entering it, and a fine label is an alternative to
its broader descriptions rather than an additional count of the same event.
"""


HAND_MENU_GROUPS = ('Hand configuration', 'Inter-hand arrangement', 'Hand placement',
                    'Self-contact', 'Self-support', 'Repetitive action', 'Uncertainty')
_INTER_HAND_NAMES = frozenset(('fingers interlaced', 'hands clasped', 'palms together'))
_CONFIGURATION_GROUPS = frozenset(('Hand configuration', 'Hand configurations'))
_REPETITIVE_GROUPS = frozenset(('Repetitive action', 'Repetitive hand actions'))


def hand_menu_group(name, group):
    """Present former built-in group names consistently, without mutating data.

    Callers limit this fallback to known core names. Arbitrary authored groups
    are retained; only former canonical spellings/placements are normalized.
    """
    if group in _CONFIGURATION_GROUPS:
        if name in _INTER_HAND_NAMES:
            return 'Inter-hand arrangement'
        if name == 'hand resting':
            return 'Hand placement'
        return 'Hand configuration'
    if group in _REPETITIVE_GROUPS:
        return 'Repetitive action'
    return group


def extend_hand_relations(categories, presets, info, add):
    """Refine current menus while preserving all preceding label identities."""
    category = 'Hand Behavior'
    categories[category]['description'] = (
        'Visible hand shape, inter-hand arrangement, placement, self-contact, '
        'self-support posture or repetitive hand action. Choose the most specific '
        'supported description of one relation; its broad and fine labels are '
        'alternatives, not duplicate events. Record object relations in HOI and '
        'interpersonal contact in Physical Interaction.')
    for name in presets[category]:
        item = info[(category, name)]
        item['group'] = hand_menu_group(name, item['group'])

    evidence = (
        'Video resolving the selected hand and the actor\'s own chin/cheek. '
        'Visible separation supports placement; contact and resting require '
        'their own visible evidence. BVH proximity alone cannot confirm contact '
        'or support, and no support force or internal state is measured.')
    no_detector = (
        'No detector for this label is connected. Manual selection is available; '
        'future model assistance requires integration and evaluation. Spatial '
        'proximity alone must not be accepted as contact or self-support.')

    rows = [
        {
            'name': 'hand under chin', 'zh': '手停在下巴下方（未接触）',
            'group': 'Hand placement',
            'description': (
                'The selected hand is held close beneath the actor\'s own chin '
                'with a visible gap. A hand elsewhere below the head is not '
                'sufficient. This is a maintained placement, not the approach '
                'movement. If the gap or contact is obscured, retain uncertainty '
                'rather than assuming absence of contact.'),
            'description_zh': (
                '所选手在本人下巴近下方保持，并可见间隙；手位于更低的其他位置不足以成立。'
                '这是保持的位置关系，不包括移入过程。看不清间隙或接触时保留不确定，'
                '不把遮挡解释为未接触。'),
            'rule': (
                'Start when the close, separated placement is established after '
                'approach. End when it changes, the gap closes, or usable '
                'separation evidence is lost. Minor adjustment that preserves '
                'the same placement does not require another segment.'),
            'rule_zh': (
                '从移入后近下方且分离的位置关系建立开始，到位置改变、间隙消失或分离证据'
                '不可用时结束；不因保持同一关系的轻微调整而拆段。'),
            'aliases': ['hand beneath chin', 'hand hovering under chin', '手放在下巴下面'],
        },
        {
            'name': 'hand to chin', 'zh': '手接触下巴',
            'group': 'Self-contact',
            'description': (
                'The selected hand visibly touches or remains against the '
                'actor\'s own chin. Approaching the chin alone is insufficient. '
                'Use this contact description when a more specific resting '
                'relation is not established; do not also count self-touch or '
                'hand to face for the same observation.'),
            'description_zh': (
                '所选手可见地触及或贴住本人的下巴，仅靠近不足以成立。接触明确但不能'
                '进一步确认托下巴姿态时使用；同一观察不再额外计为自我触碰或手部触脸。'),
            'rule': (
                'Start at visible chin contact, excluding approach. End at '
                'separation, a clear change of contact site/relation, or loss '
                'of assessable evidence. Do not infer contact through an '
                'unobservable gap.'),
            'rule_zh': (
                '从可见的下巴接触开始，排除靠近过程；在分离、接触部位／关系明确改变'
                '或证据无法评估时结束，不推断不可见区间内的接触。'),
            'aliases': ['hand-chin contact', 'hand–chin contact', 'touch chin', '手碰下巴'],
        },
        {
            'name': 'hand to cheek', 'zh': '手接触脸颊',
            'group': 'Self-contact',
            'description': (
                'The selected hand visibly touches or remains against the '
                'actor\'s own cheek. Identify cheek side in notes when needed; '
                'hand side alone does not determine it. Use this contact '
                'description when a cheek-resting relation is not established; '
                'do not also count broader self-touch/hand-to-face descriptions.'),
            'description_zh': (
                '所选手可见地触及或贴住本人的脸颊；需要时在备注注明脸颊侧别，不能由'
                '左右手自动推出接触哪侧脸颊。接触明确但托腮姿态未成立时使用，'
                '不再重复计为较宽的自我触碰或手部触脸。'),
            'rule': (
                'Start at visible cheek contact, excluding approach. End at '
                'separation, a clear change of cheek/contact relation, or loss '
                'of assessable evidence. Preserve uncertainty under occlusion.'),
            'rule_zh': (
                '从可见的脸颊接触开始，排除靠近过程；在分离、接触脸颊／关系明确改变'
                '或证据无法评估时结束，遮挡时保留不确定。'),
            'aliases': ['hand-cheek contact', 'hand–cheek contact', 'touch cheek', '手碰脸颊'],
        },
        {
            'name': 'chin resting on hand', 'zh': '托下巴',
            'group': 'Self-support',
            'description': (
                'The actor\'s chin visibly rests on the selected hand in a '
                'maintained support-like posture. Mere proximity or touch is '
                'insufficient. This describes an observable bodily relation, '
                'not a measured support force or thinking, boredom or fatigue. '
                'Use one specific relation label rather than duplicating its '
                'broader contact descriptions.'),
            'description_zh': (
                '本人的下巴可见地靠在所选手上，形成持续托住的姿态；仅靠近或碰触不足以'
                '成立。标注可观察的身体关系，不表示测得支撑力，也不代表思考、无聊或'
                '疲劳。同一关系使用这一具体标签，不再重复标较宽的接触标签。'),
            'rule': (
                'Start when the chin-resting posture is visibly established, '
                'excluding the hand approach. End when the resting relation '
                'ends, clearly changes, or can no longer be assessed. Retain '
                'one interval through minor readjustments that preserve it; '
                'record a change of supporting hand on its appropriate track.'),
            'rule_zh': (
                '从托下巴姿态可见地建立开始，排除手的靠近过程；在托住关系解除、明确'
                '改变或无法评估时结束。保持该关系的微调可留在同一区间，换手时在对应'
                '手部轨道记录。'),
            'aliases': ['chin supported by hand', 'rest chin on hand', 'hand supporting chin', '手托下巴'],
        },
        {
            'name': 'cheek resting on hand', 'zh': '托腮',
            'group': 'Self-support',
            'description': (
                'The actor\'s cheek or side of the face visibly rests against '
                'the selected hand in a maintained support-like posture. Mere '
                'touch is insufficient. Specify cheek side in notes when '
                'needed. Do not infer support force, emotion or listener status, '
                'and do not duplicate broader contact labels for this relation.'),
            'description_zh': (
                '本人的脸颊或侧脸可见地靠在所选手上，形成持续托腮姿态；仅碰触不足以'
                '成立。需要时在备注注明脸颊侧别。不推断支撑力、情感或倾听者身份，'
                '同一关系不重复标较宽的接触标签。'),
            'rule': (
                'Start when the cheek-resting posture is visibly established, '
                'excluding approach. End when it ends, changes to a different '
                'support/contact relation, or becomes unassessable. Minor '
                'readjustment does not by itself split the interval; a change '
                'of supporting hand belongs to the appropriate hand track.'),
            'rule_zh': (
                '从托腮姿态可见地建立开始，排除靠近过程；在关系解除、转为其他支撑／'
                '接触关系或无法评估时结束。轻微调整本身不要求拆段，换手时使用对应'
                '手部轨道。'),
            'aliases': ['cheek supported by hand', 'rest cheek on hand', 'hand supporting cheek', '手托腮'],
        },
    ]
    for row in rows:
        add(category, row['name'], row['zh'], row['description'],
            group=row['group'], parts=['Left Hand', 'Right Hand'],
            rule=row['rule'], aliases=row['aliases'], evidence=evidence,
            auto_mode='manual', auto_method=no_detector,
            recommended_workflow='assisted', implementation_status='planned_model',
            semantic_kind='state')
        info[(category, row['name'])].update(
            description_zh=row['description_zh'], boundary_rule_zh=row['rule_zh'],
            introduced_in='0.5.1')
