export default function ExplanationCard({ narrative, regime, pricePrediction, ticker }) {
  return (
    <div className="panel">
      <h3>AI Explanation</h3>
      <div className="kv">
        <span>Ticker</span>
        <strong>{ticker || "-"}</strong>
      </div>
      <div className="kv">
        <span>Regime</span>
        <strong>{regime || "-"}</strong>
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

