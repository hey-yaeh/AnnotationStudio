"""Read-only Windows install checks, usable before third-party dependencies exist.

The path budget includes the member that failed in the Windows PySide6 6.12
wheel. It is an early check for that observed failure, not a claim that every
future wheel has the same maximum member length. No registry setting or file
is changed by this module.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import sys


LEGACY_MAX_PATH = 260  # Includes the terminating NUL.
PYSIDE6_PROBE_MEMBER = PureWindowsPath(
    r".venv\Lib\site-packages\PySide6\qml\Qt\labs\assetdownloader"
    r"\objects-Debug\QmlAssetDownloaderPrivate_resources_1\.qt\rcc"
    r"\qrc_qmake_Qt_labs_assetdownloader_init.cpp.obj"
)


@dataclass(frozen=True)
class PathCheck:
    project_root: str
    dependency_path: str
    path_units: int
    long_paths_enabled: bool | None

    @property
    def allowed(self) -> bool:
        return self.path_units < LEGACY_MAX_PATH or self.long_paths_enabled is True


def check_windows_path(
    project_root: str, *, long_paths_enabled: bool | None
) -> PathCheck:
    """Assess a native Windows path without relying on the host operating system."""
    root = PureWindowsPath(project_root)
    if not root.is_absolute():
        raise ValueError("The project folder must be an absolute Windows path.")
    dependency = str(root / PYSIDE6_PROBE_MEMBER)
    # Win32's Unicode path limit counts UTF-16 code units, not Python code points.
    units = len(dependency.encode("utf-16-le", errors="surrogatepass")) // 2
    return PathCheck(str(root), dependency, units, long_paths_enabled)


def read_long_paths_enabled() -> bool | None:
    """Read the machine policy; an inaccessible policy remains unknown."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
            access=winreg.KEY_READ,
        ) as key:
            value, value_type = winreg.QueryValueEx(key, "LongPathsEnabled")
        return value_type == winreg.REG_DWORD and value == 1
    except FileNotFoundError:
        return False
    except (ImportError, OSError):
        return None


def describe_check(check: PathCheck) -> str:
    if check.allowed:
        if check.path_units >= LEGACY_MAX_PATH:
            return (
                "Windows install path check: long-path policy is enabled.\n"
                "If an existing terminal still reports a long-path error, use a fresh "
                "short extraction such as D:\\AS and restart setup."
            )
        return "Windows install path check passed."

    policy = "disabled" if check.long_paths_enabled is False else "unavailable"
    return (
        "SETUP STOPPED: this project folder is too deep for the current Windows "
        "path configuration.\n"
        f"Project folder: {check.project_root}\n"
        f"A known PySide6 dependency path needs {check.path_units} UTF-16 units; "
        "the legacy maximum is 259 plus the terminating NUL.\n"
        f"Windows long-path policy: {policy}.\n\n"
        "Recommended fix (no administrator access required):\n"
        "  1. Extract a fresh copy into a short folder, for example D:\\AS.\n"
        "  2. D:\\AS\\INSTALL_WINDOWS.bat should exist directly; avoid nested release folders.\n"
        "  3. Do not copy an old or partly installed .venv into the new folder.\n"
        "  4. Run INSTALL_WINDOWS.bat again, then RUN_WINDOWS.bat.\n"
        "Keep your original project JSON and media files. No files or settings "
        "were removed or changed by this check.\n"
        "See docs\\WINDOWS_SETUP_CN.md for recovery instructions."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print("Windows install path check: not applicable on this operating system.")
        return 0
    check = check_windows_path(
        str(Path(args.project_root).resolve()),
        long_paths_enabled=read_long_paths_enabled(),
    )
    print(describe_check(check))
    return 0 if check.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
