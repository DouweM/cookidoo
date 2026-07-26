.DEFAULT_GOAL := all

.PHONY: install
install:
	uv sync --group dev

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
	uv run pytest -q

.PHONY: build
build:
	uv build

.PHONY: all
all: format lint typecheck test
