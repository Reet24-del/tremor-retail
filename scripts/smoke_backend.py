"""Exercise a running API using only the synthetic bundled store.

python scripts/smoke_backend.py --base-url http://127.0.0.1:8000 --runs 3
Add --require-llm to require genuine live extraction and explanation without fallback.
"""

import argparse
import time

import httpx


def smoke(base_url: str, runs: int, require_llm: bool):
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=60) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        if require_llm and not health.json()["llm_enabled"]:
            raise RuntimeError("Live LLM mode was requested but the server has no enabled provider")
        for index in range(runs):
            started = client.post("/api/runs/demo")
            started.raise_for_status()
            rid = started.json()["run_id"]
            deadline = time.monotonic() + 240
            while True:
                response = client.get(f"/api/runs/{rid}")
                response.raise_for_status()
                status = response.json()
                if status["status"] != "running":
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Demo did not finish within four minutes")
                time.sleep(0.25)
            if status["status"] != "completed":
                raise RuntimeError(f"Demo failed: {status['error']}")
            feed = client.get(f"/api/runs/{rid}/signals").json()
            hero = next(s for s in feed["signals"] if s["entity"]["id"] == "SKU-OIL-1L")
            assert hero["financial_impact"]["amount"] == 1680, hero
            detail = client.get(f"/api/signals/{hero['signal_id']}").json()
            if require_llm:
                assert status["summary"]["extraction_methods"] == ["llm"], "Extraction fell back"
                assert detail["signal"]["model_metadata"]["explanation_source"] == "llm", "Wording fell back"
            assert detail["signal"]["claims"]
            for eid in detail["signal"]["evidence_ids"]:
                ev = client.get(f"/api/evidence/{eid}")
                ev.raise_for_status()
                if ev.json().get("page_image_url"):
                    page = client.get(ev.json()["page_image_url"])
                    page.raise_for_status()
                    assert page.headers["content-type"] == "image/png"
            saved = client.post(
                f"/api/signals/{hero['signal_id']}/reviews",
                json={"outcome": "confirmed", "reason": "Synthetic smoke test: evidence verified"},
            )
            saved.raise_for_status()
            assert client.get(f"/api/signals/{hero['signal_id']}").json()["signal"]["status"] == "confirmed"
            print(f"Run {index + 1}/{runs}: hero INR 1680, evidence pages and saved review verified", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--require-llm", action="store_true")
    args = parser.parse_args()
    smoke(args.base_url, args.runs, args.require_llm)
