import { useState, useEffect } from "react";
import axios from "axios";
import { API_BASE_URL } from "../apiConfig";

const DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA", "SPY"];

export default function ComparisonDashboard({
  onSelectTicker,
  activeTicker,
  apiBaseUrl = API_BASE_URL,
}) {
  const [tickers, setTickers] = useState(DEFAULT_TICKERS);
  const [newTicker, setNewTicker] = useState("");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ingestingTicker, setIngestingTicker] = useState("");

  async function fetchComparison(list = tickers) {
    setLoading(true);
    try {
      const res = await axios.get(`${apiBaseUrl}/compare?tickers=${list.join(",")}`);
      setData(res.data.comparison || []);
    } catch (err) {
      console.error("Comparison fetch failed:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchComparison(tickers);
  }, [tickers]);

  const handleAddTicker = (e) => {
    e.preventDefault();
    const clean = newTicker.trim().toUpperCase();
    if (clean && !tickers.includes(clean)) {
      const updated = [...tickers, clean];
      setTickers(updated);
      setNewTicker("");
      fetchComparison(updated);
    }
  };

  const handleQuickIngest = async (sym) => {
    setIngestingTicker(sym);
    try {
      const d = new Date();
      d.setFullYear(d.getFullYear() - 1);
      const start = d.toISOString().slice(0, 10);
      const end = new Date().toISOString().slice(0, 10);

      await axios.post(`${apiBaseUrl}/ingest`, {
        tickers: [sym],
        start_date: start,
        end_date: end,
      });
      await fetchComparison(tickers);
    } catch (err) {
      alert(`Ingest failed for ${sym}: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIngestingTicker("");
    }
  };

  return (
    <div className="comparisonDashboard">
      <div className="panel compHeaderPanel">
        <div className="compTitleBlock">
          <h3>Multi-Ticker Comparative Matrix</h3>
          <p className="muted subhead">
            Side-by-side asset monitoring, cross-sectional regime distribution, and machine learning forecast comparisons
          </p>
        </div>
        <form onSubmit={handleAddTicker} className="compAddForm">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Add Ticker (e.g. META)"
            className="compInput"
          />
          <button type="submit" className="compAddBtn">
            + Add Ticker
          </button>
        </form>
      </div>

      <div className="panel compTablePanel">
        {loading && <div className="compLoadingBar">Refreshing market comparisons...</div>}
        <div className="tableResponsive">
          <table className="compTable">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Current Price</th>
                <th>HMM Regime</th>
                <th>Forecasted Next Close</th>
                <th>Target Move (%)</th>
                <th>News Sentiment</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => {
                const isActive = row.ticker === activeTicker;
                const changePct = row.predicted_change_pct;
                const isReady = row.ready;

                return (
                  <tr key={row.ticker} className={isActive ? "activeRow" : ""}>
                    <td className="tickerCell">
                      <strong>{row.ticker}</strong>
                      {isActive && <span className="activeTag">ACTIVE</span>}
                    </td>
                    <td>{row.last_close != null ? `$${row.last_close.toFixed(2)}` : "—"}</td>
                    <td>
                      <span className={`pillSm ${row.regime ? row.regime.toLowerCase() : "neutral"}`}>
                        {row.regime ? row.regime.toUpperCase() : "UNINDEXED"}
                      </span>
                    </td>
                    <td>
                      {row.predicted_close != null ? (
                        <strong>${row.predicted_close.toFixed(2)}</strong>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {changePct != null ? (
                        <span className={`compMoveBadge ${changePct >= 0 ? "pos" : "neg"}`}>
                          {changePct >= 0 ? "+" : ""}
                          {changePct.toFixed(2)}%
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <span className={`sentimentPill ${row.sentiment_label || "neutral"}`}>
                        {row.sentiment_label?.toUpperCase() || "NEUTRAL"} (
                        {row.sentiment_score >= 0 ? `+${row.sentiment_score.toFixed(2)}` : row.sentiment_score.toFixed(2)})
                      </span>
                    </td>
                    <td className="compActionCell">
                      {isReady ? (
                        <button
                          type="button"
                          className={`compSelectBtn ${isActive ? "selected" : ""}`}
                          onClick={() => onSelectTicker(row.ticker)}
                        >
                          {isActive ? "Selected ✓" : "Analyze Ticker"}
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="compIngestBtn"
                          disabled={ingestingTicker === row.ticker}
                          onClick={() => handleQuickIngest(row.ticker)}
                        >
                          {ingestingTicker === row.ticker ? "Ingesting..." : "Ingest Data"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
