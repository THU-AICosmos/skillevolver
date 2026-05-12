"""Workspace setup, task loading, and skill deployment."""

import shutil
import subprocess
import sys
from pathlib import Path

from .config import (
    EVOLVED_SKILLS_DIR,
    SKILL_EVOLVER_DIR,
    TASKS_DIR,
    TASKS_EVOLVED_SKILLS_DIR,
    TASKS_NO_SKILLS_DIR,
    TASKS_TRAIN_DIR,
)


def create_agent_venv(workspace: Path) -> Path:
    """Create a clean Python venv for the agent to use.

    Returns the venv bin directory (to prepend to PATH).
    The agent's Bash commands will use this venv's python/pip
    instead of the host conda env or system python.
    """
    venv_dir = workspace / ".venv"
    if venv_dir.exists():
        return venv_dir / "bin"

    print(f"  Creating clean agent venv at {venv_dir}...")
    # Create venv without pip (ensurepip missing on this system),
    # then bootstrap pip via get-pip.py
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    venv_python = str(venv_dir / "bin" / "python3")
    # Bootstrap pip from a pre-downloaded cached copy to avoid flaky
    # network fetches of bootstrap.pypa.io during batch runs. Fall back
    # to a live download only if the cache is missing.
    cached_get_pip = Path(__file__).resolve().parent.parent / ".cache" / "get-pip.py"
    if not cached_get_pip.exists():
        cached_get_pip.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [venv_python, "-c",
             f"import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '{cached_get_pip}')"],
            check=True,
            capture_output=True,
        )
    subprocess.run(
        [venv_python, str(cached_get_pip), "--quiet"],
        check=True,
        capture_output=True,
    )
    # Pre-install packages needed by scripts the agent will call
    venv_pip = str(venv_dir / "bin" / "pip")
    subprocess.run(
        [venv_pip, "install", "--quiet",
         "claude-agent-sdk", "anyio"],
        check=True,
        capture_output=True,
    )

    # Expose the project-root `agent` package inside this venv so any
    # `python -c "from agent..."` invocation works regardless of cwd.
    # A .pth file is the standard Python mechanism for this.
    project_root = Path(__file__).resolve().parent.parent
    site_packages = venv_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if site_packages.exists():
        (site_packages / "agent_project.pth").write_text(str(project_root) + "\n")

    return venv_dir / "bin"


def load_task_context(
    task_name: str,
    tasks_root: Path | None = None,
) -> tuple[str, str, list[Path]]:
    """Load instruction.md, Dockerfile, and data file paths for a task.

    Uses the no-skills version first (same instruction, no curated skills).
    Strips any "Generate Skills First" suffix from the instruction.
    Returns (instruction, dockerfile, data_files) where data_files are paths
    to input files the benchmark agent would see inside the container.
    """
    if tasks_root is not None:
        task_dir = tasks_root / task_name
    else:
        task_dir = TASKS_NO_SKILLS_DIR / task_name
        if not task_dir.exists():
            task_dir = TASKS_DIR / task_name

    instruction_path = task_dir / "instruction.md"
    dockerfile_path = task_dir / "environment" / "Dockerfile"

    if not instruction_path.exists():
        raise FileNotFoundError(f"instruction.md not found at {instruction_path}")
    if not dockerfile_path.exists():
        raise FileNotFoundError(f"Dockerfile not found at {dockerfile_path}")

    instruction = instruction_path.read_text()
    if "## Important: Generate Skills First" in instruction:
        instruction = instruction.split("## Important: Generate Skills First")[0].strip()

    dockerfile = dockerfile_path.read_text()

    # Collect data files from environment/ (exclude Dockerfile, skills/, solution, tests)
    env_dir = task_dir / "environment"
    data_files: list[Path] = []
    exclude = {"Dockerfile", "skills"}
    for item in env_dir.iterdir():
        if item.name in exclude:
            continue
        if item.is_file():
            data_files.append(item)
        elif item.is_dir() and item.name == "data":
            data_files.extend(f for f in item.rglob("*") if f.is_file())

    return instruction, dockerfile, data_files


