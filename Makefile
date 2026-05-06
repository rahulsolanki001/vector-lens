.PHONY: dev build build-ui install install-dev test test-unit test-integration test-all lint fmt typecheck typecheck-ui build-ui-check check check-all clean help

PYTHON := python3
PIP    := pip
VARA   := vara

##@ Development

dev: ## Start Python server (--reload) + Vite dev server in parallel
	@echo "Starting Vara dev servers..."
	@$(PYTHON) -m vara.cli dev

build-ui: ## Build the React UI and copy assets into vara/server/static/
	@echo "Building React UI..."
	cd ui && npm run build
	@echo "Copying dist to vara/server/static/..."
	rm -rf vara/server/static/*
	cp -r ui/dist/* vara/server/static/
	@echo "UI build complete."

build: build-ui ## Full production build (UI + Python wheel)
	@echo "Building Python wheel..."
	$(PYTHON) -m build --no-isolation
	@echo "Build complete. Artifacts in dist/"

##@ Installation

install: ## Install vara with all adapters (editable)
	$(PIP) install -e ".[all]"

install-dev: ## Install vara with dev dependencies (editable)
	$(PIP) install -e ".[all,dev]"
	cd ui && npm install

##@ Testing

test: test-unit ## Run all fast tests (alias for test-unit)

test-unit: ## Run unit tests (no external dependencies)
	pytest -m unit -v

test-integration: ## Run integration tests (requires Docker — spins up DBs)
	docker compose -f docker-compose.dev.yml up -d --wait
	pytest -m integration -v; \
	EXIT=$$?; \
	docker compose -f docker-compose.dev.yml down; \
	exit $$EXIT

test-all: ## Run every test (unit + integration)
	docker compose -f docker-compose.dev.yml up -d --wait
	pytest -v; \
	EXIT=$$?; \
	docker compose -f docker-compose.dev.yml down; \
	exit $$EXIT

##@ Code quality

lint: ## Run ruff linter
	ruff check vara/ tests/

fmt: ## Auto-format with ruff
	ruff format vara/ tests/
	ruff check --fix vara/ tests/

typecheck: ## Run mypy type checker
	mypy vara/

typecheck-ui: ## Run TypeScript type check on the React frontend
	cd ui && npm run type-check

build-ui-check: ## Build the React frontend without copying bundled assets
	cd ui && npm run build

check: lint typecheck ## Run all Python checks (lint + types)

check-all: check typecheck-ui build-ui-check ## Run all checks (Python + UI type/build)

##@ Cleanup

clean: ## Remove build artifacts, caches
	rm -rf dist/ build/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf vara/server/static/*
	touch vara/server/static/.gitkeep
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete

##@ Help

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } \
	/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help
