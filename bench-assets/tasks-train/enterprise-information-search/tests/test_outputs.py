import json
import os

import pytest

ANSWER_PATH = "/root/answer.json"

DATA_PATH = "/root/DATA"
QUESTION_PATH = "/root/question.txt"

EXPECTED_ANSWER_Q1 = [
        "eid_07a0ca6e",
        "eid_37f8a88b",
        "eid_386ecbe0",
        "eid_392456de",
        "eid_46685257",
        "eid_6c031199",
        "eid_8b8148f6",
        "eid_a3b1799d",
        "eid_bc8960a9"
      ]

EXPECTED_ANSWER_Q2 = [
        "eid_17be3111",
        "eid_27cd8130",
        "eid_562b0f79",
        "eid_571aa876"
      ]

EXPECTED_ANSWER_Q3 = [
        "https://flowmatic.io/trial",
        "https://taskpilot.com/signup",
        "https://zenautomate.com/signup",
        "https://zenautomate.com/trial"
      ]

EXPECTED_ANSWERS = {
    "q1": EXPECTED_ANSWER_Q1,
    "q2": EXPECTED_ANSWER_Q2,
    "q3": EXPECTED_ANSWER_Q3,
}


def load_answer():
    assert os.path.exists(ANSWER_PATH), f"Missing output file: {ANSWER_PATH}"
    with open(ANSWER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestOutputs:
    def test_inputs_exist(self):
        """Check required input files exist."""
        assert os.path.exists(DATA_PATH), f"Missing input file: {DATA_PATH}"
        assert os.path.exists(QUESTION_PATH), f"Missing input file: {QUESTION_PATH}"

    def test_answer_structure_and_values(self):
        """Check answer structure and correctness for all questions."""
        actual = load_answer()
        assert isinstance(actual, dict), f"Answer is not a dict. Got {type(actual)}"
        missing = [k for k in EXPECTED_ANSWERS.keys() if k not in actual]
        assert not missing, f"Answer missing keys: {missing}. Got keys: {list(actual.keys())}"

        for q_key, expected in EXPECTED_ANSWERS.items():
            assert "answer" in actual[q_key], f"Missing 'answer' in {q_key}. Got {actual[q_key]}"
            got = actual[q_key]["answer"]
            assert isinstance(got, list), f"{q_key} answer is not a list. Got {type(got)}"
            assert len(got) == len(expected), (
                f"{q_key} length mismatch. Expected {len(expected)}, got {len(got)}"
            )
            assert set(got) == set(expected), f"{q_key} incorrect. Expected {expected}, got {got}"

    @pytest.mark.parametrize("q_key", ["q1", "q2", "q3"])
    def test_tokens_efficient(self, q_key):
        """Check token field exists and is within bounds."""
        actual = load_answer()
        assert q_key in actual, f"Answer does not contain {q_key}. Got {actual}"
        assert "tokens" in actual[q_key], f"Missing 'tokens' in {q_key}. Got {actual[q_key]}"
        tokens = actual[q_key]["tokens"]
        assert isinstance(tokens, (int, float)), f"{q_key} tokens not numeric. Got {tokens}"
        assert tokens > 0, f"{q_key} tokens not positive. Got {tokens}"
        assert tokens < 70000, f"{q_key} tokens too high. Got {tokens}"
