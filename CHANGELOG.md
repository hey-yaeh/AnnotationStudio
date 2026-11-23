# Changelog

## 0.5.4 — Total and per-type annotation exports

- Added combined CSV, separate CSV per annotation type, and both in one export.
- Added explicit type selection with matching counts and the existing review-state filters; custom and legacy types remain available.
- Kept all native annotation fields and added readable object/track/workspace and common relation/Affect columns.
- Added referenced-object lookup and an export manifest to fresh per-type result folders; native project save remains separate.
- Preserved IDs, master-clock times, points, original predictions, history and unknown attributes across total/split CSV round trips.
- Retained single-file EAF with type/review filters and explicit point rejection. The vocabulary and models are unchanged.

## 0.5.3 — Spatial relations with named objects

- Register an object/region by display name alone; no mesh, props or geometry assets required. Spatial and HOI share stable identities.
- Added Object Spatial Relation (13 labels) and Object-relative Movement (7), preserving all 480 prior labels. Nine workspaces, 28 types, 500 active labels.
- Compact target selectors: a second target only for between objects; a reference frame only for front/back/left/right. Named-object manual annotation does not claim automatic geometry or contact detection.
- Preserve existing records, unresolved/retired references, unknown attributes and isolated edits. Context queries can filter the active second between-target.
- See TEST_REPORT.md for actual regression, workbook and platform verification.

## 0.5.2 — compact Affect modes and Windows path checks

- Two Affect modes: Adjective + intensity, or independent Valence / Arousal. Evidence/origin/judgment are optional in collapsed More details.
- Preserve canonical emotion identities and previous fields. One dimensional rating label brings the active catalog to 480; no new recognition model.
- Read-only adjective and score display; mode-aware label selection, transactional editing and full JSON/CSV persistence.
- Check the reported PySide6 Windows dependency path before installation; give a direct short-directory recovery route. No automatic registry changes or environment deletion.
- Verification and native Windows limitations are recorded in TEST_REPORT.md.

## 0.5.1 — annotation organization and self-hand relations

- 479 active labels in the same 26 types and nine workspaces: five additions, no active retirements compared with 0.5.0.
- Added hand under chin, hand to chin, hand to cheek, chin resting on hand and cheek resting on hand, with bilingual evidence and interval-boundary definitions.
- Organized the 30 Hand Behavior labels into seven menu groups, including separate inter-hand arrangements and self-support. Old canonical group spellings are normalized only for display; saved authored metadata and arbitrary custom groups stay intact.
- Preserved all 474 previous active IDs, names, definitions, boundaries, aliases and automation capabilities; no automatic reinterpretation of old face-contact annotations.
- Added a complete 26-type decision protocol, specificity rules and parallel-layer examples. Updated the full workbook, exports and Codex handoff.
- No new classifier, compulsory field, annotation track, automatic semantic deduplication or ancestor aggregation was added.

## 0.5.0 — complete vocabulary and directed interpretation fields

- 474 active labels in 26 types; 208 additions and 1 historical retirement compared with 0.4.0.
- Added Whole-body Action, Gait Pattern, Physical Interaction, Cognitive State Expression and Speech Disfluency in the existing nine workspaces.
- Extended the existing primitive/posture, hand, HOI, gesture, dialogue, social, spatial, vocal and Affect lists with operational definitions and honest capability metadata.
- Added explicit undoable/idempotent annotation-track supplementation, preserving authored layouts and label restrictions.
- Added directed physical/cognitive target editing, physical outcome, human certainty/evidence and optional Affect valence/arousal. Unknown and neutral remain distinct.
- Preserved combined-neutral history and all previous IDs; complete bilingual catalog and reproducible filterable workbook accompany the code.
- Corrected Chinese boundary guidance for retained exception labels to match their specific English definitions, including hold, silence, missing data and contact states.
- No new trained semantic classifier or native Windows EXE is claimed; see TEST_REPORT.md.


## 0.4.0 — layered labels and Codex handoff

### Label structure and workflow

