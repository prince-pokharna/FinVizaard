import { useState } from "react";

export default function ExplanationCard({
  narrative,
  regime,
  pricePrediction,
  ticker,
  sentiment,
  forecast,
}) {
  const [showArticles, setShowArticles] = useState(false);

  const articles = sentiment?.articles || [];
  const score = typeof sentiment?.score === "number" ? sentiment.score : 0.0;
  const label = sentiment?.label || "neutral";

  // Calculate percentage change
  let changePct = null;
  let changeSign = "";
  if (forecast && typeof forecast.predicted_change_pct === "number") {
    changePct = forecast.predicted_change_pct;
    changeSign = changePct >= 0 ? "+" : "";
  } else if (forecast && forecast.last_close && pricePrediction) {
    const rawPct = ((pricePrediction - forecast.last_close) / forecast.last_close) * 100;
    changePct = rawPct;
    changeSign = changePct >= 0 ? "+" : "";
  }

  // Sentiment gauge percentage (maps -1..+1 to 0..100%)
  const gaugePercent = Math.min(100, Math.max(0, ((score + 1) / 2) * 100));

  return (
    <div className="panel intelligencePanel">
      <div className="cardHeader">
        <h3>AI Market Intelligence</h3>
        <span className={`regimeBadge ${regime ? regime.toLowerCase() : "neutral"}`}>
          Regime: {regime ? regime.toUpperCase() : "PENDING"}
        </span>
      </div>

      <div className="forecastHero">
        <div className="forecastMain">
          <span className="forecastSub">XGBoost Forecast (Next Close)</span>
          <div className="forecastValueRow">
            <span className="forecastNumber">
              {Number.isFinite(pricePrediction) ? `$${pricePrediction.toFixed(2)}` : "—"}
            </span>
            {changePct != null && (
              <span className={`changeBadge ${changePct >= 0 ? "positive" : "negative"}`}>
                {changeSign}{changePct.toFixed(2)}%
              </span>
            )}
          </div>
          {forecast?.confidence_low != null && (
            <div className="confidenceInterval">
              Confidence Range: ${forecast.confidence_low.toFixed(2)} – ${forecast.confidence_high.toFixed(2)}
            </div>
          )}
        </div>
      </div>

      {/* Sentiment Meter */}
      <div className="sentimentSection">
        <div className="sentimentHeader">
          <span>News Sentiment Score</span>
          <span className={`sentimentPill ${label}`}>
            {label.toUpperCase()} ({score >= 0 ? `+${score.toFixed(2)}` : score.toFixed(2)})
          </span>
        </div>
        <div className="sentimentGaugeTrack">
          <div
            className="sentimentGaugeFill"
            style={{ width: `${gaugePercent}%` }}
          />
          <div className="gaugeMarkerCenter" title="Neutral (0.0)" />
        </div>
        <div className="gaugeScaleLabels">
          <span>Bearish (-1.0)</span>
          <span>Neutral (0.0)</span>
          <span>Bullish (+1.0)</span>
        </div>
        {sentiment?.top_reason && (
          <div className="sentimentReason">
            <span className="reasonLabel">Top Catalyst:</span> {sentiment.top_reason}
          </div>
        )}
      </div>

      {/* AI Synthesis Narrative */}
      <div className="narrativeBlock">
        <div className="narrativeHeader">
          <span className="narrativeIcon">🤖</span>
          <strong>Quantitative Narrative Synthesis</strong>
        </div>
        <p className="narrativeText">
          {narrative ||
            "Run 'Predict' and 'Explain' or click 'Run Full Analysis' to synthesize regime, predictive signals, and SHAP drivers."}
        </p>
      </div>

      {/* Live News Feed Accordion */}
      {articles.length > 0 && (
        <div className="newsFeedSection">
          <button
            type="button"
            className="toggleNewsBtn"
            onClick={() => setShowArticles(!showArticles)}
          >
            <span>📰 Live News Coverage ({articles.length} articles)</span>
            <span className="accordionArrow">{showArticles ? "▲" : "▼"}</span>
          </button>

          {showArticles && (
            <div className="newsList">
              {articles.map((item, idx) => (
                <a
                  key={idx}
                  href={item.url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="newsItem"
                >
                  <div className="newsMeta">
                    <span className="newsSource">{item.source || "Market News"}</span>
                    <span className="newsTime">
                      {item.publishedAt ? new Date(item.publishedAt).toLocaleDateString() : ""}
                    </span>
                  </div>
                  <div className="newsTitle">{item.title}</div>
                  {item.description && (
                    <div className="newsDesc">{item.description.slice(0, 140)}...</div>
                  )}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
