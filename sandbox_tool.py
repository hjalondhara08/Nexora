"""
Sandbox Tool — Isolated File Change Environment (optimized)
=============================================================
Creates a SESSION-SCOPED sandbox directory (outside the bot workspace) for
safe file editing using OfficeCLI (Word/Excel/PowerPoint) and plain-text
file writes.

Key differences from the original version:
  1. Sandboxes are keyed by `session_id`, not created fresh on every call —
     so write -> read -> write in the same agent run actually works.
  2. Every filename is resolved and checked against the sandbox root, so
     '../../etc/passwd'-style path traversal is rejected outright.
  3. officecli commands run inside a locked-down Docker container:
     no network, memory/CPU caps, read-only root filesystem, non-root user,
     and only the sandbox directory is mounted in. This is the actual
     "isolation" layer the original code was missing — a /tmp directory by
     itself gives you no protection against a malicious or buggy officecli
     invocation touching the rest of the host.
  4. Sandboxes carry a last-touched timestamp and are purged automatically
     after a TTL, instead of accumulating forever in /tmp.
  5. shlex.split() instead of naive .split() for command parsing.
  6. Errors are raised/logged with real context instead of silently
     swallowed.

Docker is used opportunistically: if the Docker daemon isn't available
(e.g. local dev without it installed), officecli falls back to running as
a plain subprocess directly in the sandbox directory, with a clear warning
in the result so the agent (and you) know isolation is degraded.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

logger = logging.getLogger("sandbox_tool")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SANDBOX_BASE = Path("/tmp/bot_sandboxes")
SANDBOX_BASE.mkdir(parents=True, exist_ok=True)

SANDBOX_TTL_SECONDS = 30 * 60          # purge a session's sandbox after 30 min idle
OFFICECLI_TIMEOUT_SECONDS = 30
DOCKER_IMAGE = "officecli-sandbox:latest"   # build this to include officecli + deps
DOCKER_MEMORY_LIMIT = "512m"
DOCKER_CPU_LIMIT = "1.0"

_docker_available: bool | None = None      # cached after first check


# ---------------------------------------------------------------------------
# Sandbox lifecycle — session-scoped, not per-call
# ---------------------------------------------------------------------------

def _sandbox_dir_for_session(session_id: str) -> Path:
    """
    Returns the sandbox directory for a given session, creating it if needed.
    Reusing the same directory across calls in a session is what makes
    write -> read -> officecli sequences actually work.
    """
    # Keep session_id filesystem-safe; don't trust it blindly either.
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_") or "default"
    sandbox_path = SANDBOX_BASE / f"session_{safe_id}"
    sandbox_path.mkdir(parents=True, exist_ok=True)
    _touch(sandbox_path)
    return sandbox_path


def _touch(sandbox_path: Path) -> None:
    """Records last-access time so stale sandboxes can be swept up later."""
    (sandbox_path / ".last_touched").write_text(str(time.time()))


def cleanup_stale_sandboxes(ttl_seconds: int = SANDBOX_TTL_SECONDS) -> list[str]:
    """
    Removes sandboxes that haven't been touched within `ttl_seconds`.
    Call this periodically (e.g. at the start of each agent turn, or on a
    scheduled job) rather than relying on a per-call cleanup that would
    otherwise destroy state a multi-step agent still needs.
    """
    removed = []
    now = time.time()
    for entry in SANDBOX_BASE.iterdir():
        if not entry.is_dir():
            continue
        marker = entry / ".last_touched"
        try:
            last_touched = float(marker.read_text()) if marker.exists() else 0
        except (ValueError, OSError):
            last_touched = 0
        if now - last_touched > ttl_seconds:
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry.name)
    if removed:
        logger.info("Cleaned up %d stale sandbox(es): %s", len(removed), removed)
    return removed


def cleanup_session_sandbox(session_id: str) -> None:
    """Explicitly remove one session's sandbox (e.g. when the agent run ends)."""
    sandbox_path = SANDBOX_BASE / f"session_{session_id}"
    shutil.rmtree(sandbox_path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Path safety — this is the part the original code was missing entirely
# ---------------------------------------------------------------------------

def _resolve_safe_path(sandbox_path: Path, filename: str) -> Path:
    """
    Resolves `filename` relative to the sandbox and guarantees the result
    stays inside it. Raises ValueError on any attempt to escape (e.g. via
    '..', absolute paths, or symlink tricks).
    """
    candidate = (sandbox_path / filename).resolve()
    sandbox_resolved = sandbox_path.resolve()
    if sandbox_resolved not in candidate.parents and candidate != sandbox_resolved:
        raise ValueError(
            f"Rejected path '{filename}': resolves outside the sandbox "
            f"({candidate} is not inside {sandbox_resolved})."
        )
    return candidate


# ---------------------------------------------------------------------------
# officecli execution — Docker-isolated when possible, subprocess fallback
# ---------------------------------------------------------------------------

def _docker_is_available() -> bool:
    global _docker_available
    if _docker_available is None:
        try:
            subprocess.run(
                ["docker", "image", "inspect", DOCKER_IMAGE],
                capture_output=True,
                timeout=5,
                check=True,
            )
            _docker_available = True
        except Exception:
            _docker_available = False
            logger.warning(
                f"Docker image '{DOCKER_IMAGE}' not found — officecli will run as a host subprocess "
                "in /tmp/bot_sandboxes."
            )
    return _docker_available


def _run_officecli_in_docker(args: list[str], sandbox_path: Path) -> dict:
    """
    Runs officecli inside a locked-down, disposable container:
      --rm                 container is removed after exit, no residue
      --network none        no network access at all
      --memory / --cpus     hard resource caps
      --read-only            root filesystem is read-only
      --user 1000:1000       non-root
      -v sandbox:/work       ONLY the sandbox dir is mounted, read-write
    """
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", DOCKER_MEMORY_LIMIT,
        "--cpus", DOCKER_CPU_LIMIT,
        "--read-only",
        "--user", "1000:1000",
        "-v", f"{sandbox_path}:/work",
        "-w", "/work",
        DOCKER_IMAGE,
        "officecli", *args,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=OFFICECLI_TIMEOUT_SECONDS,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "isolated": True,
        }
    except subprocess.TimeoutExpired:
        return {"error": "officecli timed out inside sandbox container", "returncode": -1, "isolated": True}
    except Exception as e:
        logger.exception("Docker-isolated officecli run failed")
        return {"error": str(e), "returncode": -1, "isolated": True}


