# Annotation Studio — automation implementation backlog

This is an executable development backlog for work **after the implemented 0.5.4 baseline**. It separates recommended automatic workflows from detectors that actually exist. Read [the schemas](SCHEMAS.md) and [the verification report](../TEST_REPORT.md) first. Work in the existing project, take one bounded task at a time, and preserve raw media and reviewed annotations.

## Baseline that must remain working

| Capability | Current baseline |
| --- | --- |
| Motion Primitive | Actor → primary part → form, ten part tracks per actor, coarse activity and arm phases, head turn/nod/shake and left/right elbow/knee angle-change proposals |
| Speech activity | Energy baseline, optional Silero VAD; actor assignment comes from source/channel mapping |
| Speech structure | Automatic rule-based turn proposals from attributed Speaking; overlap/pause/gap; point speaker-change candidates |
| Vocal events | Optional YAMNet adapter; real-weight OCUMO accuracy is not established |
| HOI states | Label groups, object registry and manual/object-aware annotation; no contact detector |
| Time shape | Positive intervals and explicit zero-duration points, preserved in JSON/CSV |
| Context | Read-only track intersections with union-duration statistics, known-actor matching and source IDs |
| Dependencies | Read-only Recheck derived results dialog, recursive upstream checks and retained dependency parents |
| Review | Pending/approved/rejected; isolated editing; undo; protected automatic reruns |
| Export | Total CSV, per-type CSVs or both, explicit type/review filters; original fields plus named-object and score columns |

The active ontology contains 493 labels across 28 types, including Primitive 74, Posture 58 and Locomotion 24. Broad regional proposals can stay pending as `unclassified motion candidate`. The historical Activity Relation track is retired from the app workflow. Future dyadic analysis should derive overlap, synchrony, similarity and lag from the actors’ BVH and time-aligned individual records. The catalog records which specific primitives have built-in rules and the planned/manual status of other motion, fall, gait, interpersonal, cognition and affect classifiers. Existing projects can be supplemented through Project → Add missing annotation tracks… or its primitive-only counterpart, never silently on load.

Do not recreate these as another app. Do not treat pending outputs as accepted ground truth. Existing motion scores are relative salience, not calibrated confidence; thresholding a score at 0.9 is not a valid automatic-approval policy.

## Priority and dependencies

| Priority | Task | Input dependency | Expected output |
| --- | --- | --- | --- |
| P1 | M1: Body-local motion features and reversal boundaries | BVH/joint mapping and axis definition | Better primitive boundaries without whole-body rotation contamination |
| P1 | A1: Reliable per-person audio input mapping | Available recordings; optional per-person/AudioStudio outputs | Explicit source/channel identity and leakage review |
| P1 | Q1: Small reviewed evaluation fixtures | Representative real excerpts with permission to package | Measured boundary/class/identity errors, not guessed accuracy |
| P2 | M2: Fine primitive rules | M1 + evaluation fixtures | Elbow/reach/head/torso, wave/knee/leg-pattern and hold candidates |
| P2 | A2: Optional diarization adapter | Mixed audio or unresolved identity after A1 | Anonymous-speaker intervals plus explicit R01/R02 mapping |
| P2 | S1: Calibrated spatial analysis | Verified time/frame/scale transforms | Physical distance, orientation, proxemic/configuration candidates |
| P2 | H1: Scene geometry and contact evidence | Stable objects + aligned props/video | Contact/support candidates with explicit evidence |
| P3 | R1: Controlled dependency refresh | Existing speech derivations and recheck dialog | Comparison previews and policy-controlled regeneration |
| P3 | A3: Optional ASR/alignment | Correctly attributed audio | Text/time evidence for ambiguous turns |
| P3 | M3: Posture and locomotion | M1/M2 + floor/support evidence | Sitting/standing/squatting/kneeling/walking and transition candidates |
| Later | H2/G1: Fine hands, HOI actions, Gesture Phase | Reliable geometry/video and labelled examples | Assisted contextual proposals with measured limits |

