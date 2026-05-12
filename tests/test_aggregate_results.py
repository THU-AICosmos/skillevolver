"""Tests for scripts/aggregate_results.py — TDD test suite."""

import sys
import os
from pathlib import Path

# Allow importing from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import aggregate_results as ar


# ---------------------------------------------------------------------------
# Task 1: parse_baselines()
# ---------------------------------------------------------------------------

def test_parse_baselines_returns_dict():
    result = ar.parse_baselines()
    assert isinstance(result, dict), "parse_baselines() should return a dict"


def test_parse_baselines_known_task():
    result = ar.parse_baselines()
    assert "offer-letter-generator" in result, "offer-letter-generator must be in baselines"
    entry = result["offer-letter-generator"]
    assert entry["domain"] == "Office"
    assert entry["o46_no"] == 0.2
    assert entry["s45_no"] == 0.0
    assert entry["o46_with"] == 0.8
    assert entry["s45_with"] == 1.0


def test_parse_baselines_another_task():
    result = ar.parse_baselines()
    assert "court-form-filling" in result
    entry = result["court-form-filling"]
    assert entry["domain"] == "Office"
    assert entry["o46_no"] == 0.0
    assert entry["o46_with"] == 0.8


def test_parse_baselines_science_task():
    result = ar.parse_baselines()
    assert "earthquake-phase-association" in result
    entry = result["earthquake-phase-association"]
    assert entry["domain"] == "Science"
    assert entry["o46_no"] == 0.6
    assert entry["s45_no"] == 0.2


def test_parse_baselines_no_header_rows():
    result = ar.parse_baselines()
    # Header row keys like "Task" or "---" should not appear
    assert "Task" not in result
    assert "---" not in result
    assert "task" not in result


def test_parse_baselines_count():
    result = ar.parse_baselines()
    # There are 84 tasks total in the file
    assert len(result) >= 80, f"Expected ~84 tasks, got {len(result)}"


# ---------------------------------------------------------------------------
# Task 2: parse_analysis_file() / load_all_analyses()
# ---------------------------------------------------------------------------

SAMPLE_FRONTMATTER = """\
---
task: court-form-filling
skill: pdf-form-filling
category: B1
outcome: success
notes: "Evolved >= Curated"
---
Some body text here.
More body text.
"""

SAMPLE_NO_FRONTMATTER = "Just plain body text with no frontmatter.\n"

SAMPLE_QUOTED_NOTES = """\
---
task: offer-letter-generator
skill: docx-template-fill
category: B1
outcome: success
notes: "Quotes are stripped"
---
Body.
"""


def test_parse_analysis_file_basic():
    meta, body = ar.parse_analysis_file(SAMPLE_FRONTMATTER)
    assert meta["task"] == "court-form-filling"
    assert meta["skill"] == "pdf-form-filling"
    assert meta["category"] == "B1"
    assert meta["outcome"] == "success"
    assert "body text" in body


def test_parse_analysis_file_notes_unquoted():
    meta, body = ar.parse_analysis_file(SAMPLE_FRONTMATTER)
    # Quotes around value should be stripped
    assert meta["notes"] == "Evolved >= Curated"


def test_parse_analysis_file_no_frontmatter():
    meta, body = ar.parse_analysis_file(SAMPLE_NO_FRONTMATTER)
    assert meta == {}
    assert "plain body text" in body


def test_parse_analysis_file_body_stripped():
    meta, body = ar.parse_analysis_file(SAMPLE_FRONTMATTER)
    # Body should not have leading/trailing whitespace issues
    assert body.strip().startswith("Some body")


def test_load_all_analyses_skips_underscore(tmp_path):
    # Create a fake analysis dir
    (tmp_path / "offer-letter-generator.md").write_text(SAMPLE_QUOTED_NOTES)
    (tmp_path / "_patterns.md").write_text("# Patterns\nsome patterns here")
    (tmp_path / "court-form-filling.md").write_text(SAMPLE_FRONTMATTER)

    result = ar.load_all_analyses(tmp_path)
    assert "offer-letter-generator" in result
    assert "court-form-filling" in result
    assert "_patterns" not in result
    assert len(result) == 2


def test_load_all_analyses_structure(tmp_path):
    (tmp_path / "offer-letter-generator.md").write_text(SAMPLE_QUOTED_NOTES)
    result = ar.load_all_analyses(tmp_path)
    entry = result["offer-letter-generator"]
    assert "meta" in entry
    assert "body" in entry
    assert entry["meta"]["outcome"] == "success"


def test_load_all_analyses_empty_dir(tmp_path):
    result = ar.load_all_analyses(tmp_path)
    assert result == {}


