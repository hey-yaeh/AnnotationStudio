# Annotation Studio 0.5.4 标签位置与标注协议

当前有 10 个工作区、28 个标注类型、493 个有效预设标签，另有 28 个 Unlabeled 草稿占位符。词表由实际软件定义导出。完整可筛选列表见 [工作簿](Annotation_Studio_Label_Catalog.xlsx)，精确字段见 [CSV](label_catalog.csv) 和 [JSON](label_catalog.json)。

本页是结构摘要。全部类型的选择规则、手部细分、去重与并行记录示例见 [完整标注协议](ANNOTATION_PROTOCOL_CN.md)。

## 工作区与类型

| 工作区 | 标注类型 | 有效标签数 |
| --- | --- | ---: |
| Overview | 聚合视图 | — |
| Activity | Activity Episode | 1 |
| Motion | Motion Primitive、Body Posture、Hand Behavior、Locomotion、Whole-body Action、Gait Pattern | 215 |
| Gesture | Gesture Type、Gesture Phase、Speech-Gesture Relation | 26 |
| HOI | Action / HOI | 44 |
| Speech | Speaking、Speech Turn、Turn Transition、Speech Timing、Speech Disfluency、Vocal Event、Audio Activity、Dialogue Event | 53 |
| Spatial | Proxemic Movement、Spatial Configuration、Object Spatial Relation、Object-relative Movement | 37 |
| Social | Interaction Event、Physical Interaction、Cognitive State Expression | 70 |
| Affect | Perceived Affect | 33 |
| Review | QC / Notes | 14 |

同一时间段可以在不同类型有独立记录。身体动作、姿态、物体关系、言语、互动和情感各自保留边界，不为所有组合创建新标签。

## 常见现象的放置

| 观察 | 主标注位置 | 区分 |
| --- | --- | --- |
| 右手挥动 | Motion Primitive，Right Hand或Right Arm为主要部位 | 问候功能另在Gesture/Social，默认不把一次运动复制到手和整臂 |
| 手在下巴附近、触下巴／脸颊、托下巴／托腮 | Hand Behavior的Hand placement、Self-contact、Self-support | 可见间隙、实际接触、支撑姿态分别判断；同一关系选一个证据足够的具体标签 |
| 弯膝、踢腿、抬大腿 | 对应腿的Motion Primitive | 粗抬腿与髋屈曲是可选粒度，持续屈膝在Posture |
| 蹲着、跪着、交叉腿 | Body Posture | 下蹲、跪下、起立等转换在Locomotion |
| 摔倒、绊步、恢复平衡 | Whole-body Action | 终止后的坐/跪/卧姿另标，不推断受伤或真实失控原因 |
| 踉跄、拖步等行走形式 | Gait Pattern | Walking等基础移动独立，不推断疾病或醉酒 |
| 扶对方起身、搀扶行走、接住对方 | Physical Interaction | 明确Actor/Target；Outcome只表达观察到的结果 |
| 握手、拥抱、推对方 | Physical Interaction | 身体接触形式与问候、安慰、冲突等功能分开 |
| 递东西、坐沙发、手搁桌面 | Action / HOI | 选择稳定Object ID，人物不能当成物体登记 |
| 接近、退离、相互朝向 | Spatial | 空间变化不自动代表发起或退出社交 |
| 停顿、重叠、话轮间隔 | Speech Timing | 不自动判断犹豫、打断或listener身份 |
| 填充词、重复、改口等 | Speech Disfluency | 可观察的语流形式，需要语音证据 |
| 表达犹豫、不确定、没有认出对方 | Cognitive State Expression | 记录言语/动作依据，询问身份并不等于确定没认出 |
| 惊讶、挫败、尴尬等外显情感 | Perceived Affect | 分R01/R02，根据材料判断，场景设定与观察来源分开 |

## 时间与标签粒度

完整动作和持续状态使用正时长区间。说话人交接等已有Turn Transition仍为真实时间点；不能把一个瞬时标记伪造成固定短区间。动作有持续过程，即使很短，也保留可观察起止。

