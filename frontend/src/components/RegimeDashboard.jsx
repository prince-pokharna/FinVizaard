import { useState, useEffect } from "react";
import axios from "axios";
import { API_BASE_URL } from "../apiConfig";

export default function RegimeDashboard({ ticker, apiBaseUrl = API_BASE_URL }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const cleanTicker = ticker ? ticker.trim().toUpperCase() : "AAPL";

  useEffect(() => {
    let isMounted = true;
    async function loadRegimes() {
      setLoading(true);
      setError("");
      try {
        const res = await axios.get(`${apiBaseUrl}/regimes/${cleanTicker}?limit=350`);
        if (isMounted) setData(res.data);
      } catch (err) {
        if (isMounted) {
          setError(err?.response?.data?.detail || "Failed to load regime analytics. Make sure data is ingested.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadRegimes();
    return () => {
      isMounted = false;
    };
  }, [cleanTicker, apiBaseUrl]);

  if (loading) {
    return (
      <div className="panel loadingPanel">
        <div className="spinner"></div>
        <p>Fitting Gaussian Hidden Markov Model (HMM) for {cleanTicker}...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel errorPanel">
        <h3>Regime Detection Offline</h3>
        <p className="errorText">{error}</p>
        <p className="muted">Ensure {cleanTicker} has been ingested in the controls bar.</p>
      </div>
    );
  }

  if (!data) return null;

  const currentRegime = data.current_regime || "unknown";
  const probs = data.regime_probabilities || {};
  const dist = data.distribution || {};
  const stats = data.stats || {};
  const trans = data.transition_matrix || {};
  const timeline = data.timeline || [];

  return (
    <div className="regimeDashboard">
      {/* Top Banner: Current Regime & Posterior Probabilities */}
      <div className="regimeHeaderGrid">
        <div className="panel regimeCurrentCard">
          <h4>Current Inferred Market Regime</h4>
          <div className="regimeCurrentBadgeRow">
            <span className={`regimeLargeBadge ${currentRegime}`}>
              {currentRegime.toUpperCase()}
            </span>
          </div>
          <p className="regimeDesc">
            {currentRegime === "bull" && "Positive drift with moderate volatility. Trend-following momentum favored."}
            {currentRegime === "sideways" && "Mean-reverting horizontal drift with normal volatility. Range-bound oscillations."}
            {currentRegime === "bear" && "Elevated volatility and negative return pressure. Defensive hedging signaled."}
          </p>
        </div>

        <div className="panel regimeProbsCard">
          <h4>State Posterior Probabilities</h4>
          <div className="probBarsList">
            {["bull", "sideways", "bear"].map((r) => {
              const p = probs[r] || 0;
              return (
                <div className="probRow" key={r}>
                  <div className="probHeader">
                    <span className="probLabel">{r.toUpperCase()}</span>
                    <span className="probVal">{p.toFixed(1)}%</span>
                  </div>
                  <div className="probTrack">
                    <div className={`probFill fill_${r}`} style={{ width: `${p}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Historical Distribution & Performance by Regime */}
      <div className="regimeStatsGrid">
        <div className="panel">
          <h4>Historical Regime Distribution</h4>
          <p className="muted subhead">Percentage of analyzed trading sessions spent in each state</p>
          <div className="distChartRow">
            {["bull", "sideways", "bear"].map((r) => (
              <div className="distCol" key={r}>
                <div className="distBarTrack">
                  <div className={`distBarFill fill_${r}`} style={{ height: `${dist[r] || 0}%` }} />
                </div>
                <span className="distLabel">{r.toUpperCase()}</span>
                <span className="distPct">{dist[r] || 0}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <h4>Regime Performance Profile</h4>
          <p className="muted subhead">Observed returns & volatility conditional on HMM state</p>
          <table className="regimeTable">
            <thead>
              <tr>
                <th>Regime</th>
                <th>Days Observed</th>
                <th>Mean Daily Return</th>
                <th>Annualized Volatility</th>
              </tr>
            </thead>
            <tbody>
              {["bull", "sideways", "bear"].map((r) => {
                const s = stats[r] || {};
                const meanRet = s.mean_daily_return_pct || 0;
                return (
                  <tr key={r}>
                    <td>
                      <span className={`pillSm ${r}`}>{r.toUpperCase()}</span>
                    </td>
                    <td>{s.days || 0} sessions</td>
                    <td className={meanRet >= 0 ? "textGreen" : "textRed"}>
                      {meanRet >= 0 ? "+" : ""}{meanRet.toFixed(3)}%
                    </td>
                    <td>{s.annualized_volatility_pct?.toFixed(1) || 0}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Markov Transition Matrix */}
      {Object.keys(trans).length > 0 && (
        <div className="panel">
          <h4>Markov State Transition Matrix</h4>
          <p className="muted subhead">Likelihood (%) of transitioning from Row State (t) to Column State (t+1)</p>
          <div className="matrixTableContainer">
            <table className="matrixTable">
              <thead>
                <tr>
                  <th>From (t) \ To (t+1)</th>
                  <th>BULL</th>
                  <th>SIDEWAYS</th>
                  <th>BEAR</th>
                </tr>
              </thead>
              <tbody>
                {["bull", "sideways", "bear"].map((from) => (
                  <tr key={from}>
                    <th>{from.toUpperCase()}</th>
                    {["bull", "sideways", "bear"].map((to) => {
                      const val = trans[from]?.[to] || 0;
                      return (
                        <td key={to} style={{ backgroundColor: `rgba(56, 189, 248, ${Math.min(0.6, val / 150)})` }}>
                          <strong>{val.toFixed(1)}%</strong>
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

      {/* Visual Regime Timeline */}
      {timeline.length > 0 && (
        <div className="panel">
          <h4>Historical Regime Shift Timeline (Past {timeline.length} Sessions)</h4>
          <p className="muted subhead">Continuous state mapping across historical price series</p>
          <div className="timelineRibbon">
            {timeline.map((point, i) => (
              <div
                key={i}
                className={`timelineBar fill_${point.regime}`}
                title={`${point.time}: ${point.regime.toUpperCase()} ($${point.close})`}
              />
            ))}
          </div>
          <div className="timelineLegend">
            <span><i className="legendDot green"></i> Bullish Regime</span>
            <span><i className="legendDot yellow"></i> Sideways Regime</span>
            <span><i className="legendDot red"></i> Bearish Regime</span>
          </div>
        </div>
      )}
    </div>
  );
}
