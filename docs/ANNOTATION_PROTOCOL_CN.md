# Annotation Studio 0.5.4：标注结构与操作协议

当前有 10 个工作区、28 个标注类型、493 个有效预设项及 28 个 Unlabeled 占位符。Motion 清理宽泛人工选项，保留自动粗分割和历史记录。只登记物体名称即可人工标注人与物体关系。完整逐项定义见 [Excel](Annotation_Studio_Label_Catalog.xlsx)、[CSV](label_catalog.csv) 和 [自动生成指南](LABEL_GUIDE.md)，总表／分类表操作见 [导出说明](EXPORT_CN.md)。

## 1. 先确定记录的问题，再选择标签

工作区组织任务；标注类型规定记录什么；标签说明具体表现。人物、身体侧别、时间形状、证据来源和审核状态分别保存。持续状态可以存在于 Body Posture、Hand Behavior、HOI、Spatial 和 Affect，不必全部归入 Body Posture。

| 想记录什么 | 主要位置 | 例子 |
| --- | --- | --- |
| 这个人在整段时间里做了什么 | Activity / Activity Episode | 推车，描述为「弯着腰向前推车」 |
| 某个部位如何运动 | Motion / Motion Primitive | 屈肘、抬腿、挥动右手 |
| 身体保持什么姿态 | Motion / Body Posture | 坐着、跪着、双腿交叉、躯干前倾 |
| 手的形态、位置、自我接触或支撑 | Motion / Hand Behavior | 十指相扣、手接触下巴、托腮 |
| 如何移动或完成整体姿态转换 | Motion / Locomotion | 行走、坐下、起立、跪下 |
| 发生了什么全身动作 | Motion / Whole-body Action | 摔倒、绊步、恢复平衡 |
| 行走呈现什么形式 | Motion / Gait Pattern | 踉跄、拖步、不对称步态 |
| 人与哪个物体有什么关系 | HOI / Action / HOI | 手搁桌面、坐在沙发上、拿杯子 |
| 人与人的几何关系 | Spatial | 接近、退离、面对面排列 |
| 人与物体的位置与相对移动 | Spatial | 柜台前方、沙发旁边、两物体之间、接近柜台；目标只需名称 |
| 谁对谁做了身体互动 | Social / Physical Interaction | R01 扶 R02 起身、握手、拥抱 |
| 动作或互动表达什么功能 | Gesture / Social | 告别手势、请求帮助、安慰 |
| 说话、非词汇发声及话轮结构 | Speech | Speaking、笑声、话轮、交接、重叠 |
| 明确表达了什么认知内容 | Social / Cognitive State Expression | 表达犹豫、询问身份、明确表示没认出 |
| 材料呈现怎样的情感 | Affect / Perceived Affect | 感知到的愉悦、紧张、关切，以及不确定 |

优先记录证据支持的行为形式。社会功能、认知表达和情感是进一步解释，需要自己的证据。托腮不直接等于思考或无聊，笑声不直接等于愉悦，沉默不直接等于 listener。

## 2. 全部工作区与 28 个类型

Overview 是聚合视图，不重复创建标注。下表的分工是建议使用方式；具体标签是否已接入检测器由词表的 implementation_status 决定。

