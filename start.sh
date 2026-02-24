#!/usr/bin/env bash
# =============================================================================
# HCP Web Crawler — Single End-to-End Startup Script
# Cleans up existing services, initialises the DB, and starts backend + frontend
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Colour

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"
PIDFILE_API="$PROJECT_DIR/.pid_api"
PIDFILE_UI="$PROJECT_DIR/.pid_ui"
LOG_DIR="$PROJECT_DIR/logs"

# =============================================================================
# Helper functions
# =============================================================================

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $1"; }

kill_by_pidfile() {
    local pidfile="$1"
    local label="$2"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(<"$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping $label (PID $pid)…"
            kill "$pid" 2>/dev/null || true
            sleep 1
            kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
            log_ok "$label stopped."
        else
            log_warn "$label PID file exists but process ($pid) is not running."
        fi
        rm -f "$pidfile"
    fi
}

kill_by_port() {
    local port="$1"
    local label="$2"
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        log_info "Killing processes on port $port ($label): $pids"
        echo "$pids" | xargs kill -9 2>/dev/null || true
        log_ok "Port $port cleared."
    fi
}

cleanup() {
    echo ""
    log_info "Shutting down all services…"
    kill_by_pidfile "$PIDFILE_API" "FastAPI backend"
    kill_by_pidfile "$PIDFILE_UI"  "Streamlit frontend"
    kill_by_port "$API_PORT" "API"
    kill_by_port "$UI_PORT"  "UI"
    log_ok "All services stopped. Goodbye!"
    exit 0
}

# =============================================================================
# Main
# =============================================================================

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   Boehringer Ingelheim — HCP Crawler AI Agent        ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

cd "$PROJECT_DIR"

# ── Step 1: Clean up any existing services ───────────────────────────────────
log_info "Step 1/6 — Cleaning up existing services…"
kill_by_pidfile "$PIDFILE_API" "FastAPI backend"
kill_by_pidfile "$PIDFILE_UI"  "Streamlit frontend"
kill_by_port "$API_PORT" "API"
kill_by_port "$UI_PORT"  "UI"
log_ok "Cleanup complete."

# ── Step 2: Check dependencies ───────────────────────────────────────────────
log_info "Step 2/6 — Checking dependencies…"
if ! command -v uv &>/dev/null; then
    log_warn "UV not found. Installing…"
    pip install uv -q
fi

if [[ ! -d "$PROJECT_DIR/.venv" ]]; then
    log_info "Virtual environment not found. Running uv sync…"
    uv sync --all-extras -q
else
    log_ok "Virtual environment exists."
fi

# ── Step 3: Start PostgreSQL via Docker Compose ──────────────────────────────
log_info "Step 3/6 — Starting PostgreSQL database…"
if command -v docker &>/dev/null && [[ -f "$PROJECT_DIR/docker-compose.yml" ]]; then
    docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d 2>&1 | grep -v '^#' || true
    log_info "Waiting for PostgreSQL to be ready…"
    for i in $(seq 1 15); do
        if docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres pg_isready -U postgres &>/dev/null; then
            log_ok "PostgreSQL is ready."
            break
        fi
        sleep 2
        if [[ $i -eq 15 ]]; then
            log_warn "PostgreSQL may not be ready — proceeding anyway. Check docker logs if issues occur."
        fi
    done
else
    log_warn "Docker not found or docker-compose.yml missing — skipping PostgreSQL startup."
    log_warn "Make sure a PostgreSQL instance is running at the DATABASE_URL in .env"
fi

# ── Step 4: Check .env ───────────────────────────────────────────────────────
log_info "Step 4/6 — Checking environment configuration…"
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    if [[ -f "$PROJECT_DIR/.env.example" ]]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        log_warn "Created .env from .env.example — please configure your LLM API keys!"
    else
        log_err ".env file not found and no .env.example to copy. Create one first."
        exit 1
    fi
else
    log_ok ".env file found."
fi

# ── Step 5: Generate sample data ─────────────────────────────────────────────
log_info "Step 5/6 — Generating sample data (real HCP records)…"
uv run python sample_data/create_sample.py
log_ok "Sample data ready at sample_data/sample_hcp.xlsx"

# ── Step 6: Start services ───────────────────────────────────────────────────
log_info "Step 6/6 — Starting services…"
mkdir -p "$LOG_DIR"

# Trap Ctrl+C / SIGTERM to cleanly shut down
trap cleanup SIGINT SIGTERM

# Start FastAPI backend
log_info "Starting FastAPI backend on port $API_PORT…"
uv run uvicorn hcp_crawler.main:app \
    --host 0.0.0.0 \
    --port "$API_PORT" \
    --reload \
    > "$LOG_DIR/api.log" 2>&1 &
echo $! > "$PIDFILE_API"
log_ok "FastAPI backend started (PID $(<"$PIDFILE_API")) — logs: $LOG_DIR/api.log"

# Give the API a moment to initialise
sleep 2

# Start Streamlit frontend
log_info "Starting Streamlit frontend on port $UI_PORT…"
uv run streamlit run frontend/app.py \
    --server.port "$UI_PORT" \
    --server.headless true \
    --server.address 0.0.0.0 \
    > "$LOG_DIR/ui.log" 2>&1 &
echo $! > "$PIDFILE_UI"
log_ok "Streamlit frontend started (PID $(<"$PIDFILE_UI")) — logs: $LOG_DIR/ui.log"

sleep 1

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║             ✅ All services are running!              ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}🌐 Dashboard:${NC}  http://localhost:$UI_PORT"
echo -e "  ${BOLD}⚙️  API Docs:${NC}   http://localhost:$API_PORT/docs"
echo -e "  ${BOLD}❤️  Health:${NC}     http://localhost:$API_PORT/api/v1/health"
echo ""
echo -e "  ${BOLD}📄 Logs:${NC}        $LOG_DIR/api.log"
echo -e "                 $LOG_DIR/ui.log"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all services."
echo ""

# Wait for background processes — keeps script alive for Ctrl+C
wait
