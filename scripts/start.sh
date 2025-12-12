#!/bin/bash

# Start Paper2Slides - Main Entry Point
# Starts both backend API and frontend web interface
# For individual services, use start_backend.sh or start_frontend.sh

# Get script directory correctly whether run via bash, sh, or directly
if [ -n "${BASH_SOURCE:-}" ]; then
    SCRIPT_PATH="${BASH_SOURCE[0]}"
else
    SCRIPT_PATH="$0"
fi
SCRIPT_DIR="$( cd "$( dirname "$SCRIPT_PATH" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check if we are in the correct directory
if [ ! -d "api" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Cannot find project directories (api/ or frontend/)"
    echo "   Detected Project Root: $PROJECT_ROOT"
    echo "   Please run this script from the project root or via scripts/start.sh"
    exit 1
fi

echo "=========================================="
echo "Starting Paper2Slides Services"
echo "=========================================="
echo ""

# Check for required dependencies
check_dependencies() {
    local missing=0
    
    if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
        echo "❌ Error: Python not found (python or python3)"
        echo "   Please install Python: https://www.python.org/downloads/"
        missing=1
    fi

    if ! command -v npm >/dev/null 2>&1; then
        echo "❌ Error: npm not found"
        echo "   Please install Node.js (includes npm): https://nodejs.org/"
        echo "   Or install via package manager: apt install npm / brew install node"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        echo ""
        echo "Unable to start services. Please install missing dependencies."
        exit 1
    fi
}

# Run checks
check_dependencies

# Find available port starting from 8001
find_available_port() {
    local port=$1
    while lsof -i :$port > /dev/null 2>&1; do
        echo "⚠️  Port $port is in use, trying next port..." >&2
        port=$((port + 1))
        if [ $port -gt 8010 ]; then
            echo "❌ No available ports found between 8001-8010" >&2
            echo "" >&2
            echo "Ports in use:" >&2
            lsof -i :8001-8010 2>/dev/null | grep LISTEN >&2 || echo "  (Unable to list ports)" >&2
            echo "" >&2
            echo "Options:" >&2
            echo "  1. Stop conflicting services" >&2
            echo "  2. Use a custom port: ./scripts/start_backend.sh [port]" >&2
            exit 1
        fi
    done
    echo $port
}

BACKEND_PORT=$(find_available_port 8001)

echo "✓ Backend: http://localhost:$BACKEND_PORT"
echo "✓ Frontend will start on: http://localhost:5173 (may use next available port)"
echo ""
echo "📝 Note: Frontend proxies to backend at localhost:$BACKEND_PORT"
echo "   If backend port changed, restart frontend or update vite.config.js"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Start backend with retry logic
LOG_FILE="$PROJECT_ROOT/logs/backend.log"
mkdir -p "$PROJECT_ROOT/logs"
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "Starting backend on port $BACKEND_PORT (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."
    
    cd "$PROJECT_ROOT/api"
    python server.py $BACKEND_PORT > "$LOG_FILE" 2>&1 &
    BACKEND_PID=$!
    cd "$PROJECT_ROOT"
    
    # Wait for startup
    sleep 3
    
    # Check if process is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "⚠️  Backend process died, checking logs..."
        
        # Check if it's a port binding error
        if grep -q "address already in use" "$LOG_FILE"; then
            echo "⚠️  Port $BACKEND_PORT was taken during startup"
            RETRY_COUNT=$((RETRY_COUNT + 1))
            BACKEND_PORT=$((BACKEND_PORT + 1))
            
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Retrying with port $BACKEND_PORT..."
                sleep 1
                continue
            fi
        fi
        
        echo "❌ Backend failed to start. Check $LOG_FILE"
        echo ""
        echo "Last 10 lines of log:"
        tail -10 "$LOG_FILE"
        exit 1
    fi
    
    # Check if port is actually listening
    sleep 1
    if lsof -i :$BACKEND_PORT > /dev/null 2>&1; then
        echo "✓ Backend started successfully (PID: $BACKEND_PID)"
        echo "✓ Listening on port: $BACKEND_PORT"
        break
    else
        echo "⚠️  Backend started but not listening on port $BACKEND_PORT"
        kill $BACKEND_PID 2>/dev/null
        RETRY_COUNT=$((RETRY_COUNT + 1))
        BACKEND_PORT=$((BACKEND_PORT + 1))
        
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Retrying with port $BACKEND_PORT..."
            continue
        fi
        
        echo "❌ Failed to start backend after $MAX_RETRIES attempts"
        exit 1
    fi
done

echo ""

# Start frontend
echo "Starting frontend..."
cd "$PROJECT_ROOT/frontend"

# Check if node_modules exists, install dependencies if missing
if [ ! -d "node_modules" ]; then
    echo "📦 Dependencies not found. Installing..."
    npm install
fi

npm run dev

# Cleanup on exit
trap "echo ''; echo 'Stopping services...'; kill $BACKEND_PID 2>/dev/null; exit" INT TERM