| 工作区 | 标注类型 | 记录内容与时间形状 | 推荐分工 |
| --- | --- | --- | --- |
| Activity | Activity Episode（1） | 单人整段活动名称及可选物体、描述。按活动自身边界标区间 | 人工观察 |
| Motion | Motion Primitive（74） | 某部位的具体运动形式；区间 | 自动候选优先，人工修边／改标 |
| Motion | Body Posture（58） | 身体及部位保持的姿态；区间 | 自动辅助，人工核对 |
| Motion | Hand Behavior（30） | 手形、双手关系、位置、自我接触／支撑及重复动作；区间 | 人工细分，自动辅助定位 |
| Motion | Locomotion（24） | 移动、整体姿态转换及位置稳定；区间 | 自动候选优先 |
| Motion | Whole-body Action（18） | 完整全身动作事件；区间 | 自动候选与人工复核 |
| Motion | Gait Pattern（11） | 步态特征持续的时段；区间 | 自动辅助、人工复核 |
| Gesture | Gesture Type（16） | 手势的可判断表达功能；区间 | 人工判断语境与功能 |
| Gesture | Gesture Phase（6） | 手势准备、主要表达、保持、回收等阶段；区间 | 自动候选优先，允许人工修正 |
| Gesture | Speech-Gesture Relation（4） | 手势与语音的时间／表达关联；区间 | 对齐辅助，语义关联人工判断 |
| HOI | Action / HOI（44） | 人对物体的动作及持续接触／支撑；区间 | 人工确认对象与关系 |
| Speech | Speaking（4） | 实际说话、已核查静默、说话者未知及听不清的说话；区间 | VAD 候选优先，核对人物归属 |
| Speech | Speech Turn（2） | 同一人一个话轮及其内部停顿；区间 | 从已归属人物的 Speaking 派生 |
| Speech | Turn Transition（3） | 说话人变化候选或经复核的话轮交接；时间点 | 派生候选，按语境复核 |
| Speech | Speech Timing（3） | 重叠、话轮内停顿、话轮间隔；区间 | 从已核对的说话／话轮区间计算 |
| Speech | Speech Disfluency（10） | 填充词、重复、拖音、截断、改口；区间 | 音频／文本辅助，人工复核 |
| Speech | Vocal Event（15） | 笑、叹息等非词汇发声；区间 | 可用模型生成候选，人工听辨 |
| Speech | Audio Activity（2） | 音频源中的可检测活动或缺失；区间 | 信号检测，不等于人物识别 |
| Speech | Dialogue Event（14） | 提问、回答、澄清、反馈等对话功能；区间 | 人工结合言语与语境判断 |
| Spatial | Proxemic Movement（9） | 接近、退离、绕行等空间变化；区间 | 可靠共同坐标下计算候选 |
| Spatial | Spatial Configuration（8） | 两人的相对位置与朝向配置；区间 | 几何辅助，人工复核 |
| Spatial | Object Spatial Relation（13） | 人相对命名物体／区域的位置；区间 | 当前人工，不需要物体模型 |
| Spatial | Object-relative Movement（7） | 接近、退离、经过、绕行、进出命名区域；区间 | 当前人工，不需要物体模型 |
| Social | Interaction Event（27） | 问候、邀请、安慰、请求帮助等社会功能；区间 | 人工多模态判断 |
| Social | Physical Interaction（26） | 谁对谁进行了身体互动；动作或接触区间 | 人工确认方向、对象人物和结果 |
| Social | Cognitive State Expression（17） | 材料明确支持的理解、犹豫、决定、辨认表达；区间 | 人工解释并保留依据 |
| Affect | Perceived Affect（33） | 对每个人外显情感的感知判断；区间 | 人工判断，允许未知评分 |
| Review | QC / Notes（14） | 数据、人物归属、可见性和标注质量问题；区间 | 人工或规则检查 |

Body Posture 中旧有的 posture transition、历史混合轨道及旧标签继续保留。新标注的起立、坐下、下蹲、跪下优先使用 Locomotion 的具体转换标签；不要把旧类别名称当成所有记录必为静态的保证。

当前工作区、类型和有效标签的统计以[生成的标签指南](LABEL_GUIDE.md)为准。

选择 R01 或 R02，再选择主要身体部位。右侧仅建议适用于该部位的具体动作。自动粗分割输出 `unclassified motion candidate`，证据不足时保留 Pending 或拒绝。有证据时才改为具体形式并 Accept。`hold` 和 `rest` 已转入历史；需要研究持续状态时，可用该类型中有证据支持的 Body Posture 或 Hand Behavior 词条。

Motion 的 `Both / Activity Relation` 仅保留历史用途。可通过 View → Hide legacy tracks 切换时间轴显示。旧数据仍可查看、保存和导出。双人运动重叠、同步、相似度和时滞留待基于双方 BVH 和个人动作记录量化。

