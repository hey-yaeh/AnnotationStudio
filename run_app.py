"""Annotation Studio entry point for a native Windows PyInstaller build."""
from pathlib import Path
import os
import sys
import traceback


def _check_audio_bundle(argv):
    """Run both packaged adapters on a WAV/FLAC and write a local QA report."""
    import argparse
    import json
    from importlib.metadata import version

    from annotationstudio.audio_models import bundled_yamnet_path, detect_audio

    parser = argparse.ArgumentParser(prog="AnnotationStudio --check-audio-bundle")
    parser.add_argument("audio", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    report = {"frozen": bool(getattr(sys, "frozen", False)), "models": {}}
    yamnet = bundled_yamnet_path()
    for model, packages in (("silero", ("silero-vad", "torch")), ("yamnet", ("tensorflow",))):
        try:
            if model == "yamnet" and yamnet is None:
                raise RuntimeError("The bundled YAMNet SavedModel is missing.")
            events = detect_audio(args.audio, model_id=model, role="R01", download=False)
            report["models"][model] = {
                "ok": True, "versions": {package: version(package) for package in packages},
                "proposals": [{"label": item.label, "status": item.status,
                               "start_s": item.start_s, "end_s": item.end_s} for item in events],
            }
        except Exception as exc:
            report["models"][model] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return 0 if all(model["ok"] for model in report["models"].values()) else 1


def main():
    log_path = None
    if getattr(sys, "frozen", False):
        # Windowed executables have no console. Preserve startup errors in a
        # user-writable directory instead of silently losing stderr.
        log_folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AnnotationStudio" / "logs"
        try:
            log_folder.mkdir(parents=True, exist_ok=True)
            log_path = log_folder / "startup.log"
            stream = log_path.open("a", encoding="utf-8", buffering=1)
            if sys.stdout is None:
                sys.stdout = stream
            if sys.stderr is None:
                sys.stderr = stream
        except OSError:
            log_path = None
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        example_names = ("S004_I02_manual.studio.json", "S004_I02_R01_BVH.bvh", "S004_I02_R02_BVH.bvh")
        if len(sys.argv) == 1 and all((bundle_root / "examples" / name).exists() for name in example_names):
            sys.argv.append("--manual-example")
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--check-audio-bundle":
            return _check_audio_bundle(sys.argv[2:])
        from annotationstudio.ui import launch
        return launch()
    except Exception:
        traceback.print_exc()
        if getattr(sys, "frozen", False) and sys.platform == "win32":
            import ctypes
            details = f"See the startup log:\n{log_path}" if log_path else "Please launch from a console to inspect the error."
            ctypes.windll.user32.MessageBoxW(None, "Annotation Studio could not start.\n\n" + details,
                                            "Annotation Studio", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
