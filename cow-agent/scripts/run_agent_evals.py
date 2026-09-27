"""Run the offline runtime evidence suite and write a JSON report."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import run_runtime_evaluation  # noqa: E402
from app.mcp_evidence import run_mcp_smoke  # noqa: E402
from app.config import agent_home_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "docs" / "evidence" / "agent_runtime_evidence.json"),
        help="JSON output path",
    )
    args = parser.parse_args()
    agent_home = agent_home_path()
    os.chdir(agent_home)
    report = run_runtime_evaluation()
    report["mcp"] = asyncio.run(run_mcp_smoke(agent_home))
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["runtime"] = {
        "project": str(PROJECT_ROOT),
        "agent_home": str(agent_home),
        "offline": True,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"evidence written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
