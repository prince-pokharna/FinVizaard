# FinVizaard 3.0 | Institutional AI Quantitative Platform & Real-Time Engine

FinVizaard is an end-to-end AI-powered financial technology platform delivering predictive market insights, real-time tick streaming, market regime detection, strategy backtesting, multi-ticker comparisons, portfolio optimization, and local model explainability for equities.

By integrating Machine Learning regression (**XGBoost**), probabilistic sequence modeling (**Gaussian Hidden Markov Models**), **SHAP** (SHapley Additive exPlanations), **Modern Portfolio Theory (Markowitz Efficient Frontier & Tail Risk VaR/CVaR)**, and **Generative AI** (OpenAI GPT & Anthropic Claude with local NLP fallback), FinVizaard equips traders, analysts, and portfolio managers with transparent, interpretable forecasts backed by real data.

---

## 🚀 Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | React 18, Vite, CSS3 | Ultra-fast, responsive institutional dark-mode terminal. |
| **Interactive Charts** | TradingView Lightweight Charts | Canvas-based financial charts for candlesticks, volume histograms, and target price overlays. |
| **Real-Time Streaming** | WebSockets (FastAPI / Native WS) | Live real-time tick stream with bid/ask spreads, volume ticks, and dynamic candle updates. |
| **Backend** | Python 3.10–3.13, FastAPI, Uvicorn | Asynchronous REST API and WebSocket routing data pipelines, ML models, and LLM requests. |
| **Analytical Database**| DuckDB | Embedded columnar database for high-throughput OHLCV data, sentiment caching, and macro metrics. |
| **Predictive Modeling** | XGBoost Regressor | Next-day equity closing price forecasting with residual confidence bounds. |
| **Regime Detection** | HMMlearn (GaussianHMM) | Unsupervised market clustering into Bullish, Sideways, and Bearish regimes with transition probabilities. |
| **Portfolio & Risk** | SciPy SLSQP & NumPy | Markowitz Efficient Frontier optimization, Max Sharpe, Min Volatility, and Parametric / Historical VaR & CVaR. |
| **Explainability** | SHAP (TreeExplainer) | Exact Shapley value attributions rendered in interactive Bar and Waterfall charts. |
| **Generative AI** | OpenAI & Anthropic Claude | Multi-provider AI synthesis generating structured institutional 3-sentence equity research narratives. |
| **Sentiment Analysis** | NewsAPI + FinVizaard NLP | Live financial news headlines scored on a [-1.0, +1.0] scale with direct article links and top catalysts. |
| **Containerization** | Docker & Docker Compose | Multi-stage Docker builds with Nginx reverse proxy for production-ready deployment. |

---

## 📁 Project Structure

```text
FinVizaard/
├── Backend/
│   └── src/
│       ├── __init__.py
│       ├── main.py                  # FastAPI Application, REST Endpoints, & WebSocket Stream
│       ├── database.py              # DuckDB database schema, connections, and deduplication
│       ├── data_ingestion.py        # yfinance price downloader & synthetic fallback generator
│       ├── features.py              # Technical & macroeconomic feature engineering with VIX cache
│       ├── hmm_model.py             # Gaussian HMM for regime detection, transition matrix, & timeline
│       ├── xgboost_model.py         # XGBoost Regressor, forecast intervals, and backtesting engine
│       ├── shap_explainer.py        # SHAP TreeExplainer with feature metadata and attributions
│       ├── portfolio.py             # Modern Portfolio Theory (MPT), Efficient Frontier, & VaR/CVaR
│       ├── sentiment_analyzer.py    # Multi-provider news sentiment analyzer with financial lexicon
│       └── claude_narrator.py       # OpenAI & Anthropic quant research narrative synthesizer
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                  # Main application, tab routing, & hero metric ribbon
│       ├── apiConfig.js             # Centralized API and WebSocket URL configuration
│       ├── main.jsx                 # Vite entry mountpoint
│       ├── styles.css               # Modern dark-mode institutional UI stylesheet
│       └── components/
│           ├── CandlestickChart.jsx # Interactive TradingView chart with real-time WebSocket tick pulse
│           ├── ExplanationCard.tsx  # Forecast hero, sentiment gauge, narrative block, & live news feed
│           ├── ShapBarChart.jsx     # SHAP horizontal bar and waterfall charts with feature metadata
│           ├── RegimeDashboard.jsx  # HMM posterior probabilities, distribution, & transition matrix
│           ├── BacktestDashboard.jsx# Out-of-sample hit rate, MAE/RMSE, and strategy simulation
│           ├── ComparisonDashboard.jsx # Multi-ticker comparative matrix & watchlist switcher
│           └── PortfolioDashboard.jsx  # Modern Portfolio Theory, Efficient Frontier SVG, and VaR/CVaR
├── data/
│   └── finvizaard.duckdb            # Embedded DuckDB database storage
├── Dockerfile.backend               # Multi-stage Python 3.11 builder & runner
├── Dockerfile.frontend              # Multi-stage Node 20 & Nginx reverse proxy
├── docker-compose.yml               # Unified orchestration for Backend & Frontend
├── nginx.conf                       # Production Nginx reverse proxy for API & WebSockets
├── requirements.txt                 # Backend Python package requirements
├── run.py                           # Backend launcher
├── start.bat                        # Batch script to launch backend
└── start_all.bat                    # One-click launcher for Backend + Frontend simultaneously
```