Tasks can be parallelized only with clear file ownership and a stable shared interface. Do not merge source changes while another task is still changing the same data contract. Finish implementation and meaningful verification before widening scope.

## M1 — body-local features and direction-reversal boundaries

**Implemented subset:** with a valid BVH torso frame, head and arm features use torso-local coordinates. The torso frame uses rest-pose lateral arm anchors and the direction toward the head. The head/neck chain uses the declared BVH rotation order and relative rotation increments. Elbow and knee angles are invariant to rigid transforms. Fine rules split at stops and direction reversals. The editor shows measured angular evidence. Complete curves, body-local features for other regions and reversal splitting within coarse arm-height intervals remain open. The original coarse path is available by clearing the motion panel checkbox.

**Implementation scope**

1. Introduce an explicit anatomical reference frame based on usable torso/pelvis joints or calibrated local rotations. Record axis conventions and fallback availability.
2. Preserve global root trajectory as a separate feature; keep body-local arm/head movement distinct from global translation/heading.
3. Compute direction-sensitive trajectories and joint-relative rotation features. Avoid direct subtraction of wrapped Euler angles; use the declared BVH rotation order and relative rotations.
4. Add turning-point/velocity-sign reversal splitting with noise tolerance, minimum excursion and minimum duration. Keep configurable thresholds and record them in provenance.
5. Expose the relevant feature curves and candidate rationale for review. The current job drops returned feature arrays; design bounded storage/cache rather than embedding enormous arrays in every annotation.

**Acceptance criteria**

- A rigidly translated/rotated actor with unchanged local limb pose does not acquire false local arm primitives solely because of the transform, while the root/turn channel still reports global change.
- A synthetic raise–return sequence yields separate directional evidence and does not disappear because endpoints match.
- Tests cover different valid up axes, Euler channel orders, missing joints, short excerpts and sampling rates.
- Native source times and master offsets are applied exactly once; cropped and full-range runs describe their threshold scope honestly.
- Existing original files are byte-identical after the run; reviewed results survive reruns; score documentation is not upgraded to probability without calibration.

## M2 — interpretable fine Motion Primitive rules

**Input:** validated M1 features and explicit body mapping.

Implement in small independently reviewable increments:

- implemented: left/right elbow flexion and extension from joint-angle change;
- forward reach/retraction in the body frame;
- implemented: a dominant yaw turn and pitch/yaw reversal patterns for nod/shake **kinematic candidates**. Direction-specific single pitch/roll labels remain open;
- torso lean and body heading change;
- implemented: left/right knee bending/straightening, with checked joint chains and angle conventions;
- hand-wave and kick-like kinematic patterns, with direction, excursion and repetition criteria that do not assert greeting or intent;
- leg/thigh raising, lowering, separation and crossing/uncrossing patterns according to the final catalog definitions;
- stable posture/low-motion intervals, with a distinct definition from relaxed rest;
- validated raise–hold–lower composition requiring observed stable posture, not merely a gap between movement intervals.

**Acceptance criteria**

- Each emitted label has a written operational definition, minimum evidence and uncertainty route.
- Generic forms use the primary channel for side. Coarse leg raising and finer hip flexion remain documented alternative granularities; do not emit both as independent events merely because both descriptions fit.
- Leg separation movement, maintained legs-apart stance and front/middle splits stay distinct. Retained posture transition compatibility entries must not be scored as static posture.
- A point-like velocity peak does not become a zero-duration interval; valid event boundaries reflect actual support in the sampled signal.
- Opposite directions and left/right channels are tested; mirrored or rotated actors do not silently swap labels.
- Low movement is not labelled rest merely because no movement was detected. Missing/invalid data is not filled as stillness.
- “Nod” never automatically means agreement; a reach does not assert an object target without object evidence.
- Assign each result to its explicit primary body channel. Participating body parts do not automatically duplicate an event onto both arm and hand tracks.
- Primary-part applicability is consistent in the palette and add-track preview; Full Body is scoped to whole-body forms and the historical Hands channel still aggregates hand vocabulary.
- Only implemented classes receive builtin status in the catalog; unknown/unsupported classes stay clearly planned or assisted.