- Nine workspaces, 21 types and 267 active non-placeholder labels; 69 Motion Primitive + 48 Body Posture = 117 focus labels, plus 14 Locomotion/transition labels (131 in the focus catalog).
- Motion and Speech now open their automatic-analysis workflow by default; label lists remain available for manual creation and correction.
- Organized Motion Primitive as actor → primary body part → movement form; new projects start with ten primary primitive channels per actor.
- Filtered primitive lists and add-track previews by primary channel; retained Full Body/Hands aggregate views, explicit linked parts and editable historical out-of-list labels.
- Expanded full-body Primitive/Posture vocabulary, including hand-wave, head/torso/wrist forms, leg/thigh raises, knee bend/straighten, kicks, leg separation/crossing, lying/single-leg/half-kneeling/split postures, and squat/kneel lowering/rising transitions. Their fine detector rules remain planned; coarse leg activity remains implemented.
- Added explicit Project → Add missing primitive tracks… without changing old-project layouts on load.
- Added Spatial for physical proxemics/configuration. Physical Activity Relation moved to Motion; Social contains contextual Interaction Event.
- Added separate Speech Turn, Turn Transition and Speech Timing types. Historical Dialogue Event turn labels retain their original identities.
- HOI vocabulary now covers sustained object states/contact as well as actions.
- Recommended workflow, current implementation support and review state are separate.
- New gaze and facial annotation remain excluded; existing references and historical records are preserved.

- Added a focused 131-label workbook and Chinese guide: 117 Primitive/Posture labels plus 14 Locomotion/transition labels. Generic movement names use the track channel for side; coarse/fine alternatives are explicit.
- Preserved Body Posture posture transition as a compatibility entry with semantic_kind=posture_transition.

### Objects, time shape and queries

- Added stable SceneObject registry with name/class/notes, immutable identity, retirement and history-safe references.
- Added object/effector selection for HOI, retaining unresolved legacy object IDs.
- Added explicit point annotations with equal start/end, timeline markers, point editing, duplication and JSON/CSV round trips.
- Point split/interval merge is disabled. EAF rejects point-containing exports before writing instead of inventing durations.
- Added read-only Context Query with track/label/object filters, known-actor matching, source IDs, union-duration coverage and CSV export.

### Speech derivation

- Added rule-based turn candidates from already attributed R01/R02 Speaking intervals.
- Added acoustic overlap, within-turn pause, between-turn gap and speaker-change point candidates.
- Explicit reviewed backchannels can guide grouping; short duration alone does not classify feedback or interruption.
- Protected reviewed/edited/rejected outputs on rerun. Reviewed relations retain required generated parent turns; newly uncovered speech can still produce residual candidates.
- Added complete input-set checks before preview commit and transitive dependency/cycle checks.
- Added Analysis → Recheck derived results to inspect changed/missing upstream evidence without modifying accepted results.
- Diarization, ASR and automatic conversational-function recognition remain unimplemented.

### Compatibility and developer package

- Project schema 3 loads v1/v2 while preserving IDs, labels, mappings, original predictions and history.
- Original 0.3.0 source was preserved in a separate workspace copy; raw sample BVH files are unchanged.
- Regenerated blank real-BVH sample: 57 tracks, 0 annotations.
- Added synthetic schema demo: 19 records, 10 tracks, 2 objects, no real media.
- Retained historical 167-candidate Stage2 project unchanged.
- Added Codex setup/test scripts, project workspace, VS Code tasks/launch configuration, read-only doctor, agent instructions and a scoped automation backlog.
- Validation evidence is recorded in TEST_REPORT.md. This release does not claim a tested native Windows executable, YAMNet real-data accuracy, or complete semantic automation.

## 0.3.0 — per-track label lists

- Added persistent grouped label selection, definitions and boundary guidance.
- Added custom labels and optional per-track label subsets.
- Added distinct motion, posture, hand, locomotion, speech and interaction types, preserving historical vocabulary IDs.
- Removed new gaze/facial annotation menus while retaining supported reference media and old records.
- Added the original blank manual sample and regression coverage for isolated drafts, label lists and compatibility.

## 0.2.0 — editable projects and automatic adapters

- Added stable project/track/label/annotation identities, isolated editing, undo/redo and provenance.
- Added synchronized source preview, motion candidate jobs, audio energy and optional Silero/YAMNet adapters.
- Added native CSV and interval EAF export, recovery, compatibility and original-source protection.
- Historical verification remains available in docs/reports/v0_2_0_TEST_REPORT.md.
