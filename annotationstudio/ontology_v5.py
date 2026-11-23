"""Additive v0.5 vocabulary: observable events, participant relations and affect.

This module contains vocabulary and guidance only. It does not implement any
new classifier, infer a participant's private mental state or migrate records.
Historical category/name identities remain available in the main ontology.
"""


def extend_ontology(workspaces, categories, presets, info, legacy, add):
    """Extend the initialized v0.4 dictionaries without changing stored IDs."""
    workspaces['Motion'] = ('Motion Primitive', 'Body Posture', 'Hand Behavior',
                            'Locomotion', 'Whole-body Action', 'Gait Pattern', 'Activity Relation')
    workspaces['Speech'] = ('Speaking', 'Speech Turn', 'Turn Transition', 'Speech Timing',
                            'Speech Disfluency', 'Vocal Event', 'Audio Activity', 'Dialogue Event')
    workspaces['Social'] = ('Interaction Event', 'Physical Interaction', 'Cognitive State Expression')
    workspaces['Overview'] = tuple(category for workspace, types in workspaces.items()
                                    if workspace != 'Overview' for category in types)

    new_types = [
        ('Whole-body Action', 'A complete observable whole-body action or balance event. Local primitives, sustained posture and interpersonal roles remain independently annotatable.',
         'Full Body', 'single', 'synchronized video / body kinematics; support evidence where required',
         'Mark the complete action from its first discriminating movement to completion or a clear change. Use each label boundary rule; do not extend into the subsequent held posture.',
         '标从首个可辨认动作到完成或明确改变的完整过程；使用各标签专用边界，不延伸到其后保持的姿态。',
         'automatic_primary', 'planned_rule', 'whole_body_action'),
        ('Gait Pattern', 'Observable gait quality during a locomotor bout, independent of travel direction, cause, diagnosis and emotion.',
         'Full Body', 'single', 'video / successive lower-limb and root kinematics with valid tracking',
         'Mark the part of the locomotor bout in which the gait feature is consistently observable. End on a clear pattern change or loss of usable evidence.',
         '标步行或移动中该步态特征持续可观察的区间；在特征改变或证据不可用时结束。',
         'automatic_primary', 'planned_rule', 'gait_pattern'),
        ('Physical Interaction', 'Observable bodily contact, support or physically directed action between people. A directed record identifies initiator/helper and recipient; a pair record is reserved for a genuinely mutual description.',
         'Dyadic', 'single', 'video with visible interpersonal action/contact; calibrated geometry may assist',
         'Mark the observed interpersonal action or maintained relation. Separate an attempted action from its outcome and do not infer contact from distance alone.',
         '标可观察的对人动作或持续身体关系；尝试与结果分开记录，不由距离接近推断接触。',
         'manual_primary', 'manual', 'physical_interaction'),
        ('Cognitive State Expression', 'An expressed or visibly displayed cognitive/appraisal state, attributed to an actor with evidence and optional target. Script intent and private mental state are separate records.',
         'Dyadic', 'single', 'audible utterances / observable behavior and interaction context; note the evidence source',
         'Mark only the contribution or behavioral episode supporting the interpretation. Do not propagate a hidden state through silent or unobserved time.',
         '只标支持该解释的话语或行为片段；不把隐藏心理状态延伸到静默或不可观察区间。',
         'manual_primary', 'manual', 'cognitive_expression'),
        ('Speech Disfluency', 'Observable disruptions in speech production such as filled pauses, repetition, cut-offs and self-correction. Ordinary silent timing intervals remain in Speech Timing.',
         'Speech', 'single', 'audio with optional checked transcript; speaker attribution must be explicit',
         'Mark the audible disfluent material and, where specified, its immediate repair. Keep surrounding ordinary pauses in Speech Timing; disfluency alone does not establish hesitation or affect.',
         '标可听见的不流利成分及定义要求的紧接修正；普通静默另在 Speech Timing 标注，不由不流利直接推断犹豫或情绪。',
         'assisted', 'planned_model', 'speech_disfluency'),
    ]
    for category, description, channel, scope, evidence, rule, rule_zh, workflow, implementation, semantic in new_types:
        categories[category] = dict(description=description, default_channel=channel, actor_scope=scope,
                                    evidence_mode=evidence, boundary_rule=rule, boundary_rule_zh=rule_zh,
                                    recommended_workflow=workflow, implementation_status=implementation,
                                    temporal_kind='interval', semantic_kind=semantic)
        presets[category] = []
        add(category, 'Unlabeled', '未选择标签',
            'An unfinished annotation with no semantic label selected; it does not mean the behavior is absent.',
            group='Uncertainty', rule='Keep the provisional interval while editing and select a meaningful label before Accept.',
            recommended_workflow='manual_primary', implementation_status='manual', semantic_kind='placeholder')
        info[(category, 'Unlabeled')].update(
            description_zh='尚未选择语义标签的草稿，不表示该行为不存在。',
            boundary_rule_zh='编辑时保留暂定区间，在接收前选择有意义的标签。',
            auto_method='Manual placeholder; not a detector output or a reviewed absence.')

    motion_rule = 'Start at the first sustained movement in the stated direction; end at a clear stop, reversal or change of form. Exclude the subsequently held configuration.'
    motion_rule_zh = '从所述方向的明确运动开始，在停止、反向或形式改变时结束，不包含随后保持的姿态。'
    state_rule = 'Start when the stated configuration is established and end when it clearly ceases. Exclude transitions and preserve uncertainty under occlusion.'
    state_rule_zh = '从所述姿态建立开始，在其明确解除时结束；排除转换过程，遮挡时保留不确定。'
    contact_rule = 'Start when the described contact or bodily relation is visibly established; end at separation or a clear relation change. Do not fill occluded gaps as proven contact.'
    contact_rule_zh = '从可见接触或身体关系建立开始，到分离或关系改变结束；不把遮挡空隙补成已确认接触。'
    action_rule = 'Start at the first action contributing to the stated operation and end at completion, abandonment or a clear change. Record the observed outcome separately.'
    action_rule_zh = '从构成该操作的首个动作开始，到完成、放弃或明确改变结束；结果另行记录。'
    expression_rule = categories['Cognitive State Expression']['boundary_rule']
    expression_rule_zh = categories['Cognitive State Expression']['boundary_rule_zh']

    def put(category, group, parts, rows, *, rule=None, rule_zh=None,
            workflow=None, implementation=None, semantic=None, evidence=None):
        """Rows carry explicit English/Chinese meaning and optional boundaries."""
        for row in rows:
            name, zh, description, description_zh, *tail = row
            options = tail[0] if tail else {}
            row_rule = options.get('rule', rule or categories[category]['boundary_rule'])
            row_rule_zh = options.get('rule_zh', rule_zh or categories[category].get('boundary_rule_zh',
                '仅标定义所述行为或关系的实际可观察区间，改变、结束或证据不足时停止。'))
            row_impl = options.get('implementation', implementation or categories[category]['implementation_status'])
            row_workflow = options.get('workflow', workflow or categories[category]['recommended_workflow'])
            add(category, name, zh, description, group=group, parts=options.get('parts', parts),
                rule=row_rule, evidence=options.get('evidence', evidence), aliases=options.get('aliases', ()),
                recommended_workflow=row_workflow, implementation_status=row_impl,
                semantic_kind=options.get('semantic', semantic), auto_mode='manual',
                auto_method={
                    'planned_rule': 'No detector for this new label is implemented. Future candidates require validated body mapping, geometry or signal rules and review on representative data.',
                    'planned_model': 'No detector for this new label is connected. Future model assistance requires explicit integration and evaluation; current annotation is manual.',
                    'manual': 'Manual evidence-based annotation. The label does not infer an internal state, intention or unobserved outcome.',
                }[row_impl])
            meta = info[(category, name)]
            meta.update(description_zh=description_zh, boundary_rule_zh=row_rule_zh,
                        introduced_in='0.5.0')
            if category == 'Action / HOI':
                meta['uses_object_reference'] = True
            if category in ('Physical Interaction', 'Cognitive State Expression'):
                meta['target_kind'] = 'participant'
            for key in ('actor_role', 'target_role_name', 'relation_symmetry'):
                if key in options:
                    meta[key] = options[key]

    # Additional local forms use the selected primary channel for side.
    put('Motion Primitive', 'Shoulder and forearm movement', ['Left Arm', 'Right Arm'], [
        ('raise shoulder', '抬肩', 'The selected shoulder elevates relative to the trunk; a social shrug meaning is not implied.', '所选肩相对躯干上提，不推断耸肩的社会意义。', {'aliases': ['shoulder elevation', 'shrug shoulder (kinematic)']}),
        ('lower shoulder', '落肩', 'The selected shoulder moves downward relative to the trunk after elevation or from its preceding position.', '所选肩相对躯干下落，区别于全身整体下降。', {'aliases': ['shoulder depression']}),
        ('protract shoulder', '肩前伸', 'The selected shoulder girdle moves forward around the trunk; whole-body translation is excluded.', '所选肩带相对躯干前移，排除全身平移。'),
        ('retract shoulder', '肩后收', 'The selected shoulder girdle moves backward toward a retracted configuration.', '所选肩带相对躯干向后收回。'),
        ('forearm pronation', '前臂旋前', 'The selected forearm rotates about its long axis toward pronation; adequate wrist/forearm orientation evidence is required.', '所选前臂绕长轴旋前，需要可靠的腕与前臂朝向证据。'),
        ('forearm supination', '前臂旋后', 'The selected forearm rotates about its long axis toward supination; adequate wrist/forearm orientation evidence is required.', '所选前臂绕长轴旋后，需要可靠的腕与前臂朝向证据。'),
        ('circle arm (kinematic)', '手臂绕环（运动学）', 'The selected arm traces a sustained circular or approximately circular path relative to the torso.', '所选手臂相对躯干形成持续环形或近似环形轨迹。', {'rule': 'Mark the observed circular movement bout, including successive cycles until a clear stop or pattern change; do not split every directional reversal.', 'rule_zh': '标完整绕环动作段，可含连续多圈；在明确停止或模式改变时结束，不按每次方向反转拆分。'}),
    ], rule=motion_rule, rule_zh=motion_rule_zh)
    put('Motion Primitive', 'Hand and finger movement', ['Left Hand', 'Right Hand'], [
        ('wrist radial deviation', '手腕桡偏', 'The hand moves toward the thumb side relative to the forearm, with laterality supplied by the selected hand channel.', '手相对前臂向拇指侧偏转，左右由所选手部轨道给定。'),
        ('wrist ulnar deviation', '手腕尺偏', 'The hand moves toward the little-finger side relative to the forearm.', '手相对前臂向小指侧偏转。'),
        ('spread fingers', '张开手指', 'The fingers separate from one another; this is finger abduction rather than a change in arm position.', '手指彼此分开，描述指间分离而非手臂位移。'),
        ('bring fingers together', '并拢手指', 'The fingers move toward one another from a spread configuration.', '手指从分开状态向彼此靠拢。'),
        ('flex fingers', '屈曲手指', 'One or more visible fingers bend at their joints; identify individual digits in notes when required.', '一个或多个可观察手指的关节发生屈曲，需要时在备注注明具体手指。'),
        ('extend fingers', '伸展手指', 'One or more visible fingers straighten at their joints; do not infer release of an object.', '一个或多个可观察手指的关节伸直，不据此推断松开物体。'),
    ], rule=motion_rule, rule_zh=motion_rule_zh,
        evidence='resolved hand/finger video or reliable detailed hand skeleton; coarse wrist tracking alone is insufficient')
    put('Motion Primitive', 'Ankle and foot movement', ['Left Leg', 'Right Leg'], [
        ('ankle dorsiflexion', '踝背屈', 'The selected foot rotates toward the shin at the ankle; whole-leg lifting is not sufficient evidence.', '所选足在踝关节处向小腿前侧靠拢，整腿抬起不能替代踝部证据。'),
        ('ankle plantarflexion', '踝跖屈', 'The selected foot rotates away from the shin at the ankle, as in pointing the foot.', '所选足在踝关节处远离小腿前侧转动，呈绷脚方向。'),
        ('foot inversion', '足内翻', 'The selected sole turns inward relative to the lower leg, when foot orientation is resolved.', '在足朝向可辨认时，所选足底相对小腿向内侧翻转。'),
        ('foot eversion', '足外翻', 'The selected sole turns outward relative to the lower leg, when foot orientation is resolved.', '在足朝向可辨认时，所选足底相对小腿向外侧翻转。'),
        ('tap foot (kinematic)', '脚部反复轻点（运动学）', 'A repeated small foot-lift and return pattern is visible; impact sound, nervousness and impatience are not inferred.', '可见脚部反复小幅抬起与回落，不推断敲击声音、紧张或不耐烦。', {'rule': 'Mark the repeated tapping bout from first to last observed cycle, ending at a clear pause or pattern change.', 'rule_zh': '从第一轮到最后一轮标完整反复轻点段，在明确停顿或模式改变时结束。'}),
    ], rule=motion_rule, rule_zh=motion_rule_zh)

    put('Body Posture', 'Whole-body support and seated configurations', ['Full Body', 'Root', 'Left Leg', 'Right Leg'], [
        ('sitting on floor', '坐地', 'A seated configuration with the pelvis visibly supported by the floor; use sitting when the support surface is unknown.', '骨盆由地面支撑的坐姿；支撑面不明时用一般坐姿。'),
        ('sitting cross-legged', '盘腿坐', 'A seated configuration with both legs folded and crossed in front of the pelvis; distinguish from one thigh resting over the other on a chair.', '坐姿中双腿在骨盆前方折叠交叉，区别于椅上单腿搭另一腿的二郎腿。', {'aliases': ['cross-legged sitting', 'tailor sitting']}),
        ('long sitting', '长坐', 'A seated configuration with both legs extended forward from the pelvis; knees may have a small natural bend.', '坐姿中双腿由骨盆向前伸展，膝可有轻微自然弯曲。'),
        ('side sitting', '侧坐', 'A seated configuration with both bent legs arranged mainly to one side of the pelvis.', '坐姿中两条屈曲腿主要放在骨盆同一侧。'),
        ('reclined sitting', '后仰坐姿', 'The pelvis remains seated while the torso is reclined; support on a particular object is recorded separately in HOI.', '骨盆保持坐姿而躯干后仰，依靠具体物体的关系另在 HOI 记录。'),
        ('on all fours', '四点跪撑', 'Both hands and both knees visibly support the body in a quadruped configuration; support cannot be proven from low joint height alone.', '双手与双膝可见地支撑身体；关节高度低本身不能证明支撑。', {'parts': ['Full Body', 'Root', 'Left Hand', 'Right Hand', 'Left Leg', 'Right Leg']}),
        ('hands-and-feet support', '双手双脚支撑', 'The body is supported on both hands and feet with knees off the support surface; identify additional support separately.', '身体由双手双脚支撑，膝部离开支撑面；额外支撑另行记录。', {'parts': ['Full Body', 'Root', 'Left Hand', 'Right Hand', 'Left Leg', 'Right Leg']}),
        ('standing on tiptoes', '踮脚站立', 'A standing configuration with both heels raised and the forefeet providing visible support.', '双足后跟抬起、前脚掌可见地支撑身体的站姿。'),
    ], rule=state_rule, rule_zh=state_rule_zh, workflow='assisted',
        evidence='video / body configuration with visible or calibrated support evidence')
    put('Body Posture', 'Arm configurations', ['Left Arm', 'Right Arm'], [
        ('arm extended sideways', '手臂向侧方伸展', 'The selected arm is maintained away from the torso to its side; the elbow may be slightly bent.', '所选手臂保持向躯干侧方伸出，肘可稍弯。'),
        ('arm behind back', '手臂放在背后', 'The selected arm is maintained behind the torso; another hand or object contact is not implied.', '所选手臂保持在躯干后方，不推断与另一手或物体接触。'),
    ], rule=state_rule, rule_zh=state_rule_zh)

    put('Hand Behavior', 'Hand configurations', ['Left Hand', 'Right Hand'], [
        ('open palm', '手掌张开', 'The hand is held open with fingers visibly unfolded; this is a maintained configuration, not the opening movement.', '手保持张开、手指展开的形态，区别于张手运动过程。'),
        ('closed fist', '握拳保持', 'The fingers are held curled into a fist; anger, threat and object grasp are not inferred.', '手指保持蜷曲成拳，不推断愤怒、威胁或握住物体。'),
        ('index finger extended', '食指伸出保持', 'The index finger is extended while other fingers are more flexed; a communicative pointing function is separate.', '食指伸出而其余手指相对屈曲，指示功能另行判断。'),
        ('thumb raised', '拇指竖起保持', 'The thumb is extended upward relative to the hand configuration; approval is not inferred.', '拇指相对手型竖起，不推断赞同或认可。'),
        ('pinch configuration', '捏合手型', 'The thumb and one or more fingertips are held close together or visibly touching; an object grip is a separate HOI relation.', '拇指与一个或多个指尖保持靠近或可见接触，捏住物体另在 HOI 记录。'),
    ], rule=state_rule, rule_zh=state_rule_zh, semantic='hand_configuration')
    put('Hand Behavior', 'Self-contact', ['Left Hand', 'Right Hand'], [
        ('hand to neck', '手接触颈部', 'The selected hand visibly contacts the actor\'s own neck; motive and emotion are not inferred.', '所选手可见地接触本人颈部，不推断动机或情绪。'),
        ('hand to chest', '手接触胸前', 'The selected hand visibly contacts the actor\'s own chest region.', '所选手可见地接触本人胸前区域。'),
        ('hand to opposite arm', '手接触另一侧手臂', 'The selected hand visibly contacts the actor\'s other arm; identify rubbing or scratching separately if needed.', '所选手可见地接触本人另一侧手臂，需要时另标揉擦或抓挠动作。'),
        ('hand to leg', '手接触腿部', 'The selected hand visibly contacts the actor\'s own leg; the existing hands-in-lap posture remains available for that configuration.', '所选手可见地接触本人腿部，双手放膝上的姿态仍使用相应姿态标签。'),
        ('scratch self', '抓挠自己', 'A hand or fingers make an observable scratching motion on the actor\'s own body; itch or discomfort is not inferred.', '手或手指在本人身体上作可见抓挠动作，不推断瘙痒或不适。', {'semantic': 'body_behavior', 'rule': action_rule, 'rule_zh': action_rule_zh}),
        ('rub own body', '揉擦自身', 'The hand rubs the actor\'s own body in repeated or sustained contact, distinct from hand rubbing against the other hand.', '手在本人身体上反复或持续揉擦，区别于双手互相搓动。', {'semantic': 'body_behavior', 'rule': action_rule, 'rule_zh': action_rule_zh}),
    ], rule=contact_rule, rule_zh=contact_rule_zh, semantic='self_contact')
    put('Hand Behavior', 'Repetitive hand actions', ['Left Hand', 'Right Hand', 'Hands'], [
        ('clap hands (kinematic)', '拍手（运动形式）', 'The actor repeatedly brings their own palms together and separates them; applause or approval requires context.', '本人双掌反复合拢接触后分开；鼓掌喝彩或认可功能需要上下文。'),
        ('repetitive hand fidgeting', '手部反复小动作', 'Repeated small hand or finger movements form a visible bout that cannot be described more specifically; anxiety and boredom are not inferred.', '可见一段反复的小幅手或手指动作，无法更具体命名；不推断焦虑或无聊。'),
    ], rule='Mark one complete repeated-action bout from the first to last visible cycle; split at a clear pause or change of form.',
        rule_zh='从第一轮到最后一轮标完整重复动作段，在明确停顿或形式改变时拆分。')

    put('Locomotion', 'Travel and stepping', ['Root', 'Full Body', 'Left Leg', 'Right Leg'], [
        ('walking backward', '后退行走', 'The actor walks with displacement mainly opposite their body-facing direction; this does not establish social withdrawal.', '人物主要向身体朝向的反方向行走，不据此判断退出互动。'),
        ('side stepping', '侧向迈步', 'The actor takes steps mainly to the side of their body-facing direction.', '人物主要沿身体侧向迈步移动。'),
        ('running', '跑动', 'A running locomotor pattern is visible; distinguish it from merely faster walking using the available gait evidence.', '可见跑动步态，需要步态证据区别于仅仅加快的行走。'),
        ('crawling', '爬行', 'The actor moves using a low-body support pattern involving hands and lower limbs; specify the visible support form in notes.', '人物以手与下肢参与的低位支撑方式移动，在备注记录可见支撑形式。'),
        ('ascending steps', '上台阶', 'The actor progresses upward over one or more steps; annotate the movement without inventing an unseen stair or platform identity.', '人物跨越一个或多个台阶向上移动，不虚构不可见的阶梯或平台身份。'),
        ('descending steps', '下台阶', 'The actor progresses downward over one or more steps with controlled stepping.', '人物通过有控制的迈步沿一个或多个台阶向下移动。'),
        ('step over obstacle', '跨越障碍', 'A step visibly clears a barrier or obstacle; object identity may be linked separately when known.', '迈步可见地跨过障碍，已知物体身份可另行关联。'),
    ], rule=action_rule, rule_zh=action_rule_zh)
    put('Locomotion', 'Posture transitions', ['Full Body', 'Root', 'Left Leg', 'Right Leg'], [
        ('lie down', '躺下', 'The actor transitions into a lying configuration; the subsequent lying posture and support object remain separate.', '人物转换到卧姿，之后保持的卧姿与支撑物体另行标注。'),
        ('rise from lying to sitting', '从卧姿坐起', 'The actor moves from a lying configuration to an established seated configuration.', '人物从卧姿转变为已建立的坐姿。'),
        ('get up from floor', '从地面起身', 'A complete floor-to-standing transition, possibly through intermediate sitting or kneeling. This is a coarse alternative to separately labelling its stages, not an extra duplicate count.', '从地面低位到站立的完整转换，可经过坐或跪等中间姿态；这是整体粒度选择，不额外重复计数各阶段。'),
    ], rule='Start at the first movement out of the initial supported posture; end when the target configuration is established or the attempt is abandoned. Record assistance separately.',
        rule_zh='从离开初始支撑姿态的首个动作开始，到目标姿态建立或尝试放弃结束；是否受助另行记录。',
        workflow='assisted', evidence='video / full-body kinematics with posture and support evidence')

    put('Whole-body Action', 'Balance and falling', ['Full Body', 'Root', 'Left Leg', 'Right Leg'], [
        ('fall down', '摔倒', 'A visible falling descent of the body into a lower support configuration or interception by another person. The motion may be performed intentionally; injury and involuntary cause are not inferred.', '身体发生可见跌落，进入更低支撑姿态或被他人接住；动作可为有意表演，不推断受伤或非自愿原因。',
         {'aliases': ['falling', 'falling down'], 'rule': 'Start at the first clear falling descent; end at stable new support, interception, or the end of the falling phase before a distinct roll/recovery. Use action uncertain when controlled lowering cannot be distinguished.', 'rule_zh': '从首个明确跌落过程开始，到新的稳定支撑、被接住或独立翻滚／恢复前的跌落结束；无法区别有控制降低时保留不确定。', 'workflow': 'assisted'}),
        ('stumble', '绊步／短暂踉跄', 'A brief disrupted step with an observable corrective movement or ensuing fall; do not infer an unseen obstacle.', '短暂步态中断并伴可见纠正动作或随后跌倒，不推断不可见障碍。', {'rule': 'Mark the disrupted step and immediate correction; end when gait stabilizes or a separate falling phase begins.', 'rule_zh': '标异常迈步及紧接的纠正，在步态恢复或另一个跌落阶段开始时结束。'}),
        ('loss of balance', '失衡表现', 'Observable instability requiring a corrective body/step response or progressing into a fall. This is a movement description, not a force or clinical measurement.', '可见不稳定并需要身体／迈步纠正，或继续发展为跌倒；这是动作描述，不是力学或临床测量。', {'workflow': 'assisted', 'rule': 'Start at the first visible destabilization; end when correction, a fall or a new stable configuration resolves the episode. Use as a broader alternative when no more specific event is justified.', 'rule_zh': '从可见失稳开始，到纠正、跌倒或新稳定姿态使该过程结束；仅在不能更具体分类时使用这一较宽描述。'}),
        ('recover balance', '恢复平衡', 'A corrective body or step sequence visibly restores a stable configuration after instability.', '失稳后通过可见身体或迈步纠正恢复稳定姿态。', {'rule': 'Start at the corrective movement and end at restored stable support; do not include the preceding instability or an unrelated later step.', 'rule_zh': '从纠正动作开始，到恢复稳定支撑结束，不纳入此前失稳或之后无关迈步。', 'workflow': 'assisted'}),
    ])
    put('Whole-body Action', 'Whole-body movement patterns', ['Full Body', 'Root', 'Left Leg', 'Right Leg'], [
        ('jump', '跳跃', 'The actor propels the body off support and returns, with visible flight evidence; a toe rise alone is not a jump.', '身体蹬离支撑后返回，需可见腾空证据；仅踮脚不算跳跃。', {'rule': 'Mark propulsion through landing and its immediate stabilization; successive jumps may be separate cycles or one bout under the project protocol.', 'rule_zh': '标起跳到落地及紧接稳定的过程；连续跳按项目协议选单次或整段。'}),
        ('hop', '单脚跳', 'A jump-like cycle predominantly launched and landed on the same foot; keep the involved leg in body-part metadata.', '主要由同一只脚起跳并落地的跳动，在部位信息注明参与腿。', {'rule': 'Mark take-off through landing stabilization on the same foot; end on a change to another gait or support pattern.', 'rule_zh': '标同脚起跳到落地稳定，换步态或支撑形式时结束。'}),
        ('roll body', '身体翻滚', 'The body rolls around a support contact, changing the supported side or orientation.', '身体围绕支撑接触翻滚，改变支撑侧或朝向。', {'rule': action_rule, 'rule_zh': action_rule_zh}),
        ('duck body', '俯身闪避式降低', 'The head and upper body are lowered in a compact avoidance-like movement; an actual threat or intended avoidance is not inferred.', '头和上身紧凑地降低呈闪避式动作，不据此认定存在威胁或回避意图。', {'rule': 'Mark the lowering and immediate return when part of one movement; a maintained low posture is separately annotated.', 'rule_zh': '标降低及同一动作内紧接的恢复；保持低位姿态另标。'}),
        ('flinch-like movement', '骤缩式动作', 'A brief abrupt recoil or contraction of the body is visible; fear, pain and reflex origin are not inferred.', '可见短暂突然的退缩或收缩动作，不推断害怕、疼痛或反射原因。', {'rule': 'Mark the abrupt recoil and its immediate settling, excluding unrelated surrounding movement.', 'rule_zh': '标突然退缩及紧接稳定过程，排除周围无关动作。'}),
        ('sway body', '身体摆晃', 'Repeated lateral or multidirectional body sway is visible while the actor broadly maintains a location; gait quality is annotated separately during walking.', '人物大致保持位置时身体反复侧向或多方向摆晃，行走中的步态特征另标。'),
        ('rock body', '身体前后摇动', 'The body repeatedly rocks forward and backward around its current support configuration.', '身体围绕当前支撑姿态反复前后摇动。'),
        ('trembling movement', '身体颤动', 'Repeated small rapid body oscillations are visibly resolved and not explained by tracking noise; emotion or illness is not inferred.', '可辨认身体反复小幅快速振动，并排除跟踪噪声，不推断情绪或疾病。', {'workflow': 'assisted'}),
        ('stretch body', '全身伸展', 'A coordinated extension or lengthening pattern spans multiple body regions; the intended purpose is not inferred.', '多个身体区域协同呈伸展或拉长模式，不推断目的。', {'workflow': 'assisted'}),
        ('bow body (kinematic)', '鞠躬式躯体动作', 'A coordinated forward torso inclination and return forms a bow-like action; greeting, thanks and submission require separate context.', '躯干协调前倾并恢复形成鞠躬式动作，问候、感谢或服从功能另需上下文。', {'aliases': ['bowing']}),
        ('dance sequence', '舞蹈动作段', 'An observable coordinated movement sequence is identified as dancing from its movement form and context; mark specific local primitives separately only when required.', '结合运动形式与上下文判断为舞蹈的协调动作段，仅按研究需要另标具体局部动作。', {'workflow': 'manual_primary', 'implementation': 'manual'}),
    ], rule='Mark the complete observable movement bout; include repeated cycles until a clear stop or change of form. Do not split a rhythmic pattern at every reversal.',
        rule_zh='标完整可观察动作段，连续周期保留到明确停止或形式改变；不按每次反向拆开节律模式。')

    put('Gait Pattern', 'Observed gait qualities', ['Full Body', 'Root', 'Left Leg', 'Right Leg'], [
        ('staggering gait', '踉跄步态', 'Successive steps show visible instability, irregular lateral displacement or repeated corrections; this does not identify intoxication, disease or affect.', '连续迈步呈可见不稳、侧向轨迹不规则或反复纠正，不判断醉酒、疾病或情绪。', {'aliases': ['staggering', 'unsteady gait', '踉踉跄跄']}),
        ('shuffling gait', '拖步步态', 'Successive steps have low foot clearance and short sliding or dragging-like progression, when feet are sufficiently visible.', '在足部足够可见时，连续迈步离地低，呈短促滑移或拖步式前进。'),
        ('asymmetric gait', '不对称步态', 'Successive left and right steps visibly differ in timing, excursion or support pattern; no clinical cause is assigned.', '左右连续迈步的时序、幅度或支撑模式明显不同，不分配临床原因。', {'aliases': ['limping-like gait']}),
        ('tiptoe gait', '踮脚步态', 'Locomotion occurs with visibly raised heels and forefoot-dominant contact; distinguish it from a held tiptoe posture.', '移动中后跟可见抬起且以前足接触为主，区别于保持踮脚站姿。'),
        ('wide-based gait', '宽步基步态', 'Successive foot placements are visibly wider laterally than the project-defined ordinary walking reference for this actor.', '连续落足的左右间距明显大于项目为该人物定义的普通行走参照。'),
        ('narrow-based gait', '窄步基步态', 'Successive foot placements are visibly narrow relative to the project-defined actor reference; use uncertainty if perspective prevents comparison.', '连续落足左右间距相对项目人物参照明显较窄，视角妨碍比较时保留不确定。'),
        ('stop-start gait', '走停交替步态', 'The locomotor bout repeatedly alternates progression with distinct stops; hesitation or indecision is not inferred.', '一段移动反复在前进与明显停顿之间切换，不推断犹豫或难以决定。'),
        ('dragging one foot', '单足拖行', 'One foot visibly drags or remains unusually close to the surface during progression; identify the side without diagnosing a cause.', '移动时一足可见拖行或持续非常贴近表面，注明侧别而不诊断原因。'),
    ], rule=categories['Gait Pattern']['boundary_rule'], rule_zh=categories['Gait Pattern']['boundary_rule_zh'])

    # Human-human bodily relations are independent of object-oriented HOI.
    helper = {'actor_role': 'helper', 'target_role_name': 'recipient', 'relation_symmetry': 'directed'}
    put('Physical Interaction', 'Assistance and support', ['Full Body', 'Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
        ('assist partner to rise', '扶对方起身', 'The actor visibly provides bodily assistance while the partner attempts to rise. Success is an outcome, not a prerequisite for this event.', '行动者可见地提供身体帮助，使伙伴尝试起身；成功与否另记结果。', {**helper, 'aliases': ['help partner stand up', 'help someone up', '扶起来'], 'rule': 'Start at observable assistance directed at rising; end when support for that attempt ceases, the rise completes, or the attempt is abandoned. Do not include an earlier offer without bodily assistance.', 'rule_zh': '从针对起身的可观察身体帮助开始，到该帮助停止、起身完成或尝试放弃结束；不纳入此前尚未实际施助的提议。'}),
        ('support partner', '支撑对方身体', 'The actor visibly maintains bodily support for the partner; contact alone does not establish load-bearing support or a measured force.', '行动者可见地持续支撑伙伴；仅接触不能证明承重或具体受力。', {**helper, 'semantic': 'interpersonal_state', 'rule': contact_rule, 'rule_zh': contact_rule_zh}),
        ('stabilize partner', '扶稳对方', 'The actor makes a visible bodily intervention that steadies the partner during instability; note whether stabilization completes.', '行动者通过可见身体干预使不稳的伙伴趋于稳定，并记录是否完成稳定。', helper),
        ('catch falling partner', '接住跌落的对方', 'The actor intercepts a visibly falling partner and attempts to arrest or redirect the descent; outcome and continued support are separate.', '行动者拦接正在跌落的伙伴，尝试阻止或改变下落；结果与随后持续支撑另记。', helper),
        ('support partner while walking', '搀扶对方行走', 'The actor provides observable bodily support while the partner walks; each person\'s locomotion remains a separate annotation.', '伙伴行走时行动者提供可观察身体支撑，双方各自移动另标。', {**helper, 'semantic': 'interpersonal_state', 'aliases': ['assist walking', '搀扶'], 'rule': 'Mark the interval in which support and the partner\'s walking coexist; end on support release or transition to a stationary support event.', 'rule_zh': '标支撑与伙伴行走同时存在的区间，在解除支撑或转为静止支撑事件时结束。'}),
        ('assist partner to sit or lower', '帮助对方坐下或降低', 'The actor visibly assists the partner in lowering into a supported posture; the resulting posture is separate.', '行动者可见地帮助伙伴降低到有支撑姿态，结果姿态另记。', helper),
        ('lift partner', '抬起对方', 'The actor visibly raises the partner\'s body from its preceding support; do not infer an unobserved load or motive.', '行动者可见地将伙伴身体抬离原支撑，不推断不可观察的载荷或动机。', helper),
        ('carry partner', '抱／背着对方移动', 'The actor transports the partner while visibly supporting the partner\'s body; the carry form may be described in notes.', '行动者支撑伙伴身体并带其移动，具体抱背形式可在备注中记录。', {**helper, 'rule': 'Start when supported transport begins and end when transport stops or the partner is set down; stationary support is a separate state.', 'rule_zh': '从支撑下的运送开始，到运送停止或对方被放下结束；静止支撑另作状态。'}),
    ], rule=action_rule, rule_zh=action_rule_zh)
    put('Physical Interaction', 'Contact forms', ['Full Body', 'Left Arm', 'Right Arm', 'Left Hand', 'Right Hand'], [
        ('handshake', '握手', 'The participants visibly clasp hands and perform or maintain a handshake form; greeting or agreement function is separate.', '双方可见握住对方的手并形成握手动作或保持，问候或达成一致的功能另记。', {'relation_symmetry': 'mutual', 'rule': 'Start at established handshake contact and end at release; an unanswered offered hand is not completed handshake contact.', 'rule_zh': '从握手接触建立到松开；伸手但未被握住不算已建立握手接触。'}),
        ('hold partner hand', '牵／握住对方手', 'The actor visibly maintains hand-to-hand holding with the partner, without requiring an oscillating handshake pattern.', '人物可见地持续牵握伙伴手部，不要求握手式摆动。', {'relation_symmetry': 'mutual', 'semantic': 'interpersonal_state'}),
        ('hug partner', '拥抱对方', 'The actor places one or both arms around the partner in a visible embrace. Reciprocity and affect are separately evidenced.', '行动者用一臂或双臂环抱伙伴形成可见拥抱，是否回应及情感另需证据。', {'actor_role': 'initiator', 'target_role_name': 'recipient', 'relation_symmetry': 'directed'}),
        ('high five', '击掌', 'The participants make a visible raised palm-to-palm contact and separation; an uncompleted attempt can be recorded with an attempt outcome.', '双方抬掌接触后分离，未完成的尝试可在结果字段说明。', {'relation_symmetry': 'mutual', 'rule': action_rule, 'rule_zh': action_rule_zh}),
        ('fist bump', '碰拳', 'The participants bring closed fists into visible brief contact and separate.', '双方握拳短暂可见接触后分开。', {'relation_symmetry': 'mutual', 'rule': action_rule, 'rule_zh': action_rule_zh}),
        ('pat partner', '轻拍对方', 'The actor makes one or more visible light patting contacts on the partner; comfort or approval is a separate interpretation.', '行动者在伙伴身上作一次或多次可见轻拍，安慰或认可功能另行解释。', {'actor_role': 'initiator', 'target_role_name': 'recipient', 'relation_symmetry': 'directed', 'rule': action_rule, 'rule_zh': action_rule_zh}),
        ('touch partner', '接触对方', 'A visible interpersonal touch is established without a more specific supported contact form; identify body regions in notes.', '可见对人接触建立，但缺乏更具体接触形式依据，在备注注明身体部位。', {'actor_role': 'contacting actor', 'target_role_name': 'contacted partner', 'relation_symmetry': 'directed'}),
        ('lean on partner', '倚靠对方', 'The actor visibly maintains body support or leaning against the partner; proximity alone is insufficient.', '人物可见地保持对伙伴的身体倚靠或支撑关系，仅接近不足以成立。', {'actor_role': 'leaning actor', 'target_role_name': 'supporting partner', 'relation_symmetry': 'directed', 'semantic': 'interpersonal_state'}),
    ], rule=contact_rule, rule_zh=contact_rule_zh)
    put('Physical Interaction', 'Directed bodily actions', ['Full Body', 'Left Arm', 'Right Arm', 'Left Hand', 'Right Hand', 'Left Leg', 'Right Leg'], [
        ('push partner', '推对方', 'The actor applies an observable pushing action toward the partner. Displacement, aggression and success are not assumed.', '行动者对伙伴作可观察推动动作，不默认产生位移、攻击意图或成功。'),
        ('pull partner', '拉对方', 'The actor visibly pulls on the partner or a contacted body part; the partner\'s movement and outcome are separately recorded.', '行动者可见地拉动伙伴或接触的身体部位，伙伴运动及结果另记。'),
        ('guide partner by contact', '通过接触引导对方', 'The actor visibly directs the partner\'s movement through contact; intention requires the observed joint sequence rather than contact alone.', '行动者通过接触可见地引导伙伴运动，需双方动作过程支持，不能仅凭接触。'),
        ('restrain partner', '限制对方身体运动', 'Visible holding or blocking constrains the partner\'s attempted movement; playful or hostile motive is not inferred.', '可见抓持或阻挡限制伙伴试图进行的运动，不推断玩闹或敌意。'),
        ('strike partner', '击打对方', 'The actor performs a visibly directed striking action toward the partner; record attempted versus observed contact and do not infer injury.', '行动者朝伙伴作可见击打动作，区分尝试与观察到的接触，不推断受伤。', {'aliases': ['slap partner', 'punch partner']}),
        ('kick toward partner', '向对方踢腿', 'A kick-like action is visibly directed toward the partner; leg kinematics and observed contact/outcome remain separate.', '踢腿式动作可见地指向伙伴，腿部运动与接触／结果分别记录。'),
        ('release partner contact', '解除对人接触', 'The actor visibly ends a preceding handhold, grasp or support relation with the partner.', '行动者可见地解除此前牵握、抓持或支撑伙伴的关系。'),
    ], rule=action_rule, rule_zh=action_rule_zh)
    for name in ('push partner', 'pull partner', 'guide partner by contact', 'restrain partner',
                 'strike partner', 'kick toward partner', 'release partner contact'):
        info[('Physical Interaction', name)].update(actor_role='initiator', target_role_name='recipient', relation_symmetry='directed')

    put('Cognitive State Expression', 'Uncertainty and behavioral regulation', ['Full Body'], [
        ('hesitation display', '犹豫表现', 'Observable delayed, interrupted or repeatedly restarted behavior supports a hesitation interpretation in context; a silent pause alone is insufficient.', '结合上下文，延迟、中止或反复启动等可观察行为支持犹豫解释；仅静默停顿不足。', {'aliases': ['expressed hesitation', 'hesitation']}),
        ('uncertainty expressed', '表达不确定', 'The actor explicitly communicates uncertainty about a proposition, action or situation; record the relevant contribution.', '人物明确传达对命题、行动或情境的不确定，记录对应贡献。'),
        ('confusion expressed', '表达困惑', 'Words or converging contextual behavior visibly communicate difficulty making sense of the situation; a single facial or movement cue is insufficient.', '话语或相互支持的情境行为表达难以理解当前情境，单一面部或动作线索不足。'),
        ('understanding acknowledged', '表示理解', 'The actor explicitly indicates understanding of a message or situation; this is a communicated acknowledgment, not proof of internal comprehension.', '人物明确表示理解信息或情境，记录的是表达而非内部理解的证明。'),
        ('non-understanding expressed', '表达未理解', 'The actor explicitly communicates that a message, instruction or situation was not understood.', '人物明确表达未理解某个信息、指示或情境。'),
        ('deliberation expressed', '表达正在考虑', 'The actor explicitly states or clearly displays considering alternatives; inactivity alone does not establish deliberation.', '人物明确表示或清楚表现正在考虑选项，仅不活动不能证明思考。'),
        ('decision expressed', '表达决定', 'The actor communicates a choice or commitment among alternatives; record the expressed decision rather than inferring a private one.', '人物传达选项之间的选择或承诺，记录表达出的决定而不推断私下决定。'),
        ('reconsideration expressed', '表达改变主意', 'The actor explicitly revises a previously expressed choice or intention within the observable exchange.', '人物在可观察交流中明确修改此前表达的选择或意图。'),
        ('expectation mismatch expressed', '表达出乎预期', 'The actor communicates that an observed event differs from what was expected; a surprise affect tag requires its own evidence.', '人物传达实际事件与原先预期不符，惊讶情感仍需单独证据。'),
    ], rule=expression_rule, rule_zh=expression_rule_zh)
    put('Cognitive State Expression', 'Person recognition expressions', ['Full Body'], [
        ('identity query', '询问身份', 'The actor asks who the partner is or seeks identifying information; the question alone does not prove non-recognition.', '人物询问伙伴身份或识别信息，问题本身不能证明没有认出。'),
        ('recognition uncertainty expressed', '表达身份辨认不确定', 'The actor expresses uncertainty about whether or how they recognize the partner.', '人物表达是否认识或如何辨认伙伴的不确定。'),
        ('explicit non-recognition statement', '明确表达没认出', 'The actor explicitly states that they do not recognize the partner; this records the statement rather than verifying private belief.', '人物明确说未认出伙伴，记录该表达而非验证内心信念。', {'aliases': ['expressed non-recognition', 'did not recognize', '没有认出']}),
        ('incorrect identification', '可核查的误认表达', 'The actor identifies the partner as someone else and a known scene identity supports calling the identification incorrect; uncertainty is retained without that reference.', '人物把伙伴认作他人，且已知场景身份支持判定误认；没有该参照时保留不确定。'),
        ('recognition acknowledgment', '表示认出对方', 'The actor explicitly signals recognizing the partner or now connecting the partner to a known identity; this is separate from acknowledging a conversational contribution.', '人物明确表示认出伙伴或现在将其与已知身份联系起来，区别于确认收到一次会话贡献。'),
    ], rule=expression_rule, rule_zh=expression_rule_zh)

    put('Speech Disfluency', 'Audible disfluency forms', ['Speech'], [
        ('filled pause', '填充性停顿声', 'An audible filler such as uh or um occupies a hesitation-like speech position; its conversational function and cognitive interpretation remain separate.', '如 uh、um 等可听填充声出现在言语中，其会话功能和认知解释另行判断。', {'rule': 'Mark the filler\'s audible onset and offset, excluding adjacent silence and ordinary lexical material.', 'rule_zh': '标填充声的可听起止，不包含相邻静默或普通词语。'}),
        ('sound or syllable repetition', '语音／音节重复', 'A sound or syllable is immediately repeated during speech production; do not infer a clinical speech disorder.', '言语产生中语音或音节紧接重复，不推断临床言语障碍。'),
        ('word repetition', '词语重复', 'A word is immediately repeated in a disrupted production sequence; deliberate emphasis or rhetorical repetition requires contextual distinction.', '词语在不流利产生过程中紧接重复，需结合上下文区别有意强调或修辞重复。'),
        ('phrase repetition', '短语重复', 'A short phrase is restarted or immediately repeated during a disrupted speech sequence.', '短语在不流利话语中重新启动或紧接重复。'),
        ('sound prolongation', '语音拖长', 'A speech sound is audibly prolonged as part of disrupted production; intentional expressive lengthening remains a contextual alternative.', '语音作为不流利产生的一部分被可听拖长，有意表达性延长仍是备选解释。'),
        ('cut-off / false start', '中断／错误起始', 'The actor cuts off an unfinished word or phrase and either abandons it or starts again.', '人物中断未完成的词或短语，随后放弃或重新开始。', {'aliases': ['false start', 'aborted utterance'], 'rule': 'Mark the abandoned fragment from onset to audible cut-off; a subsequent repaired contribution is linked or annotated separately.', 'rule_zh': '标被放弃片段从起点到可听中止点，随后修正贡献可关联或另标。'}),
        ('self-correction', '自我修正', 'The actor replaces or repairs their own immediately preceding wording; this is the observable repair form rather than a judgment of factual truth.', '人物替换或修正自己刚说的话，记录修正形式而非判断事实真伪。', {'rule': 'Mark the repair contribution, retaining the replaced fragment as linked evidence or in notes. Do not extend across unrelated later corrections.', 'rule_zh': '标修正贡献，将被替换片段作为关联证据或备注保存，不跨越无关的后续修正。'}),
    ], rule='Mark the audible repeated or prolonged sequence from its first affected unit through the final affected unit; exclude surrounding normal speech.',
        rule_zh='从首个受影响成分到最后一个成分标可听重复或拖长段，排除周围正常言语。')

    # Expand existing semantic lists without multiplying posture × speech labels.
    put('Interaction Event', 'Communicative social actions', ['Dyadic'], [
        ('attention getting', '引起对方注意', 'The actor performs a contextual bid for the partner\'s attention; a movement alone or an Oculo gaze direction alone is insufficient.', '人物在上下文中作出引起伙伴注意的尝试，仅动作或注视方向不足。'),
        ('invitation', '邀请', 'The actor invites the partner to participate in an activity or interaction.', '人物邀请伙伴参与某活动或互动。'),
        ('agreement', '表示赞同', 'The actor communicates agreement with a proposition or proposal; a kinematic nod alone is insufficient.', '人物传达对命题或建议的赞同，单纯点头运动不足。'),
        ('disagreement', '表示不赞同', 'The actor communicates disagreement with a proposition or proposal; a head shake alone does not establish the function.', '人物传达对命题或建议的不赞同，单纯摇头不能确定功能。'),
        ('gratitude', '表达感谢', 'The actor communicates thanks for a contribution, object or action in the interaction.', '人物针对互动中的贡献、物品或行动表达感谢。'),
        ('apology', '道歉', 'The actor communicates an apology; remorse as an internal affect is not established by the action alone.', '人物作出道歉表达，仅该行为不能确定内心悔意。'),
        ('reassurance', '安抚／使安心的表达', 'The actor communicates reassurance directed at the partner; effectiveness and the recipient\'s affect are separately observed.', '人物向伙伴作使其安心的表达，是否有效及对方情感另行观察。'),
        ('comforting', '安慰', 'The actor performs a context-supported comforting contribution; bodily contact and perceived concern are independent layers.', '人物作上下文支持的安慰贡献，身体接触与可感知担忧属于独立层。'),
        ('encouragement', '鼓励', 'The actor encourages the partner to continue or undertake an action.', '人物鼓励伙伴继续或采取某行动。'),
        ('warning', '提醒危险或问题', 'The actor communicates a warning about a possible problem or hazard; actual danger need not be established.', '人物就可能问题或危险作出提醒，不要求危险已被证实。'),
        ('offer assistance', '提出帮助', 'The actor offers help to the partner; actual bodily assistance and acceptance are separate events.', '人物向伙伴提出帮助，实际身体帮助与是否接受另标。'),
        ('request assistance', '请求帮助', 'The actor asks the partner for help; absence of a response does not by itself mean refusal.', '人物请求伙伴帮助，无回应本身不等于拒绝。'),
        ('joint activity coordination', '共同活动协调', 'The participants observably coordinate contributions toward a shared activity supported by context; synchrony alone is insufficient.', '上下文支持双方围绕共同活动协调贡献，仅运动同步不足。'),
    ], rule=categories['Interaction Event']['boundary_rule'],
        rule_zh='从执行该社会功能的首个贡献开始，到贡献完成或停止结束；仅在有依据时明确发起者与对象。')
    put('Dialogue Event', 'Conversation management', ['Speech'], [
        ('question', '提问', 'The actor makes an information-seeking or questioning contribution; identity-specific questioning can be specified in Cognitive State Expression.', '人物作寻求信息或询问的会话贡献，身份相关提问可在认知表达层细分。'),
        ('answer', '回答', 'The actor provides a context-supported answer to a preceding question; temporal adjacency alone is insufficient.', '人物对前述问题作上下文支持的回答，仅时间相邻不足。'),
        ('clarification', '澄清', 'The actor clarifies a previous contribution to make its intended content more explicit.', '人物澄清此前贡献，使所表达内容更明确。'),
        ('confirmation request', '请求确认', 'The actor asks the partner to confirm a proposition or interpretation.', '人物要求伙伴确认某命题或理解。'),
        ('confirmation', '确认回应', 'The actor supplies an explicit confirmation in response to a confirmation request or uncertainty.', '人物针对确认请求或不确定作出明确确认回应。'),
        ('other-correction', '纠正对方表达', 'The actor offers a correction to the partner\'s preceding wording or claim; factual correctness is not inferred.', '人物对伙伴此前用词或主张作纠正表达，不推断其事实正确性。'),
        ('turn allocation', '指定下一位说话者', 'The actor explicitly invites or selects the partner to contribute next; the actual subsequent floor transfer is a separate event.', '人物明确邀请或指定伙伴接下来发言，实际随后交接另标。'),
        ('topic initiation', '开启话题', 'A contribution introduces a new topic under the project\'s discourse context; use notes to identify the topic.', '贡献在项目话语上下文中开启新话题，在备注说明话题。'),
        ('topic closure', '结束话题', 'A contribution observably closes the current topic; a silence alone does not establish closure.', '贡献可观察地结束当前话题，仅静默不能证明结束。'),
    ], rule=categories['Dialogue Event']['boundary_rule'],
        rule_zh='标执行该会话功能的话语或短交换本身，不扩展为整个话轮；对象需有上下文依据。')
    put('Gesture Type', 'Contextual gesture functions', ['Hands', 'Left Hand', 'Right Hand', 'Left Arm', 'Right Arm', 'Head', 'Torso'], [
        ('farewell wave', '告别挥手', 'A waving gesture performs farewell in context; its local motion form can independently be labelled as waving.', '挥手在上下文中执行告别功能，局部运动形式可另标挥动。'),
        ('beckoning gesture', '招手示意过来', 'A gesture invites the partner to approach or join; the directed meaning requires context.', '手势示意伙伴靠近或加入，方向含义需要上下文。'),
        ('stop / wait gesture', '示意停止／等待', 'A gesture communicates stop or wait to a recipient; an open palm by itself is only a hand configuration.', '手势向对象传达停止或等待，张掌本身只是手型。'),
        ('agreement gesture', '赞同手势', 'A visible gesture communicates agreement in context; a nod or thumb configuration alone is insufficient.', '可见手势在上下文中表达赞同，点头或拇指形态本身不足。'),
        ('refusal gesture', '拒绝手势', 'A visible gesture communicates refusal in context; distinguish it from kinematic head or hand movement.', '可见手势在上下文中表达拒绝，区别于单纯头或手的运动。'),
        ('uncertainty gesture', '不确定性手势', 'A gesture communicates uncertainty or lack of an answer in context; shoulder elevation alone does not establish the function.', '手势在上下文中表达不确定或不知道答案，抬肩本身不足以确定功能。'),
    ], rule=categories['Gesture Type']['boundary_rule'],
        rule_zh='标一个可解释的手势单位，可含准备与回收；独立功能手势分开，不跨无关停顿。')

    put('Action / HOI', 'Actions · transport and placement', ['Left Hand', 'Right Hand', 'Left Arm', 'Right Arm', 'Hands', 'Full Body'], [
        ('carry object', '携物移动', 'The actor transports an object while maintaining control of it; stationary holding is the existing hold object state.', '人物控制物体并带其移动，静止持有使用既有 hold object 状态。'),
        ('transfer object between own hands', '物体在本人双手间转移', 'Control of an object transfers between the actor\'s own hands; this is distinct from a partner handover.', '物体控制由本人一只手转到另一只手，区别于向伙伴交接。'),
        ('insert object', '放入／插入物体', 'The actor moves an object into a receptacle or opening; identify the moved object and note the destination separately.', '人物将物体放入容器或开口，选择被移动物体并另注目标位置。'),
        ('remove object from container', '从容器取出物体', 'The actor removes an object from a receptacle or enclosure; select the removed object and note the source.', '人物从容器或包围区域取出物体，选择被取物体并注明来源。'),
        ('throw object', '投掷物体', 'The actor releases an object with a visible launching movement; the landing or recipient outcome is separate.', '人物通过可见抛投动作释放物体，落点或接收结果另记。'),
        ('catch object', '接住物体', 'The actor intercepts a moving object and attempts to gain control; successful control is recorded as the outcome.', '人物拦接移动物体并尝试取得控制，是否成功另记结果。'),
        ('drop object', '使物体掉落', 'The actor releases or loses control so the object visibly descends without a clear throwing launch; accident or intent is not inferred.', '人物释放或失去控制，使物体在无明确抛投起动下可见下降，不推断意外或故意。'),
    ], rule=action_rule, rule_zh=action_rule_zh, semantic='object_action')
    put('Action / HOI', 'Actions · manipulation and use', ['Left Hand', 'Right Hand', 'Left Arm', 'Right Arm', 'Hands'], [
        ('open object', '打开物体', 'The actor changes an object from a closed toward an open configuration, such as opening a door or lid.', '人物使物体从关闭向打开状态变化，如开门或开盖。'),
        ('close object', '关闭物体', 'The actor changes an object from an open toward a closed configuration.', '人物使物体从打开向关闭状态变化。'),
        ('rotate object', '转动物体', 'The actor changes the orientation of a controlled object; whole-body turning alone is not sufficient.', '人物改变所控制物体的朝向，单纯全身转向不足。'),
        ('press object control', '按压物体控件', 'The actor visibly presses a button, switch or other control; successful device activation is separate.', '人物可见地按压按钮、开关或其他控件，是否成功激活装置另记。'),
        ('tap object', '轻敲物体', 'The actor makes one or more brief tapping contacts with the object.', '人物与物体发生一次或多次短促轻敲接触。'),
        ('wipe object', '擦拭物体', 'The actor makes a visible wiping motion over an object surface with a body part or held implement.', '人物以身体部位或所持工具在物体表面作可见擦拭。'),
        ('pour from object', '从物体倾倒', 'The actor tilts or operates a source container in a visible pouring action; annotate uncertain flow explicitly.', '人物倾斜或操作作为来源的容器形成可见倾倒，流动不可确认时明确保留不确定。'),
        ('drink from object', '使用物体饮用', 'The actor performs an observable drinking action using the selected vessel or source; ingestion is not inferred from mere mouth proximity.', '人物利用所选容器或来源作可观察饮用动作，仅靠近嘴部不能推断摄入。'),
        ('eat using object', '使用物体进食', 'The actor performs an observable eating action involving the selected food or utensil; record the selected object consistently.', '人物进行涉及所选食物或餐具的可观察进食动作，保持所选对象定义一致。'),
        ('write or draw with object', '用物体书写／绘画', 'The actor uses a held implement to make visible writing or drawing movements; select the implement and note the surface.', '人物用所持工具作可见书写或绘画动作，选择工具并注明表面。'),
        ('type on object', '在物体上打字', 'The actor makes visible typing actions on a keyboard or equivalent input surface; text content is not inferred.', '人物在键盘或等效输入表面作可见打字动作，不推断输入内容。'),
        ('operate handheld device', '操作手持设备', 'The actor visibly manipulates controls or a screen of a handheld device; distinguish operation from merely holding it.', '人物可见地操作手持设备的控件或屏幕，区别于仅持有设备。'),
    ], rule=action_rule, rule_zh=action_rule_zh, semantic='object_action')
    put('Action / HOI', 'States · body and object support', ['Full Body', 'Left Hand', 'Right Hand', 'Left Arm', 'Right Arm', 'Left Leg', 'Right Leg'], [
        ('kneel on object', '跪在物体上', 'One or both knees visibly maintain support on the selected object; kneeling body posture is independently available.', '一膝或双膝可见地持续支撑在所选物体上，跪姿可独立记录。'),
        ('hang from object', '悬挂于物体', 'The body is visibly suspended through a grasp or attachment to the selected object; identify the observed support relation.', '身体通过抓持或连接可见地悬挂于所选物体，说明可观察支撑关系。'),
        ('object resting on body', '物体放置在身体上', 'The selected object is visibly supported on a body surface, such as a bag on the lap; this direction differs from rest on object.', '所选物体可见地由身体表面支撑，如包放在腿上；关系方向区别于身体放在物体上。'),
    ], rule=contact_rule, rule_zh=contact_rule_zh, workflow='assisted', implementation='planned_rule', semantic='object_state')

    # Preserve the combined historical label and make new choices unambiguous.
    retired_neutral = 'neutral / no reliable cue'
    presets['Perceived Affect'].remove(retired_neutral)
    legacy.setdefault('Perceived Affect', []).append(retired_neutral)
    info[('Perceived Affect', retired_neutral)]['retired_from_active'] = True
    put('Perceived Affect', 'Assessment and broad descriptions', ['Emotion'], [
        ('perceived neutral', '感知为中性', 'Usable evidence supports an approximately neutral outward affect under the annotation protocol. This is not missing evidence or proof of a neutral internal state.', '可用证据在标注协议下支持外显情感接近中性；不代表证据缺失，也不证明内心中性。'),
        ('no clear affect display', '未见明确情感显示', 'The reviewed material is sufficiently observable but contains no clear affective display to characterize. Do not automatically assign valence zero.', '材料已审阅且足够可观察，但未见可明确描述的情感显示，不自动填正负性为零。', {'rule': 'Mark the actually reviewed, sufficiently observable span with no clear affect display. End when a clear affect display appears or usable observability is lost; never fill unreviewed gaps.', 'rule_zh': '只标实际审阅且足够可观察、未见明确情感显示的区间；在明确情感出现或可观察性丢失时结束，不填补未审阅空隙。'}),
        ('mixed affect', '混合情感表现', 'The interval contains concurrent or closely intertwined affective cues of more than one kind; specify supported tags or notes rather than averaging them into neutral.', '区间出现同时或紧密交织的多种情感线索，应注明支持的类别而非平均成中性。'),
    ], rule=categories['Perceived Affect']['boundary_rule'], rule_zh='仅标有依据的情感表现或明确审阅的评价区间；表现改变或证据不足时结束。')
    put('Perceived Affect', 'Specific perceived affect', ['Emotion'], [
        ('joy', '喜悦', 'The observer perceives a positive joyful expression from available multimodal cues; distinguish it from the narrower amused reaction where possible.', '观察者从可用多模态线索感知到喜悦表现，尽可能区别于被逗乐的反应。'),
        ('sadness', '悲伤', 'The observer perceives sadness in the outward expression; reduced movement or silence alone is insufficient.', '观察者感知到外显悲伤，运动少或静默本身不足。'),
        ('anger', '愤怒', 'The observer perceives an angry expression from converging contextual cues; loud speech or forceful movement alone is insufficient.', '观察者根据相互支持的情境线索感知愤怒，仅大声说话或用力动作不足。'),
        ('fear / apprehension', '害怕／忧惧', 'The observer perceives fear or apprehension in the expression; a fall, recoil or scripted hazard alone does not establish it.', '观察者感知害怕或忧惧表现，跌倒、退缩或剧本危险本身不能确定。'),
        ('relief', '释然', 'The observer perceives a release of tension or relief supported by the expression and context; a sigh alone is insufficient.', '表达及上下文支持观察者感知释然或紧张缓解，仅叹气不足。'),
        ('embarrassment', '尴尬', 'The observer perceives embarrassment in context with explicit supporting cues; a social mishap alone is insufficient.', '观察者结合上下文及明确线索感知尴尬，仅社交失误不足。'),
        ('concern', '担忧', 'The observer perceives concern in the actor\'s expression; helping behavior alone does not establish this affect.', '观察者感知人物表达出的担忧，帮助行为本身不能确定这一情感。'),
        ('tension / nervousness', '紧张', 'The observer perceives a tense or nervous expression from multiple supporting cues; fidgeting alone is insufficient.', '观察者由多个支持线索感知紧张表现，仅反复小动作不足。'),
        ('disgust', '厌恶', 'The observer perceives disgust from contextual expressive evidence; turning away or declining something alone is insufficient.', '观察者由情境表达证据感知厌恶，仅转身或拒绝不足。'),
    ], rule=categories['Perceived Affect']['boundary_rule'],
        rule_zh='从情感表现出现可靠依据开始，在表现改变、结束或证据不足时停止；不要按整场情境预填。')

    put('Vocal Event', 'Additional non-lexical vocal events', ['Speech'], [
        ('Yawn', '哈欠声', 'An audible yawning vocal event is present; visible mouth opening without usable audio is not this acoustic annotation.', '存在可听哈欠事件，无可用音频的张嘴动作不属于此声音标注。'),
        ('Humming', '哼鸣', 'A non-lexical sustained or patterned humming vocalization is audible; lexical singing is not automatically included.', '可听非词汇性的持续或有模式哼鸣，不自动包含有歌词演唱。'),
        ('Groan / moan', '呻吟／低吟', 'An audible groaning or moaning vocalization is present; pain or negative emotion is not inferred.', '存在可听呻吟或低吟，不推断疼痛或负面情绪。'),
        ('Non-lexical scream', '非词汇尖叫', 'A non-lexical scream-like vocalization is audible; loud lexical speech is a separate speech description.', '可听非词汇性的尖叫样发声，响亮有词言语另作言语描述。'),
    ], rule=categories['Vocal Event']['boundary_rule'], rule_zh='标声音事件从可听起点到终点，不纳入周围静默。',
        workflow='automatic_primary', implementation='planned_model')

    put('Proxemic Movement', 'Relative paths', ['Root', 'Full Body'], [
        ('pass by partner', '从对方身旁经过', 'The actor moves past the partner along an observable trajectory; interaction avoidance is not inferred.', '人物沿可观察轨迹从伙伴身旁经过，不推断回避互动。'),
        ('move around partner', '绕对方移动', 'The actor follows a curved path around the partner; distinguish the moving actor using a verified shared frame or visible video.', '人物沿伙伴周围的弯曲路径移动，需共同坐标或可见视频确定移动者。'),
    ], rule=categories['Proxemic Movement']['boundary_rule'], rule_zh='从所选人物相对伙伴的该段路径开始，到路径结束或明确改变时结束。')
    put('Spatial Configuration', 'Relative arrangements', ['Dyadic'], [
        ('front-to-back arrangement', '前后排列', 'One participant is positioned in front of the other while both broadly face the same direction; identify the front actor in notes.', '一人在另一人前方且双方大致朝同一方向，备注注明前方人物。'),
        ('different height levels', '处于不同高度层', 'The participants occupy visibly different support levels, such as floor and platform; this is not inferred from body height alone.', '双方位于可见不同支撑高度，如地面与平台，不能仅凭身高判断。', {'rule': 'Start when the distinct support levels are visibly established; end when either participant changes level or the support-level evidence becomes unavailable.', 'rule_zh': '从不同支撑高度可见地建立开始，到任一人改变高度或支撑高度证据不可用时结束。'}),
    ], rule=categories['Spatial Configuration']['boundary_rule'], rule_zh='从可观察空间排列建立到改变结束，记录相关人物与支撑参照。')

    put('QC / Notes', 'Source and attribution issues', ['Notes'], [
        ('actor attribution uncertain', '人物归属不确定', 'A source or event cannot be reliably attributed to R01 or R02; preserve Unknown rather than force an identity.', '来源或事件无法可靠归属 R01/R02，应保留 Unknown 而非强行指定。'),
        ('audio crosstalk', '音频串音', 'A nominally personal audio channel audibly contains another speaker, affecting attribution or activity detection.', '名义上的个人音频通道可听到另一说话者，影响归属或活动检测。'),
        ('audio clipping / distortion', '音频削波／失真', 'Audible or signal-supported clipping/distortion reduces usable audio evidence; record the affected source.', '可听或信号支持的削波／失真降低音频证据质量，注明来源。'),
        ('contact not observable', '接触不可观察', 'The available view or geometry does not establish a contact/support relation needed for an annotation.', '可用视角或几何无法确定标注所需的接触／支撑关系。'),
        ('script-observation mismatch', '情境设定与观察不一致', 'The observed performance does not clearly match a documented scenario instruction; preserve both sources rather than relabel the observation to fit the script.', '实际表现未清楚符合已记录的情境指令，应保留两种来源，不为迎合剧本而改写观察。'),
    ], rule=categories['QC / Notes']['boundary_rule'], rule_zh='标相关证据受影响的实际区间，并说明来源、现象与影响。',
        workflow='manual_primary', implementation='manual')

    # Every new type has an explicit residual, interpretation uncertainty and
    # evidence-missing route; these are not negative ground-truth examples.
    for category, other_name, other_zh, uncertain_name, uncertain_zh in [
        ('Whole-body Action', 'other whole-body action', '其他全身动作', 'whole-body action uncertain', '全身动作类型不确定'),
        ('Gait Pattern', 'other gait pattern', '其他步态特征', 'gait pattern uncertain', '步态特征不确定'),
        ('Physical Interaction', 'other physical interaction', '其他身体互动', 'physical interaction uncertain', '身体互动不确定'),
        ('Cognitive State Expression', 'other cognitive expression', '其他认知表达', 'cognitive expression uncertain', '认知表达不确定'),
        ('Speech Disfluency', 'other speech disfluency', '其他言语不流利', 'speech disfluency uncertain', '言语不流利类型不确定'),
    ]:
        put(category, 'Other and uncertainty', [categories[category]['default_channel']], [
            (other_name, other_zh, 'An observable instance in this category is present but does not fit the named forms. Describe the observed form in notes.', '存在该类型下的可观察实例，但不符合已列具体形式；在备注描述观察到的形式。', {'semantic': categories[category]['semantic_kind']}),
            (uncertain_name, uncertain_zh, 'Relevant evidence is observable but supports competing interpretations or an unresolved category. Preserve the ambiguity and its cues.', '相关证据可观察，但存在竞争解释或类型未定；保留歧义与依据。'),
            ('insufficient evidence', '证据不足', 'Required evidence is missing, obscured or unreliable for this category. This is not a reviewed absence of the behavior.', '该类型所需证据缺失、遮挡或不可靠，不代表已确认行为不存在。'),
        ], rule='Mark the actual interval affected by the residual interpretation or evidence problem; end when the interpretation becomes specific or evidence recovers.',
            rule_zh='标解释未定或证据问题实际影响的区间，在能具体解释或证据恢复时结束。',
            workflow='manual_primary', implementation='manual', semantic='uncertainty')