从支撑该标签的首个证据开始，到该形式/状态结束或明确改变。难以确定的边界可在Notes说明。跌倒不自动延伸到之后整个卧姿；Affect不跟随每次换人说话机械切开。

优先选择证据足够且研究需要的具体程度。不会为了层级完整，自动同时生成多个近义粗细标签。身体部位的Left/Right指参与者解剖侧别；Spatial左右方向按Reference判断。原有10个主要部位轨道保留，足踝细项在同侧腿通道选择。

## 人物、结果与证据

Physical Interaction与Cognitive State Expression使用R01/R02作为Actor，Target可选另一人或Unknown。Physical Interaction新建轨道不提供Both；握手等对称关系用Actor+Target记录一次即可，拥抱按发起者→接受者记录。相同帮助关系保留一条有方向记录，受助者起身可另标个人运动。

编辑器中的Outcome为可选结果：Attempt observed、Completed、Partly completed、Aborted、Outcome uncertain。它不证明不可见接触、力量或内在意图。对人接触部位暂在Notes描述。

Human judgment下的certainty是标注者把握，evidence_sources可多选，evidence_origin区分observed_expression、scenario_prompt、participant_report。评价或训练时应按来源筛选；场景指令不能直接当作观察者感知或参与者真实情绪。

## Affect

R01/R02 分别标区间，默认提供两种方式：**形容词 + Intensity（1…5）**，或 **Valence（−2…+2）/ Arousal（1…5）**。强度可留空；维度模式至少填写一个评分后 Accept，不强制选择情感类别。

Intensity 是情感强弱，Arousal 是激活程度；Unknown 保持为空，Valence=0 才是中性。证据、来源、判断把握在 More details 中默认收起，不要求填写。形容词模式有 32 项，覆盖 GEMEP 17 类并保留原有类别及判断选项。另有 1 项独立维度评分。切换方式保留已有值。 [GEMEP 对照表](LABEL_GUIDE.md#gemep-核心集类别对照)

## 新增与历史记录

0.5.1相对0.5.0新增5项手部位置／接触／支撑标签，没有停用原有474项；Hand Behavior整理为7个分组、30项。各项有独立定义、边界、证据和能力标记。之前已转入历史的neutral / no reliable cue继续保留UUID、原文、来源和审核历史，不自动映射为新neutral。

Motion Primitive 有 74 个具体形式或证据不足标记。粗分割的未分类结果可留作 Pending；使用具体形式才能新确认。`Both / Activity Relation` 和旧粗运动、`hold`、`rest` 保留字面、稳定 ID、审核状态和原始预测。View → Hide legacy tracks 可切换历史双人运动轨道显示。

旧项目打开不补轨、不改原标注。Project → Add missing annotation tracks…显式补缺，保留隐藏、改名、限选轨道，可撤销且幂等。自定义标签继续通过+ Label创建。

## 自动化状态

recommended_workflow 表示推荐分工，implementation_status 表示实际能力。Motion 内置部位活动、抬放臂、部分组合，以及点头、摇头、转头和左右肘膝屈伸候选。其他具体标签按目录的人工或计划状态标注。 [Motion 自动分割](WORKFLOW_CN.md#6-motion-自动分割)

## 标注试运行

先选覆盖跌倒、帮助、辨认、弱情感和安静片段的短样本，按同一上下文规则独立试标。分别检查类别分歧、时间边界分歧和证据不足比例。保留各标注者原始结果，不用共识版本掩盖不确定性。

## Spatial 与物体名称（0.5.3）

Spatial 新增 Object Spatial Relation（13 项）与 Object-relative Movement（7 项），分别记录人与物体的位置及相对移动。只需在 Objects… 填写名称，ID 自动生成；不要求物体模型或 Props 文件。前后左右选参照，between objects 选两个目标，其他普通关系只选一个。接触、倚靠和支撑继续在 HOI。完整说明见 [人与命名物体／区域](SPATIAL_OBJECTS_CN.md)。
