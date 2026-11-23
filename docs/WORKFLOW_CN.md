# Annotation Studio 0.5.4 完整操作指南

完整类型分工、手部接触／支撑及跨层记录规则见 [标注协议](ANNOTATION_PROTOCOL_CN.md)。
## 1. 这一版的工作方式

Motion Primitive 和 Speech 采用自动优先流程：系统先生成能够生成的候选，人再调整边界、改标签、检查疑难。自动模型尚未具备的具体语义，继续使用标签列表人工标注。

标签有三个相互独立的维度：

| 维度 | 回答的问题 | 示例 |
| --- | --- | --- |
| 推荐工作方式 | 这类信息适合怎样产生？ | 自动优先、自动派生、自动辅助、人工主导 |
| 当前实现能力 | 这个版本到底做到哪里？ | 已内置、可选模型、规则待实现、模型待接入 |
| 单条记录的复核状态 | 这条结果是否经过人工处理？ | pending、approved、rejected |

正在编辑只是当前草稿状态。Accept 不会把模型分数变成准确率，也不会抹掉结果最初来自哪个检测器。

本版有 10 个工作区、28 个类型、493 个正式标签，另有 28 个 Unlabeled。Primitive 74 项＋Posture 58 项，共 132 项；另有 Locomotion／转换 24 项。[完整工作簿](Annotation_Studio_Label_Catalog.xlsx)覆盖所有工作区；部位分类见[分类说明](PRIMITIVE_POSTURE_GUIDE_CN.md)。机器可读清单见 [label_catalog.csv](label_catalog.csv)，其中的边界规则与实现说明比“自动／人工”二选一更具体。

## 2. 工作区与标签层级

| 工作区 | 类型 | 适合描述的内容 |
| --- | --- | --- |
| Motion | Motion Primitive | 按人物和主要部位组织的抬放、屈伸、转动、挥动及腿部运动形式 |
| Motion | Body Posture | 坐姿、站姿、蹲姿、跪姿、抱臂、交叉腿等持续姿态 |
| Motion | Hand Behavior | 手部配置、自我接触、手指活动等 |
| Motion | Locomotion | 行走、迈步、坐下、起立，以及进入／离开蹲跪姿势等转换 |
| Motion | Whole-body Action | 跌倒、绊步、恢复平衡、跳跃等完整动作事件 |
| Motion | Gait Pattern | 踉跄、拖步、步态不对称等行走形式 |
| Gesture | Gesture Type | 指示、象似、节拍等手势解释 |
| Gesture | Gesture Phase | preparation、stroke、hold、retraction 等可选阶段 |
| Gesture | Speech-Gesture Relation | 手势与言语的关系 |
| HOI | Action / HOI | 物体操作及持续接触／支撑状态 |
| Speech | Speaking | 实际语音活动区间 |
| Speech | Speech Turn | 话轮区间 |
| Speech | Turn Transition | 单一时间点的说话人切换／交接候选 |
| Speech | Speech Timing | 重叠、话内停顿、话轮间隔 |
| Speech | Vocal Event | 笑声、叹息、咳嗽等 |
| Speech | Audio Activity | 声音能量活动等声学线索 |
| Speech | Dialogue Event | backchannel、打断等会话功能 |
| Speech | Speech Disfluency | 填充性停顿声、重复、拖长、说话中止和修正 |
| Spatial | Proxemic Movement | 接近、退离、转向对方等物理运动 |
| Spatial | Spatial Configuration | 面对面、并排等身体空间排列 |
| Spatial | Object Spatial Relation | 人与命名物体／区域的前后、旁边、紧邻、中间等位置 |
| Spatial | Object-relative Movement | 人对命名目标的接近、退离、绕行及进出区域 |
| Social | Interaction Event | 问候、回应、请求、接受等上下文事件 |
| Social | Physical Interaction | 扶起、支撑、握手、拥抱、推拉等身体互动，保留Actor和Target |
| Social | Cognitive State Expression | 犹豫、理解、决定、身份询问和辨认等表达，保留依据 |
| Affect | Perceived Affect | 形容词＋强度，或 Valence/Arousal |
| Review | QC / Notes | 数据质量、不确定性与复核信息 |

Overview 汇总所有轨道。HOI 与 Spatial 独立存在；持续接触不必强行解释成动作，身体朝向也不直接代表眼神接触。

## 3. 试用合成示例

在 **File → Open synthetic annotation demo** 打开[合成示例](../examples/README.md)。19 条演示记录、10 条轨道和两个虚构物体用于查看说话、对象关系和点事件。使用自己的 BVH 或媒体时，请新建项目并添加来源。

