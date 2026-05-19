# 🏠 AI Home Automation - QUICK REFERENCE

## 📦 Installation Quick Start

### Step 1: Install Python Dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Install Node Dependencies
```bash
cd frontend
npm install
```

### Step 3: Setup Database
```bash
# Using provided setup scripts (recommended):
# Windows: scripts/setup.bat
# Linux/Mac: bash scripts/setup.sh

# Or manually:
psql -U postgres -d home_automation -f database/schema.sql
```

---

## 🚀 Run Services

### Option A: Automated (Recommended)
```bash
# Windows
scripts\run.bat

# Linux/Mac
bash scripts/run.sh
```

### Option B: Manual

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

---

## 🌐 Access Points

| Component | URL | Purpose |
|-----------|-----|---------|
| Dashboard | http://localhost:3000 | Main UI |
| API Docs | http://localhost:8000/docs | Interactive API |
| ReDoc | http://localhost:8000/redoc | Alternative API docs |
| Health | http://localhost:8000/health | Backend status |

---

## 🧪 Verify Installation

```bash
python test_system.py
```

Output should show:
- ✅ Database connection successful
- ✅ ML Model loaded
- ✅ Agent executed successfully
- ✅ Learning system initialized

---

## 🔧 Configuration Files

### Backend `.env`
```env
DB_HOST=localhost
DB_NAME=home_automation
DB_USER=postgres
DB_PASSWORD=your_password
API_HOST=0.0.0.0
API_PORT=8000
MODEL_PATH=../model.pkl
RETRAIN_INTERVAL_DAYS=7
```

### Frontend `.env`
```env
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000/ws
```

---

## 📊 Key API Endpoints

### Devices
- `GET /api/devices/status` - All devices
- `POST /api/device/control` - Turn device on/off

### Predictions
- `POST /api/predictions` - Get AI predictions
- `GET /api/model/performance` - Model accuracy

### Analytics
- `GET /api/analytics` - System stats
- `GET /api/system/status` - Health check

### Model
- `POST /api/model/retrain` - Force retraining

[Full API docs at http://localhost:8000/docs]

---

## 🧠 AI Agent Nodes

```
Device Input → History Node → Predict Node → Rule Engine
                                                   ↓
                                            Override Node
                                                   ↓
                                          Decision Engine
                                                   ↓
                                            Control Node
                                                   ↓
                                            Logging Node
                                                   ↓
                                            Device Output
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI server |
| `ml_agent/agent.py` | AI agent logic |
| `frontend/src/App.jsx` | React dashboard |
| `database/schema.sql` | DB schema |
| `database/db_manager.py` | DB operations |
| `model.pkl` | Trained ML model |

---

## 🐛 Troubleshooting

**Port already in use?**
```bash
# Kill process on port
lsof -ti:8000 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend
```

**Database error?**
```bash
# Verify PostgreSQL running
psql -U postgres -c "SELECT version();"

# Check database exists
psql -U postgres -l | grep home_automation
```

**Model not found?**
```bash
# Train first
jupyter notebook 2024_dataset_training_model.ipynb
```

**Can't connect?**
```bash
# Check backend running
curl http://localhost:8000/health

# Check frontend serving
curl http://localhost:3000
```

---

## 📚 Documentation

- **README.md** - Project overview
- **SETUP_GUIDE.md** - Detailed instructions
- **PROJECT_SUMMARY.md** - What's been built
- **Code comments** - Inline documentation

---

## 🎯 What to Try First

1. **Check dashboard**: http://localhost:3000
2. **Look at device cards**: Should show AC, Fan, Light, TV, Fridge
3. **Toggle temperature**: Use slider to adjust
4. **Click "Get AI Predictions"**: See ML predictions
5. **Click "Turn ON/OFF"**: Test device control
6. **View analytics**: See usage charts
7. **Check API docs**: http://localhost:8000/docs

---

## 🚀 Deployment Ready

The system is ready for:
- ✅ Local development
- ✅ Docker containerization
- ✅ Cloud deployment (AWS, Azure, GCP)
- ✅ Kubernetes orchestration
- ✅ Real hardware integration

---

## 📞 Need Help?

1. Check **SETUP_GUIDE.md** (detailed troubleshooting)
2. Review code comments in relevant files
3. Check **API docs** at `/docs`
4. Look at **PROJECT_SUMMARY.md**
5. Run **test_system.py** to diagnose issues

---

**🎉 System is ready! Start with: `npm start` (frontend) and `python main.py` (backend)**

Good luck with your FYP! 🚀
