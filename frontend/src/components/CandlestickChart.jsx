import { createChart } from "lightweight-charts";
import { useEffect, useRef, useState, useMemo } from "react";

export default function CandlestickChart({ data, predictedPrice, ticker }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const [timeRange, setTimeRange] = useState("ALL");

  // Deduplicate and sort data strictly ascending by time
  const cleanData = useMemo(() => {
    if (!Array.isArray(data) || !data.length) return [];
    const map = new Map();
    for (const d of data) {
      if (d && d.time && d.close != null) {
        map.set(d.time, {
          time: d.time,
          open: Number(d.open),
          high: Number(d.high),
          low: Number(d.low),
          close: Number(d.close),
          volume: Number(d.volume || 0),
        });
      }
    }
    const arr = Array.from(map.values());
    arr.sort((a, b) => (a.time > b.time ? 1 : a.time < b.time ? -1 : 0));
    return arr;
  }, [data]);

  useEffect(() => {
    if (!containerRef.current) return;

    // Clean container before re-creating
    containerRef.current.innerHTML = "";

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth || 700,
      height: 380,
      layout: {
        textColor: "#94a3b8",
        background: { color: "#0b1220" },
        fontSize: 12,
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: {
        vertLine: { color: "#38bdf8", width: 1, style: 3 },
        horzLine: { color: "#38bdf8", width: 1, style: 3 },
      },
      rightPriceScale: {
        borderColor: "#334155",
        scaleMargins: {
          top: 0.1,
          bottom: 0.25, // Leaves bottom space for volume histogram
        },
      },
      timeScale: {
        borderColor: "#334155",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // 1. Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#f87171",
    });
    seriesRef.current = candleSeries;

    candleSeries.setData(cleanData);

    // 2. Volume series at bottom
    const volumeData = cleanData.map((d) => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? "rgba(16, 185, 129, 0.35)" : "rgba(239, 68, 68, 0.35)",
    }));

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "", // Overlay on separate internal scale
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });
    volumeSeries.setData(volumeData);

    // 3. Predicted next close line if available
    if (predictedPrice != null && Number.isFinite(predictedPrice)) {
      candleSeries.createPriceLine({
        price: Number(predictedPrice),
        color: "#38bdf8",
        lineWidth: 2,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: "Target Forecast",
      });
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth || 700 });
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [cleanData, predictedPrice]);

  // Handle zoom range
  const handleRange = (range) => {
    setTimeRange(range);
    if (!chartRef.current || !cleanData.length) return;
    const total = cleanData.length;
    let sliceCount = total;
    if (range === "1M") sliceCount = Math.min(total, 22);
    else if (range === "3M") sliceCount = Math.min(total, 66);
    else if (range === "6M") sliceCount = Math.min(total, 130);
    else if (range === "1Y") sliceCount = Math.min(total, 252);

    if (range === "ALL") {
      chartRef.current.timeScale().fitContent();
    } else {
      const fromIdx = Math.max(0, total - sliceCount);
      const fromTime = cleanData[fromIdx].time;
      const toTime = cleanData[total - 1].time;
      chartRef.current.timeScale().setVisibleRange({ from: fromTime, to: toTime });
    }
  };

  const lastCandle = cleanData[cleanData.length - 1];

  return (
    <div className="panel chartPanel">
      <div className="chartHeader">
        <div>
          <h3>{ticker || "Asset"} Interactive Chart</h3>
          {lastCandle && (
            <span className="lastCandleBadge">
              Last Close: <strong>${lastCandle.close.toFixed(2)}</strong> ({lastCandle.time})
            </span>
          )}
        </div>
        <div className="rangeSelector">
          {["1M", "3M", "6M", "1Y", "ALL"].map((r) => (
            <button
              key={r}
              type="button"
              className={`rangeBtn ${timeRange === r ? "active" : ""}`}
              onClick={() => handleRange(r)}
            >
              {r}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="chartContainer" />
      <div className="chartLegend">
        <span><i className="legendDot green"></i> Bullish Session</span>
        <span><i className="legendDot red"></i> Bearish Session</span>
        <span><i className="legendDot cyan"></i> AI Target Forecast</span>
        <span><i className="legendDot volume"></i> Volume Histogram</span>
      </div>
    </div>
  );
}
