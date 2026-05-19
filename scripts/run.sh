#!/bin/bash
# ============================================
# AI HOME AUTOMATION - RUN ALL SERVICES
# ============================================

echo "🚀 Starting AI Home Automation System"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Check ports
echo "🔍 Checking ports..."
if check_port 8000; then
    echo -e "${YELLOW}⚠️  Port 8000 is in use (Backend)${NC}"
    read -p "Kill process on port 8000? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:8000 | xargs kill -9
        echo "Process killed"
    fi
fi

if check_port 3000; then
    echo -e "${YELLOW}⚠️  Port 3000 is in use (Frontend)${NC}"
    read -p "Kill process on port 3000? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:3000 | xargs kill -9
        echo "Process killed"
    fi
fi

echo ""
echo "Starting services..."
echo ""

# Start Backend
echo -e "${GREEN}Starting Backend (Port 8000)...${NC}"
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
sleep 3

# Start Frontend
echo -e "${GREEN}Starting Frontend (Port 3000)...${NC}"
cd ../frontend
npm start &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
sleep 3

echo ""
echo -e "${GREEN}======================================"
echo "✅ All services started successfully!"
echo "=====================================${NC}"
echo ""
echo "Dashboard: http://localhost:3000"
echo "API Docs:  http://localhost:8000/docs"
echo ""
echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

echo ""
echo -e "${YELLOW}Services stopped${NC}"
