# Annotation Studio 0.5.4 — data schemas

This document describes the implemented project format, annotation contracts and source adapters. It does not imply support for arbitrary C3D, body-model, eye-tracker or scene files. Project JSON is the authoritative complete record.

## 1. Clocks, coordinates and time shape

Annotations use **master-clock seconds**. Source files retain native sample/frame rates and their source-local clocks:

```text
master_time = source_local_time + offset_s
source_local_time = master_time - offset_s
```

An offset is a constant shift, not automatic drift correction. Changing an asset offset does not retime already saved annotations. Automatic records retain the offset/configuration used for that particular run.

`temporal_kind` separates two shapes:

| Kind | Valid times | Interpretation |
| --- | --- | --- |
| `interval` | Finite `0 <= start_s < end_s` | A duration, treated as `[start_s, end_s)` in overlap calculations |
| `point` | Finite `0 <= start_s == end_s` | One timestamp; display marker width has no temporal meaning |

An interval never becomes a point just because it has zero length. Legacy records without `temporal_kind` default to interval and still require positive duration. Point events are explicitly typed. Current co-occurrence queries operate on intervals only and exclude points.

The viewer up axis and detector up axis control interpretation; neither rewrites raw coordinates. `world_frame_verified` is a user-maintained note, not a calibration transform or proof of correct units. Shared time, shared spatial frame and known length scale must be established before comparing two actors' absolute distance or object-surface geometry.

## 2. Project JSON version 3

Preferred extension: `.studio.json`. The loader accepts schema `annotationstudio.project` and legacy `ocumo.annotationstudio.project`, integer versions 1–3. Unsupported future versions are rejected. New saves use version 3:

```json
{
  "schema": "annotationstudio.project",
  "version": 3,
  "name": "Example interaction",
  "assets": [],
  "objects": [],
  "tracks": [],
  "labels": [],
  "annotations": [],
  "settings": {
    "duration_s": 120.0,
    "world_frame_verified": false,
    "up_axis": "Z",
    "project_note": ""
  }
}
```

The empty arrays illustrate structure. A new Project starts with the core vocabulary, ten Motion Primitive tracks per actor, and an Activity Episode track for each of R01 and R02. A saved empty track list stays empty on load. The bundled blank real-BVH example contains 71 tracks and no annotations. The synthetic schema demo keeps its deliberate ten-track layout.

### Assets

| Field | Type / purpose |
| --- | --- |
| `id` | Stable source ID used in provenance |
| `kind` | `motion`, `video`, `audio`, `gaze`, `aoi` or `props` |
| `role` | `R01`, `R02`, `Both`, `Scene` or `Unknown`, according to source assignment |
| `path` | Local source reference; original media is not embedded |
| `relative_to_project` | Serialized path resolves relative to the project-file parent |
| `offset_s` | Finite source-to-master shift |
| `name`, `enabled` | Display name and source enablement |
| `extra` | Adapter settings, for example video view |

Only one motion source per R01/R02 can be enabled in the current UI. Sources outside the project directory remain external references. Windows relative separators are handled on other platforms; unavailable Windows absolute paths are not rewritten into Linux-relative ones.

### Scene objects

`objects` is a stable instance registry, independent of prop trajectory or geometry data:

```json
{
  "id": "table_01",
  "name": "Round table",
  "object_class": "table",
  "notes": "Beside the sofa",
  "extra": {"retired": false}
}
```

`id` and `name` are nonempty strings. `object_class` and `notes` are strings; `extra` is a dictionary. Optional `extra.retired` is boolean. IDs are unique and immutable through the registry edit API. Renaming or retiring an instance preserves annotations referencing it. Retiring affects new suggestions, not historical data.

The registry UI requires only Display name. It generates an ID if omitted; class and notes may remain empty. An entry may represent a physical object or a named region. No mesh, model, props asset, coordinate, calibration or media is required to register an identity and manually annotate its relation.

HOI annotations store `attributes.object_id`. An old unresolved ID is allowed, preserved and displayed as unregistered; it does not cause an automatic fabricated object record. Registration does not establish 3D shape, pose, visibility, contact, support, force or object ownership. A prop centroid with a similar name is not automatically linked to a registry instance.

### Tracks

A track has `id`, `name`, `role`, `workspace`, `category`, `channel`, `body_parts`, `visible`, `color`, `order`, and `extra`:

```json
{
  "id": "r01-hand-support",
  "name": "Right hand contact / support",
  "role": "R01",
  "workspace": "HOI",
  "category": "Action / HOI",
  "channel": "Right Hand",
  "body_parts": ["Right Hand"],
  "visible": true,
  "color": null,
  "order": 0,
  "extra": {"label_scope": 0, "temporal_kind": "interval"}
}
```