---

## 🌟 Feature & Dashboard Suite

### 1. 📊 Forecast & Model Explainability Dashboard (with Real-Time WebSocket)
* **TradingView Candlestick Chart**: Interactive canvas charts with green/red sessions, volume histogram bars, timeframe zoom buttons (1M, 3M, 6M, 1Y, ALL), and target price guideline overlays.
* **🟢 Real-Time WebSocket Tick Stream**: Live pulsating connection badge, real-time bid/ask spread, micro-tick price movements, dynamic candle updating, and trade signal badges.
* **XGBoost Price Forecasting**: Estimates next-day close, projected percentage return, and expected confidence intervals.
* **SHAP Attribution Engine**: View feature contributions in both **Horizontal Bar Chart** and **Waterfall Chart** modes, with sorting by magnitude, positive-first, or negative-first.
* **Live News Sentiment Feed**: Real-time ticker news scored from -1.0 (Bearish) to +1.0 (Bullish) with headline catalyst extraction and expandable live news articles with links.
* **AI Quantitative Narrative**: High-quality 3-sentence Wall Street research summary covering Signal, Regime & Drivers, and Risk / Catalysts to monitor.

### 2. 🌐 Market Regime Detection Dashboard
* **Gaussian Hidden Markov Model**: Unsupervised sequence clustering identifying **Bull**, **Sideways**, and **Bear** market states.
* **State Posterior Probabilities**: Real-time state confidence percentages (e.g. 85% Bull, 12% Sideways, 3% Bear).
* **Markov Transition Matrix**: Interactive grid showing empirical transition likelihoods from state $t$ to state $t+1$.
* **Historical Distribution & Performance Profile**: Breakdown of days spent per regime, mean daily return %, and annualized volatility %.
* **Regime Timeline**: Continuous color-coded historical strip showing regime shifts across all analyzed trading sessions.

### 3. ⚡ Strategy Backtest Sandbox
* **Out-of-Sample Performance**: Configurable test split window (15%, 20%, 30%).
* **Key Metrics**: Directional Accuracy % (Hit Rate), Mean Absolute Error (MAE), RMSE, and MAPE %.
* **Predicted vs Actual Trajectory**: Visual price tracking comparing actual historical closes vs XGBoost forecasts over the test window.
* **Strategy Simulation**: Simulated cumulative return comparing the model's regime-adjusted trading strategy vs a passive Buy & Hold benchmark.

### 4. 🎯 Quantitative Portfolio & Risk Engine (MPT & VaR/CVaR)
* **Markowitz Efficient Frontier**: Computes the optimal risk-return curve across any basket of assets using quadratic constrained optimization (SciPy SLSQP).
* **Allocation Strategies**: 1-click toggles for **Max Sharpe Ratio** (optimal growth), **Min Volatility** (capital preservation), and **Equal Weight** (1/N benchmark).
* **Interactive Weight Sliders**: Real-time rebalancing sliders with automatic normalization and instant risk updates.
* **Institutional Risk Analytics**:
  * **Value at Risk (VaR 95% & 99%)**: Parametric & Historical VaR expressed in both % and nominal currency.
  * **Conditional VaR (CVaR / Expected Shortfall)**: Average loss in the worst tail distribution (Black Swan defense).
  * **Downside Risk & Drawdown**: Sortino ratio and Maximum Historical Drawdown.
  * **Cross-Asset Correlation Heatmap**: Color-coded matrix revealing diversification opportunities.

