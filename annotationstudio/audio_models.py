"""Optional local audio detectors and honest, reviewable annotation proposals.

Importing this module never imports a machine-learning framework or downloads a
model. ``detect_audio`` is intended to run in the application's worker thread.
Audio samples and source files are never changed. The energy detector is an
activity baseline, not a speech detector. No detector creates Listener labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata, util
from pathlib import Path
from typing import Callable
import csv
import math
import sys
import uuid

import numpy as np
from scipy.signal import resample_poly

from .models import Annotation


YAMNET_URL = "https://tfhub.dev/google/yamnet/1"
YAMNET_SAMPLE_RATE = 16000
YAMNET_HOP_S = 0.48
YAMNET_SUPPORT_S = 0.975
# The official 521-class map is fixed for google/yamnet/1. Subclasses of laughter
# are combined with max, while all triggering original class scores are retained.
YAMNET_CLASSES = {
    "Laughter": {13: "Laughter", 15: "Giggle", 16: "Snicker",
                 17: "Belly laugh", 18: "Chuckle, chortle"},
    "Sigh": {23: "Sigh"},
    "Gasp": {39: "Gasp"},
    "Cough": {42: "Cough"},
    "Throat clearing": {43: "Throat clearing"},
    "Sneeze": {44: "Sneeze"},
    "Sniff": {45: "Sniff"},
    "Breathing": {36: "Breathing"},
    "Crying": {19: "Crying, sobbing"},
}
DEFAULT_VOCAL_LABELS = ("Laughter", "Sigh", "Gasp", "Cough",
                        "Throat clearing", "Sneeze", "Sniff")


class AudioModelError(RuntimeError):
    """A detector is unavailable, misconfigured, or failed to load."""


class AudioCancelled(RuntimeError):
    """Cancellation aborts the run; no partial proposal list is returned."""


def _has_module(name: str) -> bool:
    try:
        return util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unknown"


def bundled_yamnet_path() -> Path | None:
    """Locate the optional official SavedModel in a source or frozen install."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    directory = root / "models" / "yamnet"
    if ((directory / "saved_model.pb").is_file()
            and (directory / "assets" / "yamnet_class_map.csv").is_file()
            and (directory / "variables" / "variables.index").is_file()
            and any(shard.is_file() for shard in (directory / "variables").glob("variables.data-*-of-*"))):
        return directory
    return None


def model_status() -> list[dict]:
    """Cheap dependency checks, not a claim that model inference was verified.

    ``available`` means Python dependencies are discoverable. ``needs_model``
    distinguishes YAMNet's separately selected SavedModel. A successful run is
    still required to verify native libraries and model loading on this machine.
    """
    audio = _has_module("soundfile")
    silero = audio and _has_module("torch") and _has_module("silero_vad")
    tf = audio and _has_module("tensorflow")
    hub = _has_module("tensorflow_hub")
    local_yamnet = bundled_yamnet_path()
    if tf and local_yamnet is not None:
        yamnet_detail = "Bundled YAMNet model found. The model loads locally when Run is pressed."
    elif tf:
        yamnet_detail = "TensorFlow installed. Select a local YAMNet SavedModel directory."
        if hub:
            yamnet_detail += " TensorFlow Hub is available for an explicit download."
    else:
        yamnet_detail = "Optional: install requirements-audio-yamnet.txt to load a local YAMNet SavedModel."
    return [
        {"id": "energy", "name": "Audio activity (energy)",
         "available": audio, "needs_model": False, "ready": audio,
         "detail": ("RMS activity baseline. Does not recognize speech or vocal events."
                    if audio else "Install soundfile to read WAV/FLAC audio.")},
        {"id": "silero", "name": "Silero VAD · Speaking candidates",
         "available": silero, "needs_model": False, "ready": False,
         "detail": ("Dependencies installed; bundled model loads when Run is pressed. "
                    "Loading and inference have not been checked by this status query."
                    if silero else "Optional: install requirements-audio-silero.txt. "
                    "No speech model has been loaded.")},
        {"id": "yamnet", "name": "YAMNet · Vocal event candidates",
         "available": tf, "needs_model": local_yamnet is None, "ready": False,
         "bundled_model_path": str(local_yamnet) if local_yamnet is not None else None,
         "can_download": tf and hub,
         "detail": yamnet_detail},
    ]


