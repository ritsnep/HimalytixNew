#!/usr/bin/env bash
# =============================================================================
# HIMALYTIX ERP - DEVELOPMENT SETUP SCRIPT
# =============================================================================
# Automates the initial setup process for new developers
# Usage: ./setup.sh
# =============================================================================

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║           🏔️  HIMALYTIX ERP - DEVELOPMENT SETUP  🏔️             ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# CHECK PREREQUISITES
# =============================================================================

echo "📋 Checking prerequisites..."
echo ""

# Check Python version
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.11 or 3.12"
    exit 1
fi

PYTHON_VERSION=$(python --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✅ Python version: $PYTHON_VERSION"

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL client not found. Install it for database access."
else
    echo "✅ PostgreSQL client found"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found. Install it to use containerized services."
else
    echo "✅ Docker found"
fi

# Check Git
if ! command -v git &> /dev/null; then
    echo "❌ Git not found. Please install Git."
    exit 1
fi
echo "✅ Git found"

echo ""

# =============================================================================
# CREATE VIRTUAL ENVIRONMENT
# =============================================================================

echo "🐍 Setting up Python virtual environment..."
echo ""

if [ ! -d "venv" ]; then
    python -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

echo "✅ Virtual environment activated"
echo ""

# =============================================================================
# INSTALL DEPENDENCIES
# =============================================================================

echo "📦 Installing dependencies..."
echo ""

pip install --upgrade pip
pip install -r requirements.txt
pip install pre-commit black flake8 isort bandit safety

echo "✅ Dependencies installed"
echo ""

# =============================================================================
# CONFIGURE ENVIRONMENT
# =============================================================================

echo "⚙️  Configuring environment..."
echo ""

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ .env file created from .env.example"
    echo "⚠️  Please edit .env with your configuration"
else
    echo "✅ .env file already exists"
fi

echo ""

# =============================================================================
# INSTALL PRE-COMMIT HOOKS
# =============================================================================

echo "🪝 Installing pre-commit hooks..."
echo ""

pre-commit install
pre-commit install --hook-type commit-msg

echo "✅ Pre-commit hooks installed"
echo ""

# =============================================================================
# SETUP DATABASE
# =============================================================================

echo "🗄️  Setting up database..."
echo ""

read -p "Do you want to run database migrations now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py migrate
    echo "✅ Database migrations complete"
    echo ""
    
    read -p "Create a superuser account? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python manage.py createsuperuser
    fi
fi

echo ""

# =============================================================================
# COMPLETION
# =============================================================================

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║                  ✅  SETUP COMPLETE!  ✅                         ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Next steps:"
echo ""
echo "  1. Review and configure .env file"
echo "  2. Start development server:"
echo "     python manage.py runserver"
echo "     OR"
echo "     make run"
echo ""
echo "  3. Access the application:"
echo "     - Web App: http://localhost:8000"
echo "     - Admin: http://localhost:8000/admin/"
echo "     - API Docs: http://localhost:8000/api/docs/"
echo ""
echo "  4. Run tests:"
echo "     pytest"
echo "     OR"
echo "     make test"
echo ""
echo "  5. View available make commands:"
echo "     make help"
echo ""
echo "📚 Documentation:"
echo "   - README.md - Project overview"
echo "   - CONTRIBUTING.md - Development guidelines"
echo "   - docs/ARCHITECTURE.md - System architecture"
echo ""
echo "Happy coding! 🎉"
echo ""
