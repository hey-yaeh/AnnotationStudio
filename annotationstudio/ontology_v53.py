"""Person-to-named-object spatial states and movement, without model assets.

The registry supplies identity only. These are manually annotated relations;
this extension does not reconstruct geometry, calculate distances or infer HOI.
"""


def extend_object_spatial(workspaces, categories, presets, info, add):
    state = 'Object Spatial Relation'
    motion = 'Object-relative Movement'
    workspaces['Spatial'] = (*workspaces['Spatial'], state, motion)
    workspaces['Overview'] = tuple(category for workspace, types in workspaces.items()
                                  if workspace != 'Overview' for category in types)
    common = dict(default_channel='Root', actor_scope='single',
                  recommended_workflow='manual_primary', implementation_status='manual',
                  temporal_kind='interval', uses_object_reference=True,
                  evidence_mode='Manual observation relative to a named object or region. '
                                'No mesh, prop trajectory or geometric model is required.')
    state_rule = ('Mark the interval in which the actor occupies the stated position '
                  'relative to the named target. End when that relation changes or '
                  'cannot be judged. Use a consistent whole-person position reference; '
                  'a reaching hand alone does not move the person into a new region.')
    state_zh = ('标人物整体与所选物体的关系成立的区间，在关系改变或无法判断时结束。'
                '人物位置使用一致的身体／地面参照，不因一只手伸过去就改变整个人的位置标签。')
    motion_rule = ('Start at the actor movement that establishes the named relative '
                   'change; end at completion, a clear stop or a change of movement. '
                   'A moving target alone does not establish actor movement. '
                   'Exclude the subsequent held spatial state.')
    motion_zh = ('从人物产生所述相对变化的运动开始，到完成、明确停止或运动改变结束；'
                 '物体单独移动不算人物的该项运动，不包含随后保持的位置状态。')
    categories[state] = dict(common,
        description='Whole-person position relative to one or two registered named objects or regions, independent of contact, support and social meaning.',
        description_zh='人物整体相对于一个或两个已命名物体／区域的位置，区别于接触、支撑及社会含义。',
        boundary_rule=state_rule, boundary_rule_zh=state_zh, semantic_kind='spatial_state')
    categories[motion] = dict(common,
        description='Actor movement relative to a registered named object or region. Target identity does not require a 3D model.',
        description_zh='人物相对于已命名物体或区域的移动，无需物体三维模型即可人工标注。',
        boundary_rule=motion_rule, boundary_rule_zh=motion_zh, semantic_kind='spatial_motion')
    for category in (state, motion):
        presets[category] = []
        add(category, 'Unlabeled', '未选择标签',
            'An unfinished annotation; it does not assert the relation is absent.',
            group='Uncertainty', rule='Keep the draft while editing; choose a label before Accept.',
            auto_method='Manual placeholder; not a detection or reviewed absence.',
            semantic_kind='placeholder')
        info[(category, 'Unlabeled')].update(
            description_zh='尚未选择标签的草稿，不代表该关系不存在。',
            boundary_rule_zh='编辑时保留草稿，Accept 前选择标签。',
            uses_object_reference=True, introduced_in='0.5.3')

    frame = (' Choose Object front for a defined intrinsic object orientation, or '
             'Scene directions for a fixed convention recorded in project/object '
             'notes. No 3D model is required. Do not silently change reference '
             'when the camera or person turns.')
    frame_zh = ('按物体自身已定义的正面，或项目／物体备注约定的固定场景方向判断；'
                '不要求三维模型，不随人物转身或摄像机切换而悄悄改变参照。')
    rows = [
        ('in front of object', '在物体前方', 'Direction',
         'The actor occupies the front-side region of the named object under the selected reference frame.' + frame,
         '人物整体位于所选物体的前方区域。' + frame_zh, ['in front of', '柜台前方']),
        ('behind object', '在物体后方', 'Direction',
         'The actor occupies the rear-side region of the named object under the selected reference frame.' + frame,
         '人物整体位于所选物体的后方区域。' + frame_zh, ['behind', '物体后面']),
        ('left of object', '在物体左侧', 'Direction',
         'The actor occupies the left-side region of the named object under the selected reference frame. Left is not automatically the actor or camera left.' + frame,
         '人物整体位于所选物体的左侧；不默认指人物自己的左手侧或画面左侧。' + frame_zh, ['left of', '左边']),
        ('right of object', '在物体右侧', 'Direction',
         'The actor occupies the right-side region of the named object under the selected reference frame. Right is not automatically the actor or camera right.' + frame,
         '人物整体位于所选物体的右侧；不默认指人物自己的右手侧或画面右侧。' + frame_zh, ['right of', '右边']),
        ('beside object', '在物体旁边', 'Proximity',
         'The actor occupies an alongside position beside the named object. This broad side placement does not require immediate adjacency or contact. Use one specificity level for the same proximity observation.',
         '人物整体位于物体旁侧，可有一定间隔，不要求紧贴或接触。同一邻近关系选择一种合适粒度，不同时重复标旁边、紧邻和附近。', ['beside', 'alongside object', '旁边']),
        ('next to object', '紧邻物体／挨着物体', 'Proximity',
         'The actor is immediately adjacent to the named object under the project convention. A small gap may remain; contact or body support is not implied. Do not add a broader near/beside label for the same observation.',
         '人物整体紧邻物体，允许保留小间隙；不据此断言接触或借物体支撑。采用项目一致的邻近约定，同一观察不再重复叠加附近／旁边。', ['adjacent to object', 'next to', '挨着', '紧挨着']),
        ('near object', '在物体附近', 'Proximity',
         'The actor is near the named object under the project qualitative or measured-distance convention, without a more specific direction or adjacency claim. No universal numerical cutoff is imposed.',
         '按项目一致的定性或距离标准，人物整体位于物体附近，未进一步限定方向或紧邻程度；软件不强加统一数值阈值。', ['near', '附近']),
        ('far from object', '离物体较远', 'Proximity',
         'The actor is far from the named object under the project qualitative or measured-distance convention. This state is different from actively moving away.',
         '按项目一致的定性或距离标准，人物整体离物体较远；这是位置状态，区别于正在退离物体。', ['far from', '远离物体的状态']),
        ('between objects', '在两个物体之间', 'Multiple targets',
         'The actor occupies the spatial gap or intervening region between two distinct named objects. Register both targets. Exact equidistance is not required, and this is not merely being inside one region.',
         '人物整体位于两个不同已命名物体的间隙或中间区域，需要分别选择两个目标；不要求严格等距，也不等同于在单一区域内部。', ['between', '两者之间', '两个物体中间']),
        ('inside object region', '在命名区域内部', 'Region',
         'The actor is inside the meaningful region represented by the named target, such as a booth or waiting area. Name the region explicitly; this does not mean physically inside a solid counter or other solid body.',
         '人物整体在所选命名区域内部，例如隔间、等候区。应给区域明确命名，不解释为人物位于柜台等实体物体内部。', ['inside region', 'within region', '区域内', '里面']),
        ('outside object region', '在命名区域外部', 'Region',
         'The actor is outside the meaningful region represented by the named target. The region boundary must be interpretable under the project protocol; absence of a model is not evidence of being outside.',
         '人物整体在所选命名区域外部；区域边界需按项目约定可判断，不能因没有物体模型就认定为区域外。', ['outside region', '区域外', '外面']),
        ('at center of object region', '在命名区域中央', 'Region',
         'The actor occupies the approximate central part of a named meaningful region under the project convention. This is not exact geometric-center measurement and does not refer to the center of a solid object.',
         '人物整体处于命名区域的大致中央，按项目约定判断，不表示精确几何中心测量，也不指实体物体内部的中心。', ['center of region', 'middle of region', '区域中央', '区域中间']),
        ('spatial relation uncertain', '人与物体位置关系不确定', 'Uncertainty',
         'The person-to-object position cannot be classified reliably. Keep the target when known; an unavailable target may remain unspecified. Do not fill unreviewed gaps with this label.',
         '人物与物体的位置关系无法可靠分类；知道目标时保留目标，不知道时允许留空。不用此项填满未审阅空隙。', ['object spatial relation uncertain']),
    ]
    movement_rows = [
        ('move toward object', '向物体接近', 'Relative movement',
         'The actor moves so that their whole-person position becomes closer to the named target. This does not require reaching, contact or an intention to use the object; target motion alone is insufficient.',
         '人物自身移动，使整体位置向所选目标接近；不要求伸手、接触或使用意图，仅物体移动不足以成立。', ['approach object', 'approach counter', '接近物体']),
        ('move away from object', '从物体退离', 'Relative movement',
         'The actor moves so that their whole-person position becomes farther from the named target. No social avoidance or rejection is inferred.',
         '人物自身移动，使整体位置离所选目标更远，不推断社会回避或拒绝。', ['recede from object', '退离物体']),
        ('pass by object', '从物体旁经过', 'Relative movement',
         'The actor moves past the named object, continuing beyond it. Annotate the observable passage, not the whole walk or an inferred destination.',
         '人物从所选物体旁经过并继续越过它，标实际经过过程，不延长到整段行走或推断目的地。', ['walk past object', '经过物体']),
        ('move around object', '绕物体移动', 'Relative movement',
         'The actor follows a path around the named object. A complete circuit is not required; merely turning the torso or the target rotating is insufficient.',
         '人物沿所选物体周围绕行，不要求绕满一圈；仅转动躯干或物体自身旋转不足以成立。', ['go around object', '绕行']),
        ('enter object region', '进入命名区域', 'Region transition',
         'The actor moves from outside to inside the meaningful region represented by the named target. Mark the entry transition; the subsequently maintained inside state is separate.',
         '人物从命名区域外移动进入区域内，标进入转换过程，随后保持在内部的状态另记。', ['enter region', '进入区域']),
        ('leave object region', '离开命名区域', 'Region transition',
         'The actor moves from inside to outside the meaningful region represented by the named target. Mark the exit transition, not the whole following walk.',
         '人物从命名区域内部移到外部，标离开转换过程，不延伸到其后整个行走区间。', ['exit region', 'leave region', '离开区域']),
        ('object-relative movement uncertain', '相对物体移动不确定', 'Uncertainty',
         'Actor movement relative to an object or region is observable but cannot be classified reliably. Keep the target when known; do not infer a destination or fabricate an unknown target.',
         '可观察到人物相对于物体或区域的运动，但无法可靠分类；知道目标时保留目标，不推断目的地或编造未知目标。', ['uncertain object-relative movement']),
    ]
    for category, entries in ((state, rows), (motion, movement_rows)):
        for name, zh, group, description, description_zh, aliases in entries:
            rule = categories[category]['boundary_rule']
            rule_zh = categories[category]['boundary_rule_zh']
            if name == 'spatial relation uncertain':
                rule = ('Mark the reviewed interval in which the position relation '
                        'cannot be classified reliably. End when classification '
                        'becomes possible or observation ends; do not fill unreviewed gaps.')
                rule_zh = '标已审阅但位置关系无法可靠判断的区间，在能明确分类或观察结束时结束；不覆盖未审阅空隙。'
            elif name == 'object-relative movement uncertain':
                rule = ('Mark reviewed actor movement whose object-relative type '
                        'cannot be classified reliably. End when movement stops, '
                        'classification becomes possible or observation ends; '
                        'do not fill unreviewed gaps.')
                rule_zh = '标已审阅且确有运动但相对物体的移动类型无法可靠分类的区间；在运动停止、能明确分类或观察结束时结束，不覆盖未审阅空隙。'
            add(category, name, zh, description, group=group, parts=['Root', 'Full Body'],
                rule=rule, aliases=aliases, auto_mode='manual',
                auto_method='Manual annotation against named objects/regions. No automatic '
                            'geometry, distance, region or relation detector is connected; '
                            'registration alone does not supply such measurements.')
            info[(category, name)].update(
                description_zh=description_zh, boundary_rule_zh=rule_zh,
                uses_object_reference=True, introduced_in='0.5.3',
                requires_second_object=name == 'between objects',
                requires_reference_frame=group == 'Direction')
