import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API_BASE_URL } from "../apiConfig";

const AVAILABLE_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA", "SPY"];

export default function PortfolioDashboard({ apiBaseUrl = API_BASE_URL }) {
  const [selectedTickers, setSelectedTickers] = useState(["AAPL", "MSFT"]);
  const [customTickerInput, setCustomTickerInput] = useState("");
  const [initialInvestment, setInitialInvestment] = useState(100000);
  const [riskFreeRate, setRiskFreeRate] = useState(4.0);
  const [strategyMode, setStrategyMode] = useState("max_sharpe"); // 'max_sharpe', 'min_vol', 'equal', 'custom'

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [optData, setOptData] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [customWeights, setCustomWeights] = useState({});

  // 1. Fetch Optimization Data
  const runOptimization = useCallback(async (tickersToRun = selectedTickers) => {
    if (tickersToRun.length < 2) {
      setError("Please select at least 2 tickers for portfolio optimization.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await axios.post(`${apiBaseUrl}/portfolio/optimize`, {
        tickers: tickersToRun,
        risk_free_rate: riskFreeRate / 100.0,
        num_simulations: 1000,
      });
      setOptData(res.data);

      // Determine initial weights based on current strategy
      let activeWeights = res.data.max_sharpe_portfolio.weights;
      if (strategyMode === "min_vol") {
        activeWeights = res.data.min_volatility_portfolio.weights;
      } else if (strategyMode === "equal") {
        activeWeights = res.data.equal_weight_portfolio.weights;
      }
      setCustomWeights(activeWeights);

      // Fetch risk for active weights
      await runRiskCalculation(tickersToRun, activeWeights);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to calculate portfolio optimization.");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, selectedTickers, riskFreeRate, strategyMode]);

  // 2. Fetch Risk Metrics
  const runRiskCalculation = async (tickers, weights) => {
    try {
      const res = await axios.post(`${apiBaseUrl}/portfolio/risk`, {
        tickers,
        weights,
        initial_investment: Number(initialInvestment),
        time_horizon_days: 1,
      });
      setRiskData(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    runOptimization();
  }, []);

  // Strategy preset toggle
  const handleStrategyChange = (mode) => {
    setStrategyMode(mode);
    if (!optData) return;
    let newWeights = customWeights;
    if (mode === "max_sharpe") {
      newWeights = optData.max_sharpe_portfolio.weights;
    } else if (mode === "min_vol") {
      newWeights = optData.min_volatility_portfolio.weights;
    } else if (mode === "equal") {
      newWeights = optData.equal_weight_portfolio.weights;
    }
    setCustomWeights(newWeights);
    runRiskCalculation(optData.tickers, newWeights);
  };

  // Custom weight slider change
  const handleWeightSlider = (ticker, val) => {
    const rawVal = parseFloat(val) || 0;
    const updated = { ...customWeights, [ticker]: rawVal };
    setCustomWeights(updated);
    setStrategyMode("custom");
    runRiskCalculation(optData.tickers, updated);
  };

  // Toggle ticker in basket
  const toggleTicker = (t) => {
    let updated;
    if (selectedTickers.includes(t)) {
      if (selectedTickers.length <= 2) {
        setError("At least 2 assets are required.");
        return;
      }
      updated = selectedTickers.filter((item) => item !== t);
    } else {
      updated = [...selectedTickers, t];
    }
    setSelectedTickers(updated);
    runOptimization(updated);
  };

  // Add custom ticker symbol
  const handleAddTicker = (e) => {
    e.preventDefault();
    const sym = customTickerInput.trim().toUpperCase();
    if (!sym) return;
    if (!selectedTickers.includes(sym)) {
      const updated = [...selectedTickers, sym];
      setSelectedTickers(updated);
      setCustomTickerInput("");
      runOptimization(updated);
    }
  };

  return (
    <div className="portfolioDashboard">
      <div className="panel">
        <div className="portfolioHeader">
          <div>
            <h2>Quantitative Portfolio & Risk Engine</h2>
            <p className="subtext">
              Markowitz Modern Portfolio Theory (MPT), Efficient Frontier Optimization & Tail Risk Analytics (VaR/CVaR)
            </p>
          </div>
          <button
            type="button"
            className="actionBtn primary"
            onClick={() => runOptimization()}
            disabled={loading}
          >
            {loading ? "Optimizing Assets..." : "Recalculate Frontier"}
          </button>
        </div>

        {error && <div className="errorBanner">{error}</div>}

        {/* Asset Selection Bar */}
        <div className="portfolioControls">
          <div className="controlGroup">
            <label>Selected Asset Basket:</label>
            <div className="tickerPills">
              {AVAILABLE_TICKERS.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`tickerPill ${selectedTickers.includes(t) ? "active" : ""}`}
                  onClick={() => toggleTicker(t)}
                >
                  {selectedTickers.includes(t) ? "✓ " : "+ "}
                  {t}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleAddTicker} className="addTickerForm">
            <input
              type="text"
              placeholder="Add Ticker (e.g. AMZN)"
              value={customTickerInput}
              onChange={(e) => setCustomTickerInput(e.target.value)}
              className="tickerInput"
            />
            <button type="submit" className="actionBtn small">Add</button>
          </form>

          <div className="capitalControl">
            <label>Portfolio Value ($):</label>
            <input
              type="number"
              value={initialInvestment}
              onChange={(e) => setInitialInvestment(e.target.value)}
              step="5000"
              className="numInput"
            />
          </div>
        </div>

        {/* Strategy Selector Tabs */}
        <div className="strategyTabs">
          <button
            type="button"
            className={`strategyTab ${strategyMode === "max_sharpe" ? "active" : ""}`}
            onClick={() => handleStrategyChange("max_sharpe")}
          >
            ★ Max Sharpe Ratio (Optimal Risk/Return)
          </button>
          <button
            type="button"
            className={`strategyTab ${strategyMode === "min_vol" ? "active" : ""}`}
            onClick={() => handleStrategyChange("min_vol")}
          >
            🛡 Minimum Volatility (Capital Protection)
          </button>
          <button
            type="button"
            className={`strategyTab ${strategyMode === "equal" ? "active" : ""}`}
            onClick={() => handleStrategyChange("equal")}
          >
            ⚖ Equal Weight (1/N Benchmark)
          </button>
          <button
            type="button"
            className={`strategyTab ${strategyMode === "custom" ? "active" : ""}`}
            onClick={() => setStrategyMode("custom")}
          >
            ⚙ Custom Weights
          </button>
        </div>

        {/* Key Risk & Performance Metrics Grid */}
        {riskData && (
          <div className="metricsGrid">
            <div className="metricCard highlight">
              <span className="metricLabel">Expected Annual Return</span>
              <span className="metricValue positive">
                {riskData.annualized_return_pct >= 0 ? "+" : ""}
                {riskData.annualized_return_pct}%
              </span>
              <span className="metricNote">Annualized geometric compound</span>
            </div>

            <div className="metricCard">
              <span className="metricLabel">Annual Volatility (Risk)</span>
              <span className="metricValue">{riskData.annualized_volatility_pct}%</span>
              <span className="metricNote">Standard deviation of returns</span>
            </div>

            <div className="metricCard">
              <span className="metricLabel">Sharpe Ratio</span>
              <span className="metricValue cyan">{riskData.sharpe_ratio}</span>
              <span className="metricNote">Rf = {riskFreeRate}% risk-free baseline</span>
            </div>

            <div className="metricCard">
              <span className="metricLabel">Sortino Ratio</span>
              <span className="metricValue cyan">{riskData.sortino_ratio}</span>
              <span className="metricNote">Downside volatility penalization</span>
            </div>

            <div className="metricCard alert">
              <span className="metricLabel">1-Day VaR (95%)</span>
              <span className="metricValue negative">
                ${riskData.value_at_risk.var_95_parametric_usd.toLocaleString()}
              </span>
              <span className="metricNote">
                {riskData.value_at_risk.var_95_parametric_pct}% max normal loss
              </span>
            </div>

            <div className="metricCard alert">
              <span className="metricLabel">1-Day CVaR / Expected Shortfall</span>
              <span className="metricValue negative">
                ${riskData.conditional_var.cvar_95_usd.toLocaleString()}
              </span>
              <span className="metricNote">
                {riskData.conditional_var.cvar_95_pct}% average tail loss
              </span>
            </div>

            <div className="metricCard">
              <span className="metricLabel">Max Drawdown</span>
              <span className="metricValue warning">-{riskData.max_drawdown_pct}%</span>
              <span className="metricNote">Peak-to-trough historical drop</span>
            </div>

            <div className="metricCard">
              <span className="metricLabel">Portfolio Beta</span>
              <span className="metricValue">{riskData.portfolio_beta}</span>
              <span className="metricNote">Market covariance sensitivity</span>
            </div>
          </div>
        )}

        {/* Visual Efficient Frontier Diagram */}
        {optData && optData.efficient_frontier && (
          <div className="frontierSection">
            <div className="sectionHeader">
              <h3>Markowitz Efficient Frontier & Simulation Cloud</h3>
              <span className="subtext">Risk (Annual Volatility %) vs Expected Annual Return (%)</span>
            </div>

            <div className="frontierChartContainer">
              <svg viewBox="0 0 700 280" className="frontierSvg">
                {/* Axes and Grid Lines */}
                <line x1="50" y1="240" x2="670" y2="240" stroke="#334155" strokeWidth="1.5" />
                <line x1="50" y1="20" x2="50" y2="240" stroke="#334155" strokeWidth="1.5" />
                <text x="360" y="270" fill="#94a3b8" fontSize="12" textAnchor="middle">Annualized Risk / Volatility (%)</text>
                <text x="18" y="130" fill="#94a3b8" fontSize="12" textAnchor="middle" transform="rotate(-90, 18, 130)">Expected Return (%)</text>

                {/* Monte Carlo Simulated Cloud Points */}
                {optData.simulated_cloud?.map((pt, i) => {
                  const x = 50 + Math.min(600, (pt.volatility_pct / 60) * 580);
                  const y = 240 - Math.min(210, Math.max(10, (pt.return_pct / 60) * 190));
                  return (
                    <circle
                      key={`sim-${i}`}
                      cx={x}
                      cy={y}
                      r="2.5"
                      fill="#38bdf8"
                      opacity="0.3"
                    />
                  );
                })}

                {/* Efficient Frontier Curve Points */}
                {optData.efficient_frontier?.map((pt, i, arr) => {
                  if (i === 0) return null;
                  const prev = arr[i - 1];
                  const x1 = 50 + Math.min(600, (prev.volatility_pct / 60) * 580);
                  const y1 = 240 - Math.min(210, Math.max(10, (prev.return_pct / 60) * 190));
                  const x2 = 50 + Math.min(600, (pt.volatility_pct / 60) * 580);
                  const y2 = 240 - Math.min(210, Math.max(10, (pt.return_pct / 60) * 190));
                  return (
                    <line
                      key={`ef-${i}`}
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke="#10b981"
                      strokeWidth="2.5"
                    />
                  );
                })}

                {/* Max Sharpe Marker */}
                {(() => {
                  const ms = optData.max_sharpe_portfolio;
                  const x = 50 + Math.min(600, (ms.volatility_pct / 60) * 580);
                  const y = 240 - Math.min(210, Math.max(10, (ms.expected_return_pct / 60) * 190));
                  return (
                    <g key="max-sharpe-marker">
                      <circle cx={x} cy={y} r="7" fill="#f59e0b" stroke="#ffffff" strokeWidth="2" />
                      <text x={x + 10} y={y - 8} fill="#f59e0b" fontSize="12" fontWeight="bold">Max Sharpe ({ms.sharpe_ratio})</text>
                    </g>
                  );
                })()}

                {/* Min Volatility Marker */}
                {(() => {
                  const mv = optData.min_volatility_portfolio;
                  const x = 50 + Math.min(600, (mv.volatility_pct / 60) * 580);
                  const y = 240 - Math.min(210, Math.max(10, (mv.expected_return_pct / 60) * 190));
                  return (
                    <g key="min-vol-marker">
                      <circle cx={x} cy={y} r="6" fill="#38bdf8" stroke="#ffffff" strokeWidth="2" />
                      <text x={x + 10} y={y + 16} fill="#38bdf8" fontSize="11" fontWeight="bold">Min Vol ({mv.volatility_pct}%)</text>
                    </g>
                  );
                })()}

                {/* Individual Assets */}
                {optData.individual_assets?.map((a) => {
                  const x = 50 + Math.min(600, (a.annual_volatility_pct / 60) * 580);
                  const y = 240 - Math.min(210, Math.max(10, (a.annual_return_pct / 60) * 190));
                  return (
                    <g key={`asset-${a.ticker}`}>
                      <rect x={x - 4} y={y - 4} width="8" height="8" fill="#e2e8f0" rx="2" />
                      <text x={x + 6} y={y + 4} fill="#e2e8f0" fontSize="10">{a.ticker}</text>
                    </g>
                  );
                })}
              </svg>

              <div className="frontierLegend">
                <span><span className="dot line-green"></span> Efficient Frontier Curve</span>
                <span><span className="dot gold"></span> Maximum Sharpe Portfolio</span>
                <span><span className="dot cyan"></span> Minimum Volatility Portfolio</span>
                <span><span className="dot white"></span> Individual Assets</span>
                <span><span className="dot blue-dim"></span> Monte Carlo Simulation (1,000 runs)</span>
              </div>
            </div>
          </div>
        )}

        {/* Weights Sliders & Allocation Table */}
        {optData && (
          <div className="allocationSection">
            <div className="sectionHeader">
              <h3>Asset Allocation & Rebalancing Weights</h3>
              <span className="subtext">Adjust sliders below for instant real-time risk re-weighting</span>
            </div>

            <div className="weightSlidersList">
              {optData.tickers.map((t) => {
                const rawW = customWeights[t] !== undefined ? customWeights[t] : 0;
                const pct = Math.round(rawW * 100);
                return (
                  <div key={t} className="weightSliderRow">
                    <span className="assetBadge">{t}</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={rawW}
                      onChange={(e) => handleWeightSlider(t, e.target.value)}
                      className="weightSlider"
                    />
                    <span className="weightPct">{pct}%</span>
                    <div className="weightBarContainer">
                      <div className="weightBarFill" style={{ width: `${Math.min(100, pct)}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Correlation Matrix Heatmap */}
        {optData && optData.correlation_matrix && (
          <div className="correlationSection">
            <div className="sectionHeader">
              <h3>Cross-Asset Correlation Matrix</h3>
              <span className="subtext">Lower correlation values (&lt;0.5) offer superior diversification benefits</span>
            </div>

            <div className="tableWrapper">
              <table className="dataTable correlationTable">
                <thead>
                  <tr>
                    <th>Asset</th>
                    {optData.tickers.map((t) => (
                      <th key={t} className="center">{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {optData.tickers.map((rowTicker) => (
                    <tr key={rowTicker}>
                      <td className="bold">{rowTicker}</td>
                      {optData.tickers.map((colTicker) => {
                        const val = optData.correlation_matrix[rowTicker]?.[colTicker] ?? 1.0;
                        const isSelf = rowTicker === colTicker;
                        const bgOpacity = Math.abs(val);
                        return (
                          <td
                            key={colTicker}
                            className="center corrCell"
                            style={{
                              backgroundColor: isSelf
                                ? "rgba(56, 189, 248, 0.25)"
                                : val > 0.6
                                ? `rgba(239, 68, 68, ${bgOpacity * 0.4})`
                                : `rgba(16, 185, 129, ${(1 - bgOpacity) * 0.4})`,
                            }}
                          >
                            {val.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
