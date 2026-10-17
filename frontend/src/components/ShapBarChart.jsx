import { useMemo, useState } from "react";

function axisLabelText() {
  return "Impact on next-day predicted close ($ USD relative to baseline)";
}

export default function ShapBarChart({
  explanation,
  baseValue,
  predictedPrice,
  featureColumns,
  featureMetadata,
}) {
  const [mode, setMode] = useState("bar");
  const [sortOrder, setSortOrder] = useState("abs"); // 'abs', 'pos', 'neg'

  const meta = featureMetadata || {};

  // Build raw list of [featureName, value]
  const rawItems = useMemo(() => {
    const exp = explanation || {};
    if (Array.isArray(featureColumns) && featureColumns.length) {
      return featureColumns.map((k) => [k, typeof exp[k] === "number" ? exp[k] : 0]);
    }
    return Object.entries(exp);
  }, [explanation, featureColumns]);

  // Sort items
  const items = useMemo(() => {
    const list = [...rawItems];
    if (sortOrder === "abs") {
      list.sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    } else if (sortOrder === "pos") {
      list.sort((a, b) => b[1] - a[1]);
    } else if (sortOrder === "neg") {
      list.sort((a, b) => a[1] - b[1]);
    }
    return list;
  }, [rawItems, sortOrder]);

  const maxAbs = useMemo(() => {
    if (!items.length) return 1;
    return Math.max(1e-9, ...items.map(([, v]) => Math.abs(v)));
  }, [items]);

  // Waterfall steps
  const wf = useMemo(() => {
    if (baseValue == null || !Number.isFinite(baseValue)) return null;
    const sorted = [...rawItems].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    const pred =
      predictedPrice != null && Number.isFinite(predictedPrice)
        ? predictedPrice
        : baseValue + sorted.reduce((s, [, v]) => s + v, 0);

    const steps = [];
    let cum = baseValue;

    steps.push({
      key: "__base",
      label: "Baseline Model Prior",
      desc: "Historical expected target mean",
      start: baseValue,
      delta: 0,
      end: baseValue,
      kind: "baseline",
    });

    for (const [name, delta] of sorted) {
      const start = cum;
      cum += delta;
      steps.push({
        key: name,
        label: meta[name]?.label || name,
        techName: name,
        desc: meta[name]?.desc || "",
        start,
        delta,
        end: cum,
        kind: "feature",
      });
    }

    steps.push({
      key: "__pred",
      label: "Final Predicted Next Close",
      desc: "Sum of baseline and local SHAP attributions",
      start: pred,
      delta: 0,
      end: pred,
      kind: "total",
    });

    return { steps };
  }, [rawItems, baseValue, predictedPrice, meta]);

  const bounds = useMemo(() => {
    if (!wf) return { min: 0, max: 1 };
    const vals = [];
    for (const s of wf.steps) {
      vals.push(s.start, s.end);
    }
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    if (!Number.isFinite(min) || !Number.isFinite(max)) return { min: 0, max: 1 };
    if (min === max) return { min: min - 1, max: max + 1 };
    const pad = (max - min) * 0.04;
    return { min: min - pad, max: max + pad };
  }, [wf]);

  function posPct(x) {
    const r = bounds.max - bounds.min || 1;
    return ((x - bounds.min) / r) * 100;
  }

  function segmentStyle(start, end) {
    const left = Math.min(start, end);
    const right = Math.max(start, end);
    const l = posPct(left);
    const w = Math.max(posPct(right) - l, 0.5);
    return { left: `${l}%`, width: `${w}%` };
  }

  return (
    <div className="panel shapPanel">
      <div className="shapHeader">
        <div>
          <h3>SHAP Feature Attribution & Explainability</h3>
          <p className="shapAxisLabel">{axisLabelText()}</p>
        </div>
        <div className="shapControlsRow">
          <div className="shapSortSelector">
            <span className="controlLabel">Sort:</span>
            <button
              type="button"
              className={sortOrder === "abs" ? "active" : ""}
              onClick={() => setSortOrder("abs")}
            >
              |Magnitude|
            </button>
            <button
              type="button"
              className={sortOrder === "pos" ? "active" : ""}
              onClick={() => setSortOrder("pos")}
            >
              Positive First
            </button>
            <button
              type="button"
              className={sortOrder === "neg" ? "active" : ""}
              onClick={() => setSortOrder("neg")}
            >
              Negative First
            </button>
          </div>

          <div className="shapViewToggle">
            <button
              type="button"
              className={mode === "bar" ? "active" : ""}
              onClick={() => setMode("bar")}
            >
              📊 Bar Chart
            </button>
            <button
              type="button"
              className={mode === "waterfall" ? "active" : ""}
              onClick={() => setMode("waterfall")}
            >
              🌊 Waterfall
            </button>
          </div>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="emptyState">
          <p className="muted">
            Run &quot;Explain&quot; or &quot;Run Full Analysis&quot; to compute exact TreeExplainer SHAP contributions.
          </p>
        </div>
      ) : mode === "bar" ? (
        <div className="barsContainer">
          <div className="barsGrid">
            {items.map(([feature, value]) => {
              const pct = Math.min(100, (Math.abs(value) / maxAbs) * 100);
              const positive = value >= 0;
              const fMeta = meta[feature] || {};
              const friendlyLabel = fMeta.label || feature.replace("_", " ");

              return (
                <div className="barRow" key={feature} title={fMeta.desc || feature}>
                  <div className="barInfo">
                    <span className="barFriendly">{friendlyLabel}</span>
                    <span className="barTechCode">{feature}</span>
                  </div>
                  <div className="barTrack">
                    <div
                      className={`barFill ${positive ? "pos" : "neg"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className={`barValue ${positive ? "valPos" : "valNeg"}`}>
                    {positive ? `+${value.toFixed(4)}` : value.toFixed(4)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : wf == null ? (
        <div className="emptyState">
          <p className="muted">Waterfall requires baseline calculation from backend. Run Explain.</p>
        </div>
      ) : (
        <div className="waterfall">
          <div className="wfSummaryBanner">
            <span>
              Baseline Expected Value: <strong>${baseValue?.toFixed(2)}</strong>
            </span>
            <span>→</span>
            <span>
              Predicted Next Close: <strong>${predictedPrice?.toFixed(2)}</strong>
            </span>
          </div>

          {wf.steps.map((step) => (
            <div className="wfRow" key={step.key} title={step.desc || step.label}>
              <div className="wfLabelCol">
                <span className="wfLabelText">{step.label}</span>
                {step.techName && <span className="wfTechTag">{step.techName}</span>}
              </div>
              <div className="wfTrack">
                {step.kind === "baseline" && (
                  <div
                    className="wfMarker wfMarkerBase"
                    style={{ left: `${posPct(step.end)}%` }}
                    title={`Baseline: $${step.end.toFixed(2)}`}
                  />
                )}
                {step.kind === "feature" && step.delta !== 0 && (
                  <div
                    className={`wfBar ${step.delta >= 0 ? "pos" : "neg"}`}
                    style={segmentStyle(step.start, step.end)}
                    title={`${step.label}: ${step.start.toFixed(2)} → ${step.end.toFixed(2)}`}
                  />
                )}
                {step.kind === "total" && (
                  <div
                    className="wfMarker wfMarkerTotal"
                    style={{ left: `${posPct(step.end)}%` }}
                    title={`Final Target: $${step.end.toFixed(2)}`}
                  />
                )}
              </div>
              <div className="wfValues">
                {step.kind === "feature" ? (
                  <>
                    <span className={`wfDelta ${step.delta >= 0 ? "deltaPos" : "deltaNeg"}`}>
                      {step.delta >= 0 ? "+" : ""}
                      {step.delta.toFixed(3)}
                    </span>
                    <span className="wfEnd">${step.end.toFixed(2)}</span>
                  </>
                ) : (
                  <span className="wfEnd wfEndHighlight">${step.end.toFixed(2)}</span>
                )}
              </div>
            </div>
          ))}
          <p className="wfHint">
            Green bars indicate upward pressure pushing the price higher; red bars indicate downward pressure. Markers depict the starting prior baseline and final XGBoost output.
          </p>
        </div>
      )}
    </div>
  );
}
