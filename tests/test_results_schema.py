from pathlib import Path
from agent.results import build_result_json


def test_result_json_has_baseline_fields(tmp_path):
    (tmp_path / "task").mkdir()
    build_result_json(
        tmp_path,
        task_name="demo",
        model="claude-opus-4-6",
        agent_cost_usd_sdk=0.0,
        agent_turns=0,
        agent_input_tokens=0,
        agent_output_tokens=0,
        agent_cache_read_tokens=0,
        agent_cache_creation_tokens=0,
    )
    import json
    result = json.loads((tmp_path / "result.json").read_text())
    # New optional fields for baselines; allow None but they must be present
    assert "iterations_run" in result
    assert "train_oracle_reward" in result
