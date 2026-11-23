"""Generate the bilingual catalog from the actual application ontology.

Run ``python scripts/export_label_catalog.py --check`` to detect stale docs.
No model is loaded, no project is mutated, and no media is opened.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from annotationstudio.ontology import (  # noqa: E402
    INTERACTION_EVENT_CORE_GROUPS, LABEL_PRESETS, LEGACY_LABEL_PRESETS, WORKSPACES, WORKSPACE_CATEGORIES,
    category_info, is_motion_candidate, label_spec,
)
from annotationstudio import __version__
from annotationstudio.ontology_gemep import GEMEP_SOURCE

CORE_NAMESPACE = uuid.UUID('f9ee1185-2f20-5d88-bafd-9413131745c5')
WORKFLOW_ZH = {
    'automatic_primary': '自动优先',
    'automatic_derived': '自动派生',
    'assisted': '自动辅助',
    'manual_primary': '人工主导',
}
IMPLEMENTATION_ZH = {
    'builtin': '已内置规则／派生',
    'optional_model': '可选模型已接入',
    'planned_rule': '规则待实现',
    'planned_model': '模型或界面待接入',
    'manual': '当前人工标注',
}
FIELDS = (
    'label_id', 'workspace', 'category', 'group', 'label_en', 'label_zh',
    'description_en', 'description_zh', 'boundary_rule_en', 'boundary_rule_zh',
    'actor_scope', 'actor_role', 'target_role_name', 'relation_symmetry',
    'body_parts', 'semantic_kind', 'temporal_kind',
    'recommended_workflow', 'implementation_status', 'auto_mode', 'auto_method',
    'uses_object_reference', 'evidence_mode', 'aliases',
)


def catalog_payload():
    labels = []
    categories = []
    for workspace in WORKSPACES:
        if workspace == 'Overview':
            continue
        for category in WORKSPACE_CATEGORIES.get(workspace, ()):
            category_meta = category_info(category)
            categories.append({'name': category, **category_meta,
                               'label_count': len(LABEL_PRESETS[category]) - 1})
            for name in LABEL_PRESETS[category]:
                if name == 'Unlabeled':
                    continue
                info = label_spec(category, name)
                labels.append({
                    'label_id': str(uuid.uuid5(CORE_NAMESPACE, f'core:{category}:{name}')),
                    'workspace': workspace,
                    'category': category,
                    'group': info['group'],
                    'label_en': name,
                    'label_zh': info['zh'],
                    'description_en': info['description'],
                    'description_zh': info['description_zh'],
                    'boundary_rule_en': info['boundary_rule'],
                    'boundary_rule_zh': info['boundary_rule_zh'],
                    'actor_scope': category_meta['actor_scope'],
                    'actor_role': info.get('actor_role', ''),
                    'target_role_name': info.get('target_role_name', ''),
                    'relation_symmetry': info.get('relation_symmetry', ''),
                    'body_parts': info['body_parts'],
                    'semantic_kind': info['semantic_kind'],
                    'temporal_kind': info['temporal_kind'],
                    'recommended_workflow': info['recommended_workflow'],
                    'implementation_status': info['implementation_status'],
                    'auto_mode': info['auto_mode'],
                    'auto_method': info['auto_method'],
                    'uses_object_reference': info.get('uses_object_reference', False),
                    'evidence_mode': info.get('evidence_mode', 'reviewed observation'),
                    'aliases': info['aliases'],
                })
    archived = []
    for category, names in LEGACY_LABEL_PRESETS.items():
        for name in names:
            if name in LABEL_PRESETS.get(category, ()):
                continue
            old = label_spec(category, name)
            candidate_only = is_motion_candidate(category, name)
            archived.append({
                'label_id': str(uuid.uuid5(CORE_NAMESPACE, f'core:{category}:{name}')),
                'category': category, 'label_en': name,
                'label_zh': old.get('zh', name),
                'description_en': old.get('description', ''),
                'description_zh': old.get('description_zh', ''),
                'boundary_rule_en': old.get('boundary_rule', ''),
                'boundary_rule_zh': old.get('boundary_rule_zh', ''),
                'body_parts': old['body_parts'],
                'candidate_only': candidate_only,
                'policy': ('keep pending or choose a specific label before Accept; preserve historical reviews'
                           if candidate_only else 'preserve original identity and meaning; no automatic relabeling'),
            })
    gemep_categories = []
    for row in labels:
        if row['category'] != 'Perceived Affect':
            continue
        info = label_spec(row['category'], row['label_en'])
        if 'gemep_category' in info:
            gemep_categories.append({'gemep_category': info['gemep_category'],
                                     'display_name': info['affect_adjective'],
                                     'label_en': row['label_en'], 'label_zh': row['label_zh'],
                                     'label_id': row['label_id']})
    return {
        'schema': 'annotationstudio.label_catalog', 'version': __version__,
        'active_workspaces': list(WORKSPACES),
        'active_category_count': len(categories), 'active_label_count': len(labels),
        'placeholder_count': len(LABEL_PRESETS),
        'notes': [
            'Recommended workflow and current implementation are separate fields.',
            'auto_mode is a legacy detector-capability field, not the recommended workflow.',
            'Review status and data origin are not semantic labels.',
            'Automatic candidates are predictions, not automatically human-reviewed reference data.',
            'The current motion score measures relative salience, not calibrated accuracy.',
            'Speech turns are built from already-attributed speech; no diarization or ASR is included.',
            'Object registry entries do not establish geometry, contact or support automatically.',
            'Cross-track cooccurrence is computed; it does not establish communicative meaning.',
            'Activity Relation is historical. Broad Motion Primitive proposals can stay pending; Accept a specific form when supported.',
            'Gaze/face annotations are retired from new annotation scope; legacy records remain.',
            'Hand placement, self-contact and observable self-support are separate supported descriptions; proximity does not prove contact or force.',
            'Use one specificity level for the same relation; distinct hand shape, posture, object relation and speech may coexist with independent boundaries.',
            'Affect offers Adjective + intensity or Valence / Arousal as independent editor modes; the dimensional rating record does not require an emotion category.',
            'Spatial also supports person-to-named-object states and movement. Only an object name is required for registration; no model assets or geometry are prerequisites for manual annotation.',
            'Activity Episode records a whole observable activity by actor, with an optional named object and description.',
        ],
        'categories': categories, 'labels': labels, 'archived_labels': archived,
        'gemep_affect': {'source': GEMEP_SOURCE, 'categories': gemep_categories},
    }


def _cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def render_markdown(payload):
    lines = [
        f'# Annotation Studio {__version__} — 标签结构与自动化说明', '',
        f"当前有 **{payload['active_category_count']} 个标注类型、{payload['active_label_count']} 个有效标签**，另有每类一个 Unlabeled 草稿占位符。界面使用英文，本文与 CSV/JSON 同时提供中文定义。", '',
        '## 结构原则', '',
        'Activity 的 Activity Episode 用一条区间记录人物的整段活动。可选物体和简短描述与活动名称一起保存，例如推车，描述为「弯着腰向前推车」。', '',
        '1. 身体运动形式、持续姿态、物体关系、语音时序与交际功能分开保存。它们可以在同一时间并行存在。',
        '2. Motion Primitive 和 Speech Turn 推荐自动优先；当前识别器是否已实现由另一列说明。manual 旧字段不代表该类别永远只能人工。',
        '3. HOI 同时容纳动作和持续状态。人物、身体部位、关系和稳定 Object ID 分别记录；手控制物体与物体支撑手的关系方向不同。',
        '4. 坐在沙发上、手搁在桌上等状态保留完整时段，不随说话切碎。与 Speaking/Speech Turn 的重叠由关系查询计算，避免反复手标组合标签。',
        '5. 话轮是区间，交接／说话人切换是时间点。时间点采用接入贡献起点的项目约定，不人为加上固定持续时间。',
        '6. 自动预测层与人工复核状态分开。查看和导出预测不要求逐条 Accept；严格参考标注仍需按研究协议完成验收。',
        '7. Spatial 表达空间运动和排列，Social 记录有上下文支持的互动。Activity Relation 只保留历史用途；双人时间重叠、同步、相似度和时滞留待量化。',
        '8. 新建列表不包含 Gaze/Face。Oculo 的结果继续作为外部参考，旧项目记录保留。',
        '9. Whole-body Action 标完整动作过程，Gait Pattern 标步态特征；Primitive 的局部形式与 Posture 的持续配置仍独立。',
        '10. Physical Interaction 显式保存行动者与目标人物，HOI 使用物体身份。帮助结果、接触事实与情感印象分别记录。',
        '11. Cognitive State Expression 标表达出的认知状态或可复核的辨认表达；剧本设定、自我报告和观察到的表现用证据来源区分。',
        '12. Affect 提供两种简洁方式：形容词 + Intensity（1…5），或独立 Valence（−2…+2）/Arousal（1…5）。维度评分不强制选情绪；未知为 null，强度不等于唤醒度或把握程度。证据等字段默认收起；旧标签身份不变。',
        '13. Hand Behavior 区分手形、双手关系、手部位置、自我接触、自我支撑和重复动作。手在下巴附近且可见间隙、触及下巴／脸颊、托下巴／托腮使用不同标签；不由靠近推断接触、支撑力或情感。',
        '14. 同一关系选择证据充分的具体标签，不把托下巴同时重复记为 self-touch、hand to face 和 hand to chin。独立的姿态、HOI、手形和语音可按各自边界并行记录。完整决策表见 [标注协议](ANNOTATION_PROTOCOL_CN.md)。', '',
        '15. Spatial 同时包含人与人、人与物体的空间关系。物体只需登记名称；前后左右记录参照方向，between objects 指定两个目标；区域内、区域中央指命名区域，不指人在实体物体内部。没有物体模型也能人工标注；接触和支撑继续在 HOI。', '',
        '## Motion Primitive 按身体部位组织', '',
        '推荐顺序为 **人物 → 主要身体部位 → 运动形式**，例如 R01 / Right Hand / wave right hand (kinematic)。同一人的不同部位可同时有动作，但不要求把同一挥手动作在手和手臂轨道重复画两遍。选择主要观察部位；确需研究关节级细节时，再另行记录参与部位。', '',
        '| 主轨道／channel | 典型内容 | 备注 |', '| --- | --- | --- |',
        '| Head | 前屈后伸、左右转头／侧倾、点头、摇头 | 使用头部相对躯干的运动证据，区分单次定向动作和往复模式。 |',
        '| Torso | 前弯／回正／后倾、左右侧弯与扭转 | 细项需躯干相对骨盆的变化；转向伙伴的相对关系另在 Spatial。 |',
        '| Left Arm / Right Arm | 抬放臂、肘屈伸、伸出回收、向外展开／向内收拢、同侧挥手 | 通用形式由轨道确定侧别，旧的含左右名称和 ID 保留。 |',
        '| Left Hand / Right Hand | 挥手、张手／闭手、手腕绕环与屈伸、手指屈伸 | 观察手腕与手指的相对运动。持续手形和自我接触在 Hand Behavior 记录。 |',
        '| Left Leg / Right Leg | 抬放腿、髋屈伸、向外／内移腿、膝屈伸、踢腿、交叉／解交叉腿 | 内置粗活动与膝屈伸候选。其他细模式须人工选择；跨腿过程选择主要运动腿。 |',
        '| Root | 骨盆相对支撑平移、整体转向相关运动 | 行进和换步使用 Locomotion。 |',
        '| Full Body | 分腿／并腿等适合整体观察的运动形式 | 可记录一次组合运动，按研究需要另记局部关节细节。 |', '',
        '`not visible` 用于局部证据无法评估的区间。`movement`、各部位粗运动、`hold`、`rest` 等只保留历史用途。自动分割可产生 `unclassified motion candidate`；缺少具体运动证据时保留 Pending 或拒绝，Accept 前选有证据的具体形式。已审核历史记录保留文本、ID、状态和原始预测。', '',
        '**挥手形式与功能分开：** `wave right hand (kinematic)` / `wave left hand (kinematic)` 描述可见的往复运动；`greeting wave` 描述经上下文判断的问候／告别功能。新增挥手标签推荐自动优先，但现版尚无挥手识别规则，通用手臂活动候选不能算作已识别挥手。', '',
        '### 腿部运动、持续姿态与全身转换', '',
        '| 所见现象 | 类型与标签 | 时间边界与证据 |', '| --- | --- | --- |',
        '| 弯膝／伸直膝 | Motion Primitive / bend 或 straighten left/right knee | 标关节角变化过程；不包含保持弯膝／伸直。需要大腿与小腿相对运动，不能用整腿平移或欧拉角符号代替。 |',
        '| 踢腿 | Motion Primitive / kick left/right leg (kinematic) | 较粗的髋膝联合运动模式，包含明确摆出／踢动；不自动推断踢中物体、攻击或意图。 |',
        '| 把腿交叉／放开 | Motion Primitive / cross legs、uncross legs | 标运动过程，选择主要运动腿；不要因两腿参与而复制相同片段。 |',
        '| 双腿已经交叉 | Body Posture / legs crossed、right leg over left、left leg over right、ankles crossed | 标交叉配置持续存在的区间，保留原有姿态标签。 |',
        '| 正在下蹲／从蹲姿起身 | Locomotion / lower into squat、rise from squat | 标从前一姿态离开到后一姿态建立的全身转换。 |',
        '| 保持蹲姿 | Body Posture / squatting | 标髋膝弯曲、身体降低且主要由脚支撑的持续配置，不包含下蹲和起身。 |',
        '| 正在跪下／从跪姿起身 | Locomotion / kneel down、rise from kneeling | 需要前后姿态与膝接触／支撑变化的证据；不能只看膝高度。 |',
        '| 保持跪姿 | Body Posture / kneeling | 一侧或双侧膝与支撑面建立可观察跪姿关系；缺少接触证据时保留 posture uncertain。 |', '',
        '同一个下蹲过程可以有全身转换和局部膝屈曲两个分析层次。是否同时标注由研究问题决定。内置规则可提出膝屈伸候选。踢腿、跨腿和蹲跪仍需结合运动过程人工判断。', '',
        '## Primitive / Posture 的有限基础体系', '',
        '这是一份可以继续扩展的项目起始词表。先覆盖头、躯干、双臂、双手、双腿、根节点和全身的常见可观察形式，再由研究协议选择所需粒度。每个类型采用分组的平面标签列表；当前不会自动生成父子标签、自动补齐动作分解，也不把每个轴、幅度、左右组合都展开成独立标签。', '',
        '| 范围 | Motion Primitive：正在发生的变化 | Body Posture：已经建立并保持 |',
        '| --- | --- | --- |',
        '| Head | 前屈／后伸、左右转头／侧倾，粗转动和点头／摇头模式 | 中立、低头、后仰、左右转向或侧倾保持 |',
        '| Torso | 前弯、回正、后倾、左右侧弯与扭转 | 中立、前倾／后仰、左右倾斜或扭转保持 |',
        '| Arms | 抬放、肘屈伸、前伸回收、向外展开／向内收拢、同侧挥动 | 抬起、前伸、下垂、肘弯曲／伸直、原有双臂交叉 |',
        '| Hands | 张开／闭合、腕屈伸、挥手与粗活动 | 需要的手型与接触在 Hand Behavior，和运动过程分别标注 |',
        '| Legs | 粗抬放腿、髋屈伸、外移／内收、膝屈伸、踢腿、交叉／解交叉、双腿分合 | 抬腿、屈膝／伸膝、并腿／分腿、交叉腿、具体左右搭腿、前后劈叉／横叉 |',
        '| Whole body | 粗全身活动；站起、坐下、下蹲／蹲起、跪下／跪起由 Locomotion 保存 | 站、坐、蹲、跪、半跪、左右单腿站立、躺卧及仰卧／俯卧／左右侧卧 |', '',
        '### 使用粗标签还是细标签', '',
        '| 用户说法 | 建议选择 | 区分规则 |', '| --- | --- | --- |',
        '| raise leg | Motion Primitive / raise leg | 表示整腿抬起，暂不规定由哪个关节完成。保持抬起用 Body Posture / leg raised。 |',
        '| raise thigh | Motion Primitive / hip flexion（搜索别名 raise thigh） | 大腿相对骨盆向前转动，需要髋关节证据；不能由脚抬高直接替代。 |',
        '| split leg / split legs | 过程通常选 move legs apart；单腿外移可选 move leg outward | 已经分开选 legs apart；只有具体劈叉配置成立才选 front split 或 middle split。 |',
        '| stand | Body Posture / standing | 从坐姿或较低姿势起身为 Locomotion / stand up；单脚支撑明确时选更具体的左右单腿站姿。 |',
        '| 头或躯干低运动量 | 按实际配置选姿态；证据不足保留不确定 | 静止本身不决定角度、注视、接触或休止含义。 |', '',
        '同一现象优先选择证据足够的最具体标签。例如已确认左侧卧时，不必再为相同区间重复增加 lying；已经确定 hip flexion 时，不必仅为层级补全再画一遍 raise leg。全身蹲姿与局部 knee bent 可以作为不同分析问题并行记录，是否这样做由研究协议明确。`arm extended forward` 与 `elbow straight` 分别表达整体手臂配置与肘角，前伸不要求完全伸肘。', '',
        '所有左右方向按参与者自身解剖侧别解释。头相对躯干、躯干／大腿相对骨盆、手相对前臂。画面方向用于显示。头动规则输出身体运动候选。自动候选的拆段阈值写入运行设置，研究使用的判定标准由标注协议约定。', '',
        '接触／支撑影响姿态判断时，流程标为自动辅助：例如跪姿、半跪、躺卧和单腿站立。它们仍是规则待实现，不能把BVH高度或关节接近直接当作接触、承重或力值。具体物体身份继续在 HOI 中记录。', '',
        '前臂、手腕、手指及足踝细项按完整目录中的证据与部位要求选择；新增词条不等于检测器已实现。足踝形式仍归对应侧腿部通道，额外关联部位不复制事件。历史 Body Posture / posture transition 保持原ID和过程语义；它的 semantic_kind 是 posture_transition，不属于持续状态，具体转换优先使用 Locomotion。', '',
        '解剖方向术语参考 [OpenStax Anatomy and Physiology 2e §9.5](https://openstax.org/books/anatomy-and-physiology-2e/pages/9-5-types-of-body-movements)。词表分组、粗细粒度、边界、证据要求与本版自动化状态是本项目的标注约定。', '',
        '## 工作区', '',
        '| 工作区 | 标注类型 |', '| --- | --- |',
    ]
    for workspace in WORKSPACES:
        if workspace == 'Overview':
            lines.append('| Overview | 聚合各类轨道；旧类别仍可查看 |')
        else:
            lines.append(f"| {workspace} | {'；'.join(WORKSPACE_CATEGORIES[workspace])} |")
    lines += [
        '', '## 自动化字段的含义', '',
        '| 字段 | 含义 |', '| --- | --- |',
        '| recommended_workflow | 推荐让系统和人工怎样分工；自动优先、自动派生、自动辅助、人工主导。 |',
        '| implementation_status | 这一版本的实际能力；已有内置逻辑、可选模型、规则待实现、模型／界面待接入、当前人工。 |',
        '| auto_mode | 保留兼容的旧检测器字段，不能单独用于推断推荐工作方式。 |',
        '| semantic_kind | 运动、状态、物体动作／状态、时序关系、社会功能等语义层级。 |',
        '| temporal_kind | interval 为正时长区间；point 为单个时间点。 |',
        '| auto_method | 当前方法、所需前提及主要限制。 |', '',
        '### 当前自动模块的实际范围', '',
        '- 运动：已有部位活动分割、抬放臂和组合候选，以及 BVH 点头、摇头、转头和左右肘膝屈伸候选。具体规则记录角度证据并留待人工复核。其他方向运动、手型变化、挥手、踢腿、分腿与具体姿态见各标签实现状态。',
        '- 语音：可选 Silero VAD 生成 Speaking。话轮结构模块使用已有、已归属人物的 Speaking 区间进行规则分组和时间计算，不提供自动说话人识别或 ASR。短反馈、竞争性重叠等需要复核。',
        '- 发声事件：可选 YAMNet 接口提供 7 类界面目标；真实权重在 OCUMO 数据上的准确率尚未验证。Breathing/Crying 仅有底层支持，界面仍待接入。',
        '- 物体：对象登记和关系编辑不等于已有接触／支撑检测器。自动关系候选还需可见接触或校准后的物体几何，不能由关节或物体中心靠近直接定论。',
        '- 空间：接近、退离和身体朝向适合自动规则，但现版尚未实现相应检测器。两人必须先有可验证的同步、共同坐标和尺度；判断主动接近必须区分各人的运动。',
        '- 社会功能：点头不直接等于赞同，重叠不直接等于打断，运动相似不直接等于模仿；这些解释独立记录。', '',
        '## 两个组合示例', '',
        '| 观察 | 基础记录 | 派生查询 |', '| --- | --- | --- |',
        '| R01 说话时坐在沙发上 | R01 / sit on object / sofa_01；R01 / Speaking | 两条区间的时间交集；无需新建“坐沙发说话”标签。 |',
        '| R01 说话时右手搁在桌面 | R01 / Right Hand / rest on object / table_01；R01 / Speaking | 自动计算重叠时长；不解释为 co-speech gesture。 |', '',
        '## 完整有效标签表', '',
        '下表省略 Unlabeled 占位符。每项给出中文含义与边界规则；CSV/JSON 另保存英文原文、证据来源、部位、别名和稳定 ID。', '',
    ]
    for category in payload['categories']:
        selected = [row for row in payload['labels'] if row['category'] == category['name']]
        lines += [f"### {category['workspace']} / {category['name']}（{len(selected)}）", '',
                  f"**时间形式：** {'时间点' if category['temporal_kind'] == 'point' else '区间'}。**人物范围：** {category['actor_scope']}。", '',
                  '**类型边界原则：** ' + category['boundary_rule'], '']
        if category['name'] == 'Interaction Event':
            names_zh = {row['label_en']: row['label_zh'] for row in selected}
            lines += [
                '#### 双人协作首轮分组', '',
                '在 Interaction Event 轨道右侧的标签列表，以下五组显示在前。完整列表可搜索。'
                '见 [双人协作标注规则](ANNOTATION_PROTOCOL_CN.md#双人协作首轮词表)。', '',
                '| 界面分组 | 标签 |', '| --- | --- |',
            ]
            for group, names in INTERACTION_EVENT_CORE_GROUPS.items():
                labels = '、'.join(f'{names_zh[name]} `{name}`' for name in names)
                lines.append(f'| {group} | {labels} |')
            lines.append('')
        lines += ['| 英文标签 | 中文名称与定义 | 时间边界 | 推荐流程 | 当前实现 |',
                  '| --- | --- | --- | --- | --- |']
        for row in selected:
            lines.append('| ' + ' | '.join(map(_cell, (
                row['label_en'], row['label_zh'] + '：' + row['description_zh'],
                row['boundary_rule_zh'],
                WORKFLOW_ZH[row['recommended_workflow']],
                IMPLEMENTATION_ZH[row['implementation_status']],
            ))) + ' |')
        lines.append('')
        if category['name'] == 'Perceived Affect':
            gemep = payload['gemep_affect']
            lines += [
                '#### GEMEP 核心集类别对照', '',
                '17 类均可用于人工标注演员的外显表现。本词表的定义、适用证据与时间边界按连续互动任务制定。同一表现选择有证据支持的粒度，也可以使用既有的宽义标签。',
                f"来源为 [Bänziger 等，2012]({gemep['source']})。", '',
                '| GEMEP 核心集类别 | 界面名称 | 保存标签 |', '| --- | --- | --- |',
            ]
            for row in sorted(gemep['categories'], key=lambda item: item['gemep_category']):
                lines.append('| ' + ' | '.join(_cell(row[field]) for field in (
                    'gemep_category', 'display_name', 'label_en')) + ' |')
            lines.append('')
    lines += [
        '## 历史项目兼容', '',
        '- 旧 category/name 对应的 UUID 保持不变，已有区间、角色、工作区字段、人工状态、原始预测和编辑历史不做语义重写。',
        '- 旧 Dialogue Event / speaker turn 与 turn handover 保留为历史区间标签；新 Speech Turn 和 Turn Transition 是新的明确类型。',
        '- 旧 Speaking / Overlapping speech 保留为历史标签，新建重叠区间使用 Speech Timing / overlapping speech。',
        '- 旧 Perceived Affect / neutral / no reliable cue 保留 ID、文字和原定义；新建列表区分 perceived neutral、no clear affect display、affect uncertain 与 insufficient evidence，旧记录不会自动改名或填成 Valence=0。',
        '- 同一有效类别在新导航中可以显示到规范工作区，但不必改写旧轨道保存的 workspace 字段。',
        '- CSV/JSON 附带稳定标签 ID。自定义标签、历史标签和未映射的模型文本不会因刷新界面而自动改名。', '',
        '## 更新方法', '',
        '修改 annotationstudio/ontology.py 后运行 `python scripts/export_label_catalog.py`；用 `python scripts/export_label_catalog.py --check` 验证三份目录文件一致。', '',
    ]
    return '\n'.join(lines)


def rendered_files():
    payload = catalog_payload()
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    for row in payload['labels']:
        values = dict(row)
        values['body_parts'] = '; '.join(values['body_parts'])
        values['aliases'] = '; '.join(values['aliases'])
        writer.writerow(values)
    return {
        'label_catalog.json': json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        'label_catalog.csv': '\ufeff' + output.getvalue(),
        'LABEL_GUIDE.md': render_markdown(payload),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs')
    parser.add_argument('--check', action='store_true', help='Fail if generated files are stale; do not write.')
    args = parser.parse_args(argv)
    expected = rendered_files()
    stale = []
    if not args.check:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in expected.items():
        target = args.output_dir / name
        if args.check:
            if not target.is_file() or target.read_bytes() != text.encode('utf-8'):
                stale.append(name)
        else:
            target.write_bytes(text.encode('utf-8'))
    if stale:
        print('Catalog files are stale: ' + ', '.join(stale), file=sys.stderr)
        return 1
    payload = catalog_payload()
    print(f"Catalog {'verified' if args.check else 'written'}: {payload['active_category_count']} types, {payload['active_label_count']} labels.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
