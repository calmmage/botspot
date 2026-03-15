.PHONY: help build publish-pypi publish-test clean test

help:
	@echo "Available targets:"
	@echo "  build         - Build the package"
	@echo "  publish-pypi  - Publish to PyPI"
	@echo "  publish-test  - Publish to TestPyPI"
	@echo "  clean         - Clean build artifacts"
	@echo "  test          - Run tests"

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
	uv run pytest
