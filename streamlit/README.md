# MathLABS Streamlit Dashboard

## 🚀 Quick Setup (3 Steps)

### 1. Install Dependencies
```bash
pip install -r requirements_dashboard.txt
```

### 2. Create `.env` File
Create a `.env` file with your MongoDB connection:
```
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/mathlabs?appName=MathLabs
```

### 3. Run Dashboard
```bash
streamlit run streamlit_app.py
```

Open: http://localhost:8501

## 📁 What's Included

- `streamlit_app.py` - Main dashboard
- `pages/` - Dashboard pages (Multi-Question & Single Question Analysis)
- `requirements_dashboard.txt` - Python dependencies

## 🎯 What It Does

- Connects to MongoDB and loads evaluation data
- Shows multi-question analysis with charts and statistics
- Provides single question deep dive with full evaluation details
- Interactive filters to select specific evaluation runs

## 📋 Requirements

- Python 3.9+
- MongoDB connection string
- Packages from `requirements_dashboard.txt`

## ❓ Troubleshooting

**"Module not found"** → `pip install <package_name>`

**"Can't connect to MongoDB"** → Check `.env` file has correct `MONGO_URI`

**Dashboard won't start** → Try: `streamlit run streamlit_app.py --server.port 8502`

---

That's it! Just install, configure `.env`, and run! 🎉