- `extra.temporal_kind` is the creation default. New tracks receive an explicit value; legacy tracks without it fall back to current category metadata. The annotation's own kind governs rendering/editing.
- `extra.label_scope`: 0 core + project, 1 project, 2 temporary.
- `extra.allowed_label_ids`: absent means all labels allowed by type/scope/primary-channel applicability; explicit `[]` means none. IDs must belong to the track category when set through the API.
- `extra.target_role` is an explicit directed target. R01 never automatically means a target of R02. Pair annotations use `participants=["R01","R02"]`.
- A base color is separate from review-state brightness.

Multiple tracks may share role/category/channel. Display sublanes for overlaps are computed, not persistent track IDs. Historical mixed tracks are not silently split or semantically normalized on load.

### Primitive primary-channel contract

For `category="Motion Primitive"`, `Track.channel` is the primary body-part scope. New-project defaults are `Head`, `Torso`, `Left Arm`, `Right Arm`, `Left Hand`, `Right Hand`, `Left Leg`, `Right Leg`, `Root`, and `Full Body` for each actor. `body_parts` records participating/linked parts; it does not broaden the primary-channel vocabulary filter. New/reassigned annotations retain the relevant body-part metadata through the existing draft/track contract.

`Full Body` lists forms applicable to whole-body observation. A historical `Hands` channel still aggregates hand-specific choices. Track label lookup, the right-side palette and add-track preview must agree on primary-channel applicability, then apply scope and optional allowed-ID restrictions. An existing annotation's current out-of-list label remains available for inspection and editing, without remapping its stored identity.

Default creation and old-project loading are different operations. The explicit **Project → Add missing primitive tracks…** command supplements missing role/category/channel combinations, preserving existing IDs, names, order, custom labels and annotations. Repeated supplementation is idempotent; loading by itself does not supplement a project.

Public helpers:

```python
# New projects call this for R01 and R02; old projects only through an explicit action.
added_tracks = project.ensure_primitive_tracks(roles=('R01', 'R02'))

# Normal UI lookup applies the primary-body-part filter.
labels = project.labels_for_track(track_id)

# Vocabulary management can explicitly inspect the broader category list.
all_part_labels = project.labels_for_track(track_id, match_body_part=False)
```

The caller owns the undo checkpoint for `ensure_primitive_tracks`. The helper returns only newly added tracks and matches existing records by role/category/channel, preserving their visibility and label subsets. Unspecified/custom primitive labels without body-part metadata remain browsable; historical core labels can use the current ontology's part metadata as a read-only fallback. No label or annotation is rewritten by this lookup.

Squatting/kneeling labels belong to Body Posture. Their lowering/rising labels belong to Locomotion and use Full Body as the primary scope with involved legs recorded separately. Local knee/leg primitives belong to their local primary channels. Generic movement names take side from the primary channel and do not need duplicated left/right name variants. Coarse/fine movement alternatives do not imply duplicate records. The historical Body Posture `posture transition` identity is retained with `semantic_kind=posture_transition`, so consumers must not equate category membership with static state. This organization does not imply that their planned detectors exist.

### Labels and automation metadata

| Field | Purpose |
| --- | --- |
| `id` | Stable vocabulary identity |
| `name`, `category` | Display name and annotation type |
| `scope` | `core`, `project`, `temporary` |
| `aliases` | Alternative lookup names |
| `definition`, `boundary_rule` | Meaning and temporal criteria |
| `deprecated`, `version` | Retirement and label revision |
| `extra` | Metadata described below; merge history can include `replaced_by` |

Core IDs use the original category/name UUID5 identity. Renaming keeps the ID; merge retires the source and redirects mapped annotations with history. Unknown model text remains unmapped until an explicit review action; refreshing a view or adding another label does not automatically reinterpret it.

The active ontology separates:

| Metadata | Values / meaning |
| --- | --- |
| `recommended_workflow` | `automatic_primary`, `automatic_derived`, `assisted`, `manual_primary` |
| `implementation_status` | `builtin`, `optional_model`, `planned_rule`, `planned_model`, `manual` |
| `temporal_kind` | `interval` or `point` |
| `semantic_kind` | Description of motion, state, action, temporal relation, social function or uncertainty |
| `auto_mode` | Compatibility field: `manual`, `builtin_candidate`, `optional_model`, `interface_only` |
| `auto_method` | Specific implementation and validation caveats |
| `zh`, `group`, `body_parts`, `evidence_mode` | Translation, menu group, relevant anatomy and required evidence |

For example, elbow flexion has a built-in candidate rule, whereas kinematic hand waving has a planned rule. A hand-on-table state can be assisted while the registry already exists but contact recognition does not. Each record stores review status separately from detector capability.

