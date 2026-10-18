import { useState, useMemo, useEffect, useCallback } from "react";
import axios from "axios";
import CandlestickChart from "./components/CandlestickChart";
import ExplanationCard from "./components/ExplanationCard";
import ShapBarChart from "./components/ShapBarChart";
import RegimeDashboard from "./components/RegimeDashboard";
import BacktestDashboard from "./components/BacktestDashboard";
import ComparisonDashboard from "./components/ComparisonDashboard";
import PortfolioDashboard from "./components/PortfolioDashboard";
import { API_BASE_URL } from "./apiConfig";

const api = axios.create({
  baseURL: API_BASE_URL,
});

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function datePresetISO(yearsBack = 1) {
  const d = new Date();
  d.setFullYear(d.getFullYear() - yearsBack);
  return d.toISOString().slice(0, 10);
}

const PRESET_TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA", "SPY"];

export default function App() {
  const [ticker, setTicker] = useState("AAPL");
  const [startDate, setStartDate] = useState(datePresetISO(1));
  const [endDate, setEndDate] = useState(todayISO());
  const [activeTab, setActiveTab] = useState("forecast"); // 'forecast', 'regimes', 'backtest', 'compare'

  // Dashboard Data State
  const [candles, setCandles] = useState([]);
  const [regime, setRegime] = useState("");
  const [pricePrediction, setPricePrediction] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [sentiment, setSentiment] = useState(null);
  const [explanation, setExplanation] = useState({});
  const [featureMetadata, setFeatureMetadata] = useState({});
  const [shapBaseValue, setShapBaseValue] = useState(null);
  const [featureColumns, setFeatureColumns] = useState([]);
  const [narrative, setNarrative] = useState("");
  const [status, setStatus] = useState("FinVizaard Quant Terminal Ready.");
  const [busy, setBusy] = useState(false);
  const [progressStage, setProgressStage] = useState("");

  const cleanTicker = useMemo(() => ticker.trim().toUpperCase(), [ticker]);

  // Load chart data
  const handleLoadCandles = useCallback(async (sym = cleanTicker) => {
    if (!sym) return;
    try {
      const res = await api.get(`/candles/${sym}?limit=350`);
      const candleData = res.data.candles || [];
      setCandles(candleData);
      return candleData;
    } catch (err) {
      console.warn("Candles fetch:", err);
      return [];
    }
  }, [cleanTicker]);

  // Predict
  const handlePredict = useCallback(async (sym = cleanTicker) => {
    if (!sym) return;
    try {
      const res = await api.post("/predict", { ticker: sym });
      setRegime(res.data.regime);
      setPricePrediction(res.data.price_prediction);
      if (res.data.forecast) setForecast(res.data.forecast);

      const sRes = await api.get(`/sentiment/${sym}`);
      setSentiment(sRes.data);
      return res.data;
    } catch (err) {
      throw err;
    }
  }, [cleanTicker]);

  // Explain
  const handleExplain = useCallback(async (sym = cleanTicker) => {
    if (!sym) return;
    try {
      const res = await api.post("/explain", { ticker: sym });
      setExplanation(res.data.explanation || {});
      setShapBaseValue(
        typeof res.data.base_value === "number" ? res.data.base_value : null
      );
      if (typeof res.data.regime === "string" && res.data.regime) {
        setRegime(res.data.regime);
      }
      if (typeof res.data.predicted_next_close === "number") {
        setPricePrediction(res.data.predicted_next_close);
      }
      setFeatureColumns(
        Array.isArray(res.data.feature_columns) ? res.data.feature_columns : []
      );
      setFeatureMetadata(res.data.feature_metadata || {});
      setNarrative(res.data.narrative || "");
      return res.data;
    } catch (err) {
      throw err;
    }
  }, [cleanTicker]);

  // Ingest
  const handleIngest = async (sym = cleanTicker) => {
    if (!sym) return;
    setBusy(true);
    setStatus(`Ingesting market data for ${sym}...`);
    try {
      const payload = {
        tickers: [sym],
        start_date: startDate,
        end_date: endDate,
      };
      const res = await api.post("/ingest", payload);
      setStatus(`Ingested ${res.data.rows_ingested} sessions for ${sym}.`);
      await handleLoadCandles(sym);
    } catch (err) {
      setStatus(extractError(err, "Failed to ingest data."));
    } finally {
      setBusy(false);
    }
  };

  // One-Click Master Pipeline
  const handleRunFullAnalysis = async (sym = cleanTicker) => {
    if (!sym) return;
    setBusy(true);
    setStatus(`Running full intelligence pipeline for ${sym}...`);

    try {
      // 1. Ingest (if needed or refreshing)
      setProgressStage("Ingesting & caching data...");
      try {
        await api.post("/ingest", {
          tickers: [sym],
          start_date: startDate,
          end_date: endDate,
        });
      } catch (err) {
        // If ingest failed but we have data, proceed
      }

      // 2. Load Candles
      setProgressStage("Loading candlesticks...");
      await handleLoadCandles(sym);

      // 3. Predict HMM + XGBoost
      setProgressStage("Detecting regime & generating forecast...");
      await handlePredict(sym);

      // 4. Compute SHAP & Synthesize Narrative
      setProgressStage("Generating SHAP attributions & quant narrative...");
      await handleExplain(sym);

      setStatus(`All models, regimes, and explanations computed for ${sym}!`);
    } catch (err) {
      setStatus(extractError(err, "Pipeline encountered an issue."));
    } finally {
      setBusy(false);
      setProgressStage("");
    }
  };

  // Initial load on startup
  useEffect(() => {
    handleLoadCandles("AAPL");
    handlePredict("AAPL").catch(() => {});
    handleExplain("AAPL").catch(() => {});
  }, [handleLoadCandles, handlePredict, handleExplain]);

  // Quick switch from watchlist
  const handleSelectTicker = (newSym) => {
    setTicker(newSym);
    handleRunFullAnalysis(newSym);
  };

  // Quick date presets
  const applyDatePreset = (years) => {
    setStartDate(datePresetISO(years));
    setEndDate(todayISO());
  };

  // Current price
  const lastPrice = candles.length ? candles[candles.length - 1].close : null;
  const changePct = forecast?.predicted_change_pct;

  return (
    <div className="appLayout">
      {/* Top Navbar */}
      <header className="topNavbar">
        <div className="brandBlock">
          <div className="brandLogo">⚡ FinVizaard</div>
          <span className="brandTag">QUANT ENGINE 2.0</span>
        </div>

        <div className="navbarCenter">
          <nav className="tabNav">
            <button
              type="button"
              className={`tabBtn ${activeTab === "forecast" ? "active" : ""}`}
              onClick={() => setActiveTab("forecast")}
            >
              📊 Forecast & Explainability
            </button>
            <button
              type="button"
              className={`tabBtn ${activeTab === "regimes" ? "active" : ""}`}
              onClick={() => setActiveTab("regimes")}
            >
              🌐 Regime Detection
            </button>
            <button
              type="button"
              className={`tabBtn ${activeTab === "backtest" ? "active" : ""}`}
              onClick={() => setActiveTab("backtest")}
            >
              ⚡ Strategy Backtest
            </button>
            <button
              type="button"
              className={`tabBtn ${activeTab === "portfolio" ? "active" : ""}`}
              onClick={() => setActiveTab("portfolio")}
            >
              🎯 Portfolio & Risk
            </button>
            <button
              type="button"
              className={`tabBtn ${activeTab === "compare" ? "active" : ""}`}
              onClick={() => setActiveTab("compare")}
            >
              📋 Multi-Ticker Watchlist
            </button>
          </nav>
        </div>

        <div className="navbarRight">
          <div className="engineStatusBadge">
            <span className="statusDot live"></span>
            DuckDB & Models Active
          </div>
        </div>
      </header>

      {/* Hero Metric Ribbon */}
      <section className="heroMetricRibbon">
        <div className="heroItem">
          <span className="heroLabel">Active Ticker</span>
          <div className="heroTickerBadge">{cleanTicker}</div>
        </div>

        <div className="heroItem">
          <span className="heroLabel">Current Close</span>
          <div className="heroPrice">
            {lastPrice != null ? `$${lastPrice.toFixed(2)}` : "—"}
          </div>
        </div>

        <div className="heroItem">
          <span className="heroLabel">Next-Day Forecast</span>
          <div className="heroPredicted">
            {pricePrediction != null ? `$${pricePrediction.toFixed(2)}` : "—"}
            {changePct != null && (
              <span className={`heroChangePill ${changePct >= 0 ? "pos" : "neg"}`}>
                {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
              </span>
            )}
          </div>
        </div>

        <div className="heroItem">
          <span className="heroLabel">Inferred HMM Regime</span>
          <div className={`heroRegimeTag ${regime ? regime.toLowerCase() : "neutral"}`}>
            {regime ? regime.toUpperCase() : "PENDING"}
          </div>
        </div>

        <div className="heroItem">
          <span className="heroLabel">News Sentiment</span>
          <div className={`heroSentimentTag ${sentiment?.label || "neutral"}`}>
            {sentiment?.label ? sentiment.label.toUpperCase() : "NEUTRAL"}{" "}
            ({typeof sentiment?.score === "number" ? (sentiment.score >= 0 ? `+${sentiment.score.toFixed(2)}` : sentiment.score.toFixed(2)) : "0.00"})
          </div>
        </div>
      </section>

      {/* Control Console */}
      <section className="panel controlsBar">
        <div className="controlsRow">
          {/* Ticker Input & Presets */}
          <div className="controlGroup tickerGroup">
            <label>Ticker Symbol</label>
            <div className="tickerInputWrap">
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="AAPL"
                className="tickerInput"
              />
              <div className="tickerChips">
                {PRESET_TICKERS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={`tickerChip ${cleanTicker === t ? "active" : ""}`}
                    onClick={() => {
                      setTicker(t);
                      handleRunFullAnalysis(t);
                    }}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Date Range & Presets */}
          <div className="controlGroup dateGroup">
            <div className="dateLabelRow">
              <label>Historical Window</label>
              <div className="datePresetLinks">
                <button type="button" onClick={() => applyDatePreset(0.5)}>6M</button>
                <button type="button" onClick={() => applyDatePreset(1)}>1Y</button>
                <button type="button" onClick={() => applyDatePreset(2)}>2Y</button>
              </div>
            </div>
            <div className="dateInputsRow">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
              <span className="dateSep">to</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* Actions Button Bar */}
          <div className="controlGroup actionGroup">
            <label>Engine Execution</label>
            <div className="actionButtons">
              <button
                type="button"
                className="masterRunBtn"
                disabled={busy}
                onClick={() => handleRunFullAnalysis(cleanTicker)}
              >
                {busy && progressStage ? progressStage : "🚀 Run Full Analysis"}
              </button>
              <button
                type="button"
                className="secondaryBtn"
                disabled={busy}
                onClick={() => handleIngest(cleanTicker)}
                title="Fetch market OHLCV data into DuckDB"
              >
                Ingest
              </button>
              <button
                type="button"
                className="secondaryBtn"
                disabled={busy}
                onClick={() => handleLoadCandles(cleanTicker)}
                title="Reload interactive candlestick chart"
              >
                Chart
              </button>
              <button
                type="button"
                className="secondaryBtn"
                disabled={busy}
                onClick={() => handlePredict(cleanTicker)}
                title="Run HMM regime detection & XGBoost price forecast"
              >
                Forecast
              </button>
              <button
                type="button"
                className="secondaryBtn"
                disabled={busy}
                onClick={() => handleExplain(cleanTicker)}
                title="Compute TreeExplainer SHAP values and narrative"
              >
                Explain
              </button>
            </div>
          </div>
        </div>

        {/* Live Diagnostics Ribbon */}
        <div className="statusRibbon">
          <span className="statusDot active"></span>
          <span className="statusText">{status}</span>
        </div>
      </section>

      {/* Main Tabbed Views */}
      <main className="tabContentArea">
        {activeTab === "forecast" && (
          <div className="forecastTabGrid">
            <div className="chartAndForecastRow">
              <CandlestickChart
                data={candles}
                predictedPrice={pricePrediction}
                ticker={cleanTicker}
              />
              <ExplanationCard
                narrative={narrative}
                regime={regime}
                pricePrediction={pricePrediction}
                ticker={cleanTicker}
                sentiment={sentiment}
                forecast={forecast}
              />
            </div>

            <ShapBarChart
              explanation={explanation}
              baseValue={shapBaseValue}
              predictedPrice={pricePrediction}
              featureColumns={featureColumns}
              featureMetadata={featureMetadata}
            />
          </div>
        )}

        {activeTab === "regimes" && (
          <RegimeDashboard ticker={cleanTicker} />
        )}

        {activeTab === "backtest" && (
          <BacktestDashboard ticker={cleanTicker} />
        )}

        {activeTab === "portfolio" && (
          <PortfolioDashboard apiBaseUrl={API_BASE_URL} />
        )}

        {activeTab === "compare" && (
          <ComparisonDashboard
            activeTicker={cleanTicker}
            onSelectTicker={handleSelectTicker}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <div>FinVizaard Institutional Quantitative Intelligence Platform</div>
        <div className="footerTech">
          React 18 + Vite • TradingView Lightweight Charts • DuckDB • XGBoost • HMMlearn • SHAP • NewsAPI
        </div>
      </footer>
    </div>
  );
}

function extractError(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (err?.message) return err.message;
  return fallback;
}
