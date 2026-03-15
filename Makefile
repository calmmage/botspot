.PHONY: build check clean fix fix-unsafe help publish-pypi publish-test test

help:
	@echo "Available targets:"
	@echo "  check        - Run all linters and type checks (continues past failures)"
	@echo "  fix          - Auto-fix lint issues and format code"
	@echo "  fix-unsafe   - Auto-fix with unsafe fixes enabled"
	@echo "  test         - Run tests with coverage"
	@echo "  help         - Show this help message"

build:
	uv build

publish-pypi: clean build
	uv publish

publish-test: clean build
	uv publish --publish-url https://test.pypi.org/legacy/

clean:
	rm -rf dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

test:
	uv run pytest tests/ --cov=botspot --cov-report=term --cov-fail-under=50

check:
	-uv run ruff check botspot
	-uv run ruff format --check botspot
	-uv run vulture --min-confidence 80 botspot
	-uv run pyright botspot

fix:
	-uv run ruff check --fix .
	uv run ruff format .

fix-unsafe:
	-uv run ruff check --fix --unsafe-fixes .
	uv run ruff format .