def ensure_task_variant(task_name: str, output_task_dir: Path):
    """Create the task variant skeleton once if it doesn't exist yet.

    Copies from the source task (no-skills or tasks/) and patches the
    Dockerfile to COPY skills into all agent locations.
    """
    if output_task_dir.exists():
        return

    source_task = TASKS_NO_SKILLS_DIR / task_name
    if not source_task.exists():
        source_task = TASKS_DIR / task_name

    shutil.copytree(source_task, output_task_dir)

    dockerfile_path = output_task_dir / "environment" / "Dockerfile"
    dockerfile = dockerfile_path.read_text()

    if "COPY skills /root/.claude/skills" not in dockerfile:
        copy_lines = """
# Copy evolved skills to agent-specific locations
COPY skills /root/.claude/skills
COPY skills /root/.codex/skills
COPY skills /root/.opencode/skill
COPY skills /root/.goose/skills
COPY skills /root/.factory/skills
COPY skills /root/.agents/skills
COPY skills /root/.gemini/skills
"""
        dockerfile += copy_lines
        dockerfile_path.write_text(dockerfile)

    print(f"Created task variant skeleton at: {output_task_dir}")


def deploy_skills(skills_dir: Path, output_task_dir: Path):
    """Copy evolved skills into the task variant for benchmarking.

    Replaces any existing skills in the task variant.
    """
    env_skills = output_task_dir / "environment" / "skills"
    if env_skills.exists():
        shutil.rmtree(env_skills)
    shutil.copytree(skills_dir, env_skills)

    skill_files = list(env_skills.rglob("*.md"))
    print(f"Deployed {len(skill_files)} skill file(s) to: {env_skills}")


def setup_workspace(
    task_name: str,
    timestamp: str,
    instruction: str,
    dockerfile: str,
    data_files: list[Path],
    version: str = "evolver",
    seed_skill_dir: Path | None = None,
) -> Path:
    """Create isolated workspace for the agent.

    Layout: ``evolved-skills/<version>/<task>/<timestamp>/``. Version lives at
    the top so concurrent runs are sharded cleanly.
    """
    if version != "evolver":
        raise ValueError(f"Unknown version: {version}. Only 'evolver' is supported.")

    workspace = EVOLVED_SKILLS_DIR / version / task_name / timestamp
    task_dir = workspace / "task"
    task_dir.mkdir(parents=True, exist_ok=True)

    # Write task context
    (task_dir / "instruction.md").write_text(instruction)
    (task_dir / "Dockerfile").write_text(dockerfile)

    # Copy data files
    if data_files:
        data_dir = task_dir / "task-data"
        data_dir.mkdir(parents=True, exist_ok=True)
        for f in data_files:
            shutil.copy2(f, data_dir / f.name)

    # Symlink the SKILL.md + helper layout into the workspace
    link = workspace / "skill-evolver"
    if not link.exists():
        link.symlink_to(SKILL_EVOLVER_DIR)

    # Create iteration and output directories
    (workspace / "bootstrap" / "skills").mkdir(parents=True, exist_ok=True)
    (workspace / "strategy-hints").mkdir(exist_ok=True)
    for i in range(1, 4):
        (workspace / f"iteration-{i}").mkdir(exist_ok=True)
    (workspace / "output").mkdir(exist_ok=True)

    if seed_skill_dir is not None:
        if not seed_skill_dir.exists():
            raise FileNotFoundError(f"Seed skill dir not found: {seed_skill_dir}")
        if not (seed_skill_dir / "SKILL.md").exists():
            raise FileNotFoundError(f"Seed skill missing SKILL.md: {seed_skill_dir}")
        bootstrap_dst = workspace / "bootstrap" / "skills" / seed_skill_dir.name
        if bootstrap_dst.exists():
            shutil.rmtree(bootstrap_dst)
        shutil.copytree(seed_skill_dir, bootstrap_dst)

    return workspace


def copy_train_context(task_name: str, workspace: Path) -> None:
    """Copy tasks-train/<task> contents to workspace/task/train-context/.

    Called after exploration so the agent can analyze training task details
    (test_outputs.py, solve.sh, data) for deeper trace understanding.

    Train variants no longer have a `skills/` subdirectory at all — it's
    deleted at source by `run_and_wait.py` after each exploration run, and
    the canonical state is "no skills". So an unconditional copytree is
    safe: there is nothing to exclude. As a belt-and-suspenders guard, we
    still ignore any `skills` entry directly under `environment/` in case
    someone accidentally re-creates it.
    """
    source = TASKS_TRAIN_DIR / task_name
    if not source.exists():
        print(f"WARNING: tasks-train/{task_name} not found, skipping train context copy")
        return

    dest = workspace / "task" / "train-context"
    if dest.exists():
        shutil.rmtree(dest)

    def _ignore_skills(src_dir: str, names: list[str]) -> list[str]:
        if Path(src_dir).resolve() == (source / "environment").resolve():
            return [n for n in names if n == "skills"]
        return []

    shutil.copytree(source, dest, ignore=_ignore_skills)
    print(f"Copied train context to {dest}")