## 4. 导入资料和检查时间

使用资产导入入口添加 motion、video、audio 或已支持的外部参考。为每个资产指定角色与时间偏移。

所有标注使用共同主时间轴：源文件时间加上 `offset_s` 得到主时间。偏移不是自动漂移修正，修改资产偏移也不会悄悄移动已有标注。分析前先检查视频、骨架和声音是否对应。

共同时间不等于共同空间。两个人的世界坐标、上方向、长度单位和 props 坐标需要另行验证。当前 Spatial 标签可以使用，但自动空间检测仍待实现；不要把 world-frame 复选标记当作已经完成坐标标定。

## 5. 新增轨道和人工纠错

新增轨道时选择角色、标注类型、主要身体通道和关联部位。Motion Primitive 的层级是 **人物 → 主要身体部位 → 运动形式**；右侧 Labels 与新增轨道预览都按主要通道筛选。可以选择该通道允许的词表、限定子集，或添加项目标签。

新项目为每人预设 10 条 primitive 轨道：

| 主要部位 | 轨道 |
| --- | --- |
| 头与躯干 | Head、Torso |
| 左右臂 | Left Arm、Right Arm |
| 左右手 | Left Hand、Right Hand |
| 左右腿 | Left Leg、Right Leg |
| 位移／整体 | Root、Full Body |

Full Body 显示适合整体观察的形式。已有 Hands 轨道仍聚合双手词表。关联部位用于记录哪些部位参与，不会自动把左手标签放到右手菜单，也不会把手部动作机械复制到整臂轨道。

打开旧项目时不会自动补轨道。需要完整身体分栏时，使用 **Project → Add missing primitive tracks…**。它只补缺少的角色／类型／主要通道组合，保留既有轨道、排序和标注；可 Undo，重复执行不会重复添加。

区间的基本操作：

1. 在目标轨道空白处拖出时间段，或点击已有块。
2. 在右侧 Labels 中选标签；下方编辑器显示标签、起止时间和补充信息。
3. 拖动块的边缘调整起止；需要时修改文字、对象或备注。
4. 点击 Accept 保存为已接受，或 Keep candidate 保存候选。
5. Cancel 取消本次草稿修改；Undo／Redo 管理已提交操作。

一个人可以在同一时段同时有头动、右臂动作、坐姿和说话。它们属于不同轨道，无需为了互斥而强制切成同一套段。

标签列表的改变不会删除已有记录。历史标签即使退役或被移出建议列表，也会保留在原记录中，允许检查和调整边界。

### 腿部运动、整体姿态和转换如何区分

| 观察到的内容 | 标注方式 |
| --- | --- |
| 抬腿 | 对应 Leg 的 `raise leg`，粗运动形式 |
| 抬大腿／髋屈曲 | 对应 Leg 的 `hip flexion`，更细的关节运动描述 |
| 右膝弯曲／伸直、右腿踢动 | Right Leg 的 Motion Primitive |
| 双腿正在分开／合拢 | `move legs apart`／`bring legs together` |
| 保持分腿／并腿 | Body Posture 的 `legs apart`／`legs together` |
| 保持前后劈叉／横叉 | Body Posture 的 `front split`／`middle split`，不把普通分腿当劈叉 |
| 已经站着／正在起立 | `standing`（可搜索 stand）／Locomotion 的 `stand up` |
| 左／右手挥动 | 对应 Hand 或同侧 Arm 的 Motion Primitive，按主要实际运动部位选择；打招呼的含义另标 |
| 双腿正在交叉／解开 | Motion Primitive；选择主要运动部位并记录参与腿部 |
| 双腿已经交叉并保持 | Body Posture |
| 保持蹲姿／跪姿 | Body Posture，主要范围 Full Body，关联参与的腿部 |
| 下蹲／从蹲姿起身／跪下／从跪姿起身 | Locomotion 转换，主要范围 Full Body，关联参与的腿部 |

通用标签由所选通道确定左右侧。粗 `raise leg` 与细 `hip flexion` 根据研究需要选粒度，默认不把同一次抬腿机械复制成两个事件。Body Posture 中 `posture transition` 保留旧 ID，semantic_kind 为 `posture_transition`，属于兼容过程项，不是静态姿态。不能只看到骨盆降低就确定跪姿，膝部接触或支撑需要相应证据。

词表逐项标注检测状态。点头、摇头、转头和左右肘膝屈伸有内置候选规则。侧倾、挥手、踢腿等细项仍由人工选择。

## 6. Motion 自动分割