def _check_cancel(cancel) -> None:
    requested = (cancel.is_set() if hasattr(cancel, "is_set") else cancel()) if cancel else False
    if requested:
        raise AudioCancelled("Audio analysis cancelled; no proposals were committed.")


def _progress(progress, message: str) -> None:
    if progress:
        progress(message)


def _number(value, name: str, minimum=None, maximum=None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number.")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    if maximum is not None and result > maximum:
        raise ValueError(f"{name} must be at most {maximum}.")
    return result


@dataclass
class _Audio:
    path: Path
    sample_rate: int
    frames: int
    channels: int
    selected_channel: int | str
    start_s: float
    end_s: float

    @property
    def duration_s(self):
        return self.frames / self.sample_rate

    def read(self, start_s: float, end_s: float, target_sr: int | None = None) -> np.ndarray:
        """A bounded source read. Analysis resampling never touches the file."""
        import soundfile as sf
        start = max(0, min(self.frames, int(round(start_s * self.sample_rate))))
        stop = max(start, min(self.frames, int(round(end_s * self.sample_rate))))
        with sf.SoundFile(str(self.path)) as stream:
            stream.seek(start)
            block = stream.read(stop - start, dtype="float32", always_2d=True)
        if not np.isfinite(block).all():
            raise ValueError("Audio contains non-finite samples; repair a copy before analysis.")
        if self.selected_channel == "mix":
            waveform = block.mean(axis=1, dtype=np.float32)
        else:
            waveform = block[:, self.selected_channel]
        waveform = np.ascontiguousarray(waveform, dtype=np.float32)
        if target_sr and target_sr != self.sample_rate and len(waveform):
            divisor = math.gcd(self.sample_rate, target_sr)
            waveform = resample_poly(waveform, target_sr // divisor,
                                     self.sample_rate // divisor).astype(np.float32)
        return waveform


def _open_audio(path, channel, start_s, end_s) -> _Audio:
    if not _has_module("soundfile"):
        raise AudioModelError("Audio decoding requires soundfile. Install the main requirements.txt.")
    import soundfile as sf
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {target}")
    try:
        info = sf.info(str(target))
    except (RuntimeError, OSError) as exc:
        raise AudioModelError("Cannot decode this audio. Import a WAV or FLAC file; "
                              "the original recording is left unchanged.") from exc
    if info.samplerate <= 0 or info.channels <= 0:
        raise ValueError("Audio sample rate and channel count must be positive.")
    if channel is None:
        if info.channels != 1:
            raise ValueError(f"This file has {info.channels} channels. Select a zero-based "
                             "channel index or explicitly choose 'mix'; a channel is not "
                             "automatically identified as a speaker.")
        channel = 0
    if channel != "mix":
        if isinstance(channel, bool) or not isinstance(channel, (int, np.integer)):
            raise ValueError("channel must be a zero-based integer, 'mix', or None for mono.")
        channel = int(channel)
        if not 0 <= channel < info.channels:
            raise ValueError(f"channel must be between 0 and {info.channels - 1}.")
    start_s = _number(start_s, "start_s", 0)
    duration = info.frames / info.samplerate
    end_s = duration if end_s is None else _number(end_s, "end_s", 0)
    if start_s > duration or end_s < start_s:
        raise ValueError("The requested native audio range is outside the file.")
    end_s = min(end_s, duration)
    return _Audio(target, info.samplerate, info.frames, info.channels,
                  channel, start_s, end_s)


def _merge_intervals(intervals: list[dict], gap: float, min_duration: float) -> list[dict]:
    """Merge already typed intervals while preserving score/source summaries."""
    result = []
    for value in sorted(intervals, key=lambda x: (x["start"], x["end"])):
        if value["end"] <= value["start"]:
            continue
        item = {**value, "raw_scores": dict(value.get("raw_scores", {}))}
        if result and item["start"] <= result[-1]["end"] + gap + 1e-9:
            prev = result[-1]
            prev["end"] = max(prev["end"], item["end"])
            prev["count"] = prev.get("count", 1) + item.get("count", 1)
            prev["score_sum"] = prev.get("score_sum", 0.) + item.get("score_sum", 0.)
            if item.get("score") is not None:
                prev["score"] = max(prev.get("score") or 0., item["score"])
            for key, score in item["raw_scores"].items():
                prev["raw_scores"][key] = max(prev["raw_scores"].get(key, -math.inf), score)
        else:
            result.append(item)
    return [x for x in result if x["end"] - x["start"] + 1e-9 >= min_duration]


def _energy(audio: _Audio, params, progress, cancel):
    threshold_db = _number(params.get("db_threshold", -36.), "db_threshold", -120., 20.)
    window_s = _number(params.get("window_s", 0.04), "window_s", .005, 1.)
    hop_s = _number(params.get("hop_s", .02), "hop_s", .002, window_s)
    # Integer source frames avoid gaps/drift at non-16k sample rates.
    window = max(1, round(window_s * audio.sample_rate))
    hop = max(1, round(hop_s * audio.sample_rate))
    first = round(audio.start_s * audio.sample_rate)
    last = round(audio.end_s * audio.sample_rate)
    count = max(0, math.ceil((last - first) / hop))
    frames_per_batch = max(1, int(30 * audio.sample_rate / hop))
    candidates = []
    for base in range(0, count, frames_per_batch):
        _check_cancel(cancel)
        n = min(frames_per_batch, count - base)
        read_start = first + base * hop
        read_end = min(last, read_start + (n - 1) * hop + window)
        waveform = audio.read(read_start / audio.sample_rate, read_end / audio.sample_rate)
        energy = np.concatenate(([0.], np.cumsum(waveform.astype(np.float64) ** 2)))
        starts = np.arange(n, dtype=np.int64) * hop
        stops = np.minimum(starts + window, len(waveform))
        valid = stops > starts
        rms = np.zeros(n, dtype=np.float64)
        rms[valid] = np.sqrt((energy[stops[valid]] - energy[starts[valid]]) /
                             (stops[valid] - starts[valid]))
        db = 20 * np.log10(np.maximum(rms, 1e-12))
        mask = valid & (db >= threshold_db)
        edges = np.diff(np.concatenate(([False], mask, [False])).astype(np.int8))
        for begin, finish in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            candidates.append({"start": (read_start + int(starts[begin])) / audio.sample_rate,
                               "end": (read_start + int(stops[finish - 1])) / audio.sample_rate,
                               "score": None,
                               "raw_scores": {"peak_rms_dbfs": float(db[begin:finish].max())},
                               "count": int(finish - begin)})
        _progress(progress, f"Audio activity (energy): {min(100, (base + n) * 100 // max(1, count))}%")
    gap = _number(params.get("merge_gap", .1), "merge_gap", 0., 30.)
    minimum = _number(params.get("min_duration", .15), "min_duration", 0., 60.)
    events = _merge_intervals(candidates, gap, minimum)
    for event in events:
        event.update(label="Audio activity (energy)", category="Audio Activity")
    settings = {"db_threshold": threshold_db, "window_s": window / audio.sample_rate,
                "hop_s": hop / audio.sample_rate, "merge_gap": gap,
                "min_duration": minimum, "score_kind": "RMS dBFS; not speech probability"}
    return events, settings, "rms-v1"


def _silero(audio: _Audio, params, progress, cancel):
    if not _has_module("torch") or not _has_module("silero_vad"):
        raise AudioModelError("Silero VAD is optional. Install requirements-audio-silero.txt "
                              "in the same Python environment, then retry.")
    threshold = _number(params.get("threshold", .5), "threshold", .01, .99)
    minimum = _number(params.get("min_duration", .25), "min_duration", 0., 60.)
    gap = _number(params.get("merge_gap", .1), "merge_gap", 0., 30.)
    chunk_s = _number(params.get("chunk_seconds", 60.), "chunk_seconds", 5., 300.)
    padding_ms = int(_number(params.get("speech_pad_ms", 30), "speech_pad_ms", 0, 2000))
    _check_cancel(cancel)
    _progress(progress, "Loading bundled Silero VAD model locally…")
    try:
        import torch
        from silero_vad import load_silero_vad, get_speech_timestamps
        model = load_silero_vad(onnx=False)
    except Exception as exc:
        raise AudioModelError(f"Silero VAD could not load. Check its torch runtime and "
                              f"bundled model files. {exc}") from exc
    candidates = []
    cursor = audio.start_s
    while cursor < audio.end_s:
        _check_cancel(cancel)
        end = min(audio.end_s, cursor + chunk_s)
        # One second of context avoids resetting the model exactly at a seam.
        read_start = max(audio.start_s, cursor - 1.)
        read_end = min(audio.end_s, end + 1.)
        waveform = np.clip(audio.read(read_start, read_end, 16000), -1., 1.)
        with torch.inference_mode():
            spans = get_speech_timestamps(
                torch.from_numpy(waveform), model, sampling_rate=16000,
                threshold=threshold, min_speech_duration_ms=round(minimum * 1000),
                min_silence_duration_ms=max(1, round(gap * 1000)),
                speech_pad_ms=padding_ms, return_seconds=False)
        for span in spans:
            start = max(cursor, read_start + float(span["start"]) / 16000)
            stop = min(end, read_start + float(span["end"]) / 16000)
            if stop > start:
                candidates.append({"start": start, "end": stop, "score": None,
                                   "count": 1, "raw_scores": {}})
        cursor = end
        _progress(progress, f"Silero VAD: {round(100 * (cursor - audio.start_s) / max(1e-9, audio.end_s - audio.start_s))}%")
    events = _merge_intervals(candidates, gap, minimum)
    for event in events:
        event.update(label="Speaking", category="Speaking")
    settings = {"threshold": threshold, "min_duration": minimum, "merge_gap": gap,
                "speech_pad_ms": padding_ms, "analysis_sample_rate": 16000,
                "chunk_seconds": chunk_s, "context_seconds": 1.,
                "input_transform": "resample then clip analysis samples to [-1, 1]",
                "score_kind": "timestamps only; no calibrated event confidence"}
    return events, settings, _version("silero-vad")


def _load_yamnet(model_path, download: bool, progress):
    if not _has_module("tensorflow"):
        raise AudioModelError("YAMNet requires the optional requirements-audio-yamnet.txt.")
    directory = Path(model_path).expanduser().resolve() if model_path else bundled_yamnet_path()
    if directory is not None:
        if not directory.is_dir() or not (directory / "saved_model.pb").is_file():
            raise AudioModelError("Select a local YAMNet SavedModel directory containing "
                                  "saved_model.pb. A checkpoint file is not a SavedModel.")
        _progress(progress, "Loading local YAMNet SavedModel…")
        try:
            import tensorflow as tf
            with tf.device("/CPU:0"):
                model = tf.saved_model.load(str(directory))
        except Exception as exc:
            raise AudioModelError(f"Cannot load local YAMNet SavedModel: {exc}") from exc
        origin = str(directory)
    elif download:
        if not _has_module("tensorflow_hub"):
            raise AudioModelError("Explicit YAMNet download requires tensorflow-hub.")
        _progress(progress, "Downloading/loading YAMNet from the official TensorFlow Hub…")
        try:
            import tensorflow as tf
            import tensorflow_hub as hub
            with tf.device("/CPU:0"):
                model = hub.load(YAMNET_URL)
        except Exception as exc:
            raise AudioModelError(f"YAMNet download/load failed; no candidates were committed. {exc}") from exc
        origin = YAMNET_URL
    else:
        raise AudioModelError("No bundled YAMNet model was found. Select a local SavedModel "
                              "directory, or explicitly enable download for this Run.")
    if not callable(model):
        raise AudioModelError("This SavedModel does not expose the official callable YAMNet API.")
    _validate_yamnet_vocabulary(model)
    return model, origin


def _validate_yamnet_vocabulary(model):
    """Do not attach official class names to an arbitrary 521-output model."""
    if not callable(getattr(model, "class_map_path", None)):
        raise AudioModelError("YAMNet must include its class_map_path() asset. "
                              "Copy the complete official SavedModel directory.")
    try:
        class_path = model.class_map_path()
        if hasattr(class_path, "numpy"):
            class_path = class_path.numpy()
        if isinstance(class_path, bytes):
            class_path = class_path.decode("utf-8")
        with open(class_path, "r", encoding="utf-8-sig", newline="") as stream:
            names = {int(row["index"]): row["display_name"] for row in csv.DictReader(stream)}
        for classes in YAMNET_CLASSES.values():
            for index, name in classes.items():
                if names.get(index) != name:
                    raise ValueError(f"Output {index} must be {name!r}, got {names.get(index)!r}.")
    except Exception as exc:
        raise AudioModelError(f"YAMNet class map is missing or incompatible: {exc}") from exc


def _yamnet(audio: _Audio, model_path, params, progress, cancel):
    threshold = _number(params.get("threshold", .35), "threshold", .01, 1.)
    gap = _number(params.get("merge_gap", .1), "merge_gap", 0., 30.)
    minimum = _number(params.get("min_duration", .1), "min_duration", 0., 60.)
    requested = params.get("labels", DEFAULT_VOCAL_LABELS)
    if isinstance(requested, str):
        requested = [requested]
    labels = list(dict.fromkeys(requested))
    unknown = set(labels) - YAMNET_CLASSES.keys()
    if unknown or not labels:
        raise ValueError("Select supported YAMNet vocal labels: " + ", ".join(YAMNET_CLASSES))
    per_class = params.get("thresholds", {})
    if not isinstance(per_class, dict):
        raise ValueError("thresholds must be a dictionary from Studio label to threshold.")
    limits = {label: _number(per_class.get(label, threshold), f"{label} threshold", .01, 1.)
              for label in labels}
    download = params.get("download", False)
    if not isinstance(download, bool):
        raise ValueError("download must be explicitly True or False.")
    _check_cancel(cancel)
    model, origin = _load_yamnet(model_path, download, progress)
    _check_cancel(cancel)
    # Matches the official pad_waveform: first 15,600 samples, then 7,680-sample
    # hops. ceil(duration/hop) would over-request an extra frame near the tail.
    count = max(1, math.ceil(((audio.end_s - audio.start_s) - YAMNET_SUPPORT_S) /
                             YAMNET_HOP_S - 1e-9) + 1)
    batch_size = 60  # <=29.3 seconds of resampled audio, independent of file length
    candidates = {label: [] for label in labels}
    for base in range(0, count, batch_size):
        _check_cancel(cancel)
        n = min(batch_size, count - base)
        start = audio.start_s + base * YAMNET_HOP_S
        end = min(audio.end_s, start + (n - 1) * YAMNET_HOP_S + YAMNET_SUPPORT_S)
        waveform = np.clip(audio.read(start, end, YAMNET_SAMPLE_RATE), -1., 1.)
        if not len(waveform):
            continue
        try:
            output = model(waveform)
            scores = output[0].numpy() if hasattr(output[0], "numpy") else np.asarray(output[0])
        except Exception as exc:
            raise AudioModelError(f"YAMNet inference failed: {exc}") from exc
        if (scores.ndim != 2 or scores.shape[1] != 521 or not np.isfinite(scores).all()
                or (scores < 0).any() or (scores > 1).any()):
            raise AudioModelError("Expected finite YAMNet scores with shape [frames, 521]. "
                                  "The selected model is incompatible.")
        if len(scores) < n:
            # The official model pads to emit a frame for every remaining hop.
            raise AudioModelError("YAMNet returned too few frames for its official 0.48s hop.")
        scores = scores[:n]
        for label in labels:
            classes = YAMNET_CLASSES[label]
            active_scores = scores[:, list(classes)].max(axis=1)
            for i in np.flatnonzero(active_scores >= limits[label]):
                frame_start = start + int(i) * YAMNET_HOP_S
                candidates[label].append({
                    "start": frame_start, "end": min(audio.end_s, frame_start + YAMNET_SUPPORT_S),
                    "score": float(active_scores[i]), "score_sum": float(active_scores[i]),
                    "count": 1,
                    "raw_scores": {name: float(scores[i, index]) for index, name in classes.items()},
                })
        _progress(progress, f"YAMNet vocal events: {round(100 * (base + n) / max(1, count))}%")
    events = []
    for label in labels:
        for event in _merge_intervals(candidates[label], gap, minimum):
            event.update(label=label, category="Vocal Event")
            events.append(event)
    settings = {"threshold": threshold, "thresholds": limits,
                "merge_gap": gap, "min_duration": minimum,
                "analysis_sample_rate": 16000, "patch_window_s": .96,
                "analysis_support_s": YAMNET_SUPPORT_S, "hop_s": YAMNET_HOP_S,
                "score_kind": "peak class score; not calibrated event probability",
                "labels": labels, "model_location": origin,
                "input_transform": "resample then clip analysis samples to [-1, 1]",
                "timing": "window-support candidates; manually refine boundaries"}
    return events, settings, "google/yamnet/1"


def detect_audio(path, model_id="energy", role="R01", offset_s=0., channel=None,
                 model_path=None, progress: Callable[[str], None] | None = None,
                 cancel=None, **params) -> list[Annotation]:
    """Generate pending proposals without modifying a Project or audio file.

    ``channel`` is zero-based, or explicit ``'mix'``. None accepts mono only.
    ``start_s``/``end_s`` parameters select native audio time, before ``offset_s``.
    ``progress`` receives one message string. ``cancel`` is a callable returning
    bool, or an Event with ``is_set``. Cancellation raises AudioCancelled.

    Common controls: min_duration, merge_gap, source_asset_id. Silero/YAMNet use
    threshold. Energy uses db_threshold (dBFS). YAMNet accepts labels, thresholds,
    and download=True ONLY for an explicit user-initiated model download.
    """
    if model_id not in {"energy", "silero", "yamnet"}:
        raise ValueError("Unknown audio model. Choose energy, silero, or yamnet.")
    offset_s = _number(offset_s, "offset_s")
    _check_cancel(cancel)
    audio = _open_audio(path, channel, params.get("start_s", 0.), params.get("end_s"))
    if audio.start_s == audio.end_s:
        return []
    if model_id == "energy":
        events, settings, model_version = _energy(audio, params, progress, cancel)
    elif model_id == "silero":
        events, settings, model_version = _silero(audio, params, progress, cancel)
    else:
        events, settings, model_version = _yamnet(audio, model_path, params, progress, cancel)
    _check_cancel(cancel)
    annotations = []
    for event in events:
        native_start = max(audio.start_s, float(event["start"]))
        native_end = min(audio.end_s, float(event["end"]))
        global_start, global_end = max(0., native_start + offset_s), native_end + offset_s
        if global_end <= global_start:
            continue
        attrs = {
            "model_id": model_id, "model_version": model_version,
            "parameters": dict(settings), "source_asset_id": params.get("source_asset_id", ""),
            "source_file": str(audio.path), "native_sample_rate": audio.sample_rate,
            "native_channels": audio.channels, "selected_channel": audio.selected_channel,
            "native_start_s": native_start, "native_end_s": native_end,
            "native_start_sample": round(native_start * audio.sample_rate),
            "native_end_sample": round(native_end * audio.sample_rate),
            "offset_s": offset_s, "clipped_at_project_start": native_start + offset_s < 0,
            "actor_attribution": "asset/channel assignment; identity not verified",
            "attribution_verified": False, "raw_class_scores": event.get("raw_scores", {}),
            "positive_windows": event.get("count", 1),
        }
        if event.get("score") is not None:
            attrs["mean_positive_window_score"] = event.get("score_sum", 0.) / max(1, event.get("count", 1))
        annotation = Annotation(
            id=str(uuid.uuid4()), start_s=global_start, end_s=global_end,
            role=role, channel="Speech", layer="L2 · Action / Gesture",
            label=event["label"], category=event["category"], status="pending",
            source=f"auto:{model_id}", confidence=event.get("score"),
            notes="Automatic proposal; review event and timing. Actor assignment is not verified.",
            attributes=attrs,
            original={"start_s": global_start, "end_s": global_end,
                      "label": event["label"], "category": event["category"],
                      "source": f"auto:{model_id}", "status": "pending",
                      "confidence": event.get("score")},
        )
        annotations.append(annotation)
    annotations.sort(key=lambda a: (a.start_s, a.end_s, a.label))
    _progress(progress, f"Completed: {len(annotations)} pending audio proposals. Human review required.")
    return annotations
