#!/usr/bin/env bash
# ==============================================================================
# 🚀 Nexora — Application Startup Script
# ==============================================================================
# Usage:
#   ./run.sh            Start local FastAPI backend + React UI (with Docker db services)
#   ./run.sh --docker   Run full application stack entirely inside Docker containers
#   ./run.sh --dev      Run FastAPI backend + Vite React dev server simultaneously
#   ./run.sh --stop     Stop all running Nexora Docker containers
#   ./run.sh --status   Check status of backend, database, and vector store
#   ./run.sh --help     Display this help message
# ==============================================================================

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Color Codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "======================================================================"
    echo "      🚀 Nexora — Hybrid RAG & Multi-Tool Agentic Platform"
    echo "======================================================================"
    echo -e "${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_env() {
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            print_warning ".env file not found. Creating from .env.example..."
            cp .env.example .env
            print_warning "Please update .env with your GROQ_API_KEY and COHERE_API_KEY."
        else
            print_error "Neither .env nor .env.example was found!"
        fi
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH."
        echo "Please install Docker to run PostgreSQL (pgvector) and Qdrant."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker and retry."
        exit 1
    fi
}

start_db_services() {
    print_info "Ensuring PostgreSQL (PGVector) and Qdrant containers are running..."
    docker compose up -d postgres qdrant

    print_info "Waiting for database services to become healthy..."
    local attempts=0
    local max_attempts=20
    while [ $attempts -lt $max_attempts ]; do
        local pg_status=$(docker inspect --format='{{json .State.Health.Status}}' nexora-postgres 2>/dev/null || echo '"unknown"')
        local qd_status=$(docker inspect --format='{{json .State.Health.Status}}' nexora-qdrant 2>/dev/null || echo '"unknown"')

        if [[ "$pg_status" == "\"healthy\"" ]] && [[ "$qd_status" == "\"healthy\"" ]]; then
            print_success "PostgreSQL (5433) and Qdrant (6333) are healthy and ready."
            return 0
        fi

        attempts=$((attempts + 1))
        sleep 1
    done

    print_warning "Services took longer than expected to report healthy, continuing anyway..."
}

find_python() {
    if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo "$SCRIPT_DIR/.venv/bin/python"
    elif [ -f "$SCRIPT_DIR/.venv/Scripts/python.exe" ]; then
        echo "$SCRIPT_DIR/.venv/Scripts/python.exe"
    elif command -v python3 &> /dev/null; then
        echo "$(command -v python3)"
    elif command -v python &> /dev/null; then
        echo "$(command -v python)"
    else
        print_error "No Python interpreter found. Please install Python 3.10+."
        exit 1
    fi
}

ensure_venv() {
    if [ ! -d ".venv" ]; then
        print_info "Virtual environment not detected. Creating .venv..."
        if command -v uv &> /dev/null; then
            uv venv .venv
        else
            python3 -m venv .venv
        fi
        print_info "Installing dependencies from requirements.txt..."
        if command -v uv &> /dev/null; then
            uv pip install -r requirements.txt
        else
            "$SCRIPT_DIR/.venv/bin/pip" install -r requirements.txt
        fi
        print_success "Virtual environment initialized."
    fi
}

stop_containers() {
    print_banner
    print_info "Stopping all Nexora Docker containers..."
    docker compose down
    print_success "All Nexora services stopped."
}

check_status() {
    print_banner
    echo -e "${BOLD}--- Container Status ---${NC}"
    docker compose ps
    echo ""
    echo -e "${BOLD}--- Port Status ---${NC}"
    for port in 8000 5433 6333; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 || nc -z localhost $port 2>/dev/null; then
            echo -e "Port $port: ${GREEN}LISTENING${NC}"
        else
            echo -e "Port $port: ${RED}NOT RUNNING${NC}"
        fi
    done
}

run_docker_mode() {
    print_banner
    check_docker
    check_env
    print_info "Starting full Nexora stack via Docker Compose..."
    echo -e "${CYAN}Services will be available at:${NC}"
    echo "  - Web UI & API:  http://localhost:8000"
    echo "  - API Swagger:   http://localhost:8000/docs"
    echo "  - Qdrant UI:     http://localhost:6333/dashboard"
    echo "  - PGVector:      localhost:5433"
    echo ""
    docker compose up --build
}

run_dev_mode() {
    print_banner
    check_docker
    check_env
    start_db_services
    ensure_venv

    local PYTHON_BIN
    PYTHON_BIN=$(find_python)

    print_info "Starting in Dual-Dev mode (FastAPI Backend + Vite Frontend)..."

    # Trap Ctrl+C to kill both background processes
    trap 'kill $(jobs -p) 2>/dev/null' EXIT

    export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH:-}"

    print_info "Starting FastAPI Backend on http://localhost:8000..."
    "$PYTHON_BIN" -m uvicorn nexora.api.server:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!

    if [ -d "ui" ] && [ -f "ui/package.json" ]; then
        print_info "Starting Vite React Frontend Dev Server on http://localhost:5173..."
        (cd ui && npm run dev) &
        FRONTEND_PID=$!
    fi

    wait
}

run_local_mode() {
    print_banner
    check_docker
    check_env
    start_db_services
    ensure_venv

    local PYTHON_BIN
    PYTHON_BIN=$(find_python)

    print_info "Using Python: $PYTHON_BIN"
    print_info "Starting Nexora FastAPI Backend & Integrated React SPA..."
    echo ""
    echo -e "${GREEN}${BOLD}======================================================${NC}"
    echo -e "  🌐 ${BOLD}Application Web UI:${NC}    ${CYAN}http://localhost:8000/${NC}"
    echo -e "  📚 ${BOLD}Interactive API Docs:${NC}  ${CYAN}http://localhost:8000/docs${NC}"
    echo -e "  ⚡ ${BOLD}Qdrant Dashboard:${NC}      ${CYAN}http://localhost:6333/dashboard${NC}"
    echo -e "${GREEN}${BOLD}======================================================${NC}"
    echo ""

    export PYTHONPATH="$SCRIPT_DIR/src:${PYTHONPATH:-}"
    exec "$PYTHON_BIN" main.py
}

# ------------------------------------------------------------------------------
# Command Routing
# ------------------------------------------------------------------------------
case "${1:-}" in
    --docker|docker)
        run_docker_mode
        ;;
    --dev|dev)
        run_dev_mode
        ;;
    --stop|stop|down)
        stop_containers
        ;;
    --status|status)
        check_status
        ;;
    --help|-h|help)
        print_banner
        echo "Usage: ./run.sh [OPTION]"
        echo ""
        echo "Options:"
        echo "  (none), local     Start backend + pre-built React UI locally (Default)"
        echo "  --docker, docker  Build & run everything inside Docker containers"
        echo "  --dev, dev        Run FastAPI backend + Vite React dev server in parallel"
        echo "  --stop, stop      Stop all running Nexora Docker containers"
        echo "  --status, status  Check status of containers and service ports"
        echo "  --help, -h        Show this help message"
        echo ""
        ;;
    *)
        run_local_mode
        ;;
esac