## 3. 手部行为重新整理

Hand Behavior 现在按 7 个菜单分组组织。人物与左右手仍使用轨道；自己的下巴、脸颊等目标在标签定义中明确，不登记为场景物体，也不使用对方人物 Target。

| 菜单分组 | 标签内容 |
| --- | --- |
| Hand configuration / 手形 | open palm、closed fist、index finger extended、thumb raised、pinch configuration |
| Inter-hand arrangement / 双手关系 | fingers interlaced、hands clasped、palms together |
| Hand placement / 手部位置 | hand resting、hand under chin |
| Self-contact / 自我接触 | self-touch、hand to face、hand to chin、hand to cheek、hand to hair、hand to neck、hand to chest、hand to opposite arm、hand to leg、scratch self、rub own body |
| Self-support / 自我支撑 | chin resting on hand、cheek resting on hand |
| Repetitive action / 重复手部动作 | hand rubbing、finger tapping、thumb twiddling、clap hands (kinematic)、repetitive hand fidgeting |
| Uncertainty / 不确定与不可见 | hand behavior uncertain、not visible |

抓挠自己、揉擦自身保留在 Self-contact 的主要位置。它们是动作区间；同一类目也允许接触或支撑状态区间，不因共有接触就再复制一个同义标签。

### 新增 5 项的操作定义

| 标签 | 中文 | 最低证据与时间边界 |
| --- | --- | --- |
| hand under chin | 手保持在下巴下方 | 手在本人下巴附近且可观察到间隙；从位置保持建立到改变。不是任意低于头部的手，也不覆盖无法看清接触的片段。 |
| hand to chin | 手接触下巴 | 明确接触本人下巴，从接触建立到解除；靠近过程不算。hand–chin contact 为检索别名。 |
| hand to cheek | 手接触脸颊 | 明确接触本人脸颊，从接触建立到解除；尚无足够证据判断托腮时使用。hand–cheek contact 为检索别名。 |
| chin resting on hand | 手托下巴 | 可见下巴靠在手上的保持姿态，从关系建立到解除或改变；描述可观察关系，不声称测量支撑力。 |
| cheek resting on hand | 托腮 | 可见脸颊／侧头部靠在手上，从关系建立到解除或改变；轻微手指调整不必切段。 |

这 5 项已进入新版本列表。当前没有专用自动检测器；推荐未来自动辅助，实际标注使用视频等可用证据。BVH 中手腕靠近头部只能作为候选线索，不能单独证明皮肤接触或承重。

## 4. 两条去重原则

### 同一关系，只保存证据足够的具体层级

已经确定 chin resting on hand 时，通常保存这一条手部关系即可。不要同时为同一观察重复画 self-touch、hand to face、hand to chin、chin resting on hand 四条记录。若只能看清脸部接触，就用 hand to face；接触部位和支撑关系清楚后，人工将同一记录改为更具体标签。

这是标注协议，不是软件自动删除／合并规则。软件仍允许重叠记录，没有新增自动上位标签汇总功能；统计时要按项目定义的映射处理粗细粒度。

### 不同问题，可以并行记录

握拳托下巴同时包含手形和手—头支撑关系。研究需要手形时，可另加同一人物／手侧的 Hand Behavior 轨道，分别记录 closed fist 与 chin resting on hand。它们不是同义重复，也不要求所有标注者都增加这一层工作。

坐着、肘撑桌、手托腮、同时说话分别对应姿态、物体关系、手部关系和语音。每条记录保持自己的起止时间，不跟随其他模态机械切段。

## 5. 身体动作、姿态和整体事件的边界

