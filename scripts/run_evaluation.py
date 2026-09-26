"""Run the frozen evaluation from the command line: python scripts/run_evaluation.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from app.pipeline.evaluate import run_evaluation  # noqa: E402

rep = run_evaluation()
for k, v in rep["metrics"].items():
    print(f"{k:34s} {v.get('count', v['value'])!s:>12}   target {v.get('target', '-')}")
print("\nPASSED" if rep["passed"] else "\nFAILED")
Path("runtime").mkdir(exist_ok=True)
Path("runtime/evaluation_report.json").write_text(json.dumps(rep, indent=2))
sys.exit(0 if rep["passed"] else 1)
