export default function ExplanationCard({ narrative, regime, pricePrediction, ticker, sentiment }) {
  return (
    <div className="panel">
      <h3>AI Explanation</h3>
      <div className="kv">
        <span>Ticker</span>
        <strong>{ticker || "-"}</strong>
      </div>
      <div className="kv">
        <span>Regime</span>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
          <strong>{regime || "-"}</strong>
          {sentiment && (
            <span 
              className={`sentiment-pill ${sentiment.label}`}
              data-reason={sentiment.top_reason}
            >
              News: {sentiment.label} ({sentiment.score.toFixed(2)})
            </span>
          )}
        </div>
      </div>
      <div className="kv">
        <span>Predicted Next Close</span>
        <strong>{Number.isFinite(pricePrediction) ? pricePrediction.toFixed(2) : "-"}</strong>
      </div>
      <p className="narrative">
        {narrative || "Run Predict and Explain to generate a narrative for your model output."}
      </p>
    </div>
  );
}

