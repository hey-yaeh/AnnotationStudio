"""GEMEP core categories for manual ratings of perceived outward expression.

The names follow the 17 target categories in Bänziger, Mortillaro & Scherer
(2012). The definitions and interval rules adapt them to continuous dyadic
annotation. They preserve the broader project categories and existing IDs.
"""

GEMEP_SOURCE = 'https://doi.org/10.1037/a0025827'

GEMEP_EXISTING = {
    'amusement': 'Amusement',
    'disgust': 'Disgust',
    'relief': 'Relief',
    'surprise': 'Surprise',
    'sadness': 'Sadness',
}

GEMEP_ADDITIONS = (
    ('admiration', 'Admiring', 'Admiration', '钦佩', (),
     'The actor expresses appreciative regard for someone’s quality, skill or achievement.',
     '演员表现出对他人品质、能力或成就的欣赏或钦佩。',
     'Mark the appreciative reaction while its target and expression are supported by context. Polite praise alone is insufficient.',
     '标有明确对象和表达线索的钦佩反应区间。单一句礼貌夸奖不足以判定。'),
    ('tenderness', 'Tender', 'Tenderness', '柔情', (),
     'The actor expresses gentle warmth or affection directed toward someone.',
     '演员对他人表现出温柔、亲切的情感。',
     'Mark the span with observable warmth supported by voice, wording or interaction context. Touch or caregiving alone is insufficient.',
     '标声线、用词或互动语境支持温柔情感的区间。单凭接触或照料动作不足以判定。'),
    ('hot anger', 'Enraged', 'Hot anger (rage)', '暴怒', ('rage', '爆发性愤怒'),
     'The actor expresses anger in an overt, forceful outburst or clearly escalating angry response.',
     '演员明显爆发或强烈升级地表达愤怒。',
     'Mark the span with evidence of the angry outburst or escalation. Use the broader Angry label if the expression form is unclear. Loudness alone is insufficient.',
     '从有证据的怒意爆发或明显升级开始，到该表达缓和或结束。形式不清时可用 Angry，单凭音量不足以判定。'),
    ('despair', 'Despairing', 'Despair', '绝望', (),
     'The actor’s expression conveys a perceived loss of hope or a sense that there is no way forward.',
     '演员的外显表现传达失去希望或感到无路可走的印象。',
     'Mark the passage with supporting verbal or contextual cues. Crying, stillness and sadness alone are insufficient to distinguish despair.',
     '标有言语或情境线索支持绝望感的区间。单凭哭泣、静止或悲伤不足以判定。'),
    ('pride', 'Proud', 'Pride', '自豪', (),
     'The actor expresses positive regard for an achievement or quality they associate with themselves or someone they identify with.',
     '演员对自己或与自己有认同关系的人所取得的成就或特质表现出自豪。',
     'Mark the expressed self- or group-related appraisal. Upright posture or a successful outcome alone is insufficient.',
     '标与自己或所属群体相关的自豪表达区间。单凭挺直姿态或事件成功不足以判定。'),
    ('anxiety', 'Anxious', 'Anxiety', '焦虑', ('anticipatory anxiety', '预期性焦虑'),
     'The actor conveys apprehension about an uncertain or anticipated outcome.',
     '演员表现出对不确定结果或预期事件的忧虑。',
     'Mark where the anticipatory concern is supported by expression and context. Use Tense / nervous when only nonspecific tension is observable.',
     '标外显表达与情境共同支持预期性忧虑的区间。只能感知到一般紧张时选 Tense / nervous。'),
    ('interest', 'Interested', 'Interest', '感兴趣', ('expressed interest', '有兴趣'),
     'The actor expresses affective engagement or curiosity toward a topic, person or event.',
     '演员对话题、人物或事件表现出兴趣或好奇。',
     'Mark the observable interested response while its object and expression are clear. Looking at something or paying attention alone is insufficient.',
     '标对象和表达均清楚的兴趣反应区间。单凭注视或注意不足以判定。'),
    ('irritation', 'Irritated', 'Irritation (cold anger)', '恼火／克制的怒意', ('cold anger', 'annoyed', '冷怒'),
     'The actor conveys annoyance or restrained angry displeasure in response to a perceived provocation or impediment.',
     '演员面对挑衅或阻碍时，表现出恼火或较克制的怒意。',
     'Mark the irritation supported by words, tone or context. A quiet voice or a low intensity rating alone is insufficient.',
     '标用词、语调或语境支持的恼火区间。声音小或强度低本身不足以判定。'),
    ('elated joy', 'Elated', 'Elated joy', '欢欣雀跃', ('elation', '欣喜若狂'),
     'The actor expresses exuberant joy, such as an openly celebratory or visibly lifted reaction.',
     '演员表现出外显而高涨的欢欣，如明显雀跃或庆祝性的反应。',
     'Mark the span of exuberant expression. Use Joyful for joy without clear exuberance. A high intensity or isolated smile is insufficient.',
     '标高涨欢欣表现持续的区间。没有明确雀跃线索时可用 Joyful，单凭高强度或一次微笑不足以判定。'),
    ('contempt', 'Contemptuous', 'Contempt', '轻蔑', ('scornful', '蔑视'),
     'The actor expresses dismissive disregard or disdain toward another person or target.',
     '演员对某人或某个对象表现出轻视、蔑视或不屑。',
     'Mark the span where the target and dismissive appraisal are supported by expression or context. A look away or an isolated facial movement is insufficient.',
     '标表达或语境能支持轻视评价和对象的区间。单凭移开视线或孤立表情不足以判定。'),
    ('panic fear', 'Panicked', 'Fear (panic)', '惊恐／恐慌', ('panic', 'panic fear', '慌张'),
     'The actor expresses acute fear with visible or audible alarm and an urgent reaction to an apparent threat.',
     '演员面对可辨认的威胁表现出急性的惊恐，并伴随可见或可听的急迫反应。',
     'Mark the acute fearful reaction while alarm and urgency are evident. Use the broader Fearful / apprehensive label when the acute form is unclear.',
     '标惊恐与急迫性均有证据的区间。急性形式不清时可用 Fearful / apprehensive。'),
    ('pleasure', 'Pleased', 'Pleasure', '愉悦／享受', ('enjoyment', '享受'),
     'The actor expresses enjoyment of an experience or satisfaction with what is happening.',
     '演员表现出对正在经历的事物的享受或愉悦。',
     'Mark while the enjoyment is apparent. Use Relief when the expression specifically follows the removal of strain, or Amused when the cues support being amused.',
     '标享受或愉悦清楚的区间。情境指向紧张解除时用 Relieved，指向被逗乐时用 Amused。'),
)


def extend_gemep_affect(info, add):
    category = 'Perceived Affect'
    for name, reference in GEMEP_EXISTING.items():
        info[category, name]['gemep_category'] = reference
    for name, adjective, reference, zh, aliases, description, description_zh, rule, rule_zh in GEMEP_ADDITIONS:
        search_aliases = dict.fromkeys((adjective, reference, *aliases))
        add(category, name, zh, description, group='GEMEP observer categories', parts=['Emotion'],
            aliases=[alias for alias in search_aliases if alias.casefold() != name.casefold()], rule=rule,
            evidence='Synchronized video, voice, wording and interaction context available to the observer.',
            auto_method='Manual rating of perceived affect. No automatic affect classifier is connected.',
            recommended_workflow='manual_primary', implementation_status='manual')
        info[category, name].update(affect_adjective=adjective, gemep_category=reference,
                                    description_zh=description_zh, boundary_rule_zh=rule_zh)