| 现象 | 首选标注 | 另一个层级何时需要 |
| --- | --- | --- |
| 右手挥动 | Primitive，选主要手或手臂轨道 | 只有功能明确时另记问候／告别 Gesture；不强制两条部位轨重复记录 |
| 屈膝、伸膝、抬大腿、踢腿 | Primitive，对应腿轨道 | 已保持的屈膝配置用 Posture；朝伙伴踢的身体互动另记 Physical Interaction |
| 双腿交叉的运动 | Primitive，选主要运动腿或已有组合形式 | 交叉后保持的状态用 Body Posture |
| 蹲下／跪下／起立 | Locomotion 的姿态转换 | 蹲着／跪着／站着保持段用 Body Posture |
| 摔倒／绊步／恢复平衡 | Whole-body Action | 结束后的卧／坐／跪姿独立，不把跌倒无限延伸 |
| 踉跄地走 | Locomotion / walking 与 Gait Pattern / staggering gait | 两者分别记录移动与步态；不推断醉酒、疾病或受伤 |
| 双人同时活动 | 保留各自的运动记录 | 双人运动重叠留待量化；协调、模仿和共同意图需另有证据 |

Motion／Hand Behavior 的 Left/Right 指参与者的解剖侧别；Spatial 的 left/right of object 使用所选参照方向。Primitive 的身体部位为主要观察通道；参与部位不自动产生重复标注。粗抬腿与细髋屈曲是可选择的粒度，按研究需要选择，避免把同一动作当作两个独立事件计数。

## 6. 自己、物体、对方与空间关系

| 关系 | 放置位置 | 身份记录 |
| --- | --- | --- |
| 手接触／支撑自己的头 | Hand Behavior | 人物 + 手侧；具体自身部位由标签或 Notes 说明 |
| 手或肘接触桌面、坐在沙发 | HOI | 人物 + 稳定 Object ID + 实际效应部位 |
| R01 扶 R02 起身 | Physical Interaction | Actor=R01，Target=R02，Outcome 按观察填写 |
| 握手 | Physical Interaction | 当前界面用R01或R02作为Actor并指定Target；一条记录表达同一对称关系，避免再画一条镜像重复记录 |
| 拥抱对方 | Physical Interaction | 按可见发起者→接受者记录；hug partner不自动表示对方也回抱 |
| 请求／提出帮助 | Interaction Event | 社会功能，由言语／动作／上下文支持 |
| 对伙伴接近／退离／相对转向 | Spatial / Proxemic Movement | 谁在移动须明确；共同坐标、尺度和时间关系要可靠 |
| 面对面／并排等排列 | Spatial / Spatial Configuration | 身体配置，不等同于 mutual gaze |
| 人在柜台前、沙发旁、两个物体之间 | Spatial / Object Spatial Relation | 人物 + 一个或两个命名目标；方向关系选 Reference |
| 人向柜台接近、从等候区离开 | Spatial / Object-relative Movement | 人物 + 命名物体／区域；物体单独移动不算人物运动 |

如果 HOI 界面没有某个更细部位的专用选项，使用现有 Other body part 并在 Notes 写清左肘等细节；不要声称已经新增细部位控件。Physical Interaction 的细接触部位同样可写 Notes。

Physical Interaction 的新增轨道当前使用 R01／R02／Unknown，关系中的另一人由 Target 指定。对称关系不要求另建 Both 轨道；真正采用 Both 的其他双人类型仍按各自协议使用。

### 双人协作首轮词表

