.PHONY: setup build run agent-dev agent-console call-test test

setup:
	uv sync --dev
	npm install --legacy-peer-deps

build:
	npm run build

run: build
	uv run uvicorn beacon_call.api:app --host 127.0.0.1 --port 8080

agent-dev:
	uv run python main.py dev

agent-console:
	uv run python main.py console

call-test:
	uv run python scripts/trigger_call.py --arm-live-call

test:
	uv run ruff check .
	uv run pytest
	npm test
	npm run typecheck
	npm run build
