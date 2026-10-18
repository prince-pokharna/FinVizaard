import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { API_BASE_URL } from "../apiConfig";

export default function BacktestDashboard({ ticker, apiBaseUrl = API_BASE_URL }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [testRatio, setTestRatio] = useState(0.2);

  const cleanTicker = ticker ? ticker.trim().toUpperCase() : "AAPL";

  useEffect(() => {
    let isMounted = true;
    async function runBacktest() {
      setLoading(true);
      setError("");
      try {
        const res = await axios.get(
          `${apiBaseUrl}/backtest/${cleanTicker}?test_ratio=${testRatio}`
        );
        if (isMounted) setData(res.data);
      } catch (err) {
        if (isMounted) {
          setError(
            err?.response?.data?.detail ||
              "Backtest simulation failed. Ensure at least 6 months of historical data are ingested."
          );
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    runBacktest();
    return () => {
      isMounted = false;
    };
  }, [cleanTicker, testRatio, apiBaseUrl]);

  const points = data?.chart_points || [];

  // Calculate SVG scales for Predicted vs Actual
  const priceSvg = useMemo(() => {
    if (!points.length) return null;
    const w = 800;
    const h = 260;
    const pad = 40;

    const actuals = points.map((p) => p.actual);
    const preds = points.map((p) => p.predicted);
    const minVal = Math.min(...actuals, ...preds);
    const maxVal = Math.max(...actuals, ...preds);
    const rangeVal = maxVal - minVal || 1;

    const getX = (idx) => pad + (idx / (points.length - 1)) * (w - pad * 2);
    const getY = (val) => h - pad - ((val - minVal) / rangeVal) * (h - pad * 2);

    const actualPath = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)},${getY(p.actual).toFixed(1)}`)
      .join(" ");

    const predPath = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)},${getY(p.predicted).toFixed(1)}`)
      .join(" ");

    return { w, h, actualPath, predPath, minVal, maxVal };
  }, [points]);

  // Calculate SVG scales for Strategy vs Buy & Hold Cumulative Return
  const retSvg = useMemo(() => {
    if (!points.length) return null;
    const w = 800;
    const h = 260;
    const pad = 40;

    const bh = points.map((p) => p.buy_and_hold_return);
    const strat = points.map((p) => p.strategy_return);
    const minVal = Math.min(0, ...bh, ...strat);
    const maxVal = Math.max(0, ...bh, ...strat);
    const rangeVal = maxVal - minVal || 1;

    const getX = (idx) => pad + (idx / (points.length - 1)) * (w - pad * 2);
    const getY = (val) => h - pad - ((val - minVal) / rangeVal) * (h - pad * 2);

    const bhPath = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)},${getY(p.buy_and_hold_return).toFixed(1)}`)
      .join(" ");

    const stratPath = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)},${getY(p.strategy_return).toFixed(1)}`)
      .join(" ");

    const zeroY = getY(0);

    return { w, h, bhPath, stratPath, minVal, maxVal, zeroY };
  }, [points]);

  if (loading) {
    return (
      <div className="panel loadingPanel">
        <div className="spinner"></div>
        <p>Running out-of-sample backtesting simulation for {cleanTicker}...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel errorPanel">
        <h3>Backtesting Sandbox</h3>
        <p className="errorText">{error}</p>
        <p className="muted">Ingest a wider date range (e.g., 1 Year) for robust backtesting results.</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="backtestDashboard">
      {/* Test Controls & Dataset Info */}
      <div className="panel backtestControlBar">
        <div className="backtestMeta">
          <h3>Strategy & XGBoost Sandbox: {cleanTicker}</h3>
          <span className="muted">
            Trained on {data.train_size} sessions | Evaluated on {data.sample_size} out-of-sample test sessions
          </span>
        </div>
        <div className="testRatioToggle">
          <span className="controlLabel">Out-of-Sample Window:</span>
          {[0.15, 0.2, 0.3].map((r) => (
            <button
              key={r}
              type="button"
              className={testRatio === r ? "active" : ""}
              onClick={() => setTestRatio(r)}
            >
              {(r * 100).toFixed(0)}%
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpiGrid">
        <div className="panel kpiCard">
          <span className="kpiLabel">Directional Accuracy (Hit Rate)</span>
          <div className="kpiValue textCyan">{data.directional_accuracy}%</div>
          <span className="kpiSub">Correctly forecasted price up/down direction</span>
        </div>

        <div className="panel kpiCard">
          <span className="kpiLabel">FinVizaard Strategy Return</span>
          <div className={`kpiValue ${data.strategy_return >= 0 ? "textGreen" : "textRed"}`}>
            {data.strategy_return >= 0 ? "+" : ""}{data.strategy_return}%
          </div>
          <span className="kpiSub">Outperformed Buy & Hold by {data.outperformance >= 0 ? `+${data.outperformance}%` : `${data.outperformance}%`}</span>
        </div>

        <div className="panel kpiCard">
          <span className="kpiLabel">Passive Buy & Hold Return</span>
          <div className={`kpiValue ${data.buy_and_hold_return >= 0 ? "textGreen" : "textRed"}`}>
            {data.buy_and_hold_return >= 0 ? "+" : ""}{data.buy_and_hold_return}%
          </div>
          <span className="kpiSub">Benchmark over test period</span>
        </div>

        <div className="panel kpiCard">
          <span className="kpiLabel">Mean Absolute Error (MAE)</span>
          <div className="kpiValue">${data.mae}</div>
          <span className="kpiSub">MAPE: {data.mape}% of stock price</span>
        </div>
      </div>

      {/* Predicted vs Actual Price Chart */}
      {priceSvg && (
        <div className="panel backtestChartPanel">
          <div className="chartHeader">
            <div>
              <h4>Out-of-Sample: Predicted vs Actual Close Price</h4>
              <p className="muted subhead">Tracking how closely the model mirrored historical next-day close</p>
            </div>
            <div className="svgLegend">
              <span><i className="legendDot green"></i> Actual Observed Close</span>
              <span><i className="legendDot cyan"></i> XGBoost Predicted Target</span>
            </div>
          </div>
          <div className="svgWrap">
            <svg viewBox={`0 0 ${priceSvg.w} ${priceSvg.h}`} className="chartSvg">
              {/* Grid Lines */}
              <line x1="40" y1="40" x2="760" y2="40" stroke="#1e293b" strokeDasharray="3 3" />
              <line x1="40" y1="130" x2="760" y2="130" stroke="#1e293b" strokeDasharray="3 3" />
              <line x1="40" y1="220" x2="760" y2="220" stroke="#1e293b" strokeDasharray="3 3" />

              {/* Paths */}
              <path d={priceSvg.actualPath} fill="none" stroke="#10b981" strokeWidth="2.5" />
              <path d={priceSvg.predPath} fill="none" stroke="#38bdf8" strokeWidth="2" strokeDasharray="4 3" />

              {/* Price labels */}
              <text x="35" y="45" fill="#64748b" textAnchor="end" fontSize="11">${priceSvg.maxVal.toFixed(1)}</text>
              <text x="35" y="225" fill="#64748b" textAnchor="end" fontSize="11">${priceSvg.minVal.toFixed(1)}</text>
            </svg>
          </div>
        </div>
      )}

      {/* Cumulative Return: FinVizaard Strategy vs Buy & Hold */}
      {retSvg && (
        <div className="panel backtestChartPanel">
          <div className="chartHeader">
            <div>
              <h4>Cumulative Return Simulation: Quantitative Strategy vs Buy & Hold</h4>
              <p className="muted subhead">Model signals long exposure on positive forecasts; risk-off in negative/defensive states</p>
            </div>
            <div className="svgLegend">
              <span><i className="legendDot cyan"></i> FinVizaard Model Strategy</span>
              <span><i className="legendDot purple"></i> Buy & Hold Baseline</span>
            </div>
          </div>
          <div className="svgWrap">
            <svg viewBox={`0 0 ${retSvg.w} ${retSvg.h}`} className="chartSvg">
              {/* Zero return line */}
              <line x1="40" y1={retSvg.zeroY} x2="760" y2={retSvg.zeroY} stroke="#475569" strokeWidth="1" strokeDasharray="2 2" />

              {/* Paths */}
              <path d={retSvg.bhPath} fill="none" stroke="#a855f7" strokeWidth="2" strokeDasharray="3 2" />
              <path d={retSvg.stratPath} fill="none" stroke="#38bdf8" strokeWidth="2.5" />

              {/* Labels */}
              <text x="35" y="45" fill="#64748b" textAnchor="end" fontSize="11">{retSvg.maxVal.toFixed(1)}%</text>
              <text x="35" y={retSvg.zeroY + 4} fill="#94a3b8" textAnchor="end" fontSize="11">0%</text>
              <text x="35" y="225" fill="#64748b" textAnchor="end" fontSize="11">{retSvg.minVal.toFixed(1)}%</text>
            </svg>
          </div>
        </div>
      )}
    </div>
  );
}
