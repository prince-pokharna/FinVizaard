import { createChart } from "lightweight-charts";
import { useEffect, useRef, useState, useMemo } from "react";
import { WS_BASE_URL } from "../apiConfig";

export default function CandlestickChart({ data, predictedPrice, ticker }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const wsRef = useRef(null);

  const [timeRange, setTimeRange] = useState("ALL");
  const [liveTick, setLiveTick] = useState(null);
  const [wsStatus, setWsStatus] = useState("disconnected"); // 'connecting', 'live', 'disconnected'

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

  // WebSocket Live Stream Connection
  useEffect(() => {
    if (!ticker) return;

    setWsStatus("connecting");
    setLiveTick(null);

    const wsUrl = `${WS_BASE_URL}/ws/stream/${ticker.trim().toUpperCase()}`;
    let socket;
    try {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setWsStatus("live");
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "tick") {
            setLiveTick(msg);
            // Real-time tick update to active candle
            if (seriesRef.current && cleanData.length > 0) {
              const lastCandle = cleanData[cleanData.length - 1];
              const updatedCandle = {
                time: lastCandle.time,
                open: lastCandle.open,
                high: Math.max(lastCandle.high, msg.price),
                low: Math.min(lastCandle.low, msg.price),
                close: msg.price,
              };
              seriesRef.current.update(updatedCandle);
            }
          }
        } catch (e) {
          console.warn("WS parse error:", e);
        }
      };

      socket.onerror = () => {
        setWsStatus("disconnected");
      };

      socket.onclose = () => {
        setWsStatus("disconnected");
      };
    } catch (err) {
      console.warn("WebSocket init error:", err);
      setWsStatus("disconnected");
    }

    return () => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [ticker, cleanData]);

  // Chart initialization
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
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h3 style={{ margin: 0 }}>{ticker || "Asset"} Interactive Chart</h3>
            <span className={`liveStreamBadge ${wsStatus}`}>
              <span className="liveStreamDot"></span>
              {wsStatus === "live" ? "LIVE STREAM" : wsStatus === "connecting" ? "CONNECTING..." : "OFFLINE"}
            </span>
          </div>

          {liveTick ? (
            <div className="liveTickBar">
              <span className="liveTickPrice">${liveTick.price.toFixed(2)}</span>
              <span className={`liveTickChange ${liveTick.change >= 0 ? "positive" : "negative"}`}>
                {liveTick.change >= 0 ? "+" : ""}{liveTick.change.toFixed(2)} ({liveTick.change_pct >= 0 ? "+" : ""}{liveTick.change_pct.toFixed(2)}%)
              </span>
              <span className="liveTickMeta">Bid: ${liveTick.bid.toFixed(2)} | Ask: ${liveTick.ask.toFixed(2)}</span>
              <span className="liveTickMeta">Vol: {liveTick.volume.toLocaleString()}</span>
              <span className={`liveTickSignal ${liveTick.signal}`}>{liveTick.signal.toUpperCase()}</span>
            </div>
          ) : lastCandle ? (
            <span className="lastCandleBadge">
              Last Close: <strong>${lastCandle.close.toFixed(2)}</strong> ({lastCandle.time})
            </span>
          ) : null}
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
