from __future__ import annotations

import argparse
import asyncio
import json
import os

from .config import load_settings
from .engine import build_engine
from .evaluator import run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description="DataPilot data analysis agent")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start the web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    serve.add_argument("--reload", action="store_true")
    evaluate = commands.add_parser("eval", help="Run the bundled evaluation dataset")
    evaluate.add_argument("--cases", default="evals/cases.jsonl")
    args = parser.parse_args()

    if args.command == "eval":
        settings = load_settings()
        report = asyncio.run(run_evaluation(settings, build_engine(settings), args.cases))
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return

    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "datapilot.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )


if __name__ == "__main__":
    main()