Specific head, elbow and knee proposals store `attributes.primitive_evidence` with the rule, joint names, measured excursion and first/last native frame indices. Head records also store the dominant axis, axis share and reversal criteria. `attributes.config` records the analysis settings, and `original.native_prediction` preserves the source-local prediction. Segment times in the project use the master clock. These rule proposals have a null `confidence`; the measured angles support manual review.

The current catalog has 493 non-placeholder entries across 28 types, plus 28 Unlabeled entries. Motion contains 215 labels, including Motion Primitive 74, Body Posture 58 and Locomotion 24. The `gemep_affect` section of `label_catalog.json` lists the source and the 17 GEMEP category mappings to display names and stable IDs. Use `label_catalog.csv/json` and `LABEL_GUIDE.md` for exact active values. Saved projects preserve authored label definitions and metadata. UI fallback guidance reads them without mutation.

Interaction Event prioritizes 13 existing labels in five `Core` menu groups. Older preset group names are mapped at display time. Saved group metadata, authored definitions, label IDs and explicit track label subsets keep their original values.

Activity Episode uses workspace and channel `Activity`, positive-duration intervals, and a single actor. Its user description is stored in `notes`. The optional `attributes.object_id` references the same named object registry as HOI and Spatial. The native and analysis CSV fields carry the activity label, description and object identity.

### Annotations

In 0.5.1, the five new Hand Behavior relations are ordinary `semantic_kind=state` intervals. Actor and hand side use the existing role/channel fields; the actor's own chin/cheek is defined by the selected label. Notes can specify cheek side, which is not inferred from hand side. No new annotation schema or mandatory attributes were introduced. Read-only display grouping does not rewrite saved label metadata, and old broad contact records do not automatically acquire finer meanings.

| Fields | Purpose |
| --- | --- |
| `id`, `track_id` | Stable record and track references |
| `start_s`, `end_s`, `temporal_kind` | Master-clock bounds or explicit point |
| `role`, `channel`, `layer`, `category` | Actor, body/channel and interpretation layer |
| `label`, `label_id` | Display text and optional stable vocabulary reference |
| `status` | `pending`, `approved`, `rejected` |
| `source` | `manual`, imported source, or named `auto:...` generator |
| `confidence` | Detector-specific score or `null`; not a global accuracy probability |
| `reviewer`, `notes`, `tags` | Review metadata |
| `parent_id` | Optional parent/related reference |
| `original` | First prediction or record retained for audit |
| `history` | Edit records with timestamp, action, reviewer, before and after |
| `attributes` | Source provenance, object/effector references, relation dependencies and parameters |

Editing is a separate draft. Accepted UI state is stored as `approved`. Automatic and manual candidates can both be pending. A human edit keeps the detector source and its first original prediction.

A point example:

```json
{
  "id": "transition-example",
  "start_s": 12.4,
  "end_s": 12.4,
  "temporal_kind": "point",
  "role": "Both",
  "channel": "Speech",
  "category": "Turn Transition",
  "label": "speaker change candidate",
  "status": "pending",
  "source": "auto:speech-structure:v1",
  "attributes": {
    "from_turn_id": "turn-r01",
    "to_turn_id": "turn-r02",
    "from_role": "R01",
    "to_role": "R02",
    "boundary_offset_s": 0.2,
    "anchor_convention": "incoming_turn_start"
  }
}
```

The example omits default fields for readability. It does not imply that a change in audible speaker establishes an interaction-level handover.

HOI uses `attributes.object_id` and `attributes.effector`; track body parts are copied into `attributes.body_parts` for new/reassigned drafts. The object ID identifies the particular sofa/table/cup; the label identifies the relation. `hold object` means a person maintains control of an object; `rest on object` means a body part is resting on that object. Avoid reversing these relations.

### Automatic clocks and provenance

Motion jobs store master-clock annotation bounds and top-level original bounds, together with source IDs, source offsets, native spans, analysis ranges, model/configuration/run identifiers. Raw source-local segmentation provenance remains in `original.native_prediction`. Multi-asset derivations retain all applicable asset IDs and offsets.

Audio results preserve original sample indices, input rate/channel, native bounds, offset, model parameters and class scores. Asset/channel attribution is explicitly unverified until reviewed. A speech-structure run records separate confirmation that the selected Speaking tracks have the intended R01/R02 attribution; it does not rewrite an audio model into an identity recognizer.

### Save, history and recovery

Save validates identities and times, serializes finite JSON values, writes a temporary file, then atomically replaces the target. It does not rewrite any source media. The in-memory whole-project Undo/Redo includes objects, labels, tracks, assets and annotations. Persistent per-annotation history is different from the undo stack.

