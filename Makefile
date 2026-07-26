.DEFAULT_GOAL := all

.PHONY: .uv
.uv:
	@uv --version || echo 'Please install uv: https://docs.astral.sh/uv/getting-started/installation/'

.PHONY: install
install: .uv
	uv sync --frozen --group dev --group lint --extra cli

.PHONY: sync
sync: .uv
	uv sync --group dev --group lint --extra cli

.PHONY: format
format:
	uv run ruff format
	uv run ruff check --fix --fix-only

.PHONY: lint
lint:
	uv run ruff format --check
	uv run ruff check

.PHONY: typecheck
typecheck:
	uv run pyright

.PHONY: test
test:
	uv run coverage run -m pytest
	@uv run coverage report

.PHONY: testcov
testcov: test
	@uv run coverage html

.PHONY: build
build:
	uv build

.PHONY: all
all: format lint typecheck testcov
