"""Anti-cheating path guard for the skill-creator agent.

Whitelist-only approach: only paths under allowed prefixes are accessible.
Everything else is denied by default.

Uses Agent SDK's can_use_tool callback to enforce access control.
"""
import re
import shlex
from pathlib import Path
from typing import Optional


# Populated at runtime by configure_allowed_prefixes()
_allowed_prefixes: list[str] = []

# Denylist tripwire: paths containing any of these substrings are blocked
# even if they're inside the workspace whitelist. Used to prevent the agent
# from accessing the curated human-written skill via train-context/, even
# if a future change accidentally re-includes it in the copy.
_DENY_SUBSTRINGS: tuple[str, ...] = (
    "train-context/environment/skills",
)


def configure_allowed_prefixes(
    workspace: Path,
    project_root: Path,
) -> None:
    """Set the allowed path prefixes for the current run.

    Allowed:
      - workspace/            (read + write — agent's working directory)
    Skills and skill-creator scripts are copied/symlinked into the workspace,
    so no other paths need to be allowed.
    """
    global _allowed_prefixes
    _allowed_prefixes = [
        str(workspace.resolve()) + "/",
    ]


def set_allowed_prefixes(prefixes: list) -> None:
    """Set the allowed path prefixes explicitly (used by subagent runtime).

    Unlike configure_allowed_prefixes(), this takes an arbitrary list of
    directories. Each subagent subprocess gets its own narrow whitelist
    via this entry point.
    """
    global _allowed_prefixes
    _allowed_prefixes = [
        str(Path(p).resolve()) + "/" for p in prefixes
    ]


def is_path_allowed(path: str, allowed_prefixes: Optional[list[str]] = None) -> bool:
    """Check if a path falls under any allowed prefix."""
    prefixes = allowed_prefixes if allowed_prefixes is not None else _allowed_prefixes
    if not prefixes:
        return True  # Guard not configured yet — allow (defensive)

    # Check raw absolute path first (handles symlinks inside workspace),
    # then check resolved path (handles .. traversal attempts).
    try:
        abspath = str(Path(path).absolute())
        resolved = str(Path(path).resolve())
    except (OSError, ValueError):
        abspath = resolved = path

    return any(
        abspath.startswith(p) or abspath == p.rstrip("/")
        or resolved.startswith(p) or resolved == p.rstrip("/")
        for p in prefixes
    )


def check_path_access(path: str, allowed_prefixes: Optional[list[str]] = None) -> Optional[str]:
    """Check if a file path is allowed.

    Returns None if allowed, or an error message string if blocked.
    Whitelist-only: paths not under allowed prefixes are denied. Additionally,
    a denylist tripwire blocks paths containing forbidden substrings (e.g.
    `train-context/environment/skills`) even when they fall inside the
    workspace whitelist.
    """
    # Denylist tripwire — checked first, overrides the whitelist
    for needle in _DENY_SUBSTRINGS:
        if needle in path:
            return (
                f"Access denied: '{path}' is not part of the available "
                f"training context. Distill from traces, `solve.sh`, and "
                f"`test_outputs.py` only."
            )

    # Reject any path containing a `..` component. Without this, the agent
    # could read outside the workspace via `Read /workspace/../escape` or
    # similar — Path.resolve() handles this correctly only if the agent's
    # cwd matches the workspace, which we cannot rely on after a `cd` in
    # the bash tool.
    if ".." in Path(path).parts:
        return (
            f"Access denied: path '{path}' contains a parent-directory "
            f"reference (`..`). Use absolute paths inside your workspace, "
            f"or workspace-relative paths without `..`."
        )

    if is_path_allowed(path, allowed_prefixes):
        return None

    return (
        f"Access denied: '{path}' is outside your workspace. "
        f"You may only access files within your workspace directory."
    )


# ---------------------------------------------------------------------------
# Bash guard — extract paths from commands and check each one
# ---------------------------------------------------------------------------

# Regex to find absolute paths in a command string
_ABS_PATH_RE = re.compile(r'(?:^|[\s="])(/[^\s;"\'|&><]+)')

# Commands that take a directory/path argument and can leak information
_SEARCH_COMMANDS = {"find", "grep", "rg", "ag", "ack", "fd", "locate", "tree", "ls"}


def _extract_paths_from_command(command: str) -> list[str]:
    """Extract absolute paths from a bash command string."""
    paths: list[str] = []

    # Method 1: regex for absolute paths
    for match in _ABS_PATH_RE.finditer(command):
        paths.append(match.group(1))

    # Method 2: try shlex split for better parsing
    try:
        tokens = shlex.split(command)
        for token in tokens:
            if token.startswith("/") and not token.startswith("//"):
                paths.append(token)
    except ValueError:
        pass  # Malformed command — regex results are enough

    return list(set(paths))  # deduplicate


def check_bash_command(command: str) -> Optional[str]:
    """Check if a Bash command accesses paths outside the allowed prefixes.

    Returns None if allowed, or an error message string if blocked.
    """
    # Denylist tripwire — checked even before run_and_wait.py allowance,
    # so the agent can't smuggle a denied-path access through any helper.
    for needle in _DENY_SUBSTRINGS:
        if needle in command:
            return (
                f"Access denied: command references '{needle}', which is "
                f"not part of the available training context. Distill from "
                f"traces, `solve.sh`, and `test_outputs.py` only."
            )

    # Block parent-directory traversal in any form. The workspace is the
    # agent's own root — there is never a legitimate reason to use `..` to
    # walk up out of it. Without this rule, the absolute-path check below
    # is trivially bypassed by `cd ../../foo && cat ...` (relative paths
    # are not extracted by _extract_paths_from_command). Catches `..` as a
    # standalone token, `../foo`, `foo/../bar`, etc., but allows `..` only
    # when it appears inside a longer non-path identifier (e.g. `..foo`,
    # `var..bar` — extremely rare in shell).
    if re.search(r'(^|[\s\'"=/])\.\.(?:/|[\s\'";)|&]|$)', command):
        return (
            "Access denied: parent-directory traversal (`..`) is not "
            "permitted in shell commands. Use absolute paths (which must "
            "be inside your workspace) or workspace-relative paths."
        )

    # Always allow run_and_wait.py calls — the script internally accesses
    # Harbor/SkillsBench dirs, but that's safe (it's our controlled code)
    if "run_and_wait.py" in command:
        return None

    # Extract and check all absolute paths in the command
    paths = _extract_paths_from_command(command)
    for path in paths:
        if not is_path_allowed(path):
            return (
                f"Access denied: command references '{path}' which is outside "
                f"your workspace. You may only access files within your workspace."
            )

    return None
