#!/bin/bash
# ============================================
# AI HOME AUTOMATION - COMPLETE SETUP SCRIPT
# ============================================

set -e  # Exit on error

echo "🚀 AI Home Automation System Setup"
echo "===================================="
echo ""

# Check prerequisites
echo "✓ Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 16+"
    exit 1
fi

echo "✅ All prerequisites found"
echo ""

# Database info
echo "📦 Database: SQLite (no setup needed)"
echo "   The database file home_automation.db is created automatically."
echo ""

# Setup Backend
echo "🔧 Setting up Backend..."

cd backend

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python packages..."
pip install -r requirements.txt

# Update .env file
echo "Configuring .env..."
cat > .env << EOF
# Database (SQLite — file-based, no server needed)
DB_PATH=../home_automation.db

# API
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Model
MODEL_PATH=../home_automation_model.pkl
RETRAIN_INTERVAL_DAYS=7
EOF

echo "✅ Backend setup complete"
echo ""

# Setup Frontend
cd ../frontend

echo "🎨 Setting up Frontend..."
echo "Installing Node packages..."
npm install

echo "✅ Frontend setup complete"
echo ""

# Return to root
cd ../

# Summary
echo "===================================="
echo "✅ SETUP COMPLETE!"
echo "===================================="
echo ""
echo "Next steps:"
echo "1. Train ML model (if not done):"
echo "   jupyter notebook 2024_dataset_training_model.ipynb"
echo ""
echo "2. Start backend (Terminal 1):"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "3. Start frontend (Terminal 2):"
echo "   cd frontend"
echo "   npm start"
echo ""
echo "4. Open dashboard:"
echo "   http://localhost:3000"
echo ""
echo "API Documentation: http://localhost:8000/docs"
echo ""