Recovery is a separate copy. Reserved `_recovery_original_path` and `_recovery_draft` settings preserve the original destination and a valid active draft. A recovered draft is not an accepted annotation. This recovery mechanism does not replace external backups or version control.

## 3. BVH

A BVH must contain a valid `HIERARCHY`, declared channels, `MOTION`, frame count and positive `Frame Time`. Each joint's rotation channel order is honored; a single assumed XYZ order is not applied to all joints. Forward kinematics uses offsets, root translation and local rotations.

The included R01/R02 sample files each contain 12,808 frames and a declared frame time of 0.008333 s. Their positional units and common spatial calibration are not established by that timing metadata. The final pose timestamp is `(nframes - 1) * frame_time`.

The renderer previews skeleton joints/bones. No body surface mesh, inverse kinematics fitting, retargeting, or BVH repair is performed. Analysis may sample fewer frames for feature extraction while retaining native sample timestamps and the original file unchanged.

## 4. Joint-position NPZ

The loader uses `numpy.load(..., allow_pickle=False)` and accepts a finite numeric array of shape `[frames, joints, 3]` under one of:

`joint_positions`, `joints`, `positions`, `joint_xyz`, `xyz`, `gpos`.

Optional metadata:

| Key | Shape/type | Meaning |
| --- | --- | --- |
| `fps` | positive scalar | Native uniform frame rate; if absent, 120 Hz is assumed and reported |
| `joint_names` | `[joints]` Unicode/byte strings | Unique joint names, ignoring case |
| `parents` | `[joints]` integer indices | Skeleton topology, using `-1` for roots; no cycles |

Without `parents`, the app shows points; it does not invent a bone chain. Without recognized anatomical names, body-specific heuristics may not find their required joints. Joint positions alone do not supply local Euler rotations, so BVH-only local rotation features are unavailable.

This format supports already-computed SMPL/SMPL-H joint positions. Arrays such as `poses`, `betas` or `trans` alone are not a renderable body model. C3D files and SMPL-H parameter-to-mesh reconstruction need separate future adapters.

## 5. Gaze CSV

Recommended columns for a ray endpoint:

```csv
time_s,origin_x,origin_y,origin_z,target_x,target_y,target_z
0.000,0,0,150,100,0,150
0.020,0,0,150,100,5,150
```

Or a direction:

```csv
time_s,origin_x,origin_y,origin_z,dir_x,dir_y,dir_z
0.000,0,0,150,1,0,0
0.020,0,0,150,1,0.05,0
```

Direction is normalized and displayed as a fixed visual ray length of 100 supplied coordinate units. It is not a measured gaze intersection distance. Time aliases include `time`, `timestamp_s`, `relative_time_s`, `aligned_time_s`, and `c3d_time_s`; naming a column `c3d_time_s` does not add C3D parsing or coordinate conversion.

Samples are sorted; duplicate timestamps keep the final valid row. Invalid/nonfinite rows are excluded. Gaze is only shown near a valid sample, not held indefinitely across missing data. Origins and endpoints must already be in the intended visualization coordinate system.

## 6. AOI CSV

Interval form:

```csv
start_s,end_s,label
1.0,2.4,partner face
3.0,4.2,cup_01
```

Sample form:

```csv
time_s,label
1.00,partner face
1.10,partner face
1.20,cup_01
1.30,cup_01
```

Sample sequences become intervals when the label changes or the gap exceeds 0.25 s; spans shorter than 0.05 s are omitted by this adapter. These are current import rules, not validated gaze event criteria. Use explicit intervals when exact boundaries matter. The imported asset supplies actor and offset mapping.

## 7. Prop centroids

CSV:

```csv
time_s,prop_id,x,y,z
0.0,cup_01,15,20,80
0.1,cup_01,15,20,81
0.1,box_01,30,10,70
```

NPZ accepts `[frames, props, 3]` or `[frames, 3]` under `prop_positions`, `translations`, `positions`, or `xyz`. Optional keys: `prop_names`, positive `fps`, and one increasing timestamp array `time_s`, `times`, or `timestamps_s`. If there are no timestamps, uniform times derive from `fps` (default 120).

Missing individual props may use NaN positions; infinity and wholly invalid datasets are rejected. A missing point is not placed at the origin. This adapter displays centroids only and does not infer hand contact, object shape or HOI labels.

## 8. Audio and video

Qt Multimedia controls video and audio playback. Filename extensions are filters, not a guarantee that every codec variant can be decoded on the target operating system.

Automatic audio analysis uses SoundFile and is intended for WAV/FLAC. It requires explicit selection for multichannel input: zero-based `channel=0/1/...`, or the deliberate `mix` option. GUI labels Channel 1 and Channel 2 correspond to zero-based 0 and 1. Model resampling/mixing operates on analysis buffers, never the source file.

