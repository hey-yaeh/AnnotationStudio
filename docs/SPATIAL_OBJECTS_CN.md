# Spatial：人与命名物体／区域

**物体只需要一个名称，就能用于人工标注。无需物体模型、网格、Props 文件、三维位置或自动检测结果。** 名称可以是“柜台”“左侧沙发”“柜台前等候区”；同一个登记对象可同时供 Spatial 和 HOI 选择。

## 1. 先登记名称

点击左侧或编辑区的 **Objects…**，在物体窗口中填写 **Display name**。类别、备注和 Stable ID 都可留空；ID 会自动生成。点击 Add object，再点 Save。一个物体登记一次即可；可以改显示名称，已有标注继续通过稳定 ID 关联它。保存项目后，物体列表也一起保存。

这里的物体列表用于身份登记。名称不是几何模型，也不会自动产生距离、朝向或接触测量。

## 2. Spatial 的四个类型

| 类型 | 记录什么 | 目标 |
| --- | --- | --- |
| Proxemic Movement | 人与人之间的接近、退离和相对转向 | 伙伴人物 |
| Spatial Configuration | 两人的面对面、并排等配置 | 两人关系 |
| Object Spatial Relation | 人在物体前后、旁边、紧邻、区域内等持续位置 | 一个物体；between objects 用两个 |
| Object-relative Movement | 人向物体接近、退离、经过、绕行或进出区域 | 一个物体或命名区域 |

新建两个人的相应轨道时，R01 和 R02 分别标。旧项目可用 Project → Add missing annotation tracks… 显式补齐，也可用 + Add track 只添加需要的类型；打开旧项目不会自动改变原轨道。

## 3. 当前新增的关系列表

| 英文标签 | 中文含义 | 选择要点 |
| --- | --- | --- |
| in front of object | 在物体前方 | 选择方向参照 |
| behind object | 在物体后方 | 选择方向参照 |
| left of object | 在物体左侧 | 不是默认指人物自身左手侧 |
| right of object | 在物体右侧 | 不是默认指画面右侧 |
| beside object | 在物体旁边 | 较宽的旁侧关系，可有间隔 |
| next to object | 挨着／紧邻物体 | 可以有小间隙，不等于接触 |
| near object | 在物体附近 | 一般邻近，未进一步限定方位 |
| far from object | 离物体较远 | 距离状态，区别于退离过程 |
| between objects | 在两个物体之间 | 选两个不同的目标，不要求严格等距 |
| inside object region | 在命名区域内部 | 例如隔间、等候区，不是实体柜台内部 |
| outside object region | 在命名区域外部 | 区域边界按项目约定判断 |
| at center of object region | 在命名区域中央 | 大致中央，不声称精确几何测量 |
| spatial relation uncertain | 位置关系不确定 | 可保留未知目标；只标审阅过的区间 |
| move toward object | 向物体接近 | 人物自身向目标移动 |
| move away from object | 从物体退离 | 人物自身离目标更远 |
| pass by object | 从物体旁经过 | 标实际经过过程 |
| move around object | 绕物体移动 | 不要求绕满一圈 |
| enter object region | 进入命名区域 | 标从区域外进入的过程 |
| leave object region | 离开命名区域 | 标从区域内离开的过程 |
| object-relative movement uncertain | 相对物体移动不确定 | 运动可观察但具体类型不清楚 |

这 20 项当前均为人工标注，没有新增自动空间关系检测器。

## 4. 保持界面简洁

基本操作仍是：**选人物轨道 → 拖区间 → 从列表选标签 → 选择物体名称 → Accept**。

- 普通关系只显示一个物体选择框。
- `between objects` 才额外显示第二个物体；两个目标必须不同。
- 前、后、左、右才显示 **Reference**。Object front 使用物体已定义的正面；Scene directions 使用固定场景方向。两者都可人工约定，不要求三维模型。场景方向在项目／物体备注中约定一次，不随摄像机切换而改变。
- 未完成的关系可以 Keep candidate；常规新标注在 Accept 前需要目标，方向关系还需选择参照。不确定标签可以保留未知目标。

同一条邻近观察通常在 near、beside、next to 中选择合适粒度，不必三条重复记录。明确方向与距离是不同属性；确有研究需要时，可以在独立轨道保留各自区间，软件不强制增加轨道。

## 5. 柜台例子

登记“柜台”后，可以分别记录：

| 内容 | 类型／标签 | 目标 |
| --- | --- | --- |
| 人向柜台走近 | Object-relative Movement / move toward object | 柜台 |
| 人在柜台前方保持位置 | Object Spatial Relation / in front of object | 柜台，并选择 Reference |
| 人挨着柜台 | Object Spatial Relation / next to object | 柜台 |
| 双手放在台面上保持 | HOI / rest on object，Both hands | 同一个柜台 |
| 双手明显撑着身体 | HOI / support body on object，Both hands | 同一个柜台 |

这些记录按自己的边界选段。人的整体位置和手的接触关系可以同时存在；不因手伸到台面上就认定整个人进入了柜台区域。说话不会自动切断持续的空间或接触关系。

## 6. 保存与已有数据

人物身份、目标 ID、第二目标和参照方向保存在原生 JSON/CSV 中。物体改名不改变 ID；退役／未解析的历史引用保留。已接收的旧记录仅调整时间或备注时不会被强迫重新分类，切换标签不会悄悄删除隐藏的历史字段。

关系查询的物体筛选也可匹配 between objects 中的第二目标；其他关系保留但未使用的第二目标不参与查询。EAF 不保留完整对象／参照属性，完整交付请保留项目 JSON。
