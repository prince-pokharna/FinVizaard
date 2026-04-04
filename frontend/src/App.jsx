import { useMemo, useState } from "react";
import axios from "axios";
import CandlestickChart from "./components/CandlestickChart";
import ExplanationCard from "./components/ExplanationCard";
import ShapBarChart from "./components/ShapBarChart";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000"
});

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function oneYearAgoISO() {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 1);
  return d.toISOString().slice(0, 10);
}

export default function App() {
  const [ticker, setTicker] = useState("AAPL");
  const [startDate, setStartDate] = useState(oneYearAgoISO());
  const [endDate, setEndDate] = useState(todayISO());
  const [candles, setCandles] = useState([]);
  const [regime, setRegime] = useState("");
  const [pricePrediction, setPricePrediction] = useState(null);
  const [sentiment, setSentiment] = useState(null);
  const [explanation, setExplanation] = useState({});
  const [shapBaseValue, setShapBaseValue] = useState(null);
  const [featureColumns, setFeatureColumns] = useState([]);
  const [narrative, setNarrative] = useState("");
  const [status, setStatus] = useState("Ready.");
  const [busy, setBusy] = useState(false);

  const cleanTicker = useMemo(() => ticker.trim().toUpperCase(), [ticker]);

  async function handleIngest() {
    if (!cleanTicker) return;
    setBusy(true);
    setStatus("Ingesting market data...");
    try {
      const payload = {
        tickers: [cleanTicker],
        start_date: startDate,
        end_date: endDate
      };
      const res = await api.post("/ingest", payload);
      setStatus(`Ingested ${res.data.rows_ingested} rows for ${cleanTicker}.`);
    } catch (err) {
      setStatus(extractError(err, "Failed to ingest."));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadCandles() {
    if (!cleanTicker) return;
    setBusy(true);
    setStatus("Loading candles...");
    try {
      const res = await api.get(`/candles/${cleanTicker}?limit=300`);
      setCandles(res.data.candles || []);
      setStatus(`Loaded ${res.data.candles?.length || 0} candles.`);
    } catch (err) {
      setStatus(extractError(err, "Failed to load candles."));
    } finally {
      setBusy(false);
    }
  }

  async function handlePredict() {
    if (!cleanTicker) return;
    setBusy(true);
    setStatus("Running HMM + XGBoost prediction...");
    try {
      const res = await api.post("/predict", { ticker: cleanTicker });
      setRegime(res.data.regime);
      setPricePrediction(res.data.price_prediction);

      setStatus("Fetching news sentiment...");
      const sRes = await api.get(`/sentiment/${cleanTicker}`);
      setSentiment(sRes.data);

      setStatus(`Prediction and sentiment ready for ${cleanTicker}.`);
    } catch (err) {
      setStatus(extractError(err, "Prediction failed."));
    } finally {
      setBusy(false);
    }
  }

  async function handleExplain() {
    if (!cleanTicker) return;
    setBusy(true);
    setStatus("Generating SHAP explanation...");
    try {
      const res = await api.post("/explain", { ticker: cleanTicker });
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
      setNarrative(res.data.narrative || "");
      setStatus("Explanation generated.");
    } catch (err) {
      setStatus(extractError(err, "Explain failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <header className="header">
        <h1>FinVizaard Dashboard</h1>
        <p>Regime detection + prediction + explainability</p>
      </header>

      <section className="panel controls">
        <div className="field">
          <label>Ticker</label>
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="AAPL" />
        </div>
        <div className="field">
          <label>Start Date</label>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div className="field">
          <label>End Date</label>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
        <div className="actions">
          <button disabled={busy} onClick={handleIngest}>Ingest</button>
          <button disabled={busy} onClick={handleLoadCandles}>Load Chart</button>
          <button disabled={busy} onClick={handlePredict}>Predict</button>
          <button disabled={busy} onClick={handleExplain}>Explain</button>
        </div>
        <div className="status">{status}</div>
      </section>

      <section className="grid">
        <CandlestickChart data={candles} />
        <ExplanationCard
          narrative={narrative}
          regime={regime}
          pricePrediction={pricePrediction}
          ticker={cleanTicker}
          sentiment={sentiment}
        />
        <ShapBarChart
          explanation={explanation}
          baseValue={shapBaseValue}
          predictedPrice={pricePrediction}
          featureColumns={featureColumns}
        />
      </section>
    </main>
  );
}

function extractError(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return fallback;
}

