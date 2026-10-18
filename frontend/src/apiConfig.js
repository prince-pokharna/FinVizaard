export const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (typeof window !== "undefined" && window.location.port === "5173"
    ? "http://127.0.0.1:8000"
    : "");

export const WS_BASE_URL =
  import.meta.env.VITE_WS_URL ||
  (typeof window !== "undefined" && window.location.port === "5173"
    ? "ws://127.0.0.1:8000"
    : (typeof window !== "undefined" && window.location.protocol === "https:"
        ? `wss://${window.location.host}`
        : `ws://${typeof window !== "undefined" ? window.location.host : "127.0.0.1:8000"}`));
