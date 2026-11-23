# Annotation protocol — Annotation Studio 0.5.4

完整类型分工、手部接触／支撑及跨层记录规则见 [标注协议](ANNOTATION_PROTOCOL_CN.md)。
## Purpose

Use independent annotation layers to describe observable motion, sustained state, object relation, speech activity and contextual interpretation. Generate automatic proposals where supported, then correct and review according to the study protocol. A recommended automatic workflow is distinct from an implemented detector and from a reviewed individual record.

The active vocabulary contains ten workspaces, 28 types and 493 labels, excluding 28 Unlabeled placeholders. Motion Primitive and Body Posture contain 74 and 58 labels. Locomotion contains 24. Perceived Affect includes the 17 GEMEP core categories for manual observation. Definitions, boundaries and capability metadata are in `LABEL_GUIDE.md` and `label_catalog.csv/json`. The [complete workbook](Annotation_Studio_Label_Catalog.xlsx) covers all workspaces. [Chinese classification guidance](PRIMITIVE_POSTURE_GUIDE_CN.md) explains body-part granularity.

## Layer allocation

| Information | Type / workspace |
| --- | --- |
| Physical movement form | Motion Primitive / Motion |
| Sustained body configuration | Body Posture / Motion |
| Hand shape, self-contact and hand activity | Hand Behavior / Motion |
| Walking, stepping and posture transitions | Locomotion / Motion |
| Complete body action events | Whole-body Action / Motion |
| Observable walking quality | Gait Pattern / Motion |
| Co-activity and physical motion correspondence | Keep the individual Motion observations. Activity Relation is a historical Motion type and remains exportable. |
| Gesture meaning and optional phases | Gesture Type / Gesture Phase / Gesture |
| Object action or sustained contact/support | Action / HOI / HOI |
| Acoustic speech activity | Speaking / Speech |
| Conversational turn hypothesis | Speech Turn / Speech |
| Entry/transfer marker | Turn Transition / Speech, point shape |
| Overlap, pause and gap | Speech Timing / Speech |
| Laughter, sigh and other vocal events | Vocal Event / Speech |
| Conversational function | Dialogue Event / Speech |
| Audible speech disfluencies | Speech Disfluency / Speech |
| Relative distance/body heading | Proxemic Movement / Spatial |
| Pair body arrangement | Spatial Configuration / Spatial |
| Whole-person position relative to named objects/regions | Object Spatial Relation / Spatial |
| Moving toward, away from or around a named target | Object-relative Movement / Spatial |
| Contextual interaction event | Interaction Event / Social |
| Directed bodily contact/assistance | Physical Interaction / Social |
| Expressed uncertainty, decisions and recognition | Cognitive State Expression / Social |
| Optional affect interpretation | Perceived Affect / Affect |
| Missing/uncertain evidence and review notes | QC / Notes / Review |

Gaze and facial annotation are not new tasks in this application. Use supported Oculo/reference results as evidence. Preserve historical records without automatically reinterpreting them.

## Actor, body part and object identity

Annotate R01 and R02 independently. Both represents the pair, not an unidentified individual. Target actors must be explicit when a directed relationship is supported. Do not infer the other actor as target from a single-actor label.

Use stable registered object IDs for specific instances such as sofa_01 and table_01. Display names can change; IDs remain stable. Retired objects retain existing references. A legacy unregistered ID remains unresolved until explicitly reconciled.

A registry name/class does not supply geometry or prove contact. Record the relevant effector/body part independently of object identity.

## Interval and point boundaries

Intervals have finite positive duration and represent `[start_s, end_s)`. Points explicitly use `temporal_kind='point'` with equal start/end. They have no invented window or duration.

- Sustained posture/contact starts when the configuration is established and ends when it ceases under the label definition.
- A transition such as sit-down is distinct from the resulting sitting state.
- A short cough or feedback utterance still has an interval if it has an observable duration.
- A transition point uses the chosen anchor convention. Automatic speaker-change candidates use incoming-turn onset and preserve the signed outgoing-end/incoming-start difference.
- Playback context around a point is evidence for review, not the event's duration.

Do not split/merge points as intervals. Native JSON/CSV retain them. Current EAF export rejects point-containing selections before writing.

## Motion annotation

