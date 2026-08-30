.PHONY: setup build run agent-phone agent-webrtc agent-chat test deck

setup:
	uv sync --dev
	npm install --legacy-peer-deps

build:
	npm run build

run: build
	uv run uvicorn beacon_call.api:app --host 127.0.0.1 --port 8080

agent-phone:
	guava run . -- --phone

agent-webrtc:
	guava run . -- --webrtc

agent-chat:
	guava run . -- --chat

test:
	uv run ruff check .
	uv run pytest
	npm test
	npm run typecheck
	npm run build

deck:
	npm run deck
