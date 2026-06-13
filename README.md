# FinVizaard

FinVizaard is an AI-powered financial technology platform designed to deliver predictive market insights, regime detection, and model explainability for equities. By integrating Machine Learning regression (XGBoost), probabilistic sequence modeling (Hidden Markov Models), and Generative AI (Anthropic Claude), FinVizaard equips users with robust predictions accompanied by transparent, readable rationales.

---

## 🚀 Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | React, Vite, CSS3 | A fast, responsive dashboard built with modern React and styled with vanilla CSS. |
| **Interactive Charts** | lightweight-charts | High-performance canvas-based financial charts from TradingView for candlesticks. |
| **Backend** | Python, FastAPI, Uvicorn | High-performance asynchronous API service routing data, modeling pipeline, and LLM requests. |
| **Database** | DuckDB | Embeddable, analytical database optimizing storage and query performance for historical price and sentiment cache. |
| **Machine Learning** | XGBoost, HMMlearn, SHAP | Predictive modeling (regression), market regime clustering, and local feature attribution (SHAP values). |
| **Generative AI** | Anthropic Claude API | Sentiment scoring of financial news articles and natural language synthesis explaining predictions. |
| **Data Ingestion** | yfinance | Downloads real-time and historical asset market prices (OHLCV). |

---

## 📁 Project Structure

```text
FinVizaard-Prince/
├── Backend/
│   └── src/
│       ├── __init__.py
│       ├── main.py                  # FastAPI Application Entry Point
│       ├── database.py              # DuckDB database schema & connections
│       ├── data_ingestion.py        # yfinance price downloader & synthetic fallback generator
│       ├── features.py              # Technical & macroeconomic feature engineering
│       ├── hmm_model.py             # Hidden Markov Model for market regime detection (bear, sideways, bull)
│       ├── xgboost_model.py         # XGBoost Regressor for next-day close price forecasting
│       ├── shap_explainer.py        # SHAP TreeExplainer for feature importance attributions
│       ├── sentiment_analyzer.py    # NewsAPI fetching and Claude-based news sentiment scoring
│       └── claude_narrator.py       # Claude LLM synthesis for predictions and feature impact narrative
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                  # Dashboard state manager & UI layout
│       ├── main.jsx                 # Vite application mountpoint
│       ├── styles.css               # Modern dark-mode layout styling
│       └── components/
│           ├── CandlestickChart.jsx # Interactive financial candlestick charts
│           ├── ShapBarChart.jsx     # SHAP horizontal bar and waterfall charts
│           └── ExplanationCard.tsx  # Metrics, sentiment badge, & AI prediction summary
├── notebooks/
│   ├── 01_data_exploration.ipynb    # DuckDB data loading and initial exploratory data analysis
│   ├── 02_hmm_training.ipynb        # Market regime HMM testing and price-by-regime scatter plots
│   └── 03_xgboost_training.ipynb    # XGBoost regression training, backtesting, and SHAP test runs
├── .gitignore
├── requirements.txt                 # Backend Python package requirements
└── .env.example                     # Reference template for required configuration keys
```

---

## 🛠️ Prerequisites

To run this application locally, you will need:
1. **Python 3.9+** (Python 3.10 or 3.11 is recommended)
2. **Node.js v16+** and **npm**
3. A **NewsAPI key** (obtain free from [newsapi.org](https://newsapi.org/))
4. An **Anthropic API key** (obtain from the [Anthropic Console](https://console.anthropic.com/))

### Environment Configuration
Copy the template `.env.example` in the root folder to a new file named `.env`:
```bash
# In the project root:
cp .env.example .env
```
Open `.env` and enter your API keys:
```ini
NEWS_API_KEY=your_news_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```
> [!NOTE]
> If keys are not present in `.env`, the application will use built-in synthetic market data generation and fallback narrative templates so the dashboard remains functional for demo purposes.

---

## 📥 Installation

Follow these steps to set up the backend and frontend environments separately.

### 1. Backend Setup
Navigate to the root directory and install dependencies:
```bash
# Install required Python packages
pip install -r requirements.txt
```

### 2. Frontend Setup
Navigate to the `frontend/` folder and install dependencies:
```bash
# Go to frontend folder
cd frontend

# Install package packages
npm install
```

---

## 🚀 Running the Application

You must run both the backend FastAPI server and the frontend Vite development server simultaneously.

### 1. Run the Backend API Server
From the project root directory, run the FastAPI application:
```bash
python -m Backend.src.main
```
The API documentation will be interactive and available at `http://127.0.0.1:8000/docs`.

### 2. Run the Frontend Development Server
From the `frontend/` directory, start the development server:
```bash
cd frontend
npm run dev
```
Open your browser and navigate to `http://localhost:5173/` to interact with the dashboard.

---

## 🌟 Features Overview

### Current End-to-End Features (Working Right Now)
* **Market Data Ingestion:** Downloads real-time OHLCV data using the Yahoo Finance API (falls back to a local, deterministic synthetic market generator if rate-limited).
* **Market Regime Detection:** Classifies market conditions into three core regimes (*Bullish*, *Sideways*, or *Bearish*) using a Gaussian Hidden Markov Model (HMM) fitted on asset returns and volatility.
* **Price Forecasting:** Predicts the next trading day's closing price utilizing an XGBoost Regressor trained on lagged returns, moving averages, standard deviation trends, VIX indicators, and sentiment metrics.
* **SHAP Explainability:** Computes exact feature contributions to the prediction utilizing SHAP (SHapley Additive exPlanations). Explanations are rendered dynamically on the UI in both **Horizontal Bar Chart** and **Waterfall Chart** formats.
* **News Sentiment Analysis:** Integrates with NewsAPI to pull live, relevant ticker articles, which are scored using Claude Sonnet (`-1.0` to `+1.0` range).
* **AI narrative synthesis:** Leverages Claude Opus to generate a concise, human-readable 3-sentence summary of the model's signal, HMM regime correlation, and variables to watch.

### Planned Features
* **Multi-Ticker Comparison View:** Support for side-by-side asset prediction and metric overlays.
* **Portfolio Optimization Engine:** Custom allocations adjusted dynamically based on HMM-detected regime shifts.
* **Advanced Backtesting Sandbox:** Simulated historical tracking of XGBoost performance across specific historical regimes.
* **User Accounts:** Save watchlists, custom feature weights, and dashboard configurations.

---

### Author
**Prince Pokharna**  
GitHub: [@prince-pokharna](https://github.com/prince-pokharna)
