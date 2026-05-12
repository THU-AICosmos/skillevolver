"""Configuration for the skill-evolver agent."""

from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# SkillsBench paths
SKILLSBENCH_ROOT = PROJECT_ROOT / "Benchmarks" / "skillsbench"
TASKS_DIR = SKILLSBENCH_ROOT / "tasks"
TASKS_NO_SKILLS_DIR = SKILLSBENCH_ROOT / "tasks-no-skills"
TASKS_TRAIN_DIR = SKILLSBENCH_ROOT / "tasks-train"

# SkillEvolver — looped explore / analyze / update pipeline
SKILL_EVOLVER_DIR = PROJECT_ROOT / "skill-evolver"

# Output directory for evolved skills (workspace)
EVOLVED_SKILLS_DIR = PROJECT_ROOT / "evolved-skills"

# Task variant with evolved skills (inside SkillsBench submodule for Harbor)
TASKS_EVOLVED_SKILLS_DIR = SKILLSBENCH_ROOT / "tasks-evolved-skills"

# Agent defaults
DEFAULT_MODEL = "claude-opus-4-6"
MAX_TURNS = 200    # Higher — agent waits for Harbor runs (~30 min)
MAX_BUDGET = 30.0  # Opus + long session with 2 Harbor phases (5 explore + 5 validate).

# Trace-distillation pipeline defaults
DEFAULT_N_ATTEMPTS = 5            # Exploration runs per task (matches SkillsBench standard)
EXPLORATION_TEMPERATURE = 1.0     # Default Claude Code temperature
VALIDATION_N_ATTEMPTS = 5         # Validation runs per task (matches SkillsBench standard)
HARBOR_TIMEOUT_MULTIPLIER = 1.5   # Per-trial timeout multiplier (applied to each task's timeout).
                                  # Was 0.75 — too tight for slow optimization tasks (e.g. grid-dispatch-operator
                                  # DC-OPF, 600s upstream → 450s effective). Caused systematic AgentTimeoutError +
                                  # SIGTERM mid-run, killing trajectory.json even when reward was 1.

# Model pricing (USD per million tokens)
# Source: https://docs.anthropic.com/en/docs/about-claude/pricing
# Format: { model_key: (input_per_M, output_per_M, cache_read_per_M, cache_write_per_M) }
MODEL_PRICING = {
    "claude-opus-4-6":   (5.0,  25.0, 0.50, 6.25),
    "claude-sonnet-4-6": (3.0,  15.0, 0.30, 3.75),
    "claude-haiku-4-5":  (1.0,  5.0,  0.10, 1.25),
}


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    model: str,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> float | None:
    """Estimate cost in USD based on model pricing. Returns None if model unknown."""
    key = model.split("/")[-1] if "/" in model else model
    pricing = MODEL_PRICING.get(key)
    if pricing is None:
        return None
    inp_price, out_price, cache_read_price, cache_write_price = pricing
    cost = (
        input_tokens * inp_price
        + output_tokens * out_price
        + cache_read_tokens * cache_read_price
        + cache_creation_tokens * cache_write_price
    ) / 1_000_000
    return round(cost, 4)


# SkillEvolver pipeline profile
EVOLVER_N_EXPLORATION = 4               # Exploration trials per iteration on tasks-train/
EVOLVER_N_VALIDATION = 5                # Final validation trials on tasks/
EVOLVER_DEFAULT_ITERATIONS = 2          # Iterations of the explore/analyze/update loop
EVOLVER_MAX_ITERATIONS = 3              # Upper bound when --max-iterations is used
EVOLVER_MAX_BUDGET = 30.0               # USD cap per task run
EVOLVER_MAX_TURNS = 200                 # Turn cap per task run
EVOLVER_REWARD_SIGNAL_MODE = "auto"     # auto | discrete | continuous (auto = inferred from task)
EVOLVER_PASS_REWARD_MIN = 0.0           # Secondary threshold for binarized accounting (continuous reward only)
