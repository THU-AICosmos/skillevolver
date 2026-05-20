#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITE = PROJECT_ROOT / "Benchmarks" / "skillsbench" / ".venv" / "lib" / "python3.12" / "site-packages" / "harbor"


def insert_once(text: str, anchor: str, addition: str) -> str:
    if addition.strip() in text:
        return text
    if anchor not in text:
        raise ValueError(f"anchor not found: {anchor!r}")
    return text.replace(anchor, anchor + addition, 1)


def patch_trial_config(text: str) -> str:
    return insert_once(
        text,
        '    trial_name: str = ""\n',
        '    trial_index: int = 0  # PATCH: 0-based index for strategy selection\n',
    )


def patch_job(text: str) -> str:
    text = text.replace(
        "for _ in range(self.config.n_attempts)",
        "for attempt_idx in range(self.config.n_attempts)",
    )
    return insert_once(
        text,
        "                job_id=self._id,\n",
        "                trial_index=attempt_idx,  # PATCH\n",
    )


def patch_trial_py(text: str) -> str:
    return insert_once(
        text,
        "            logger=self._logger,\n",
        "            trial_index=self.config.trial_index,  # PATCH\n",
    )


def patch_docker_py(text: str) -> str:
    field_anchor_candidates = [
        '    network_mode: str = "bridge"\n',
        '    memory: str = "1G"\n',
    ]
    for anchor in field_anchor_candidates:
        if anchor in text:
            text = insert_once(
                text,
                anchor,
                '    harbor_trial_index: int = 0  # PATCH\n',
            )
            break
    else:
        raise ValueError("anchor not found for DockerEnvironmentEnvVars harbor_trial_index")

    gpu_field_anchor = '    harbor_trial_index: int = 0  # PATCH\n'
    if gpu_field_anchor in text:
        text = insert_once(
            text,
            gpu_field_anchor,
            '    gpus: int = 0  # PATCH\n',
        )

    init_anchor_candidates = [
        '            network_mode="bridge" if task_env_config.allow_internet else "none",\n',
        '            memory=f"{task_env_config.memory_mb}M",\n',
    ]
    addition2 = '            harbor_trial_index=kwargs.get("trial_index", 0),  # PATCH\n'
    for anchor in init_anchor_candidates:
        if anchor in text:
            text = insert_once(text, anchor, addition2)
            break
    else:
        raise ValueError("anchor not found for DockerEnvironmentEnvVars init harbor_trial_index")

    gpu_init_anchor = '            harbor_trial_index=kwargs.get("trial_index", 0),  # PATCH\n'
    if gpu_init_anchor in text:
        text = insert_once(
            text,
            gpu_init_anchor,
            '            gpus=task_env_config.gpus,  # PATCH\n',
        )

    old = """        full_command = [
            "docker",
            "compose",
            "--project-name",
            _sanitize_docker_compose_project_name(self.session_id),
            "--project-directory",
            str(self.environment_dir.resolve().absolute()),
        ]
"""
    new = """        project_name = _sanitize_docker_compose_project_name(self.session_id)
        project_dir = str(self.environment_dir.resolve().absolute())
        if shutil.which("docker-compose"):
            full_command = [
                "docker-compose",
                "--project-name",
                project_name,
                "--project-directory",
                project_dir,
            ]
        else:
            full_command = [
                "docker",
                "compose",
                "--project-name",
                project_name,
                "--project-directory",
                project_dir,
            ]
"""
    if old in text:
        text = text.replace(old, new, 1)

    if os.environ.get("ENABLE_HARBOR_DOCKER_GPU_PATCH") != "1":
        return text

    if '    COMPOSE_GPU_PATH,\n' not in text:
        import_anchor = '    COMPOSE_PREBUILT_PATH,\n)'
        if import_anchor in text:
            text = text.replace(import_anchor, '    COMPOSE_PREBUILT_PATH,\n    COMPOSE_GPU_PATH,\n)')

    if '_DOCKER_COMPOSE_GPU_PATH = COMPOSE_GPU_PATH' not in text:
        class_anchor = '    _DOCKER_COMPOSE_NO_NETWORK_PATH = COMPOSE_NO_NETWORK_PATH\n'
        if class_anchor in text:
            text = text.replace(class_anchor, class_anchor + '    _DOCKER_COMPOSE_GPU_PATH = COMPOSE_GPU_PATH\n', 1)

    text = text.replace(
        '    def supports_gpus(self) -> bool:\n        return False\n',
        '    def supports_gpus(self) -> bool:\n        return True\n',
    )

    repeated_gpu_block = """        if self.task_env_config.gpus > 0:
            paths.append(self._DOCKER_COMPOSE_GPU_PATH)

"""
    while text.count(repeated_gpu_block) > 1:
        text = text.replace(repeated_gpu_block + repeated_gpu_block, repeated_gpu_block, 1)

    gpu_paths_old = """        if not self.task_env_config.allow_internet:
            paths.append(self._DOCKER_COMPOSE_NO_NETWORK_PATH)

        return paths
"""
    gpu_paths_new = """        if self.task_env_config.gpus > 0:
            paths.append(self._DOCKER_COMPOSE_GPU_PATH)

        if not self.task_env_config.allow_internet:
            paths.append(self._DOCKER_COMPOSE_NO_NETWORK_PATH)

        return paths
"""
    if gpu_paths_old in text:
        text = text.replace(gpu_paths_old, gpu_paths_new, 1)

    while text.count(repeated_gpu_block) > 1:
        text = text.replace(repeated_gpu_block + repeated_gpu_block, repeated_gpu_block, 1)

    return text


