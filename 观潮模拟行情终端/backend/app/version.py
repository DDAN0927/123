"""应用版本号（/api/health 与 OpenAPI 里展示用）。"""

from __future__ import annotations

import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _git_short() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=3,
        )
        sha = out.stdout.strip()
        return sha or "unknown"
    except Exception:
        return "unknown"


GIT_SHA = _git_short()
APP_VERSION = f"0.1.0+{GIT_SHA}"
