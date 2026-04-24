from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"


def run_step(label: str, command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"\n==> {label}")
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run core CI checks for DocStruct.")
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    args = parser.parse_args()

    if args.backend_only and args.frontend_only:
        parser.error("--backend-only and --frontend-only cannot be used together")

    run_backend = not args.frontend_only
    run_frontend = not args.backend_only

    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(ROOT / ".uv-cache"))

    if run_backend:
        run_step(
            "Backend compile check",
            ["uv", "run", "python", "-m", "compileall", "main.py", "core", "schemas", "scripts"],
            ROOT,
            env=env,
        )
        run_step(
            "Backend app import check",
            ["uv", "run", "python", "-c", "import main; assert main.app is not None"],
            ROOT,
            env=env,
        )
        run_step(
            "Backend parser contract test",
            ["uv", "run", "python", "-m", "unittest", "scripts.test_parser_contract"],
            ROOT,
            env=env,
        )
        run_step(
            "Backend extraction resilience test",
            ["uv", "run", "python", "-m", "unittest", "scripts.test_extraction_resilience"],
            ROOT,
            env=env,
        )

    if run_frontend:
        run_step("Frontend build", ["npm.cmd", "run", "build"], FRONTEND_DIR, env=env)

    print("\nAll ci-test checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
