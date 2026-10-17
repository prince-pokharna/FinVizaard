@echo off
echo ========================================================
echo Starting FinVizaard AI Quantitative Platform
echo ========================================================
start "FinVizaard Backend (FastAPI)" cmd /k "call venv\Scripts\activate && python run.py"
start "FinVizaard Frontend (Vite React)" cmd /k "cd frontend && npm run dev"
echo Both Backend (port 8000) and Frontend (port 5173) launched!
echo Open your browser at http://localhost:5173