## A1 — per-person audio and leakage-aware identity mapping

**Input-dependent workflow:** First confirm which recordings are available. If the session has two personal lavalier recordings or camera audio, map their roles explicitly. AudioStudio outputs, when available, may be processed/aligned per-person recordings. A microphone worn by R01 can still contain R02's voice; two channels do not prove two clean identities.

**Implementation scope**

1. Add an explicit mapping record from source asset/channel to R01/R02, with mapping method, reviewer and verification status.
2. Preserve input provenance when importing AudioStudio outputs; map their local time to the master clock and retain the original/processed source distinction.
3. Present short comparison playback and activity evidence for leakage/crosstalk review. Do not silently identify the wearer from file/channel position alone.
4. Generate separate Speaking streams from appropriately mapped audio; retain uncertain attribution rather than forcing it to one actor.
5. Let the speech-structure builder consume the attributed streams without requiring a transcript.

**Acceptance criteria**

- Independent microphones, stereo camera audio, missing channels, swapped assignments and leakage have explicit cases.
- Changing a mapping does not silently rewrite reviewed historical annotations; a new run records the new mapping/version.
- Source duration/sample indices stay traceable. Do not time-stretch, crop or overwrite recordings as a hidden prerequisite.
- Unknown identity cannot pass as verified merely because VAD returned a confident speech interval.
- A run preview shows selected sources, roles, offsets and ambiguity; generated candidates remain pending.

## A2 — optional speaker diarization

**Purpose:** produce anonymous-speaker activity intervals when per-person identity cannot be obtained adequately from A1. This task does not require ASR.

**Implementation scope**

- Add an optional local diarization adapter with lazy imports, explicit weight/model configuration, progress and cancellation.
- Preserve anonymous cluster IDs and separately record the human-confirmed mapping to R01/R02. Support unknown/background speakers without silently forcing every cluster into one of the two roles.
- Preserve overlapping speakers. An exclusive one-speaker transcript alignment view must not overwrite overlap-aware timing evidence.
- Record model/version/configuration, native spans, source assets, speaker assignments and known uncertainty.
- Integrate safe scoped reruns and the existing turn builder after mapping.

**Acceptance criteria**

- A deterministic fake backend verifies data contracts/cancellation; a real-model smoke is separately reported and does not masquerade as a real-data quality result.
- Speaker-order changes across files do not swap R01/R02 silently.
- Overlap, silence, unknown speakers and very short contributions remain explicit.
- Absence of a valid model/runtime produces an actionable error; no energy/VAD fallback is labelled diarization.
- No model download at application launch. Installation and any required access conditions are explicit.
- Evaluate speaker attribution and overlap on reviewed OCUMO excerpts before claiming accuracy; document metric definitions and exclusions.

## S1 — calibrated proxemics and spatial configuration

**Problem:** physical spatial relations should be automatic, but valid numbers require common coordinates, time and scale. A checkbox named world-frame verified is not itself calibration.

**Implementation scope**

1. Store explicit per-source transforms, handedness/up-axis, units and time mapping with provenance.
2. Calculate root/torso reference positions, interpersonal distance, distance rate, headings and actor-to-partner angles as continuous features.
3. Derive approach/withdrawal, toward/away turning and configuration candidates using documented tolerances/hysteresis.
4. Attribute movement to each actor using their motion relative to the connecting direction; do not assign both actors “approaching” merely because distance decreases.
5. Keep labels such as face-to-face as body configuration, distinct from gaze/eye contact.

**Acceptance criteria**