See [AUDIO_MODELS.md](AUDIO_MODELS.md) for model input rates, window support, provenance and dependency installation.

## 9. Annotation CSV

The low-level `models.export_csv` includes every Annotation dataclass field, including `temporal_kind`. `original`, `history` and `attributes` are JSON strings inside CSV fields. Encoding is UTF-8 with BOM. A zero-duration record is valid only when explicitly typed point. From 0.5.4, the GUI uses the enriched exporter described in section 17, preserving these same native columns and appending convenient analysis columns.

The importer also accepts Stage2 review CSV. Precedence:

- Start: `corrected_start_s`, then `start_s`, then `start`.
- End: `corrected_end_s`, then `end_s`, then `end`.
- Label: `approved_L1_labels`, then `label`, then `kinematic_L1_labels`.

Missing `temporal_kind` defaults to interval. Native IDs survive a round trip. Stage2 event IDs derive from CSV basename plus event ID; subsequent native exports should use the explicit `id` for stable exchange. Importing an ID already present defaults to skip, not overwrite of reviewed data.

Invalid bounds, mismatched point endpoints, malformed structured fields or duplicate IDs report the CSV row. Explicitly exported `original={}` is preserved. Legacy/external rows without an original field retain the old uncorrected Stage2 bounds and label when corrected values are imported.

Annotation CSV is not the complete object registry or vocabulary. The 0.5.4 GUI includes readable names and its split bundles include a referenced-object lookup, while project JSON remains the complete record for definitions, tracks, assets and settings.

## 10. ELAN EAF export

The implemented EAF exporter accepts **intervals only**. If the selected set contains any point, it raises an error before creating or overwriting the destination. Select interval records intentionally, or use JSON/CSV for point-preserving interchange. There is no silent point skipping or artificial point duration.

Intervals are time-aligned in milliseconds. Overlaps occupy numbered subtiers keyed by actor/channel/category/track. A positive sub-millisecond interval becomes at least 1 ms in EAF only; project/CSV times remain unchanged.

EAF does not include complete vocabulary, object registry, attributes/history or an import-back implementation. It does not preserve arbitrary ELAN tier constraints. Review states are chosen in the export dialog and are not promoted by exporting.

## 11. Speech structure and derived-record dependencies

The rule builder accepts non-rejected R01/R02 interval annotations with category `Speaking` and label `Speaking`. Input tracks and approved-only filtering are optional. `attribution_confirmed=True` must reflect an explicit user/data mapping decision; the module performs no VAD, diarization or ASR.

```python
proposals, report = build_speech_structure(
    project, attribution_confirmed=True,
    merge_gap_s=0.3, short_turn_s=0.6,
    approved_only=False, track_ids=None,
)
```

This is read-only. It returns pending annotations and a preview report. `apply_speech_structure` commits the batch after checking the complete eligible input set against the report. A new, deleted or changed eligible Speaking/backchannel/curated-turn input invalidates the preview. The controller settles any active draft and owns its history checkpoint.

Generated source identifier: `auto:speech-structure:v1`.

| Output type | Shape / label |
| --- | --- |
| Speech Turn | Interval, `speaker turn` |
| Speech Timing | Interval, `overlapping speech`, `within-turn pause`, `between-turn gap` |
| Turn Transition | Point, `speaker change candidate` |

The configurable short-pause rule creates proposals, not a universal definition of a conversational turn. A short contribution is flagged, not automatically labelled a backchannel. Only explicitly approved backchannel intervals can explain/exclude fully covered speech contributions from floor-taking candidates; those speech intervals still count for acoustic overlap.

Generated `attributes` include `algorithm`, `scope_key`, `parameters`, `source_annotation_ids`, `dependency_snapshots`, `dependency_signature`, `all_dependencies_reviewed`, `review_reasons`, `attribution_confirmed_for_run`, and `conversational_floor_verified=false`. Turn records also identify their Speaking/backchannel inputs. Transitions include from/to turn IDs and roles, the anchor convention, signed boundary offset, actual turn overlap and an intervening-speech flag.

A point uses the incoming turn start. A positive `boundary_offset_s` is a gap between the selected boundaries; a negative value is an overlapping entry. Neither alone proves interruption, listener status or social intent.

Reruns replace only untouched pending outputs in the matching scope when replacement is enabled. Reviewed/rejected/edited results are protected. Reviewed/edited turns can act as retained anchors; rejected ones do not. A reviewed relation also retains the generated parent turns needed to keep its links resolvable. Curated coverage is subtracted from input Speaking spans, allowing newly uncovered fragments to produce residual candidates. A protected derived record whose dependencies change remains saved and is reported stale. `dependency_issues(project, annotation)` follows direct and transitive dependencies, detects cycles, and returns affected upstream IDs.

