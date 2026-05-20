.PHONY: setup smoke render batch test lint typecheck doctor clean

setup:
	uv sync
	cd satori-service && pnpm install
	@echo "→ place SourceSerif4-Black.ttf and SourceSerif4-Regular.ttf in satori-service/fonts/"

satori:
	cd satori-service && pnpm dev

smoke:
	uv run nbn render --spec batches/smoke.yaml

batch:
	uv run nbn batch batches/week-1.yaml

test:
	uv run pytest -x -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy --strict src

doctor:
	uv run nbn doctor

clean:
	rm -rf out/ .pytest_cache .mypy_cache .ruff_cache