# ---------------------------------------------------------------------------
# Task 3: discover_tasks() / load_task_data()
# ---------------------------------------------------------------------------

def test_discover_tasks_returns_dict():
    result = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    assert isinstance(result, dict)


def test_discover_tasks_finds_offer_letter():
    result = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    assert "offer-letter-generator" in result, "offer-letter-generator must be discovered"


def test_discover_tasks_skips_former():
    result = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    assert "former" not in result, "'former' dir should be skipped"


def test_discover_tasks_path_is_dir():
    # Each value should be a Path pointing to a dir
    result = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    for slug, ts_dir in result.items():
        assert isinstance(ts_dir, Path), f"{slug}: expected Path, got {type(ts_dir)}"
        assert ts_dir.is_dir(), f"{slug}: {ts_dir} is not a directory"


def test_load_task_data_offer_letter():
    tasks = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    assert "offer-letter-generator" in tasks
    data = ar.load_task_data(tasks["offer-letter-generator"])
    assert "timestamp" in data
    assert "total_cost_usd" in data
    assert "exploration" in data


def test_load_task_data_exploration_fields():
    tasks = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    data = ar.load_task_data(tasks["offer-letter-generator"])
    exp = data["exploration"]
    assert "pass" in exp
    assert "fail" in exp
    assert "attempts" in exp
    assert "avg_turns" in exp
    assert "avg_tokens" in exp
    assert "avg_duration" in exp
    assert "trials" in exp


def test_load_task_data_normalized_keys():
    """Verify n_turns -> turns, total_tokens -> tokens, duration_seconds -> duration."""
    tasks = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    data = ar.load_task_data(tasks["offer-letter-generator"])
    exp = data["exploration"]
    # Trial keys should be normalized
    if exp["trials"]:
        t = exp["trials"][0]
        assert "turns" in t, "n_turns should be renamed to turns"
        assert "tokens" in t, "total_tokens should be renamed to tokens"
        assert "duration" in t, "duration_seconds should be renamed to duration"


def test_load_task_data_validation_or_none():
    tasks = ar.discover_tasks(ar.EVOLVED_SKILLS_DIR)
    data = ar.load_task_data(tasks["offer-letter-generator"])
    # Validation can be None or a dict
    assert data["validation"] is None or isinstance(data["validation"], dict)


# ---------------------------------------------------------------------------
# Task 4: build_record() / _compute_efficiency()
# ---------------------------------------------------------------------------

SAMPLE_EXPLORATION = {
    "pass": 3,
    "fail": 1,
    "attempts": 4,
    "avg_turns": 10.0,
    "avg_tokens": 150000,
    "avg_duration": 85.0,
    "cost_usd": 0.8,
    "trials": [],
}

SAMPLE_VALIDATION = {
    "pass": 3,
    "fail": 0,
    "attempts": 3,
    "avg_turns": 7.0,
    "avg_tokens": 200000,
    "avg_duration": 90.0,
    "cost_usd": 0.6,
    "trials": [],
}

SAMPLE_TASK_DATA = {
    "timestamp": "2026-03-25T16:56:26",
    "total_cost_usd": 1.44,
    "exploration": SAMPLE_EXPLORATION,
    "validation": SAMPLE_VALIDATION,
}

SAMPLE_BASELINE = {
    "domain": "Office",
    "o46_no": 0.2,
    "s45_no": 0.0,
    "o46_with": 0.8,
    "s45_with": 1.0,
}

SAMPLE_ANALYSIS_META = {
    "task": "offer-letter-generator",
    "skill": "docx-template-fill",
    "category": "B1",
    "outcome": "success",
    "notes": "Evolved >= Curated",
}


def test_build_record_returns_dict():
    rec = ar.build_record("offer-letter-generator", SAMPLE_TASK_DATA, SAMPLE_BASELINE, SAMPLE_ANALYSIS_META)
    assert isinstance(rec, dict)


def test_build_record_basic_fields():
    rec = ar.build_record("offer-letter-generator", SAMPLE_TASK_DATA, SAMPLE_BASELINE, SAMPLE_ANALYSIS_META)
    assert rec["task"] == "offer-letter-generator"
    assert rec["domain"] == "Office"
    assert rec["category"] == "B1"
    assert rec["outcome"] == "success"
    assert rec["skill"] == "docx-template-fill"


def test_build_record_baseline_fields():
    rec = ar.build_record("offer-letter-generator", SAMPLE_TASK_DATA, SAMPLE_BASELINE, SAMPLE_ANALYSIS_META)
    assert rec["o46_no"] == 0.2
    assert rec["o46_with"] == 0.8


