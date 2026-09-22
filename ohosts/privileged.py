"""Writing a file that belongs to root, with a backup and without a root editor.

The new contents are written to a temporary file first and installed in one step, so
/etc/hosts is never half-written — a half-written hosts file is a machine that cannot
resolve its own name.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile


class PrivilegeError(Exception):
    pass


def elevator() -> list[str]:
    """How to become root: sudo on a terminal, pkexec from a menu.

    $OMARCHY_HOSTS_ELEVATOR overrides both, for doas, for a passwordless setup, or
    for a test harness.
    """
    override = os.environ.get("OMARCHY_HOSTS_ELEVATOR")
    if override:
        return shlex.split(override)
    if os.geteuid() == 0:
        return []
    if sys.stdin.isatty() and shutil.which("sudo"):
        return ["sudo"]
    for candidate in ("pkexec", "sudo", "doas"):
        if shutil.which(candidate):
            return [candidate]
    raise PrivilegeError("none of pkexec, sudo or doas is available")


def install(text: str, target: str, backup_suffix: str = "") -> None:
    fd, tmp = tempfile.mkstemp(prefix="omarchy-hosts.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        script = "set -e\n"
        if backup_suffix:
            script += f'[ -f "{target}" ] && cp -a "{target}" "{target}{backup_suffix}"\n'
        script += f'install -Dm644 "{tmp}" "{target}"\n'
        run_privileged(script)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def run_privileged(script: str) -> str:
    cmd = [*elevator(), "/bin/sh", "-c", script]
    r = subprocess.run(cmd, capture_output=True, check=False)
    if r.returncode != 0:
        detail = (r.stderr + r.stdout).decode("utf-8", "replace").strip()
        raise PrivilegeError(detail or f"the privileged step exited {r.returncode}")
    return r.stdout.decode("utf-8", "replace")


def writable(path: str) -> bool:
    return os.access(path, os.W_OK)