The commit returns counts `added`, `removed`, `protected`, `skipped_duplicates`, `blocked_dependencies`, `stale_protected`, `retained_dependency_parents`, `retained_dependency_turns`, `residual_turn_candidates` and `clipped_speaking_fragments`. Analysis → Recheck derived results exposes affected records without changing them. There is no global always-on recomputation. Rebuild after upstream edits and inspect stale protected records; do not silently rewrite human work.

## 12. Read-only context/intersection results

```python
rows, summary = intersect_tracks(
    project, first_track_id, second_track_id,
    same_actor=True, approved_only=False,
    label_a=None, label_b=None, object_a=None, object_b=None,
)
```

Queries require two different existing tracks and select valid non-rejected intervals. Points are excluded. Same-actor mode requires the same known R01/R02; Unknown, Scene and Both are excluded from eligible inputs in that mode. Review state, exact label and object-ID filters are optional. Source annotations are not changed, split or copied into a new compound label.

From 0.5.3, object filters match the primary `object_id` or the active second target of a `between objects` record. The context result/CSV adds `secondary_object_a` and `secondary_object_b`. Hidden second-target values retained under another relation are not interpreted as active matches. The existing context dialog includes active second targets in its dropdown and cell text without adding columns.

Each result row contains start/end/duration, both roles, categories, labels, object IDs, statuses and source annotation IDs, plus `both_reviewed`. `export_context_csv(path, rows)` exports these pair rows; the summary is displayed separately and is not embedded into that CSV.

`summary` includes source counts, pair-row count, source time unions, `overlap_union_s`, reviewed overlap union and coverage fractions. Pair rows may overlap; summing their durations can double-count time. Aggregate with the interval union. Fractions divide by the selected source-track time unions; an empty denominator yields `None`. These are elapsed-time measures, not participant-seconds.

“Speaking while sitting on sofa_01” can be queried by intersecting Speaking with an HOI state. Using Speech Turn instead includes any internal pauses. The result expresses temporal co-occurrence only and does not establish a co-speech gesture, response or causal relation.

## 13. Compatibility and migration boundaries

All original 187 v0.2 category/name UUID5 identities remain addressable. v0.3 Dialogue Event `speaker turn` and `turn handover` remain historical entries when new distinct types are added. Renamed/deprecated labels are preserved on old records; existing labels and tracks are not silently recategorized to the new hierarchy.

The active workspace structure is defined by `ontology.py`. Spatial holds spatial relations and Social holds contextual interaction events. Activity Relation is a historical Motion category. Its tracks and records remain accessible and exportable. `unclassified motion candidate` remains pending until a reviewer chooses a supported specific form. Historical reviews retain their original identity. Face and gaze annotation are absent from new menus; supported external reference/media adapters remain.

A v2 load preserves authored labels, annotation mappings, original predictions, history, track metadata and unresolved object references. Missing current core IDs are appended. Version 3 adds an empty registry when absent and defaults old annotations to intervals. It does not manufacture props, contacts, speaker identities, reviewed negatives or semantic ground truth.

## 14. Optional interpretation fields in 0.5.0

Schema remains version 3. New human-entered values use the existing attributes object:

```json
{
  "annotation_fields_version": 1,
  "target_role": "R02",
  "physical_interaction": {"outcome": "completed"},
  "human_judgment": {
    "certainty": "high",
    "evidence_sources": ["reference_video", "body_motion"],
    "evidence_origin": "observed_expression"
  }
}
```

Affect supplies optional attributes described below. Historical `affect: {"valence": null, "arousal": 3}` records remain readable and keep their category. Valence is optional integer −2…+2; arousal is optional integer 1…5. Unknown/null is distinct from neutral valence=0. No implicit multilabel inference is performed.

Physical outcomes are unspecified/null, attempted, completed, partial, aborted or uncertain. Judgment certainty is separate from detector confidence and review status. Evidence origin differentiates observed_expression, scenario_prompt and participant_report; those sources must not be pooled as the same observer target. Evidence sources are a list and can retain unknown future strings. Contact body parts currently belong in Notes; no helper/recipient phase graph is silently created.

Controls appear only for their relevant categories, and only explicitly edited fields are patched. Binding, boundary edits and Cancel retain arbitrary legacy attributes and unknown nested keys. The opt-in field version defines validation; unversioned/future formats retain their authored interpretation. Native project JSON and annotation CSV preserve these attributes; EAF does not preserve the full contract.

`project.ensure_annotation_tracks(roles=('R01','R02'))` returns added tracks only. It calls the part-specific primitive helper, supplies one lane per missing actor/type, and pair lanes only when both actors are selected. Authored hidden/restricted tracks count. It skips QC / Notes, does not inspect media, and does not run on load. The UI owns the history checkpoint and skips no-op checkpoints.

