"""Audio adapter/contracts, not a benchmark of pretrained-model accuracy.

The energy path uses real local WAV/FLAC files. Contract tests substitute small
deterministic fake models. One additional local-weight smoke test runs only if
Silero and Torch are already installed. Tests never download weights or need a GPU.
"""
from contextlib import nullcontext
import csv
import hashlib
import math
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from annotationstudio import audio_models as am
from annotationstudio.models import Project


def _tone_file(tmp_path, name="audio.wav", sample_rate=16000, duration=2.4,
               intervals=((.5, 1.), (1.5, 1.8)), stereo=False):
    t = np.arange(round(sample_rate * duration)) / sample_rate
    wave = np.zeros(len(t), np.float32)
    for start, stop in intervals:
        region = (t >= start) & (t < stop)
        wave[region] = .25 * np.sin(2 * np.pi * 220 * t[region])
    if stereo:
        wave = np.stack((wave, np.zeros_like(wave)), axis=1)
    path = tmp_path / name
    sf.write(str(path), wave, sample_rate)
    return path


def _yamnet_frame_count(samples):
    return max(1, math.ceil((samples - 15600) / 7680 - 1e-9) + 1)


def test_real_energy_candidates_preserve_audio_and_do_not_claim_speech(tmp_path):
    path = _tone_file(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    messages = []
    events = am.detect_audio(path, offset_s=.2, progress=messages.append,
                             source_asset_id="wav-1")
    assert len(events) == 2
    assert all(a.category == "Audio Activity" and a.label == "Audio activity (energy)"
               and a.confidence is None and a.status == "pending" for a in events)
    assert events[0].start_s == pytest.approx(.68, abs=.02)
    assert events[0].end_s == pytest.approx(1.22, abs=.02)
    assert events[0].attributes["source_asset_id"] == "wav-1"
    assert events[0].attributes["raw_class_scores"]["peak_rms_dbfs"] < 0
    assert events[0].attributes["attribution_verified"] is False
    assert messages[-1].startswith("Completed: 2")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_stereo_requires_explicit_channel_and_can_read_flac(tmp_path):
    path = _tone_file(tmp_path, "stereo.flac", sample_rate=44100, stereo=True)
    with pytest.raises(ValueError, match="Select a zero-based"):
        am.detect_audio(path)
    assert am.detect_audio(path, channel=1) == []
    audible = am.detect_audio(path, channel=0, role="R02")
    mixed = am.detect_audio(path, channel="mix")
    assert len(audible) == len(mixed) == 2
    assert all(a.role == "R02" and a.attributes["selected_channel"] == 0 for a in audible)
    assert mixed[0].attributes["selected_channel"] == "mix"
    assert audible[0].attributes["native_sample_rate"] == 44100
    with pytest.raises(ValueError, match="between 0 and 1"):
        am.detect_audio(path, channel=2)


def test_offset_clipping_and_native_range_keep_original_boundaries(tmp_path):
    path = _tone_file(tmp_path, intervals=((.1, .6), (1.5, 2.)))
    events = am.detect_audio(path, offset_s=-.3, start_s=.1, end_s=.6)
    assert len(events) == 1
    event = events[0]
    assert event.start_s == 0
    assert event.end_s == pytest.approx(.3)
    assert event.attributes["native_start_s"] == pytest.approx(.1)
    assert event.attributes["native_end_s"] == pytest.approx(.6)
    assert event.attributes["native_start_sample"] == 1600
    assert event.attributes["clipped_at_project_start"] is True
    assert event.original["label"] == event.label
    assert am.detect_audio(path, offset_s=-10) == []


def test_cancel_never_returns_partial_results(tmp_path):
    path = _tone_file(tmp_path, duration=65., intervals=((0., 65.),))
    stopped = threading.Event()
    with pytest.raises(am.AudioCancelled):
        am.detect_audio(path, cancel=stopped, progress=lambda _: stopped.set())
    with pytest.raises(am.AudioCancelled):
        am.detect_audio(path, cancel=lambda: True)


@pytest.mark.parametrize("params", [{"offset_s": float("nan")}, {"min_duration": -1},
                                   {"merge_gap": -1}, {"db_threshold": float("inf")},
                                   {"start_s": -1}, {"start_s": 3}])
def test_invalid_parameters_fail(tmp_path, params):
    with pytest.raises(ValueError):
        am.detect_audio(_tone_file(tmp_path), **params)


def test_missing_optional_models_fail_explicitly_without_fallback(tmp_path, monkeypatch):
    original = am._has_module
    monkeypatch.setattr(am, "_has_module", lambda name: False if name in
                        {"torch", "silero_vad", "tensorflow"} else original(name))
    path = _tone_file(tmp_path)
    with pytest.raises(am.AudioModelError, match="optional"):
        am.detect_audio(path, model_id="silero")
    with pytest.raises(am.AudioModelError, match="optional"):
        am.detect_audio(path, model_id="yamnet")


def test_yamnet_never_downloads_implicitly(tmp_path, monkeypatch):
    monkeypatch.setattr(am, "_has_module", lambda _: True)
    monkeypatch.setattr(am, "bundled_yamnet_path", lambda: None)
    with pytest.raises(am.AudioModelError, match="explicitly enable download"):
        am._load_yamnet(None, False, None)
    with pytest.raises(am.AudioModelError, match="saved_model.pb"):
        am._load_yamnet(tmp_path / "missing", False, None)
    with pytest.raises(ValueError, match="explicitly True or False"):
        am.detect_audio(_tone_file(tmp_path), model_id="yamnet", download="False")


def test_frozen_yamnet_loads_the_bundled_model_and_honors_an_override(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    bundled = tmp_path / "models" / "yamnet"
    for name in ("saved_model.pb", "assets/yamnet_class_map.csv", "variables/variables.index",
                 "variables/variables.data-00000-of-00001"):
        path = bundled / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    model = lambda waveform: waveform
    loaded = []

    def load(directory):
        loaded.append(directory)
        return model

    monkeypatch.setitem(sys.modules, "tensorflow", SimpleNamespace(
        device=lambda _: nullcontext(), saved_model=SimpleNamespace(load=load)))
    monkeypatch.setattr(am, "_has_module", lambda name: name != "tensorflow_hub")
    monkeypatch.setattr(am, "_validate_yamnet_vocabulary", lambda actual: None)

    status = next(row for row in am.model_status() if row["id"] == "yamnet")
    assert status["bundled_model_path"] == str(bundled)
    assert status["needs_model"] is False and status["ready"] is False
    assert am._load_yamnet(None, False, None) == (model, str(bundled))

    override = tmp_path / "override"
    override.mkdir()
    (override / "saved_model.pb").touch()
    assert am._load_yamnet(override, False, None) == (model, str(override))
    assert loaded == [str(bundled), str(override)]


def test_yamnet_rejects_reordered_class_vocabulary(tmp_path):
    path = tmp_path / "class_map.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["index", "mid", "display_name"])
        for classes in am.YAMNET_CLASSES.values():
            for index, name in classes.items():
                writer.writerow([index, "unused-test-mid", name])
    model = SimpleNamespace(class_map_path=lambda: str(path))
    am._validate_yamnet_vocabulary(model)
    path.write_text(path.read_text().replace("Sigh", "Something else"))
    with pytest.raises(am.AudioModelError, match="incompatible"):
        am._validate_yamnet_vocabulary(model)


def test_yamnet_independent_labels_and_original_subclass_scores(tmp_path, monkeypatch):
    path = _tone_file(tmp_path, duration=3.)
    def fake_model(wave):
        assert wave.dtype == np.float32 and wave.ndim == 1
        result = np.zeros((_yamnet_frame_count(len(wave)), 521), np.float32)
        result[1:3, 13] = .7
        result[2, 15] = .9
        result[4, 23] = .8
        return result, None, None
    monkeypatch.setattr(am, "_load_yamnet", lambda *args: (fake_model, "test-model"))
    events = am.detect_audio(path, model_id="yamnet", threshold=.6, offset_s=10,
                             labels=["Laughter", "Sigh"])
    assert [x.label for x in events] == ["Laughter", "Sigh"]
    laugh, sigh = events
    assert laugh.start_s == pytest.approx(10.48)
    assert laugh.end_s == pytest.approx(11.935)
    assert sigh.start_s == pytest.approx(11.92)
    assert laugh.end_s > sigh.start_s  # Event labels may overlap.
    assert laugh.confidence == pytest.approx(.9)
    assert laugh.attributes["raw_class_scores"]["Giggle"] == pytest.approx(.9)
    assert laugh.attributes["positive_windows"] == 2
    assert all(x.status == "pending" and x.category == "Vocal Event" for x in events)
    assert all("Listener" not in x.label for x in events)


def test_yamnet_chunk_seam_is_merged_and_tail_is_bounded(tmp_path, monkeypatch):
    path = _tone_file(tmp_path, duration=30., intervals=())
    calls = []
    def fake_model(wave):
        calls.append(len(wave))
        result = np.zeros((_yamnet_frame_count(len(wave)), 521), np.float32)
        result[-1 if len(calls) == 1 else 0, 42] = .8
        return result, None, None
    monkeypatch.setattr(am, "_load_yamnet", lambda *args: (fake_model, "test-model"))
    events = am.detect_audio(path, model_id="yamnet", labels=["Cough"])
    assert len(calls) == 2
    assert max(calls) <= round(29.295 * 16000)
    assert len(events) == 1
    assert events[0].start_s == pytest.approx(28.32)
    assert events[0].end_s == pytest.approx(29.775)
    assert events[0].end_s <= 30.


def test_yamnet_short_input_and_bad_model_shape(tmp_path, monkeypatch):
    path = _tone_file(tmp_path, duration=.2, intervals=())
    monkeypatch.setattr(am, "_load_yamnet", lambda *args:
                        (lambda wave: (np.zeros((1, 521)), None, None), "fake"))
    assert am.detect_audio(path, model_id="yamnet") == []
    monkeypatch.setattr(am, "_load_yamnet", lambda *args:
                        (lambda wave: (np.zeros((1, 6)), None, None), "wrong"))
    with pytest.raises(am.AudioModelError, match="521"):
        am.detect_audio(path, model_id="yamnet")


def test_silero_contract_is_sample_based_and_merges_chunk_context(tmp_path, monkeypatch):
    path = _tone_file(tmp_path, sample_rate=44100, duration=12., intervals=((0., 12.),))
    calls = []
    def fake_timestamps(wave, model, **kwargs):
        calls.append((len(wave), kwargs))
        assert wave.dtype == np.float32
        return [{"start": 0, "end": len(wave)}]
    original = am._has_module
    monkeypatch.setattr(am, "_has_module", lambda name: True if name in
                        {"torch", "silero_vad"} else original(name))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        from_numpy=lambda x: x, inference_mode=nullcontext, Tensor=type("FakeTensor", (), {})))
    monkeypatch.setitem(sys.modules, "silero_vad", SimpleNamespace(
        load_silero_vad=lambda onnx: object(), get_speech_timestamps=fake_timestamps))
    events = am.detect_audio(path, model_id="silero", chunk_seconds=5., offset_s=1.)
    assert len(calls) == 3
    assert max(n for n, _ in calls) <= 7 * 16000
    assert all(options["sampling_rate"] == 16000 and options["return_seconds"] is False
               for _, options in calls)
    assert len(events) == 1
    event = events[0]
    assert (event.start_s, event.end_s) == pytest.approx((1., 13.))
    assert event.label == event.category == "Speaking"
    assert event.confidence is None
    assert event.attributes["native_end_sample"] == 12 * 44100


