# Source release verification

Annotation Studio 0.5.4, verified on Windows on 2026-11-23 with 64-bit CPython 3.11.9 and PySide6/Qt 6.12.0.

| Check | Result |
| --- | --- |
| python scripts/doctor.py | Core imports and project schema v3 passed. |
| python scripts/export_label_catalog.py --check | Passed for 28 types and 493 active labels. |
| python -m pytest tests -q -rs --tb=short, Qt offscreen | 387 passed, 12 skipped in 122.53 seconds. Three deprecation warnings came from Silero/PyTorch. |
| Native Qt synthetic media test with local FFmpeg | 1 passed in 7.25 seconds. Verified H.264/MP4 and PCM/WAV decoding, seeking, source offsets and playback outside the source range. |
| Source-only demonstration | Opened through the File menu. 19 synthetic records, with no linked media. |

Of the 12 skips in the offscreen run, 11 require research fixtures that are kept outside the source distribution. The remaining skip was the FFmpeg-dependent media test, which passed in the separate native run. GUI editing tests use generated BVH files. These checks cover the software workflow and runtime integration. Scientific evaluation of detector accuracy is outside this test run.
