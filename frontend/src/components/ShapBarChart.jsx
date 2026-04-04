import { useMemo, useState } from "react";

function axisLabelText() {
  return "Impact on predicted price ($)";
}

function buildWaterfall(explanation, baseValue, predictedPrice) {
  const entries = Object.entries(explanation || {});
  if (baseValue == null || !Number.isFinite(baseValue)) return null;

  const pred =
    predictedPrice != null && Number.isFinite(predictedPrice)
      ? predictedPrice
      : baseValue + entries.reduce((s, [, v]) => s + v, 0);

  const sorted = [...entries].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const steps = [];
  let cum = baseValue;

  steps.push({
    key: "__base",
    label: "Baseline (SHAP expected value)",
    start: baseValue,
    delta: 0,
    end: baseValue,
    kind: "baseline"
  });

  for (const [name, delta] of sorted) {
    const start = cum;
    cum += delta;
    steps.push({
      key: name,
      label: name,
      start,
      delta,
      end: cum,
      kind: "feature"
    });
  }

  steps.push({
    key: "__pred",
    label: "Predicted next close",
    start: pred,
    delta: 0,
    end: pred,
    kind: "total"
  });

  return { steps };
}

function scaleBounds(steps) {
  const vals = [];
  for (const s of steps) {
    vals.push(s.start, s.end);
  }
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
  if (min === max) return { min: min - 1, max: max + 1 };
  const pad = (max - min) * 0.03;
  return { min: min - pad, max: max + pad };
}

export default function ShapBarChart({ explanation, baseValue, predictedPrice }) {
  const [mode, setMode] = useState("bar");

  const items = useMemo(() => Object.entries(explanation || {}), [explanation]);

  const maxAbs = useMemo(() => {
    if (!items.length) return 1;
    return Math.max(1e-9, ...items.map(([, v]) => Math.abs(v)));
  }, [items]);

  const wf = useMemo(
    () => buildWaterfall(explanation, baseValue, predictedPrice),
    [explanation, baseValue, predictedPrice]
  );

  const bounds = useMemo(() => (wf ? scaleBounds(wf.steps) : { min: 0, max: 1 }), [wf]);

  function posPct(x) {
    const r = bounds.max - bounds.min || 1;
    return ((x - bounds.min) / r) * 100;
  }

  function segmentStyle(start, end) {
    const left = Math.min(start, end);
    const right = Math.max(start, end);
    const l = posPct(left);
    const w = Math.max(posPct(right) - l, 0.4);
    return { left: `${l}%`, width: `${w}%` };
  }

  return (
    <div className="panel">
      <h3>SHAP explainability</h3>
      <p className="shapAxisLabel">{axisLabelText()}</p>
      <div className="shapViewToggle">
        <button
          type="button"
          className={mode === "bar" ? "active" : ""}
          onClick={() => setMode("bar")}
        >
          Bar chart
        </button>
        <span className="shapToggleSep">|</span>
        <button
          type="button"
          className={mode === "waterfall" ? "active" : ""}
          onClick={() => setMode("waterfall")}
        >
          Waterfall
        </button>
      </div>

      {items.length === 0 ? (
        <p className="muted">Run Explain to see feature contributions.</p>
      ) : mode === "bar" ? (
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
      ) : wf == null ? (
        <p className="muted">Waterfall needs a baseline from the API (run Explain).</p>
      ) : (
        <div className="waterfall">
          {wf.steps.map((step) => (
            <div className="wfRow" key={step.key}>
              <div className="wfLabel">{step.label}</div>
              <div className="wfTrack">
                {step.kind === "baseline" && (
                  <div
                    className="wfMarker"
                    style={{ left: `${posPct(step.end)}%` }}
                    title={`${step.end.toFixed(4)}`}
                  />
                )}
                {step.kind === "feature" && step.delta !== 0 && (
                  <div
                    className={`wfBar ${step.delta >= 0 ? "pos" : "neg"}`}
                    style={segmentStyle(step.start, step.end)}
                    title={`${step.start.toFixed(4)} → ${step.end.toFixed(4)}`}
                  />
                )}
                {step.kind === "total" && (
                  <div
                    className="wfMarker wfMarkerAccent"
                    style={{ left: `${posPct(step.end)}%` }}
                    title={`${step.end.toFixed(4)}`}
                  />
                )}
              </div>
              <div className="wfValues">
                {step.kind === "feature" ? (
                  <>
                    <span className="wfDelta">{step.delta >= 0 ? "+" : ""}{step.delta.toFixed(4)}</span>
                    <span className="wfEnd">{step.end.toFixed(4)}</span>
                  </>
                ) : (
                  <span className="wfEnd">{step.end.toFixed(4)}</span>
                )}
              </div>
            </div>
          ))}
          <p className="muted wfHint">
            Bars show each feature&apos;s push on the prediction; markers show baseline expected value and
            final predicted next close (green / red: #22c55e / #ef4444).
          </p>
        </div>
      )}
    </div>
  );
}
