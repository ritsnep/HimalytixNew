# =============================================================================
# MAKEFILE FOR HIMALYTIX ERP
# =============================================================================
# Common development tasks automation
# Usage: make <target>
# =============================================================================

.PHONY: help install test coverage lint format clean docker-up docker-down migrate shell

# Default target - show help
help:
	@echo "Himalytix ERP - Available Commands"
	@echo "==================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          Install all dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo "  make setup-hooks      Install pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-smoke       Run smoke tests only"
	@echo "  make coverage         Run tests with coverage report"
	@echo "  make coverage-html    Generate HTML coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run all linters (flake8, black --check)"
	@echo "  make format           Auto-format code (black, isort)"
	@echo "  make security         Run security checks (bandit, safety)"
	@echo ""
	@echo "Database:"
	@echo "  make migrate          Run database migrations"
	@echo "  make migrations       Create new migrations"
	@echo "  make migrate-check    Check for pending migrations"
	@echo "  make db-reset         Reset database (DANGER!)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        Start all containers"
	@echo "  make docker-down      Stop all containers"
	@echo "  make docker-logs      View container logs"
	@echo "  make docker-clean     Remove all containers and volumes"
	@echo ""
	@echo "Development:"
	@echo "  make run              Start development server"
	@echo "  make shell            Open Django shell"
	@echo "  make superuser        Create superuser"
	@echo "  make collectstatic    Collect static files"
	@echo ""
	@echo "Load Testing:"
	@echo "  make locust           Run Locust Web UI (uses HOST)"
	@echo "  make locust-headless  Run Locust headless (uses HOST, USERS, RATE, TIME, OUT)"
	@echo "    Defaults: HOST=http://localhost:8000 USERS=200 RATE=20 TIME=10m OUT=results/himalytix"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Remove Python cache files"
	@echo "  make backup           Backup database"
	@echo "  make update-deps      Update all dependencies"

# =============================================================================
# SETUP & INSTALLATION
# =============================================================================

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

install-dev:
	@echo "Installing development dependencies..."
	pip install -r requirements.txt
	pip install pre-commit black flake8 isort bandit safety

setup-hooks:
	@echo "Installing pre-commit hooks..."
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "Pre-commit hooks installed successfully!"

# =============================================================================
# TESTING
# =============================================================================

test:
	@echo "Running all tests..."
	pytest -v

test-unit:
	@echo "Running unit tests..."
	pytest -v -m unit

test-integration:
	@echo "Running integration tests..."
	pytest -v -m integration

test-smoke:
	@echo "Running smoke tests..."
	pytest -v -m smoke

coverage:
	@echo "Running tests with coverage..."
	pytest -v --cov=. --cov-report=term-missing --cov-fail-under=80

coverage-html:
	@echo "Generating HTML coverage report..."
	pytest -v --cov=. --cov-report=html
	@echo "Coverage report generated at htmlcov/index.html"
	start htmlcov/index.html

# =============================================================================
# CODE QUALITY
# =============================================================================

lint:
	@echo "Running linters..."
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	black --check .

format:
	@echo "Formatting code..."
	black .
	isort .
	@echo "Code formatted successfully!"

security:
	@echo "Running security checks..."
	bandit -r . -ll
	safety check

# =============================================================================
# DATABASE
# =============================================================================

migrate:
	@echo "Running database migrations..."
	python manage.py migrate

migrations:
	@echo "Creating new migrations..."
	python manage.py makemigrations

migrate-check:
	@echo "Checking for pending migrations..."
	python manage.py showmigrations | grep -E '\[ \]' || echo "All migrations applied!"

db-reset:
	@echo "WARNING: This will delete all data!"
	@echo "Press Ctrl+C to cancel, or press Enter to continue..."
	@read
	python manage.py flush --noinput
	python manage.py migrate
	@echo "Database reset complete!"

# =============================================================================
# DOCKER
# =============================================================================

docker-up:
	@echo "Starting Docker containers..."
	docker-compose up -d
	@echo "Containers started! Access services:"
	@echo "  - Web App: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/api/docs/"
	@echo "  - Jaeger UI: http://localhost:16686"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"

docker-down:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs:
	@echo "Viewing container logs (Ctrl+C to exit)..."
	docker-compose logs -f

docker-clean:
	@echo "Removing all containers and volumes..."
	docker-compose down -v
	docker system prune -f

# =============================================================================
# DEVELOPMENT
# =============================================================================

run:
	@echo "Starting development server..."
	python manage.py runserver

shell:
	@echo "Opening Django shell..."
	python manage.py shell

superuser:
	@echo "Creating superuser..."
	python manage.py createsuperuser

collectstatic:
	@echo "Collecting static files..."
	python manage.py collectstatic --noinput

# =============================================================================
# MAINTENANCE
# =============================================================================

clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/
	rm -f .coverage
	rm -f coverage.xml
	@echo "Cleanup complete!"

backup:
	@echo "Creating database backup..."
	bash scripts/backup_database.sh

update-deps:
	@echo "Updating dependencies..."
	pip install --upgrade pip
	pip install --upgrade -r requirements.txt
	@echo "Dependencies updated!"

# =============================================================================
# CI/CD
# =============================================================================

ci:
	@echo "Running CI pipeline locally..."
	make lint
	make security
	make test
	make coverage
	@echo "CI checks passed!"

# =============================================================================
# QUICK START
# =============================================================================

quickstart: install setup-hooks migrate superuser
	@echo ""
	@echo "🎉 Himalytix ERP setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and configure"
	@echo "  2. Run 'make run' to start the development server"
	@echo "  3. Visit http://localhost:8000"
	@echo ""

# =============================================================================
# LOAD TESTING (Locust)
# =============================================================================

.PHONY: locust locust-headless

# Defaults (can be overridden: make locust-headless HOST=http://... USERS=500 RATE=50 TIME=15m OUT=results/run1)
HOST ?= http://localhost:8000
USERS ?= 200
RATE ?= 20
TIME ?= 10m
OUT ?= results/himalytix

locust:
	@echo "Starting Locust Web UI against $(HOST)..."
	locust -f load_tests/locustfile.py --host $(HOST)

locust-headless:
	@echo "Running Locust headless: users=$(USERS) rate=$(RATE)/s time=$(TIME) host=$(HOST)"
	@if [ ! -d results ]; then mkdir -p results; fi
	locust -f load_tests/locustfile.py --host $(HOST) -u $(USERS) -r $(RATE) -t $(TIME) --csv $(OUT)
	@echo "Results saved with prefix: $(OUT)"
