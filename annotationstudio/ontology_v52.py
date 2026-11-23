"""Presentation aliases and the independent dimensional Affect record.

Canonical names/identities of existing emotion labels remain unchanged. The
adjectives are display/search metadata, not automatic relabeling of saved data.
"""


def extend_affect_modes(categories, info, add):
    category = 'Perceived Affect'
    adjectives = {
        'positive affect': 'Positive',
        'negative affect': 'Negative',
        'amusement': 'Amused',
        'frustration': 'Frustrated',
        'surprise': 'Surprised',
        'other perceived affect': 'Other affect',
        'affect uncertain': 'Uncertain',
        'insufficient evidence': 'Insufficient information',
        'perceived neutral': 'Neutral',
        'no clear affect display': 'No clear affect',
        'mixed affect': 'Mixed',
        'joy': 'Joyful',
        'sadness': 'Sad',
        'anger': 'Angry',
        'fear / apprehension': 'Fearful / apprehensive',
        'relief': 'Relieved',
        'embarrassment': 'Embarrassed',
        'concern': 'Concerned',
        'tension / nervousness': 'Tense / nervous',
        'disgust': 'Disgusted',
    }
    for name, adjective in adjectives.items():
        meta = info[(category, name)]
        meta['affect_adjective'] = adjective

    name = 'valence / arousal rating'
    add(category, name, '正负性／唤醒度评分',
        'A dimensional rating of the actor\'s perceived outward affect over the '
        'selected interval. Valence and arousal are optional independently; '
        'at least one is rated before Accept. This record does not assign an '
        'emotion category, and a missing score is not neutral or low.',
        group='Dimensional rating', parts=['Emotion'],
        rule='Mark the interval characterized by the supplied ratings. Adjust '
             'or split the interval when the rated impression changes. Do not '
             'fill unreviewed spans or infer scores from motion/audio alone.',
        auto_mode='manual',
        auto_method='Manual valence/arousal rating. No affect recognition model '
                    'or automatic conversion from emotion labels is connected.',
        evidence='Optional annotation of perceived outward affect; detailed '
                 'evidence fields are available under More details.',
        aliases=['valence arousal', 'V/A', 'dimensional affect', '情感维度评分'],
        recommended_workflow='manual_primary', implementation_status='manual',
        semantic_kind='affect_rating')
    info[(category, name)].update(
        description_zh='对所选人物在该区间的外显情感作维度评分；Valence 与 Arousal '
                       '可以各自留空，Accept 前至少填写一个。此记录不指定情感类别，'
                       '空值不表示中性或低唤醒。',
        boundary_rule_zh='选择可由这组评分描述的区间；评分印象明显变化时调整或分段。'
                         '不补齐未审阅区间，不仅凭运动或发声自动推断分数。',
        introduced_in='0.5.2', affect_annotation_mode='valence_arousal')
    categories[category]['editor_modes'] = ['adjective_intensity', 'valence_arousal']
