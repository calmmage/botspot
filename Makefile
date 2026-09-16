.PHONY: build check clean fix fix-unsafe help publish-pypi publish-test test wizard setup doctor

help:
	@echo "Available targets:"
	@echo "  wizard       - Agent install: print this help, then make setup"
	@echo "  setup        - uv sync, then make doctor (only install path)"
	@echo "  doctor       - Import botspot + import fixtures (prints cli: ok)"
	@echo "  check        - Run all linters and type checks (continues past failures)"
	@echo "  fix          - Auto-fix lint issues and format code"
	@echo "  fix-unsafe   - Auto-fix with unsafe fixes enabled"
	@echo "  test         - Run tests with coverage"
	@echo "  help         - Show this help message"
	@echo "Botspot needs Python 3.12+ and uv on PATH. First setup needs network"
	@echo "and creates .venv here. Checks need no Telegram token; no LaunchAgent."

wizard:
	@$(MAKE) help
	@$(MAKE) setup
	@echo "Done when: \`make doctor\` prints \`cli: ok\`."

setup:
	@command -v uv >/dev/null 2>&1 || { printf '%s\n' 'uv is required on PATH; see https://docs.astral.sh/uv/' >&2; exit 1; }
	uv sync
	@$(MAKE) doctor

doctor:
	UV_OFFLINE=1 uv run --no-sync python -c "import botspot; print('botspot', botspot.__version__)"
	@printf '%s\n' 'cli: ok'
	UV_OFFLINE=1 uv run --no-sync pytest -q tests/test_imports.py
	@printf '%s\n' 'fixtures: ok'

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
	uv run pytest tests/ --cov=botspot --cov-report=term --cov-fail-under=54

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