- A stationary R01 and approaching R02 produce R02 movement attribution; R01 remains stationary under the chosen rule.
- Common rigid transformations leave relative-distance/configuration results invariant.
- Separate source offsets and missing spatial coverage are handled explicitly; no interpolation across unsupported gaps without a documented limit.
- Unknown units do not yield a falsely precise meter label. Unknown common frame prevents production of unqualified cross-actor physical labels.
- Approach/withdrawal does not become interaction initiation/disengagement. Proximity does not become mutual gaze.
- The original BVH and source transforms are not overwritten; rerun provenance identifies the calibration used.

## H1 — object geometry and observable contact/support

**Baseline:** objects already have stable IDs, and HOI states can reference them. The current props adapter supplies centroids only. Centroid closeness cannot establish a hand resting on a tabletop.

**Implementation scope**

1. Add explicit scene/prop geometry adapters and links to registry IDs. Preserve user-established IDs across tracking/reloading; do not identify objects only by class name.
2. Keep geometry, pose trajectory, shape uncertainty and visibility distinct from registry names.
3. Use suitable body/hand geometry plus object surfaces and/or video evidence to generate contact/support-state candidates.
4. Produce temporally stable observable relationships such as rest on object, sit on object and lean against object. Separate candidate proximity from confirmed contact/support.
5. Display which surfaces/body parts and frames support a proposal. Preserve uncertainty under occlusion or unavailable geometry.

**Acceptance criteria**

- Two tables of the same class remain distinct instances; renaming a table does not change references.
- A hand passing near the table does not automatically become sustained resting contact.
- “Hand rests on table” and “hand holds object” retain the correct relation direction.
- Seated posture can exist without a known seat object; do not invent a sofa ID from pose alone.
- Geometry/frame/scale mismatch produces a clear unavailable or candidate state rather than false contact.
- Missing evidence remains unknown. Do not infer exact support force or physical pressure from joint positions alone.
- Context query finds speaking overlapping the HOI state without creating or requiring a second compound label.

## R1 — dependency review and controlled refresh

The current speech module records dependencies, rejects stale previews and reports stale protected outputs. A read-only Recheck derived results dialog already follows direct/transitive dependencies and opens affected records; reviewed relations retain required generated parents. It does not automatically recompute every derived annotation whenever a source is edited.

**Implementation scope**

- Extend the existing stale-dependency recheck dialog with grouped evidence comparisons and clearly scoped refresh actions.
- Permit scoped regeneration with a comparison preview; preserve reviewed or edited records and offer an explicit human replacement decision.
- Update unreviewed derivations only under an explicit project policy; keep original prediction and regeneration history.
- Distinguish interval arithmetic that is automatic from a semantic decision that a transition is a confirmed conversational handover.

**Acceptance criteria**

- Editing a Speaking boundary marks dependent turn/timing outputs stale; deleting an upstream annotation reports a broken link.
- A reviewed turn used as an anchor is not overwritten by a later VAD run.
- New source annotations added after a preview invalidate it, as do deletions/changed eligible inputs.
- Undo/Redo covers a whole dependency update; cancellation leaves the project unchanged.
- No recursive cycles or dangling “accepted” relationship claims are silently created.
- Backchannel uncertainty is retained; duration alone never resolves it.

## A3 — optional transcription and alignment evidence

Transcripts can help resolve ambiguous turn grouping, but the Motion/Speaking/turn-proposal workflows must remain usable without ASR.

**Implementation scope**

- Add a local optional ASR/alignment adapter with language/model selection and explicit provenance.
- Keep text segments/word timestamps separate from Speaking and conversational-turn boundaries.
- Link text to source audio and mapped speakers without replacing overlap-aware acoustic annotations.
- Display transcripts as review evidence and allow corrections without rewriting raw audio.

**Acceptance criteria**

- Missing words, silence, laughter, overlapping voices and unsupported alignment languages are handled explicitly.
- ASR does not erase coughs/laughter or convert every segment boundary into a turn boundary.
- Text corrections do not silently retime approved motion/audio records.
- Character/word accuracy and timing quality are evaluated separately; no invented confidence from text fluency.

## M3 — posture and locomotion candidates