Use automatic activity/primitive proposals as a starting point. Review part identity, onset/offset, direction reversals and label fit. Distinguish whole-body movement from movement relative to the body.

The Motion panel proposes head turns, nods and shakes and left/right elbow and knee angle changes alongside activity, arm raise/lower and phase candidates. Review the stored kinematic evidence and the boundaries. Fine reach, hand waving, posture and locomotion classifiers remain planned. Assess a hold from the maintained configuration and reserve rest for the corresponding observed state.

A nod describes movement form; agreement is a contextual interpretation. Simultaneous arm activity is not proof of imitation or communicative synchrony.

### Primary part before movement form

Choose **R01/R02 → primary body part → movement form**. New projects provide Head, Torso, left/right arms, left/right hands, left/right legs, Root and Full Body primitive tracks for each actor. The label palette and add-track preview filter primitive vocabulary by the primary channel.

Linked parts record involvement without widening the primary-part list. Full Body lists applicable whole-body forms. Existing Hands tracks aggregate both hand channels. Use separate arm and hand annotations when the study describes distinct movements. A coarse segment can stay pending as `unclassified motion candidate` until evidence supports a specific form.

| Observation | Primary annotation choice |
| --- | --- |
| Leg rises as a coarse movement | Corresponding Leg / `raise leg` |
| Thigh rises through hip flexion | Corresponding Leg / `hip flexion`, at a finer joint level |
| Right knee bends or straightens | Right Leg / Motion Primitive |
| Legs move apart or together | `move legs apart` / `bring legs together` |
| Legs remain separated | Body Posture / `legs apart`; not automatically a split |
| Person holds a front or middle split | Body Posture / `front split` or `middle split` |
| Person stands, or moves up into standing | `standing` state (alias stand), or `stand up` transition |
| Left leg makes a kick-like excursion | Left Leg / Motion Primitive; physical form only |
| Hand makes a waving movement | Corresponding Hand or same-side Arm / Motion Primitive; choose the primary moving part, with greeting meaning separate |
| Legs move into or out of a crossed arrangement | Motion Primitive; choose the leading part or aggregate scope and record participating legs |
| Legs stay crossed | Body Posture |
| Person remains in a squat or kneel | Body Posture, Full Body primary, relevant linked legs |
| Person lowers into or rises from a squat/kneel | Locomotion transition, Full Body primary, relevant linked legs |

Generic movement labels take side from the selected track. Coarse `raise leg` and fine `hip flexion` are alternative granularities unless the protocol deliberately annotates both. Body Posture retains `posture transition` only for compatibility, with `semantic_kind=posture_transition`; it is not a static state.

A sustained kneeling interpretation needs observable knee/support evidence; BVH height alone is insufficient. Leg/thigh raises, lower-limb separation and standing-related labels should follow their explicit catalog definitions, without collapsing them into generic arm movement or posture transitions.

The expanded fine vocabulary does not add its detectors. Wave, knee, kick and squat/kneel-specific rules remain planned; current coarse left/right-leg activity can already generate candidates.

Existing projects keep their layouts. To add missing default lanes, use **Project → Add missing primitive tracks…**. Old cross-part/out-of-list annotations remain inspectable and editable; a menu filter must not erase them.

## HOI actions and sustained states

The HOI category contains both changing actions and maintained relations:

| Observation | Suggested label |
| --- | --- |
| Hand moves toward an identified object | reaching toward object |
| Hand establishes grip | grasp object |
| Object is lifted | pick up object |
| Person maintains object control | hold object |
| Body part visibly touches an object | touch object |
| Hand/body part rests on a surface | rest on object |
| Person sits on a known seat object | sit on object |
| Body is leaning against an object | lean against object |

Choose the specific object and effector. Do not reverse “object held by hand” into “hand supported by object.” Do not use body-joint proximity or a centroid intersection as definitive contact. Uncertain/occluded contact remains uncertain.

Body Posture and HOI can coexist, but do not require duplicate manual intervals merely to express a compound description. Choose the layers needed for the study; this version does not automatically copy a sitting-on-object record into a separate sitting annotation.

## Speech and turn structure

