# Annotation Studio 0.5.4：总表、分类表与单类型导出

在顶部点击 **Export**，或使用 **File → Export annotations… / Ctrl+E**。导出窗口按当前项目中的标注类型和审核状态选数据；切换工作区、隐藏轨道不会代替这里的显式筛选。

## 1. 三种 CSV 输出

Format 选择 **CSV · annotation tables**，再选择 Output：

| Output | 输出结果 | 适用情况 |
| --- | --- | --- |
| Combined table | 一张 CSV，总结这次筛选出的所有标注 | 总表分析；也可只选一种类型单独保存 |
| Separate tables by type | 每种有数据的类型各一张 CSV，另含物体对照表和导出清单 | 按类型使用数据 |
| Combined + separate tables | 同一次生成总表及全部分类表，另含物体对照表和导出清单 | 推荐的研究数据交付方式；默认选项 |

“类型”指 `category`，例如 Motion Primitive、Body Posture、Action / HOI、Speaking、Speech Turn、Object Spatial Relation。一个 Motion Primitive 文件包含该类型中被选中的所有标签和人物；不会把它的每个具体标签再拆成独立文件。

同一次导出的总表和分类表使用完全相同的筛选与列结构。按 `id` 合并各分类表可得到总表中的同一批记录，每条记录只属于自己保存的一个 category。已有自定义类型和历史类型也可以导出；不会按新版词表悄悄重分类。

## 2. 只导出 Primitive、HOI 或任意几种类型

1. Annotation types 从 **All types** 改成 **Choose types…**。
2. 点击 **None** 清空勾选，再勾选所需类型，例如 Motion Primitive、Action / HOI。
3. 选好 Review state，确认窗口中的标注数量和非空类型数量。
4. 想保存一张所选类型的表，选 **Combined table**；想每种各一张，选 **Separate tables by type**。
5. 点击 **Export…**，选择文件路径或结果目录。

只勾选 Action / HOI 并选择 Combined table，就得到一份独立的 HOI CSV。重复选择其他类型也可分别保存；需要多种类型时可以一次勾选，批量写出。

没有匹配记录时 Export 不可用。某类型在当前审核状态下有 0 条记录时，不会生成伪造记录或空分类文件。改变审核状态可查看候选数据。

## 3. 审核状态统一生效

| Review state | 包含记录 |
| --- | --- |
| Accepted only | 仅 `status=approved`，默认选项 |
| Candidates + accepted | 候选和已接收，排除 rejected |
| All including rejected | 全部审核状态 |

导出不会把候选改成已接收，不会把模型来源改成人工来源。`status`、`source`、`confidence`、原始预测和编辑历史保持原值。原有自动候选项目可能没有任何 accepted 记录；需要导出候选时应明确选择第二或第三项。

R01、R02 和其他已有主体都保留在 `role` 列；本版按类型分表，没有额外按人物复制文件。需要单人／单部位数据时，可在 CSV 中筛选 `role` 和 `channel`。

## 4. 文件组织与命名

Combined table 使用保存文件对话框，可自行指定 CSV 路径。其他两种模式先选择一个父目录，软件在其中创建新的导出结果文件夹，再写入全部文件。重复导出创建另一个目录，保留先前结果。

以下以保存为 `Practice_Session.studio.json` 的项目为命名示意；具体类型取决于实际勾选和数据：

| 文件例子 | 内容 |
| --- | --- |
| `Practice_Session_annotations.csv` | 本次选择的总表；仅 Combined / Both 模式生成 |
| `Practice_Session_motion_primitive.csv` | Motion Primitive |
| `Practice_Session_body_posture.csv` | Body Posture |
| `Practice_Session_hoi.csv` | Action / HOI |
| `Practice_Session_speaking.csv` | Speaking |
| `Practice_Session_speech_turn.csv` | Speech Turn |
| `Practice_Session_object_spatial_relation.csv` | Object Spatial Relation |
| 物体对照 CSV | 被所选标注引用的物体 ID、名称、类别、备注及登记状态 |
| 导出清单 JSON | 本次筛选、类型到文件的对应关系、行数与完整性信息 |

软件会把项目名／类型名转换为可用文件名，并处理同名、大小写冲突、特殊字符和 Windows 保留名称。正式类别文字仍保留在 CSV 的 `category` 中。文件名不承担标签身份，稳定 ID 才承担记录关联。

Windows 分类包还会按最终文件完整路径预算结果文件夹名称，必要时缩短文件夹中的项目名前缀。表格文件名、类别与 ID 不变；父目录过深而仍无法安全容纳文件时，会提示选择更短目录，不发布不可正常读取的结果包。原有导出目录保持不变。

## 5. CSV 包含哪些信息

CSV 使用 UTF-8 with BOM。每条标注一行；按起始时间、人物和稳定 ID 排序。

| 内容 | 保存方式 |
| --- | --- |
| 稳定身份 | `id`、`track_id`、`label_id`、`parent_id` |
| 时间 | `start_s`、`end_s`、`temporal_kind`，均使用项目主时间轴的秒 |
| 人物与部位 | `role`、`channel`；附加部位保留在 `attributes` |
| 类型与标签 | `category`、`label`、`layer`，附加 workspace／track_name 方便阅读 |
| 审核与来源 | `status`、`source`、`confidence`、`reviewer`、`notes` 等原有字段 |
| 物体 | 主目标 ID／名称／类别；between 关系正在使用的第二目标 ID／名称 |
| 关系与评分 | Spatial 参照、HOI 接触部位、目标人物、Affect 模式／Intensity／Valence／Arousal 的便捷列 |
| 完整原始属性 | `attributes`、`original`、`history` 仍作为 JSON 文本保留在单元格中 |

便捷列帮助分析，不替代原始属性。未知评分保持空值，不填成 0；Valence=0 仍是有效的中间评分。模式切换保留的历史数值不能脱离 mode 来解释。未知或未来扩展字段保留在原始 JSON 中。

物体名称来自导出时的项目登记表。未登记的历史目标保留原 ID，不编造名称；分类包中的物体对照表会记录其缺失状态。隐藏保留的第二目标仍留在原始属性中，只有当前 between 关系才作为有效第二目标出现在便捷列。

身体动作、HOI、Speaking 和 Spatial 各自保留原有时间边界。导出不会强制重采样、对齐区间边界、删除重叠或重新运行算法。点事件保持 `start_s=end_s` 和 `temporal_kind=point`。

## 6. 完整项目与 EAF

**继续编辑所需的完整主档仍是 Save project 生成的 `.studio.json`。** CSV 保留标注记录，但不替代完整轨道、词表、资产路径与设置。过滤导出不会自动把所有未选择的候选／拒绝记录塞进一个项目备份。原始视频、音频和 BVH 不复制到导出包，也不被改写。

EAF 仍是一个文件、内部多 tier。可以使用相同的类型与审核状态筛选，但不提供 CSV 的总表／分类表模式。选中点事件时会提示改用 CSV 或选择只包含区间的类型，不会偷偷删点或制造时长。EAF 不完整保存 object、Affect、原始预测或编辑历史，不作为完整备份。

Context Query 的 Export result CSV 仍导出查询结果；它和这里的标注总表／分类表是两种不同的数据产品。