def test_build_record_efficiency():
    rec = ar.build_record("offer-letter-generator", SAMPLE_TASK_DATA, SAMPLE_BASELINE, SAMPLE_ANALYSIS_META)
    eff = rec["efficiency"]
    assert "turn_delta" in eff
    assert eff["turn_delta"] == -3.0  # 7.0 - 10.0


def test_build_record_evolved_vs_curated_evolved_gt():
    # validation pass_rate = 3/3 = 1.0, curated = 0.8 → evolved_gt_curated
    rec = ar.build_record("offer-letter-generator", SAMPLE_TASK_DATA, SAMPLE_BASELINE, SAMPLE_ANALYSIS_META)
    eff = rec["efficiency"]
    assert eff["evolved_vs_curated"] == "evolved_gt_curated"


def test_build_record_evolved_vs_curated_both_fail():
    baseline = dict(SAMPLE_BASELINE, o46_with=0.0)
    val = dict(SAMPLE_VALIDATION, **{"pass": 0, "attempts": 3})
    td = dict(SAMPLE_TASK_DATA, validation=val)
    rec = ar.build_record("test-task", td, baseline, {})
    eff = rec["efficiency"]
    assert eff["evolved_vs_curated"] == "both_fail"


def test_build_record_no_analysis_meta():
    rec = ar.build_record("offer-letter-generator", SAMPLE_TASK_DATA, SAMPLE_BASELINE, None)
    assert rec["outcome"] == "incomplete"
    assert rec["skill"] is None


def test_build_record_no_baseline():
    rec = ar.build_record("offer-letter-generator", SAMPLE_TASK_DATA, None, SAMPLE_ANALYSIS_META)
    assert rec["o46_no"] is None
    assert rec["o46_with"] is None


# ---------------------------------------------------------------------------
# Task 5: generate_report()
# ---------------------------------------------------------------------------

SAMPLE_RECORDS = [
    {
        "task": "offer-letter-generator",
        "domain": "Office",
        "category": "B1",
        "outcome": "success",
        "skill": "docx-template-fill",
        "timestamp": "2026-03-25T16:56:26",
        "total_cost_usd": 1.44,
        "o46_no": 0.2, "s45_no": 0.0, "o46_with": 0.8, "s45_with": 1.0,
        "exploration": SAMPLE_EXPLORATION,
        "validation": SAMPLE_VALIDATION,
        "efficiency": {
            "turn_delta": -3.0,
            "token_delta_pct": 33.3,
            "evolved_pass_rate": 1.0,
            "curated_pass_rate": 0.8,
            "evolved_vs_curated": "evolved_gt_curated",
        },
        "notes": "Evolved >= Curated",
    }
]

SAMPLE_ANALYSES = {
    "offer-letter-generator": {
        "meta": SAMPLE_ANALYSIS_META,
        "body": "This skill succeeded because it provided the template filling approach.",
    }
}


def test_generate_report_returns_string():
    report = ar.generate_report(SAMPLE_RECORDS)
    assert isinstance(report, str)
    assert len(report) > 100


def test_generate_report_has_auto_generated_comment():
    report = ar.generate_report(SAMPLE_RECORDS)
    assert "AUTO-GENERATED" in report


def test_generate_report_has_summary_section():
    report = ar.generate_report(SAMPLE_RECORDS)
    assert "## Summary" in report or "# Summary" in report


def test_generate_report_has_task_name():
    report = ar.generate_report(SAMPLE_RECORDS)
    assert "offer-letter-generator" in report


def test_generate_report_has_harbor_metrics_section():
    report = ar.generate_report(SAMPLE_RECORDS)
    assert "Harbor" in report or "harbor" in report


def test_generate_report_has_evolved_vs_curated_section():
    report = ar.generate_report(SAMPLE_RECORDS)
    assert "Evolved" in report and "Curated" in report


def test_generate_detail_report_analysis_body_injected():
    detail = ar.generate_detail_report(SAMPLE_RECORDS, SAMPLE_ANALYSES, "")
    assert "template filling approach" in detail


def test_generate_detail_report_patterns_body_injected():
    patterns = "## Patterns\n\nSome pattern here."
    detail = ar.generate_detail_report(SAMPLE_RECORDS, SAMPLE_ANALYSES, patterns)
    assert "Some pattern here" in detail


def test_fmt_tokens():
    assert ar._fmt_tokens(263000) == "263k"
    assert ar._fmt_tokens(1380000) == "1.38M"
    assert ar._fmt_tokens(0) == "0"


def test_fmt_phase():
    phase = {"pass": 3, "attempts": 4}
    assert ar._fmt_phase(phase) == "3/4"
    assert ar._fmt_phase(None) == "—"


