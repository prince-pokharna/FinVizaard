import { createChart } from "lightweight-charts";
import { useEffect, useRef } from "react";

export default function CandlestickChart({ data }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth || 700,
      height: 320,
      layout: {
        textColor: "#e2e8f0",
        background: { color: "#0f172a" }
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" }
      },
      rightPriceScale: {
        borderColor: "#334155"
      },
      timeScale: {
        borderColor: "#334155"
      }
    });

    const series = chart.addCandlestickSeries({
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444"
    });

    series.setData(Array.isArray(data) ? data : []);

    const handleResize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth || 700 });
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data]);

  return (
    <div className="panel">
      <h3>Candlestick Chart</h3>
      <div ref={containerRef} className="chartContainer" />
    </div>
  );
}