## 15. Compact Affect modes in 0.5.2

Project schema stays at version 3 and optional field validation stays at version 1. New fields extend the existing `attributes.affect` object:

```json
{
  "annotation_fields_version": 1,
  "affect": {
    "annotation_mode": "adjective_intensity",
    "intensity": 3
  }
}
```

The normal annotation `label` and `label_id` retain the selected category identity. The UI can display an adjective from `Label.extra.affect_adjective`; saved canonical names, IDs, authored definitions and histories remain unchanged.

For independent dimensions, `annotation_mode` is `valence_arousal`, and the annotation uses the dedicated core label `valence / arousal rating`. It does not use neutral or Unlabeled as an emotion placeholder:

```json
{
  "annotation_fields_version": 1,
  "affect": {
    "annotation_mode": "valence_arousal",
    "valence": 1,
    "arousal": 2,
    "intensity": 3,
    "adjective_label": "amusement",
    "adjective_label_id": "the previously selected stable label ID"
  }
}
```

The optional prior adjective fields above illustrate a record explicitly switched from the first mode. A new dimensional record needs neither adjective nor intensity. Inactive values are retained; the active mode determines the default display. Switching back restores the remembered label without silently expanding track restrictions. The code uses the actual stable label ID, not the illustrative text above.

Intensity is an optional ordinal integer 1…5; it is neither arousal nor annotator confidence. Valence −2…+2 and arousal 1…5 may independently be null. Dimensional Accept requires at least one supplied rating; an unfinished candidate may keep both unknown. No label automatically fills scores, and no score automatically becomes an emotion category.

`annotation_mode`, `adjective_label` and `adjective_label_id` accept strings/null under v1 validation; unknown strings remain available for future formats. Old unversioned continuous scores and future-version metadata are not normalized simply by opening, editing a boundary or choosing another optional field. Unknown nested keys are preserved.

Evidence, origin and human judgment remain optional and unchanged in storage; the Affect editor puts them under collapsed More details. Cancel discards all draft changes. Native JSON/CSV preserve these fields. EAF exports interval text and does not preserve the ratings or mode contract.

## 16. Person-to-named-object Spatial fields in 0.5.3

Schema 3 and annotation_fields_version 1 remain unchanged. The two new categories are Object Spatial Relation (states) and Object-relative Movement (movement), under Spatial. Each records the actor's whole-person position/movement, not a hand contact. They use the same named-object registry as HOI.

```json
{
  "annotation_fields_version": 1,
  "object_id": "counter_01",
  "spatial_relation": {
    "reference_frame": "object_intrinsic"
  }
}
```

For `between objects`, `object_id` is target A and `spatial_relation.secondary_object_id` is target B. The actor remains `role=R01` or `R02`; a second object is not a second person. The editor only shows B for that relation. For the four front/back/left/right relations, it shows Reference with `object_intrinsic` (defined object front) and `scene_reference` (fixed scene directions). These are manually chosen interpretation frames, not geometry or camera transformations. A convention can be recorded once in project/object notes without a model.

Under v1 validation, `spatial_relation` is an object and its known reference/secondary-ID fields are strings or null; unknown nested keys and strings are preserved. Unversioned/future metadata retains its authored interpretation. No label change deletes hidden prior fields.

The editor and EditSession Accept path apply the relation requirements after resolving the prospective label identity:

- Normal new/reclassified spatial records need an active registered primary target.
- Between needs two different active registered targets.
- Front/back/left/right need an explicit supported reference frame.
- The two uncertainty labels allow an unspecified target.
- Incomplete candidates remain saveable. Existing approved records whose relation, actor, track and object/reference identity are unchanged can receive boundary/notes edits while preserving unresolved, retired or future-format references.

Validation precedes history checkpoints and custom-label creation. Cancel does not modify committed data. Loading preserves the existing track list. Explicit supplementation for the current vocabulary yields 71 tracks without QC. A newly generated example has 72 including QC. The bundled blank real-BVH example still has its original 71 tracks.

`annotation_object_ids` reports all stored primary/secondary IDs, including inactive retained references, for registry usage counts. `active_secondary_object_id` is narrower: only a current between relation contributes a second target to semantic context queries. Neither helper infers geometry or creates missing objects.

Native JSON/CSV preserve the fields. EAF remains an interval-text exchange and does not preserve the target/reference contract. No automatic person-object spatial detector is implemented in this release.

## 17. Combined and per-type annotation exports (0.5.4)

`annotation_export.py` provides a read-only export layer. It does not mutate annotations, tracks, labels, object registration, project save path or source assets. The project schema remains version 3; the export-manifest schema is independent.