# ---------------------------------------------------------------------------
# Task 6: main() / _run()
# ---------------------------------------------------------------------------

def test_main_exists():
    assert hasattr(ar, "main"), "aggregate_results must have a main() function"
    assert callable(ar.main)


def test_run_exists():
    assert hasattr(ar, "_run"), "_run() must exist"


def test_run_summary_mode(capsys_or_nothing):
    """_run with summary=True should not raise."""
    import argparse
    args = argparse.Namespace(summary=True, task=None)
    # Should not raise
    try:
        ar._run(args)
    except SystemExit:
        pass  # acceptable for missing files


def _dummy_args(**kwargs):
    import argparse
    defaults = {"summary": False, "task": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def capsys_or_nothing(func):
    """Stub decorator for non-pytest usage."""
    return func


def test_sort_order():
    """Records should sort: success first, then partial, fail, incomplete; alpha within."""
    records = [
        {"task": "z-task", "outcome": "success"},
        {"task": "a-task", "outcome": "fail"},
        {"task": "m-task", "outcome": "success"},
        {"task": "b-task", "outcome": "incomplete"},
        {"task": "c-task", "outcome": "partial"},
    ]
    sorted_recs = ar._sort_records(records)
    outcomes = [r["outcome"] for r in sorted_recs]
    # success group comes first
    assert outcomes[0] == "success"
    assert outcomes[1] == "success"
    # success entries are alphabetical
    tasks_success = [r["task"] for r in sorted_recs if r["outcome"] == "success"]
    assert tasks_success == sorted(tasks_success)


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [
        # Task 1
        test_parse_baselines_returns_dict,
        test_parse_baselines_known_task,
        test_parse_baselines_another_task,
        test_parse_baselines_science_task,
        test_parse_baselines_no_header_rows,
        test_parse_baselines_count,
        # Task 2
        test_parse_analysis_file_basic,
        test_parse_analysis_file_notes_unquoted,
        test_parse_analysis_file_no_frontmatter,
        test_parse_analysis_file_body_stripped,
        # Task 2 with tmp_path simulation
        # (load_all_analyses tests need tmp_path, run them separately)
        # Task 3
        test_discover_tasks_returns_dict,
        test_discover_tasks_finds_offer_letter,
        test_discover_tasks_skips_former,
        test_discover_tasks_path_is_dir,
        test_load_task_data_offer_letter,
        test_load_task_data_exploration_fields,
        test_load_task_data_normalized_keys,
        test_load_task_data_validation_or_none,
        # Task 4
        test_build_record_returns_dict,
        test_build_record_basic_fields,
        test_build_record_baseline_fields,
        test_build_record_efficiency,
        test_build_record_evolved_vs_curated_evolved_gt,
        test_build_record_evolved_vs_curated_both_fail,
        test_build_record_no_analysis_meta,
        test_build_record_no_baseline,
        # Task 5
        test_generate_report_returns_string,
        test_generate_report_has_auto_generated_comment,
        test_generate_report_has_summary_section,
        test_generate_report_has_task_name,
        test_generate_report_has_harbor_metrics_section,
        test_generate_report_has_evolved_vs_curated_section,
        test_generate_detail_report_patterns_body_injected,
        test_generate_detail_report_analysis_body_injected,
        test_fmt_tokens,
        test_fmt_phase,
        # Task 6
        test_main_exists,
        test_run_exists,
        test_sort_order,
    ]

    # Task 2 tmp_path tests
    import tempfile
    tmp = Path(tempfile.mkdtemp())

    def run_load_all_analyses_tests():
        test_load_all_analyses_skips_underscore(tmp / "t1")
        (tmp / "t1").mkdir(exist_ok=True)
        test_load_all_analyses_skips_underscore(tmp / "t1")
        test_load_all_analyses_empty_dir(tmp / "t2")
        (tmp / "t2").mkdir(exist_ok=True)
        test_load_all_analyses_empty_dir(tmp / "t2")

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  PASS  {test_fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test_fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    # Run tmp_path tests manually
    for name, fn, args in [
        ("test_load_all_analyses_skips_underscore", test_load_all_analyses_skips_underscore, [tmp / "t1"]),
        ("test_load_all_analyses_structure", test_load_all_analyses_structure, [tmp / "t2"]),
        ("test_load_all_analyses_empty_dir", test_load_all_analyses_empty_dir, [tmp / "t3"]),
    ]:
        try:
            args[0].mkdir(exist_ok=True)
            fn(args[0])
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    if failed == 0:
        print("All tests passed")
    else:
        sys.exit(1)