def patch_docker_init(text: str) -> str:
    if os.environ.get("ENABLE_HARBOR_DOCKER_GPU_PATCH") != "1":
        return text
    if "COMPOSE_GPU_PATH" in text:
        return text
    return text + 'COMPOSE_GPU_PATH = COMPOSE_DIR / "docker-compose-gpu.yaml"\n'


def ensure_gpu_compose_file() -> None:
    path = SITE / "environments" / "docker" / "docker-compose-gpu.yaml"
    content = "services:\n  main:\n    deploy:\n      resources:\n        reservations:\n          devices:\n            - driver: nvidia\n              count: ${GPUS}\n              capabilities: [gpu]\n"
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
        print(f"patched {path}")
    else:
        print(f"already patched {path}")

def patch_compose_yaml(text: str) -> str:
    proxy_build_block = (
        "      args:\n"
        "        http_proxy: ${http_proxy:-}\n"
        "        https_proxy: ${https_proxy:-}\n"
        "        HTTP_PROXY: ${HTTP_PROXY:-}\n"
        "        HTTPS_PROXY: ${HTTPS_PROXY:-}\n"
        "        no_proxy: ${no_proxy:-}\n"
        "        NO_PROXY: ${NO_PROXY:-}\n"
    )
    if "    build:\n" in text and "        http_proxy: ${http_proxy:-}\n" not in text:
        text = insert_once(text, "    build:\n", proxy_build_block)

    if "    environment:\n" not in text and '    command: [ "sh", "-c", "sleep infinity" ]\n' in text:
        text = insert_once(text, '    command: [ "sh", "-c", "sleep infinity" ]\n', "    environment:\n")

    if "    environment:\n" not in text and "      - TEST_DIR=${TEST_DIR}\n" in text:
        text = insert_once(text, "      - TEST_DIR=${TEST_DIR}\n", "    environment:\n")

    proxy_env_lines = [
        "      - HARBOR_TRIAL_INDEX=${HARBOR_TRIAL_INDEX}\n",
        "      - http_proxy=${http_proxy:-}\n",
        "      - https_proxy=${https_proxy:-}\n",
        "      - HTTP_PROXY=${HTTP_PROXY:-}\n",
        "      - HTTPS_PROXY=${HTTPS_PROXY:-}\n",
        "      - no_proxy=${no_proxy:-}\n",
        "      - NO_PROXY=${NO_PROXY:-}\n",
    ]

    if "    environment:\n" in text:
        for line in reversed(proxy_env_lines):
            if line not in text:
                text = insert_once(text, "    environment:\n", line)
        return text

    raise ValueError("anchor not found for docker-compose environment block")


def patch_claude_code(text: str) -> str:
    # Append `chmod -R a+rX $CLAUDE_CONFIG_DIR` to the SAME ExecInput as the
    # claude command, joined with `;`. Two reasons it has to be the same shell,
    # not a separate ExecInput: (1) Harbor short-circuits the ExecInput sequence
    # on non-zero exit, so a follow-up chmod is silently skipped whenever the
    # agent hits budget / Claude CLI crashes / network errors, leaving the
    # session JSONL files mode 600 root:root and the trajectory unreadable from
    # the host ("Failed to convert Claude Code events to trajectory: Permission
    # denied"). (2) `a+rX` (capital X) adds traversal on directories without
    # making regular files executable; plain `a+r` leaves the dir un-traversable.
    if "chmod -R a+rX $CLAUDE_CONFIG_DIR" in text:
        return text
    anchor = '"/logs/agent/claude-code.txt"'
    if anchor not in text:
        raise ValueError(
            "patch_claude_code: anchor '/logs/agent/claude-code.txt' not found; "
            "harbor's claude command shape has changed — re-derive the patch"
        )
    return text.replace(
        anchor,
        '"/logs/agent/claude-code.txt ; chmod -R a+rX $CLAUDE_CONFIG_DIR || true"',
        1,
    )


PATCH_MAP = {
    SITE / "agents" / "installed" / "claude_code.py": patch_claude_code,
    SITE / "models" / "trial" / "config.py": patch_trial_config,
    SITE / "job.py": patch_job,
    SITE / "trial" / "trial.py": patch_trial_py,
    SITE / "environments" / "docker" / "__init__.py": patch_docker_init,
    SITE / "environments" / "docker" / "docker.py": patch_docker_py,
    SITE / "environments" / "docker" / "docker-compose-build.yaml": patch_compose_yaml,
    SITE / "environments" / "docker" / "docker-compose-prebuilt.yaml": patch_compose_yaml,
}


def main() -> None:
    if os.environ.get("ENABLE_HARBOR_DOCKER_GPU_PATCH") == "1":
        ensure_gpu_compose_file()
    for path, patcher in PATCH_MAP.items():
        original = path.read_text(encoding="utf-8")
        updated = patcher(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            print(f"patched {path}")
        else:
            print(f"already patched {path}")


if __name__ == "__main__":
    main()