### Selection and API

```python
from annotationstudio.annotation_export import (
    available_export_types, select_annotations,
    export_annotation_csv, export_annotation_bundle,
)

export_annotation_csv(
    project, 'Practice_Session_hoi.csv',
    review_state='accepted', categories=['Action / HOI'],
)
result = export_annotation_bundle(
    project, 'results', review_state='candidates_accepted',
    categories=['Motion Primitive', 'Action / HOI'], layout='both',
)
```

Review keys are `accepted` (approved only), `candidates_accepted` (pending plus approved), and `all`. `categories=None` means every type; an empty iterable means no types and cannot generate a file. Filtering uses the annotation's stored `category`, not its track's category, current workspace, visibility or label preset membership. Authored custom and historical categories remain available.

`available_export_types` returns category/workspace/total_count/count for types present in tracks or annotations; `count` reflects the review filter. `select_annotations` returns the committed records ordered by start_s, role and id. No asset offset is reapplied. Both roles remain rows in the same file, and point records retain their exact bounds.

The GUI offers Combined table, Separate tables by type, and Combined + separate tables (default). Both and Separate choose a parent directory and create a fresh result directory; Combined chooses one CSV path. All types is the default type scope; Choose types exposes checkboxes. The same review/type selection applies to EAF, but EAF stays single-file and refuses any selection containing points.

### CSV columns and round trip

`CSV_COLUMNS` is all original Annotation fields followed by:

```text
workspace, track_name, annotation_fields_version,
object_id, object_name, object_class,
secondary_object_id, secondary_object_name, spatial_reference_frame,
effector, target_role, affect_mode, affect_intensity, affect_valence, affect_arousal
```

The extra columns are derived views. `workspace` uses the authored track workspace when available, otherwise the category fallback; it does not redefine category partitioning. Names are looked up in the registry at export time. Unresolved IDs stay intact with blank names. `secondary_object_id/name` represents only the active second target of a current between relation; `spatial_reference_frame` is populated for the four directional relations. Hidden retained values remain in the original attributes JSON.

`affect_mode` reads stored `affect.annotation_mode`. Scalar values are copied as stored, including unknown/future scales; they are not converted into current ratings. Null becomes blank and zero stays zero. Retained inactive mode values may appear, so consumers must use mode and annotation_fields_version when interpreting scores. Containers that cannot be represented as a scalar remain in the authoritative attributes JSON.

`original`, `history` and `attributes` remain complete JSON strings, including explicitly empty original objects and unknown fields. The native importer reads the original columns and ignores the new convenience columns. Changing only a convenience column does not change the imported authoritative attribute or registry. Importing duplicate annotation IDs retains the existing skip-by-default policy.

### Split bundle and objects

Each nonempty category writes one CSV. When layout is `both`, the combined CSV contains exactly the union of those per-category records, once per annotation ID, with identical columns and values. Empty requested types are listed in the manifest and do not create empty annotation files.

Portable filenames use a sanitized project stem and category stem; Action / HOI uses `hoi`, Perceived Affect uses `affect`. Reserved names, traversal characters and collisions (including case-only or total/objects-name collisions) are resolved without changing saved category text. The manifest maps each type to its actual filename.

Each split bundle also writes `<stem>_objects.csv` with columns:

```text
object_id, object_name, object_class, notes, retired, missing, reference_count, extra
```

Only references from the selected annotations are included, including retained inactive secondary references. A missing reference row records the unresolved ID and `missing=True`; it never registers a new scene object. `extra` is retained as JSON. An export with no object references contains a header-only object lookup.

`<stem>_export_manifest.json` uses schema `annotationstudio.annotation_export`, version 1. It records application version, source project name/filename, filters, selected/skipped categories, time convention, per-table row counts, object scope, column interpretation and file byte counts/SHA256 hashes. The manifest excludes its own hash. It does not include an unfiltered project backup or copy source media.

### Write guarantees

All selected records and serializable metadata are validated before publishing any final output. A single CSV uses a temporary sibling and atomic replacement at the explicitly selected path; source asset and project-file paths are protected. Split payloads are fully staged in a private sibling directory, then moved to a fresh uniquely named result directory. Existing result directories are skipped, and failure cleanup removes only this operation's staging data.

On Windows, bundle directory names budget all final leaf paths in UTF-16 units, keeping them within 259 units without relying on machine long-path policy. The directory's project-name prefix can be shortened; CSV names and saved identities remain unchanged. A parent with insufficient room is rejected before publication. This prevents a successful staging-directory rename from producing files inaccessible through ordinary Windows paths. See [the source release verification report](../TEST_REPORT.md) for the scope of testing.
