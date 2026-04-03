export default function ShapBarChart({ explanation }) {
  const items = Object.entries(explanation || {});
  const maxAbs = Math.max(1, ...items.map(([, v]) => Math.abs(v)));

  return (
    <div className="panel">
      <h3>SHAP Feature Importance</h3>
      {items.length === 0 ? (
        <p className="muted">Run Explain to see feature contributions.</p>
      ) : (
        <div className="bars">
          {items.map(([feature, value]) => {
            const pct = Math.min(100, (Math.abs(value) / maxAbs) * 100);
            const positive = value >= 0;
            return (
              <div className="barRow" key={feature}>
                <div className="barLabel">{feature}</div>
                <div className="barTrack">
                  <div
                    className={`barFill ${positive ? "pos" : "neg"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="barValue">{value.toFixed(4)}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

