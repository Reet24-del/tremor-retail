.PHONY: setup data api web test lint eval stress check

setup:            ## install backend and frontend dependencies
	cd services/api && pip install -r requirements.txt -r requirements-dev.txt
	cd apps/web && npm install

data:             ## regenerate the frozen demo fixture (deterministic)
	cd scripts && python generate_demo_data.py && python generate_demo_invoices.py

api:              ## run the API on :8000
	cd services/api && uvicorn app.main:app --reload --port 8000

web:              ## run the web app on :3000
	cd apps/web && npm run dev

test:             ## backend unit + integration tests
	cd services/api && pytest -q

lint:             ## lint and type-check everything
	cd services/api && ruff check . && ruff format --check .
	ruff check scripts --config services/api/ruff.toml
	cd apps/web && npm run lint && npx tsc --noEmit

eval:             ## frozen evaluation against PRD targets
	python scripts/run_evaluation.py

stress:           ## unchanged pipeline on 50 unseen random stores -> docs/stress-test.md
	python scripts/stress_test.py --stores 50 --seed-start 2000

check: lint test eval   ## everything CI runs

contracts:       ## regenerate shared TypeScript and OpenAPI contracts
	python scripts/export_contracts.py
