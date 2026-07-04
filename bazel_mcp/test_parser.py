"""Parse bazel test stdout into structured results."""

from __future__ import annotations

import re
from pathlib import Path

from bazel_mcp.models import (
    BazelTestCaseFailure,
    BazelTestResult,
    BazelTestTargetResult,
)

_TEST_LINE = re.compile(
    r"^(?P<target>(?:@[\w.-]+)?//[\S]+)\s+(?P<status>PASSED|FAILED|FLAKY|TIMEOUT|SKIPPED)"
    r"(?:\s+in\s+(?P<duration>[\d.]+)s)?",
    re.MULTILINE,
)
_COLON_TEST_LINE = re.compile(
    r"^(?P<status>PASSED|FAILED|FLAKY|TIMEOUT|SKIPPED):\s+"
    r"(?P<target>(?:@[\w.-]+)?//\S+)"
    r"(?:\s+\((?P<details>[^)]*)\))?",
    re.MULTILINE,
)
_LOG_PATH = re.compile(
    r"(?:stdout|stderr|test\.log).*?:\s*(?P<path>\S+test\.log\S*)",
    re.IGNORECASE,
)
_BARE_LOG_PATH = re.compile(
    r"^\s+(?P<path>\S*testlogs/\S+/test\.log\S*)\s*$",
    re.MULTILINE,
)
_FAIL_CASE = re.compile(
    r"^\s*FAIL:\s+(?P<test_name>.+?)\s+\((?P<suite>[^)]+)\)"
    r"(?:\s+\((?P<duration>[\d.]+)s\))?",
    re.MULTILINE,
)
_XCTEST_FAILURE = re.compile(
    r"^(?P<file>\S+\.swift):(?P<line>\d+):\s+"
    r"(?P<message>XCT\w+\s+failed.*)$",
    re.MULTILINE,
)
_FAILED_STATUSES = {"FAILED", "FLAKY", "TIMEOUT"}
_MAX_FAILED_CASES = 10


def _find_log_paths(output: str) -> list[str]:
    matches = [
        (match.start(), match.group("path"))
        for pattern in (_LOG_PATH, _BARE_LOG_PATH)
        for match in pattern.finditer(output)
    ]
    return [path for _, path in sorted(matches, key=lambda item: item[0])]


def _read_log_excerpt(log_path: str, max_chars: int = 4000) -> str | None:
    path = Path(log_path.strip().strip('"'))
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(content) <= max_chars:
        return content
    keep = max_chars // 2
    return content[:keep] + "\n...[truncated]...\n" + content[-keep:]


def _append_target(
    targets: list[BazelTestTargetResult],
    seen_targets: set[str],
    *,
    target: str,
    status: str,
    duration_seconds: float | None = None,
    log_excerpt: str | None = None,
) -> None:
    if target in seen_targets:
        return
    seen_targets.add(target)
    targets.append(
        BazelTestTargetResult(
            target=target,
            status=status,
            duration_seconds=duration_seconds,
            log_excerpt=log_excerpt,
        )
    )


def _parse_failed_cases(text: str, *, target: str | None = None) -> list[BazelTestCaseFailure]:
    failed_cases: list[BazelTestCaseFailure] = []

    for match in _FAIL_CASE.finditer(text):
        suite = match.group("suite").strip()
        test_name = match.group("test_name").strip()
        duration_raw = match.group("duration")
        failed_cases.append(
            BazelTestCaseFailure(
                target=target or suite,
                test_name=f"{suite}.{test_name}",
                message=match.group(0).strip(),
                duration_seconds=float(duration_raw) if duration_raw else None,
            )
        )

    for match in _XCTEST_FAILURE.finditer(text):
        failed_cases.append(
            BazelTestCaseFailure(
                target=target,
                file=match.group("file"),
                line=int(match.group("line")),
                message=match.group("message").strip(),
            )
        )

    return failed_cases


def _dedupe_failed_cases(
    failed_cases: list[BazelTestCaseFailure],
) -> list[BazelTestCaseFailure]:
    seen: set[tuple[str | None, str | None, str | None, int | None, str]] = set()
    unique: list[BazelTestCaseFailure] = []
    for case in failed_cases:
        key = (case.target, case.test_name, case.file, case.line, case.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(case)
    return unique


def parse_bazel_test_output(
    stdout: str,
    stderr: str,
    return_code: int,
    *,
    workspace: Path | None = None,
) -> BazelTestResult:
    combined = stdout + "\n" + stderr
    targets: list[BazelTestTargetResult] = []
    failed_cases: list[BazelTestCaseFailure] = []
    seen_targets: set[str] = set()
    log_paths = _find_log_paths(combined)
    log_index = 0

    for match in _TEST_LINE.finditer(combined):
        status = match.group("status")
        duration_raw = match.group("duration")
        duration = float(duration_raw) if duration_raw else None
        log_excerpt: str | None = None
        if status in ("FAILED", "FLAKY", "TIMEOUT") and log_index < len(log_paths):
            log_path = log_paths[log_index]
            if workspace and not Path(log_path).is_absolute():
                log_path = str(workspace / log_path)
            log_excerpt = _read_log_excerpt(log_path)
            if log_excerpt:
                failed_cases.extend(
                    _parse_failed_cases(log_excerpt, target=match.group("target"))
                )
            log_index += 1

        _append_target(
            targets,
            seen_targets,
            target=match.group("target"),
            status=status,
            duration_seconds=duration,
            log_excerpt=log_excerpt,
        )

    for match in _COLON_TEST_LINE.finditer(combined):
        _append_target(
            targets,
            seen_targets,
            target=match.group("target"),
            status=match.group("status"),
        )

    failed_target_labels = [target.target for target in targets if target.status in _FAILED_STATUSES]
    combined_failure_target = failed_target_labels[0] if len(failed_target_labels) == 1 else None
    failed_cases.extend(_parse_failed_cases(combined, target=combined_failure_target))
    failed_cases = _dedupe_failed_cases(failed_cases)[:_MAX_FAILED_CASES]

    passed = sum(1 for t in targets if t.status == "PASSED")
    failed = sum(1 for t in targets if t.status in _FAILED_STATUSES)
    summary = f"{passed} passed, {failed} failed, {len(targets)} total"
    if not targets:
        summary = "No per-target summary lines parsed; see raw output."

    return BazelTestResult(
        success=return_code == 0,
        exit_code=return_code,
        total=len(targets),
        passed=passed,
        failed=failed,
        summary=summary,
        targets=targets,
        failed_cases=failed_cases,
        stdout=stdout,
        stderr=stderr,
    )