Implement standing/sitting/squatting/kneeling, posture transitions, stationary location, walking/stepping, turning in place, sit-down and stand-up after the underlying body mapping and relevant support/floor evidence are established. For squatting/kneeling, keep sustained Body Posture separate from lower/rise or kneel-down/rise transitions in Locomotion. Use Full Body as the primary scope and record involved legs; local knee/leg primitives remain independently available where needed.

**Acceptance criteria**

- Stationary root location allows active arms/head; it does not mean whole-body rest.
- Sitting/standing/squatting/kneeling transitions are separate from sustained posture intervals.
- Pelvis height alone does not prove kneeling or knee contact. State the visible/geometry/support evidence and uncertainty route.
- Full-body posture annotation does not require duplicate manual annotations on both leg tracks.
- Pelvis motion alone does not prove true center-of-pressure or support-foot transfer.
- Crossing legs, ankles or arms uses a documented geometric criterion; contact/support claims require appropriate evidence.
- Motions at the recording boundaries and missing foot/head channels have explicit handling.
- Every added detector has representative failure examples in the evaluation report.

## H2 / G1 — later contextual assistance

Fine hand configuration (interlaced fingers, clasping, rubbing, tapping), object manipulation/transfer, and communicative Gesture Phase require more detailed observation and validated models/rules.

Start with one well-defined target. Use reliable finger data or sufficient-resolution video; use object tracking when object identity/control is essential. For Gesture Phase, preserve the distinction between kinematic peaks/holds and communicative preparation/stroke/hold/retraction.

**Acceptance criteria**

- The detector emits candidates with evidence and uncertainty, not assumed social meaning.
- A kinematic nod is not automatically agreement; synchrony is not automatically mimicry; overlap is not automatically interruption.
- No mandatory Face/Gaze annotation module is introduced. Oculo outputs remain external evidence where relevant.
- Evaluation includes alternatives that share similar motion but different function, rather than only easy positive examples.

## Q1 — evaluation and release evidence

Create a small, reviewable reference set with documented sampling, actor/body coverage and inclusion criteria. Keep development/tuning examples distinguishable from held-out evaluation. Do not distribute private media or licensed weights unless authorized for that package.

Report metrics that match the target:

- interval detection: event matching rule, temporal overlap and onset/offset error;
- primitive/posture classification: confusion by class and body part, with support counts;
- speaker attribution: identity errors and overlap handling under a stated protocol;
- point events: timing error under a declared tolerance and event-pairing rule;
- contact: false proximity-as-contact cases and uncertain/occluded coverage;
- usability: time spent correcting candidates compared with manual annotation on a representative subset, rather than assumed time savings.

No numeric accuracy target is claimed by this backlog. Choose acceptance thresholds with the research protocol after baseline measurement.

### Release gate for every implemented task

1. The base app still launches without optional ML runtimes or network access for inference setup.
2. Relevant regression tests pass, including raw-source protection, stable IDs, draft cancellation, time shapes, offset handling and reviewed-data protection.
3. The label catalog and UI state the actual implemented capability. A planned classifier is never displayed as completed merely because its label exists.
4. Source-only and sample packages contain no virtual environment, cache, secrets or model weights. Original sample media remains unchanged.
5. Native Windows playback/packaging is reported only when tested on Windows. Linux offscreen tests remain labelled as such.
6. `TEST_REPORT.md` records the exact environment, commands, results and remaining limitations. Do not invent test runs, model downloads or benchmark accuracy.

## Spatial 与物体名称（0.5.3）

Spatial 新增 Object Spatial Relation（13 项）与 Object-relative Movement（7 项），分别记录人与物体的位置及相对移动。只需在 Objects… 填写名称，ID 自动生成；不要求物体模型或 Props 文件。前后左右选参照，between objects 选两个目标，其他普通关系只选一个。接触、倚靠和支撑继续在 HOI。完整说明见 [人与命名物体／区域](SPATIAL_OBJECTS_CN.md)。
