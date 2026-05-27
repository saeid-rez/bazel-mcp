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
    assert result.exit_code == 1
    assert len(result.targets) == 3
    assert result.targets[0].target == "//foo:bar_test"
    assert result.targets[0].status == "PASSED"
    assert result.targets[0].duration_seconds == 1.2
    assert result.targets[1].status == "FAILED"
    assert result.targets[2].status == "FLAKY"
    assert "1 passed" in result.summary or "passed" in result.summary


def test_parse_empty_output():
    result = parse_bazel_test_output("", "stderr only", return_code=2)
    assert result.exit_code == 2
    assert result.targets == []
    assert "No per-target" in result.summary


def test_parse_bare_test_log_path(tmp_path):
    log_path = tmp_path / "bazel-out" / "k8-fastbuild" / "testlogs" / "foo" / "baz_test" / "test.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("failure details\n")
    output = """
//foo:baz_test                                                   FAILED in 0.5s
  bazel-out/k8-fastbuild/testlogs/foo/baz_test/test.log
"""

    result = parse_bazel_test_output(output, "", return_code=1, workspace=tmp_path)

    assert result.targets[0].target == "//foo:baz_test"
    assert result.targets[0].status == "FAILED"
    assert result.targets[0].log_excerpt == "failure details\n"
