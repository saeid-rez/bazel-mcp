"""Tests for bazel build output parsing."""

from bazel_mcp.build_parser import parse_bazel_build_output


def test_parse_success_summary():
    result = parse_bazel_build_output(
        stdout="INFO: Build completed successfully, 4 total actions\n",
        stderr="",
        return_code=0,
        duration=1.25,
    )

    assert result.success is True
    assert result.exit_code == 0
    assert result.duration_seconds == 1.25
    assert result.summary == "INFO: Build completed successfully, 4 total actions"
    assert result.failed_targets == []
    assert result.errors == []


def test_parse_compiler_errors_and_warnings():
    output = """
/repo/src/App.swift:34:12: error: cannot find type 'Foo' in scope
/repo/src/App.swift:40: warning: variable 'x' was never mutated
FAILED: Build did NOT complete successfully
"""

    result = parse_bazel_build_output("", output, return_code=1)

    assert result.success is False
    assert result.summary == "FAILED: Build did NOT complete successfully"
    assert len(result.errors) == 1
    assert result.errors[0].file == "/repo/src/App.swift"
    assert result.errors[0].line == 34
    assert result.errors[0].col == 12
    assert result.errors[0].message == "cannot find type 'Foo' in scope"
    assert len(result.warnings) == 1
    assert result.warnings[0].file == "/repo/src/App.swift"
    assert result.warnings[0].line == 40
    assert result.warnings[0].col is None


def test_parse_bazel_rule_error_and_failed_targets():
    output = """
ERROR: /repo/foo/BUILD:12:5: in cc_library rule //foo:bar: missing required attr
ERROR: /repo/foo/BUILD:12:5: Compiling //foo:bar failed
Target //foo:bar failed to build
FAILED: Build did NOT complete successfully
"""

    result = parse_bazel_build_output("", output, return_code=1)

    assert result.failed_targets == ["//foo:bar"]
    assert len(result.errors) == 1
    assert result.errors[0].file == "/repo/foo/BUILD"
    assert result.errors[0].line == 12
    assert result.errors[0].col == 5
    assert result.errors[0].target == "//foo:bar"
    assert result.errors[0].message == "in cc_library rule //foo:bar: missing required attr"


def test_caps_errors_and_warnings():
    errors = "\n".join(
        f"/repo/file{i}.cc:1:1: error: failure {i}"
        for i in range(25)
    )
    warnings = "\n".join(
        f"/repo/file{i}.cc:2:1: warning: warning {i}"
        for i in range(25)
    )

    result = parse_bazel_build_output("", errors + "\n" + warnings, return_code=1)

    assert len(result.errors) == 20
    assert len(result.warnings) == 20
    assert result.errors[0].message == "failure 0"
    assert result.warnings[0].message == "warning 0"