### 5. 📋 Multi-Ticker Comparison & Watchlist
* **Cross-Sectional Matrix**: Side-by-side view of top equities comparing current price, 1-day move, detected regime, forecasted target, and sentiment score.
* **1-Click Switching**: Click "Analyze Ticker" on any asset to immediately update the entire dashboard suite.
* **Add Custom Tickers**: Type any valid ticker (e.g. META, AMD, NFLX) to immediately add it to your live tracking matrix.

---

## 🛠️ Quick Start Guide

### Option 1: Docker 1-Click Deployment (Recommended for Production)
Make sure Docker Desktop is running, then execute:
```bash
docker compose up --build
```
* **Frontend**: Open `http://localhost:3000` (served via Nginx reverse proxy)
* **Backend API**: Open `http://localhost:8000/docs` (Swagger UI)

---

### Option 2: Automated Local Launch (Windows)
Double-click **`start_all.bat`** in the project directory. This launches both the FastAPI backend (port 8000) and the Vite frontend (port 5173).

---

### Option 3: Manual Step-by-Step Launch

#### 1. Backend Setup
```bash
# Navigate to project folder
cd FinVizaard-Prince

# Activate Python environment
call venv\Scripts\activate   # Windows
# or: source venv/bin/activate  # macOS/Linux

# Start FastAPI server
python run.py
```
* Interactive API Documentation: `http://127.0.0.1:8000/docs`

#### 2. Frontend Setup
```bash
# In a separate terminal, navigate to frontend
cd FinVizaard-Prince/frontend

# Install dependencies (if not already installed)
npm install

# Start Vite development server
npm run dev
```
* Open your browser at: `http://localhost:5173/`

---

## 🔑 Environment Configuration (.env)

Copy `.env.example` to `.env`:
```ini
NEWS_API_KEY=your_news_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```
> [!NOTE]
> FinVizaard supports **both OpenAI and Anthropic Claude keys** seamlessly. If API keys are missing or rate-limited, the system automatically engages an intelligent local financial lexicon analyzer and quantitative narrative engine so the entire application remains 100% operational offline and out-of-the-box!

---

## 📡 API Endpoints & WebSocket Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System health check, database stats, and streaming status |
| `GET` | `/tickers` | Lists all tickers currently stored in DuckDB |
| `POST`| `/ingest` | Downloads OHLCV data, cleans & deduplicates, and caches sentiment |
| `GET` | `/candles/{ticker}` | Returns deduplicated candles with volume and moving averages |
| `POST`| `/predict` | Computes HMM regime and XGBoost price forecast with confidence intervals |
| `POST`| `/explain` | Generates SHAP attributions, feature metadata, and AI narrative |
| `GET` | `/sentiment/{ticker}` | Returns sentiment score, label, catalyst reason, and live news articles |
| `GET` | `/regimes/{ticker}` | Returns HMM regime analysis, probabilities, transition matrix, & timeline |
| `GET` | `/backtest/{ticker}` | Computes out-of-sample accuracy, MAE/RMSE, and cumulative strategy return |
| `GET` | `/compare` | Batch comparison of multiple tickers for watchlist matrix |
| `POST`| `/portfolio/optimize` | Computes Markowitz Efficient Frontier, Max Sharpe, and Min Volatility allocations |
| `POST`| `/portfolio/risk` | Computes Parametric & Historical VaR (95%/99%), CVaR, Beta, & Sortino ratio |
| `WS`  | `/ws/stream/{ticker}` | Real-time WebSocket live tick stream (prices, bid/ask spreads, volumes) |

---

### Author
**Prince Pokharna**  
GitHub: [@prince-pokharna](https://github.com/prince-pokharna)