从主窗口顶栏点 **Auto-detect…**。在 **Motion** 选择 R01、R02 或所有已载入人物，勾选需要检测的部位（例如 Head、Left Leg、Right Leg），再点 **Generate motion proposals**。**Audio** 提供音频检测，**Build speech turns / timing…** 从已有 Speaking 区间生成话轮和时序候选。

生成完成后，若仍停在检测面板且没有打开的编辑草稿，右侧会进入本轮候选的 **Review** 列表。也可随时从自动面板点 **Review latest candidates** 回到列表。点一条候选会定位并打开标签和时间编辑器。确认标签后可调整 Start / End 或拖动时间轴边缘，点 **Accept** 回到队列。取消勾选 **Latest run only** 可查看之前的记录。

**Classify head, elbow and knee motion** 默认开启。它在部位活动、抬放臂和组合候选基础上，为 Head 轨道提出点头、摇头或转头，为左右 Arm 提出弯肘或伸直肘，为左右 Leg 提出弯膝或伸直膝。证据不足的活动段仍可保留为 `unclassified motion candidate`。取消勾选可以单独运行原有粗分割。

头部规则使用头颈相对躯干的转动，利用回转和主轴区分点头、摇头与单向转头。肘膝规则测量相邻骨段的夹角变化，并在停下或变向时分段。编辑器中的 **BVH rule** 提示可查看候选的角度变化。关节映射缺失、动作过小或转轴混合时，具体候选可能留空。抬放臂仍使用区间高度变化，往返运动可能需要人工细分。

候选无需逐条 Accept 才能查看或导出。研究真值需要什么程度的复核，应按项目协议决定。当前运动分数是显著度，不能用高分直接充当人工确认。

## 7. Speech 从声音到话轮

### 先产生 Speaking

音频能量活动只表示声音变强，不等于人说话。Silero VAD 可产生 Speaking 候选；R01/R02 来自所选资产／声道归属，并非模型辨认出了身份。

如果使用两支个人领夹麦，也可能互相收音，因此在生成话轮前要确认所选 Speaking 轨道的角色归属。音频匿名化或 AudioStudio 处理结果也需要保留原有时间对应关系。

### 再生成话轮和时序

点击 **Build speech turns / timing…**：

1. 选择已经有 Speaking 区间的输入轨道。
2. 确认这些轨道分别属于正确的 R01／R02。
3. 设置同一说话人允许合并的短停顿；这只是项目规则，不是通用话轮定义。
4. 可选择只用已接受的 Speaking。
5. 点击 Generate preview，查看角色、类型、边界和复核原因。
6. 点击 Add to project 写入整批候选。

系统会生成 Speech Turn、Speech Timing 和 Turn Transition。短发声只会被标为需要检查，不能仅凭持续时间断定 backchannel。已明确人工接受的 backchannel 可作为上下文，避免机械地把每次“嗯”都当完整话轮。

同一讲话人可以有包含短暂停顿的话轮。重叠说话是声学事实；打断、话轮交接等需要更具体的会话证据。自动的 speaker change candidate 保留为候选。

本版不做 diarization 或 ASR。没有音频身份识别器时，不应把“已经能组合话轮”误解为“能从任意混合录音可靠地认出两人”。

### 已复核结果与重新生成

重跑会保护已接受、已拒绝和人工编辑的结果。已复核话轮不应吞掉后来新增、尚未覆盖的语音；系统可以为剩余片段生成新候选。已复核关系引用的父话轮会保留，避免留下无法解析的链接。

上游变化后打开 **Analysis → Recheck derived results…**，查看哪些派生记录的直接或间接来源已经改变／缺失。可以定位原记录检查，再决定是否重新生成。检查本身不改变 review state，也不是全局实时自动重算。

## 8. HOI：动作和持续关系

HOI 内的动作组包括接近物体、抓握、拿起、放下、推动、递交等。持续状态包括触碰、持有、搁置在物体上、坐在物体上、靠在物体上等。

先点击 **Objects…**：

1. 在 Display name 填物体或区域名称，如“左侧沙发”“桌子”即可。
2. ID 自动生成；类别、备注和手动 ID 均可留空。如需指定 ID，也可填写 `sofa_01`、`table_01`。
3. 点击 Add object，再用 Save 应用登记；Cancel 不改变项目。
4. 后续可以改显示名称或退休对象，已有标注仍保留原 ID。

例如，R01 右手放在桌上：在 Action / HOI 轨道标注 `rest on object`，对象选择 `table_01`，部位选择 Right Hand。R01 坐在沙发上：标注 `sit on object`，对象选择 `sofa_01`。

