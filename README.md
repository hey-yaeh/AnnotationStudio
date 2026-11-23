
# Annotation Studio

Annotation Studio is a local desktop application for annotating synchronized motion capture, video, and audio. It was built for the OCUMO research workflow and uses a shared timeline for all linked media and annotations.

[Illustrated user guide (PDF)](docs/Annotation_Studio_Illustrated_User_Guide_EN.pdf) · [简体中文](README_中文.md) · [Changelog](CHANGELOG.md)

## Start

Use 64-bit Python 3.11 or 3.12. Install in a short directory on Windows, such as `C:\AS`, to avoid long dependency paths.

| Platform | Install | Run |
| --- | --- | --- |
| Windows | `INSTALL_WINDOWS.bat` | `RUN_WINDOWS.bat` |
| Linux | `bash install_linux.sh` | `bash run_linux.sh` |

The installers create a project-local virtual environment. For a first look, choose **File → Open synthetic annotation demo**. The [demo](examples/README.md) illustrates speech and object annotations without recorded media. To work with your own data, choose **File → New project**, add sources, and map them to actors or to the scene.

## Workflow

1. **Align sources.** Link BVH or NPZ motion, video, and audio. Use **Timing / relink** to check their offsets against the master clock.
2. **Choose tracks.** Use the workspaces for activity, motion, gesture, human-object interaction, speech, spatial relations, social interaction, perceived affect, and review.
3. **Annotate or propose.** Mark intervals and point events, or use **Auto-detect…** for body-part motion candidates and audio proposals. Optional Silero VAD and YAMNet adapters handle speech activity and selected vocal events. Review actor attribution before deriving turn and timing proposals from Speaking intervals.
4. **Review and share.** Check boundaries, accept or reject candidates, and save the editable `.studio.json`. Export combined and per-type CSV tables using explicit type and review-state filters. Use ELAN EAF for interval-only selections.

Original media stays local. The application keeps original proposals and edit history. A generated label is a candidate for review. Speech transcription, speaker diarization, and contextual gesture or affect inference are outside the current detector scope.

## Documentation

- [English annotation guide](docs/ANNOTATION_GUIDE.md) and [Chinese annotation guide](docs/ANNOTATION_PROTOCOL_CN.md)
- [Bilingual label catalog](docs/Annotation_Studio_Label_Catalog.xlsx), [CSV](docs/label_catalog.csv), and [JSON](docs/label_catalog.json)
- [Project and export schemas](docs/SCHEMAS.md) and [CSV export instructions](docs/EXPORT_CN.md)
- [Optional audio models and Windows builds](docs/AUDIO_MODELS.md)
- [Windows installation troubleshooting](docs/WINDOWS_SETUP_CN.md)

## Develop

`annotationstudio/` contains the application, `tests/` contains regression tests, and `scripts/` contains environment and catalog utilities. Run `SETUP_CODEX_WINDOWS.bat` or `bash setup_codex.sh` to install test dependencies. In the resulting virtual environment, run:

```bash
python scripts/doctor.py
python -m pytest tests -q
python scripts/export_label_catalog.py --check
```

The test harness selects Qt offscreen mode by default. The [source-only checkout](examples/README.md) skips tests that require the original research recordings or original sample projects.
