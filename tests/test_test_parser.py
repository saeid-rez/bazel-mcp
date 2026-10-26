"""Tests for bazel test output parsing."""

from bazel_mcp.test_parser import parse_bazel_test_output

SAMPLE_OUTPUT = """
INFO: Build completed successfully
//foo:bar_test                                                   PASSED in 1.2s
//foo:baz_test                                                   FAILED in 0.5s
  /home/user/project/bazel-out/k8-fastbuild/testlogs/foo/baz_test/test.log
//pkg:flaky_test                                                 FLAKY in 2.0s
Executed 3 out of 3 tests: 1 fails locally.
"""


def test_parse_passed_and_failed():
    result = parse_bazel_test_output(SAMPLE_OUTPUT, "", return_code=1)
    assert result.success is False
    assert result.exit_code == 1
    assert result.total == 3
    assert result.passed == 1
    assert result.failed == 2
    assert len(result.targets) == 3
    assert result.targets[0].target == "//foo:bar_test"
    assert result.targets[0].status == "PASSED"
    assert result.targets[0].duration_seconds == 1.2
    assert result.targets[1].status == "FAILED"
    assert result.targets[2].status == "FLAKY"
    assert "1 passed" in result.summary or "passed" in result.summary


def test_parse_empty_output():
    result = parse_bazel_test_output("", "stderr only", return_code=2)
    assert result.success is False
    assert result.total == 0
    assert result.passed == 0
    assert result.failed == 0
    assert result.exit_code == 2
    assert result.targets == []
    assert "No per-target" in result.summary


def test_parse_bare_test_log_path(tmp_path):
    log_path = tmp_path / "bazel-out" / "k8-fastbuild" / "testlogs" / "foo" / "baz_test" / "test.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("FAIL: test_login_flow (AuthTests)\n")
    output = """
//foo:baz_test                                                   FAILED in 0.5s
  bazel-out/k8-fastbuild/testlogs/foo/baz_test/test.log
"""

    result = parse_bazel_test_output(output, "", return_code=1, workspace=tmp_path)

    assert result.targets[0].target == "//foo:baz_test"
    assert result.targets[0].status == "FAILED"
    assert result.targets[0].log_excerpt == "FAIL: test_login_flow (AuthTests)\n"
    assert result.failed_cases[0].target == "//foo:baz_test"
    assert result.failed_cases[0].test_name == "AuthTests.test_login_flow"


def test_parse_colon_prefixed_target_summary():
    output = """
FAILED: //MyApp:MyAppTests (3 tests, 1 failed)
PASSED: //MyApp:OtherTests (5 tests)
"""

    result = parse_bazel_test_output(output, "", return_code=1)

    assert result.total == 2
    assert result.passed == 1
    assert result.failed == 1
    assert result.targets[0].target == "//MyApp:MyAppTests"
    assert result.targets[0].status == "FAILED"
    assert result.targets[1].target == "//MyApp:OtherTests"
    assert result.targets[1].status == "PASSED"


def test_parse_junit_like_failed_case_from_output():
    output = """
//app:tests FAILED in 1.0s
FAIL: testLoginFlow (MyAppTests)
"""

    result = parse_bazel_test_output(output, "", return_code=1)

    assert len(result.failed_cases) == 1
    assert result.failed_cases[0].target == "//app:tests"
    assert result.failed_cases[0].test_name == "MyAppTests.testLoginFlow"
    assert result.failed_cases[0].message == "FAIL: testLoginFlow (MyAppTests)"


def test_parse_xctest_failure_from_output():
    output = """
//app:tests FAILED in 1.0s
MyTests.swift:45: XCTAssertEqual failed: ("3") is not equal to ("4")
"""

    result = parse_bazel_test_output(output, "", return_code=1)

    assert len(result.failed_cases) == 1
    assert result.failed_cases[0].target == "//app:tests"
    assert result.failed_cases[0].file == "MyTests.swift"
    assert result.failed_cases[0].line == 45
    assert result.failed_cases[0].message == 'XCTAssertEqual failed: ("3") is not equal to ("4")'


def test_parse_test_success_omits_raw_streams_by_default():
    output = """
//foo:bar_test                                                   PASSED in 1.2s
Executed 1 out of 1 test: 1 passes.
"""
    result = parse_bazel_test_output(output, "INFO: Elapsed time: 1.5s", return_code=0)
    assert result.success is True
    assert result.stdout == ""
    assert result.stderr == ""


def test_parse_test_failure_with_details_omits_raw_streams_by_default():
    output = """
//app:tests FAILED in 1.0s
FAIL: testLoginFlow (MyAppTests)
"""
    result = parse_bazel_test_output(output, "some stderr", return_code=1)
    assert result.success is False
    assert len(result.failed_cases) == 1
    assert result.stdout == ""
    assert result.stderr == ""


def test_parse_test_failure_without_details_retains_raw_streams_as_fallback():
    # Failure where test runner crashed without test.log or parseable FAIL lines
    output = "Test runner terminated abruptly with signal 9"
    stderr = "FATAL: Test runner crashed"
    result = parse_bazel_test_output(output, stderr, return_code=1)
    assert result.success is False
    assert len(result.failed_cases) == 0
    assert result.stdout == output
    assert result.stderr == stderr


def test_parse_test_verbose_always_retains_raw_streams():
    output = "//foo:bar_test PASSED in 0.5s"
    stderr = "INFO: Test passed"
    res_success = parse_bazel_test_output(output, stderr, return_code=0, verbose=True)
    assert res_success.stdout == output
    assert res_success.stderr == stderr

    output_fail = "//app:tests FAILED in 1.0s\nFAIL: testA (Suite)"
    res_fail = parse_bazel_test_output(output_fail, "err", return_code=1, verbose=True)
    assert res_fail.stdout == output_fail
    assert res_fail.stderr == "err"