def test_audio_provenance_survives_project_roundtrip(tmp_path):
    path = _tone_file(tmp_path)
    project = Project("Audio adapter contract")
    project.annotations = am.detect_audio(path)
    target = tmp_path / "project.json"
    project.save(target)
    loaded = Project.load(target)
    assert loaded.annotations[0].attributes == project.annotations[0].attributes
    assert loaded.annotations[0].original == project.annotations[0].original


def test_status_does_not_claim_installed_weights(monkeypatch):
    monkeypatch.setattr(am, "_has_module", lambda _: False)
    monkeypatch.setattr(am, "bundled_yamnet_path", lambda: None)
    rows = {row["id"]: row for row in am.model_status()}
    assert rows.keys() == {"energy", "silero", "yamnet"}
    assert not any(row["available"] for row in rows.values())
    assert rows["yamnet"]["needs_model"] is True
    assert rows["yamnet"]["ready"] is False


@pytest.mark.skipif(not (am._has_module("torch") and am._has_module("silero_vad")),
                    reason="Optional Silero/Torch runtime is not installed; no download attempted")
def test_installed_silero_model_load_and_inference(tmp_path):
    import torch
    from silero_vad import load_silero_vad
    model = load_silero_vad(onnx=False)
    with torch.inference_mode():
        score = float(model(torch.zeros(512), 16000).item())
    assert math.isfinite(score) and 0 <= score <= 1
    # A tone is an integration fixture, not a speech-accuracy benchmark.
    results = am.detect_audio(_tone_file(tmp_path), model_id="silero", channel=0)
    assert isinstance(results, list)
    assert all(x.valid() and x.source == "auto:silero" and x.status == "pending"
               for x in results)
