"""Portable tests for the observed Windows wheel-path installation failure."""
from pathlib import PureWindowsPath

import pytest

from scripts.windows_preflight import (
    LEGACY_MAX_PATH,
    PYSIDE6_PROBE_MEMBER,
    check_windows_path,
    describe_check,
)


FAILED_USER_ROOT = (
    r"D:\DuoFlow\0_TOOLS\AnnotationStudio"
    r"\Annotation_Studio_v0_5_1_Codex_Package\AnnotationStudio_v0_5_1"
)


def test_reported_pyside6_failure_stops_before_installation():
    check = check_windows_path(FAILED_USER_ROOT, long_paths_enabled=False)
    assert check.path_units == 265
    assert not check.allowed
    assert check.dependency_path.endswith(
        r"\.qt\rcc\qrc_qmake_Qt_labs_assetdownloader_init.cpp.obj"
    )
    explanation = describe_check(check)
    assert "D:\\AS\\INSTALL_WINDOWS.bat" in explanation
    assert "Do not copy an old or partly installed .venv" in explanation


@pytest.mark.parametrize("policy", [False, True, None])
def test_fresh_short_install_is_supported_without_policy_changes(policy):
    check = check_windows_path(r"D:\AS", long_paths_enabled=policy)
    assert check.allowed
    assert check.path_units == 172


@pytest.mark.parametrize("policy,allowed", [(False, False), (None, False), (True, True)])
def test_existing_long_path_capability_is_respected(policy, allowed):
    check = check_windows_path(FAILED_USER_ROOT, long_paths_enabled=policy)
    assert check.allowed is allowed


def test_limit_accounts_for_the_terminating_nul():
    # D:\ + one root component + separator + dependency member.
    root_chars_at_limit = LEGACY_MAX_PATH - len(str(PYSIDE6_PROBE_MEMBER)) - 4
    at_limit = check_windows_path("D:\\" + "x" * root_chars_at_limit, long_paths_enabled=False)
    below_limit = check_windows_path(
        "D:\\" + "x" * (root_chars_at_limit - 1), long_paths_enabled=False
    )
    assert at_limit.path_units == 260
    assert not at_limit.allowed
    assert below_limit.path_units == 259
    assert below_limit.allowed


def test_unicode_unc_and_special_character_roots_keep_their_identity():
    root = r"\\server\share\测量 & !\🙂"
    check = check_windows_path(root, long_paths_enabled=False)
    expected = str(PureWindowsPath(root) / PYSIDE6_PROBE_MEMBER)
    assert check.project_root == root
    assert check.dependency_path == expected
    assert check.path_units == len(expected) + 1  # One astral character uses two units.


@pytest.mark.parametrize("root", ["relative", r"D:relative", r"\root_without_drive"])
def test_relative_inputs_are_not_misreported_as_safe(root):
    with pytest.raises(ValueError, match="absolute Windows path"):
        check_windows_path(root, long_paths_enabled=False)