def _run_officecli_subprocess(args: list[str], sandbox_path: Path) -> dict:
    """Fallback path when Docker isn't available. No real isolation — logged as such."""
    try:
        result = subprocess.run(
            ["officecli", *args],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
            timeout=OFFICECLI_TIMEOUT_SECONDS,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "isolated": False,
        }
    except subprocess.TimeoutExpired:
        return {"error": "officecli timed out", "returncode": -1, "isolated": False}
    except Exception as e:
        logger.exception("officecli subprocess run failed")
        return {"error": str(e), "returncode": -1, "isolated": False}


def run_officecli(args: list[str], sandbox_path: Path) -> dict:
    if _docker_is_available():
        return _run_officecli_in_docker(args, sandbox_path)
    return _run_officecli_subprocess(args, sandbox_path)


# ---------------------------------------------------------------------------
# The LangGraph tool
# ---------------------------------------------------------------------------

@tool
def sandbox_file_tool(
    session_id: str,
    operation: Literal["write_text", "officecli", "read"],
    filename: str,
    content: str = "",
    officecli_command: str = "",
) -> dict:
    """
    Execute safe file creation, editing, or inspection inside an isolated,
    session-scoped sandbox. Use this tool when the user asks to:
      - Create or edit a Word (.docx), Excel (.xlsx), PowerPoint (.pptx) file
      - Write or modify a text/code file without touching the real workspace
      - Preview a file change before applying it to the real workspace

    Args:
        session_id: Stable identifier for the current agent run/conversation.
            Reusing the same session_id across calls reuses the same sandbox,
            so a write followed by a later read/officecli call sees the file.
        operation: One of 'write_text', 'officecli', 'read'.
        filename: File name relative to the sandbox root (e.g. 'report.docx').
            Must resolve inside the sandbox — '..' escapes are rejected.
        content: Text content for 'write_text' operations.
        officecli_command: Full officecli command string, e.g. 'create report.docx'.

    Returns:
        dict with sandbox_path, status, and operation-specific output.
    """
    try:
        cleanup_stale_sandboxes()  # cheap opportunistic sweep, not per-file
        sandbox_path = _sandbox_dir_for_session(session_id)

        if operation == "write_text":
            filepath = _resolve_safe_path(sandbox_path, filename)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return {
                "status": "success",
                "operation": "write_text",
                "sandbox_path": str(sandbox_path),
                "filename": filename,
                "message": f"File '{filename}' written successfully in sandbox.",
                "preview": content[:300] + ("..." if len(content) > 300 else ""),
            }

        elif operation == "officecli":
            if not officecli_command.strip():
                return {"status": "failed", "error": "officecli_command is empty."}
            args = shlex.split(officecli_command)
            result = run_officecli(args, sandbox_path)
            if result.get("returncode", -1) != 0:
                return {
                    "status": "failed",
                    "operation": "officecli",
                    "sandbox_path": str(sandbox_path),
                    "command": officecli_command,
                    "isolated": result.get("isolated"),
                    "error": result.get("stderr") or result.get("error") or "unknown error",
                }
            return {
                "status": "success",
                "operation": "officecli",
                "sandbox_path": str(sandbox_path),
                "command": officecli_command,
                "isolated": result.get("isolated"),
                "output": result.get("stdout", ""),
            }

        elif operation == "read":
            filepath = _resolve_safe_path(sandbox_path, filename)
            if not filepath.exists():
                return {"status": "failed", "error": f"File '{filename}' not found in sandbox."}
            result = run_officecli(["view", filename, "outline"], sandbox_path)
            return {
                "status": "success",
                "operation": "read",
                "sandbox_path": str(sandbox_path),
                "filename": filename,
                "isolated": result.get("isolated"),
                "output": result.get("stdout", ""),
            }

        else:
            # Unreachable given Literal typing, kept as a defensive guard.
            return {"status": "failed", "error": f"Unknown operation '{operation}'."}

    except ValueError as e:
        # Raised by _resolve_safe_path on path-traversal attempts.
        logger.warning("Rejected unsafe sandbox path: %s", e)
        return {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.exception("sandbox_file_tool failed")
        return {"status": "failed", "error": f"Unexpected error: {e}"}