打开 **Social → Interaction Event** 并选中一条轨道。右侧标签列表最前面的五个 `Core` 分组包含 13 个首轮协作标签。其他 14 个预设也可浏览和搜索。逐项定义见 [首轮分组与完整词表](LABEL_GUIDE.md#双人协作首轮分组)。

- **请求与提供。** 先判断人物在向对方索取信息、物品或行动，还是主动提供。明确涉及协助时，选 `request assistance` 或 `offer assistance`。请求或提供标发起者的区间，伙伴的回应另标，并在证据明确时填写 Target。
- **确认、接受与赞同。** “听到了”是 `acknowledgment`，记录确认收到；“好，我来扶”是 `acceptance`，记录接受请求；“我也觉得走左边好”是 `agreement`，记录认同建议或观点。`refusal` 拒绝请求或提议，`disagreement` 表达不同意见。点头、摇头和短促应声要结合前后的行为或话语判断。继续听对方说时的一声接应可用 Speech → Dialogue Event 的 `vocal backchannel`。
- **共同协调与交接。** 一人推车、另一人扶车并配合转弯，可在 Social 的 `Both` 轨道标 `joint activity coordination`，从开始配合到结束。个人的推车区间可单独标在 Activity。物品控制从一人交给另一人用 `object handover`，各人的物理接触或操作可单独标在 HOI。仅有同时运动时保留个人运动记录。
- **保留不确定。** 有可辨认的互动贡献，但无法可靠判定功能时，使用 `interaction uncertain` 并在 Notes 记录可见或可听的依据。

这套首轮词表参考 ISO 24617-2 的沟通功能、Clark 的共同行动框架，以及 MUMIN 对多模态反馈和话轮的区分。分组和观察规则用于本项目的人工标注。 [ISO 24617-2:2020](https://www.iso.org/standard/76443.html) · [Clark《Using Language》共同行动章](https://web.stanford.edu/~clark/1990s/Using%20language/Clark.Ch3.Using.language.96.pdf) · [MUMIN](https://link.springer.com/article/10.1007/s10579-007-9061-5)

## 7. 语音、话轮与瞬时事件

Speaking 类型中的同名 Speaking 标签记录实际说话区间；该类型还包含 Speaker unknown、Unintelligible speech 和 silence (reviewed)。已核查静默要求音频可用，音频缺失使用 Audio Activity 中的相应标签。Speech Turn 是经规则和语境组织的话轮区间，可能包含内部停顿；Turn Transition 是明确约定锚点的时间点。当前说话人变化候选使用接入者话轮开始作为锚点，人工确认的交接也必须遵循项目约定。

重叠、停顿和间隔使用 Speech Timing 区间。可听的填充词、重复、拖音或改口使用 Speech Disfluency。Dialogue Event 描述提问、回答、澄清、反馈等功能。短、重叠、安静或换人说话都不能单独决定 backchannel、打断、listener 或话轮交接的社会含义。

瞬时边界用真实 point，start=end；持续过程即使很短仍用正时长 interval。不要把一次交接点人为扩成固定长度事件，也不要把整个握手／跌倒等动作压成一个点。

Gesture Phase 可以接受自动候选并人工修正，当前阶段分类器仍待接入。运动峰值或停顿不自动证明 stroke 或 hold，且也不要求标注者手工为所有 Primitive 配手势阶段。

## 8. 认知表达与 Affect

Cognitive State Expression 记录材料中明确表达的理解、不理解、犹豫、决定或辨认信息。identity query 仅表示询问身份；recognition uncertainty expressed 表示明确不确定；explicit non-recognition statement 才表示明确说没认出；recognition acknowledgment 表示表达认出了。单次停顿、看向别人或摸下巴不能替代这些证据。

Perceived Affect 按 R01/R02 分别记录，编辑时先选一种方式：

| 方式 | 主要字段 | Accept |
| --- | --- | --- |
| Adjective + intensity | 形容词（如 Amused / Sad / Angry / Nervous）；Intensity 1…5 | 选定标签即可，强度允许留空 |
| Valence / Arousal | Valence −2…+2；Arousal 1…5 | 至少填写一项；不要求选择情感类别 |

Intensity 是“这种情感有多强”，Arousal 是“有多平静或激活”，不等于判断把握。Unknown 保存为空；Valence=0 是接近中性。不要从形容词自动填 V/A，也不要把 Arousal 直接当作 Intensity。

默认界面只呈现当前方式的字段。Evidence、Origin、Judgment 在可展开的 More details 中，全部可选。无需逐段填写说明；已有数据照常保存。形容词是现有标签的显示名称，不改变旧 ID。切换方式保留之前的类别及评分，Cancel 不提交修改。

维度记录使用专门的 `valence / arousal rating` 标签，不占用 neutral、other 或 Unlabeled 的含义。受限标签列表不会因切换方式自动扩展；需要时在轨道设置中明确允许该项。原有中性、未见明确表现、解释不确定、信息不足四项继续分别保留。

形容词模式覆盖 GEMEP 核心集的 17 类。`Amused`、`Disgusted`、`Relieved`、`Surprised` 和 `Sad` 沿用既有标签，其他 12 类有独立标签。使用看得到、听得到的表演线索和互动上下文来判断，标表现出现到结束或改变的区间，包括没说话时的反应。同一种表现选一个证据支持的粒度。例如，感知到一般喜悦可以用 `Joyful`，看到明显雀跃再选 `Elated`。强度单独评分。 [GEMEP 对照与边界](LABEL_GUIDE.md#gemep-核心集类别对照) · [GEMEP 原论文](https://doi.org/10.1037/a0025827)

Affect 仍由人工判断，托腮、笑声、叹息或运动速度不会自动变成情感标签。使用 JSON/CSV 保存完整分数；EAF 只作有损的区间文本交换。

## 9. 自动化、来源与审核分别记录

| 字段／概念 | 含义 |
| --- | --- |
| recommended_workflow | 推荐自动优先、自动派生、自动辅助还是人工主导 |
| implementation_status | 实际已内置、可选模型、待实现规则、待接入模型或人工 |
| source / original | 实际来源、首次预测及其原始信息 |
| confidence | 模型或方法输出的分数，不默认是校准准确率 |
| pending / approved / rejected | 已保存的审核状态 |
| editing | 独立的编辑草稿，不是覆盖原记录的第四种持久状态 |

Motion 自动生成部位活动、部分组合、点头、摇头、转头和左右肘膝屈伸候选。头部的交际功能继续在 Social 结合上下文判断。语音提供可选音频适配器与从已归属人物的 Speaking 派生的时序／话轮候选。其他词条的实际检测能力见完整词表。

未标注表示尚无记录；不确定、不可见、证据不足是已作出的内容判断；这些状态不可互换。自动候选可保存和导出，不需要为了可用而强制逐条 Accept；用于严格参考标注时按研究协议复核。

## 10. 实际操作与例子

流程：选工作区 → 选标注类型 → 选人物／主要部位 → 拖时间区间 → 从对应列表选标签 → 调整边缘与必要属性 → Accept。需要瞬时事件时使用点轨道和点工具。

例子仅说明标注规则，不是对所附 BVH 的实际分析：R01 在 2–10 秒坐着；3–8 秒左肘撑桌；4–7 秒左手托腮；5–6.5 秒说话。分别建立 Body Posture、HOI、Hand Behavior、Speaking 四条记录；没有必要构造“坐着托腮撑桌说话”的组合标签。与语音重叠的片段由查询得到，各条原始边界保留。

旧项目打开后保留原有轨道、标签定义、限制、来源与审核记录。若缺少 Hand Behavior 轨道，使用 Add track 或 Project → Add missing annotation tracks…；如旧轨道限定了标签子集，在 Edit list 中明确加入新标签。新版本不会绕过原来的限选规则，也不自动把旧 hand to face 改为托腮。

自定义标签仍可通过 + Label 添加。先选覆盖托腮、遮挡、轻触、动作转换和多人说话的短片段试标，比较“类别分歧”和“边界分歧”，再决定是否需要更细粒度。无需为了覆盖所有词表而在每个片段都填写所有轨道。

## Spatial 与物体名称（0.5.3）

Spatial 新增 Object Spatial Relation（13 项）与 Object-relative Movement（7 项），分别记录人与物体的位置及相对移动。只需在 Objects… 填写名称，ID 自动生成；不要求物体模型或 Props 文件。前后左右选参照，between objects 选两个目标，其他普通关系只选一个。接触、倚靠和支撑继续在 HOI。完整说明见 [人与命名物体／区域](SPATIAL_OBJECTS_CN.md)。