如果研究只需要带对象的坐姿，直接维护对应 HOI 状态即可；是否另外保留 Body Posture 的 sitting 由研究需要决定。本版不会自动在两种轨道之间复制标注。

注意区分：

- `sit down` 是坐下的转换过程，`sitting` 是姿态，`sit on object` 是带对象的持续关系。
- `hold object` 是人对物体的持续控制；`rest on object` 是身体部位搁在物体上。
- 手靠近桌面时可以是接近候选；看不清接触时不要直接接受为支撑。

物体登记没有自动几何／接触识别能力。未来接入 MotionStudio props 的表面和姿态、视频证据后，才适合进一步自动生成这类关系候选。

## 9. Context Query：说话时在做什么

点击 **Context query…** 或菜单 **Analysis → Context / overlap query…**。

- Track A 选择 Speaking，Track B 选择 HOI 状态轨道。
- B 的标签可筛选 `rest on object`，对象可筛选 `table_01`。
- Same known actor only 默认开启，仅匹配 R01／R02 的同一人物；Unknown、Scene、Both 不能被当成同一个已知人。
- Accepted annotations only 可只计算已接受来源。
- 点击 Calculate overlap，查看重叠区间、时长和 A 轨覆盖比例。
- Export result CSV 导出当前查询行，包含两侧来源 ID 和复核状态。

使用 Speaking 计算实际语音活动期间的状态；使用 Speech Turn 则会包括话内停顿。两个原始轨道的边界保持不变，不需要手工补一个“说话时手放桌上”的标签。

多条配对结果可能相互重叠，总时长使用时间区间并集，不能直接把每行时长相加。查询表达同时出现，不能自动推导注意、交际功能或因果关系。

## 10. 瞬时事件使用真正的时间点

Turn Transition 默认是点类型。可以在点轨单击时间，或使用 **Edit → Add point at playhead**（Ctrl+M）。点击标记后调整单一时间位置，再选标签并 Accept。

点的可见宽度仅用于点击，它在数据中没有持续时间，不支持区间式边缘拉伸、Split 或 Merge。自动说话人切换点保留 from/to 话轮引用；当前手工点编辑主要是时间、标签和备注，不应假设存在完整手动关系图编辑器。

咳嗽、短反馈、快速动作虽然很短，但有实际持续时间时仍用区间。

## 11. 导出、兼容与保护

- `.studio.json`：完整项目，包含物体 registry、标签定义、时间形状、原始预测与历史。
- CSV：在 Export 中可选总表、每类型分表或两者同时生成；可选全部／指定类型，统一按审核状态筛选。包含完整原始字段，并增加物体名称与常用评分等便捷列。分类包附被引用物体的对照表与导出清单；完整项目定义仍在 JSON。详见 [导出说明](EXPORT_CN.md)。
- EAF：当前为区间交换格式；选择中含点时会明确报错，且不会先覆盖目标文件。保留点请用 JSON／CSV。

新版本接受旧 v1／v2 项目，并保留稳定 ID、历史标签和 original/history。新标签不会自动改写旧数据含义。历史 Face/Gaze 记录仍可通过 Overview／Review 访问，但不会重新成为新标注入口。

数据结构和验证范围见[数据规范](SCHEMAS.md)和[测试报告](../TEST_REPORT.md)。

## 新增类型与完整轨道

Motion 增加 Whole-body Action 与 Gait Pattern；Social 增加 Physical Interaction 与 Cognitive State Expression；Speech 增加 Speech Disfluency。完整位置和逐项使用规则见 [标签位置说明](LABEL_STRUCTURE_CN.md)。

旧项目使用 Project → Add missing annotation tracks… 显式补齐缺少类型；已有轨道布局、限选列表、原始预测和审核记录保留，重复执行不增轨，Undo 可撤销。

Physical Interaction 的 Actor + Target 表达谁扶谁，Outcome记录观察到的完成结果。Affect可选形容词＋Intensity，或独立Valence/Arousal；Unknown保持为空。Evidence、Origin和Judgment默认折叠在More details，不必填写。未知不填零，接受状态不代表高确定性。新旧neutral的兼容规则和证据来源区别详见上述说明。

## Spatial 与物体名称（0.5.3）

Spatial 新增 Object Spatial Relation（13 项）与 Object-relative Movement（7 项），分别记录人与物体的位置及相对移动。只需在 Objects… 填写名称，ID 自动生成；不要求物体模型或 Props 文件。前后左右选参照，between objects 选两个目标，其他普通关系只选一个。接触、倚靠和支撑继续在 HOI。完整说明见 [人与命名物体／区域](SPATIAL_OBJECTS_CN.md)。