1. Obtain Speaking intervals from audio detection/import/manual review.
2. Verify R01/R02 attribution for the chosen sources. VAD inherits assignment; it does not identify the person.
3. Build rule-based Speech Turn/timing proposals from selected tracks.
4. Inspect short contributions, overlap and ambiguous entry/exit.
5. Keep contextual functions such as backchannel and interruption separate from acoustic overlap.

A turn may contain short pauses. A brief response may be a new turn or feedback; duration alone does not decide. Only explicitly approved backchannel intervals are used as such by the current builder. Speaker-change points are candidates, not confirmed handovers.

If personal microphones are available, their recordings can still contain cross-talk. Channel count is not identity evidence. The present builder performs no diarization, ASR or automatic listener inference.

Automatic derivations remain pending. Accepted/edited/rejected results are protected on rerun; dependency parents needed by reviewed relations stay available. New uncovered speech can produce additional residual candidates. Use Analysis → Recheck derived results after source changes to find direct/transitive stale dependencies. This check does not change accepted records.

## Temporal co-occurrence

A person can be speaking while sitting on a sofa and resting a hand on a table. Preserve those source annotations' independent boundaries. Use Context Query for intersections instead of creating compound labels.

Default same-actor matching uses only the same known R01/R02. Unknown, Scene and Both are not interchangeable individual identities. Use the explicit cross-actor option when the research question requires it.

Point markers and rejected records are excluded. Pairwise result rows can overlap; use union duration for aggregate time/coverage. Exports retain both source annotation IDs. Use Speaking for actual speech activity, Speech Turn when internal pauses should be included.

Temporal co-occurrence does not by itself establish co-speech gesture, attention, response, causality or social intent.

## Review states and provenance

- `pending`: candidate or unfinished manual record.
- `approved`: explicitly accepted by a reviewer.
- `rejected`: retained rejected record, protected from blind regeneration.
- Editing: transient draft, never a fourth persistent state.

Candidates may be viewed and exported without accepting every one. Scientific reference labels must satisfy the project's actual review/adjudication protocol. Model scores are not comparable calibrated probabilities; do not use them to fabricate approved status.

Retain detector source, original prediction, parameters and edit history. Cancel leaves the committed record unchanged. Undo covers committed project actions, including labels and objects. Keep JSON as the complete project record alongside derivative CSV/EAF exports.

## Data coverage and evaluation

An empty timeline does not mean reviewed absence. Missing audio, invisible hands and absent geometry are availability limits, not negative behavioral labels. Do not automatically fill gaps with listener, silence, rest, no-contact or neutral affect.

Use representative reviewed examples and documented boundary/class rules to assess detectors. Separate synthetic contract tests, real-model integration checks, Windows playback and real-data accuracy. The supplied schema demo is synthetic; the historical Stage2 project contains candidates, not reference truth.

## 0.5.0 structured label workflows

The complete active list now also covers whole-body events and gait, directed human-human physical interaction, expressed cognition/person recognition and observable speech disfluencies. See `LABEL_STRUCTURE_CN.md` for allocation examples and `Annotation_Studio_Label_Catalog.xlsx` for the full reviewable list.

Use Project → Add missing annotation tracks… explicitly to supplement old projects. R01/R02 plus Target identifies who assists whom; Both only indicates shared participation. The physical Outcome and human evidence/certainty fields persist through JSON/CSV. Affect offers Adjective + intensity or independent Valence / Arousal. Evidence/origin/judgment are collapsed under More details. Null remains unknown; a dimensional record requires at least one rating before Accept. Detector confidence and review status are independent.

The historical combined-neutral label is retained without relabelling authored records. New menus separate perceived neutral, no clear affect display, affect uncertain and insufficient evidence. Scenario-origin records describe intended portrayal and must not be aggregated as observed expression.

Existing automatic modules remain at their documented capability. New labels are available for manual selection and future scoped automatic proposals; no new affect, cognitive, fall or gait recognition model was added in this release.

## Spatial 与物体名称（0.5.3）

Spatial 新增 Object Spatial Relation（13 项）与 Object-relative Movement（7 项），分别记录人与物体的位置及相对移动。只需在 Objects… 填写名称，ID 自动生成；不要求物体模型或 Props 文件。前后左右选参照，between objects 选两个目标，其他普通关系只选一个。接触、倚靠和支撑继续在 HOI。完整说明见 [人与命名物体／区域](SPATIAL_OBJECTS_CN.md)。
