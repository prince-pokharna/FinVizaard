import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import random
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import data_ingestion
from . import hmm_model
from . import xgboost_model
from . import shap_explainer
from . import claude_narrator
from . import database
from . import sentiment_analyzer
from . import portfolio


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist on startup
    conn = database.get_duckdb_connection()
    conn.close()
    yield


app = FastAPI(title="FinVizaard Backend", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    tickers: List[str]
    start_date: str
    end_date: str


class PredictRequest(BaseModel):
    ticker: str
    as_of: Optional[str] = None


class ExplainRequest(BaseModel):
    ticker: str
    as_of: Optional[str] = None


class PortfolioOptimizeRequest(BaseModel):
    tickers: List[str]
    risk_free_rate: Optional[float] = 0.04
    num_simulations: Optional[int] = 1200


class PortfolioRiskRequest(BaseModel):
    tickers: List[str]
    weights: Optional[Dict[str, float]] = None
    initial_investment: Optional[float] = 100000.0
    time_horizon_days: Optional[int] = 1


# Connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)


manager = ConnectionManager()


@app.get("/health")
async def health() -> dict:
    conn = database.get_duckdb_connection()
    try:
        tickers = database.get_stored_tickers(conn)
    finally:
        conn.close()
    return {
        "status": "ok",
        "system": "FinVizaard Quant Engine",
        "stored_tickers": tickers,
        "database": "DuckDB active",
        "streaming": "WebSockets active",
        "version": "0.3.0",
    }


@app.get("/tickers")
async def list_tickers() -> dict:
    conn = database.get_duckdb_connection()
    try:
        tickers = database.get_stored_tickers(conn)
    finally:
        conn.close()
    return {"tickers": tickers}


@app.post("/ingest")
async def ingest(req: IngestRequest) -> dict:
    try:
        n_rows = data_ingestion.ingest_tickers(
            tickers=req.tickers, start_date=req.start_date, end_date=req.end_date
        )

        # Fetch sentiment for each ticker and store in DuckDB
        conn = database.get_duckdb_connection()
        try:
            for ticker in req.tickers:
                sentiment = sentiment_analyzer.get_ticker_sentiment(ticker)
                database.upsert_sentiment(conn, ticker, sentiment)
        finally:
            conn.close()

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"rows_ingested": n_rows, "tickers": [t.strip().upper() for t in req.tickers]}


@app.post("/predict")
async def predict(req: PredictRequest) -> dict:
    try:
        ticker = req.ticker.strip().upper()
        regime = hmm_model.predict_regime(ticker, req.as_of)
        price_pred = xgboost_model.predict_price(ticker, req.as_of)
        forecast = xgboost_model.get_price_forecast(ticker, req.as_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "ticker": ticker,
        "as_of": req.as_of,
        "regime": regime,
        "price_prediction": price_pred,
        "forecast": forecast,
    }


@app.post("/explain")
async def explain(req: ExplainRequest) -> dict:
    try:
        ticker = req.ticker.strip().upper()
        result = shap_explainer.explain_prediction(ticker, req.as_of)
        explanation = result["explanation"]
        base_value = result["base_value"]
        predicted_value = result["predicted_value"]
        last_close = result["last_close"]
        regime = hmm_model.predict_regime(ticker, req.as_of)
        narrative = claude_narrator.narrate_explanation(
            ticker=ticker,
            regime=regime,
            predicted_next_close=predicted_value,
            last_close=last_close,
            explanation=explanation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "ticker": ticker,
        "as_of": req.as_of,
        "explanation": explanation,
        "narrative": narrative,
        "base_value": base_value,
        "predicted_next_close": predicted_value,
        "last_close": last_close,
        "regime": regime,
        "feature_columns": result["feature_columns"],
        "feature_metadata": result.get("feature_metadata", {}),
    }


@app.get("/sentiment/{ticker}")
async def get_sentiment_endpoint(ticker: str) -> dict:
    try:
        sentiment = sentiment_analyzer.get_ticker_sentiment(ticker.strip().upper())
        return sentiment
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/candles/{ticker}")
async def candles(ticker: str, limit: int = 350) -> dict:
    try:
        conn = database.get_duckdb_connection()
        try:
            data = database.fetch_candles(conn, ticker.strip().upper(), limit=limit)
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ticker": ticker.strip().upper(), "candles": data}


@app.get("/regimes/{ticker}")
async def regimes(ticker: str, limit: int = 350) -> dict:
    try:
        data = hmm_model.get_regime_analysis(ticker.strip().upper(), limit=limit)
        return data
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/backtest/{ticker}")
async def backtest(ticker: str, test_ratio: float = 0.2) -> dict:
    try:
        return xgboost_model.backtest_model(ticker.strip().upper(), test_ratio=test_ratio)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/compare")
async def compare(tickers: str = "AAPL,MSFT,NVDA,GOOGL,TSLA,SPY") -> dict:
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    results = []
    for t in ticker_list:
        try:
            forecast = xgboost_model.get_price_forecast(t)
            regime = hmm_model.predict_regime(t)
            sentiment = sentiment_analyzer.get_ticker_sentiment(t)
            results.append({
                "ticker": t,
                "last_close": forecast["last_close"],
                "predicted_close": forecast["predicted_close"],
                "predicted_change": forecast["predicted_change"],
                "predicted_change_pct": forecast["predicted_change_pct"],
                "direction": forecast["direction"],
                "regime": regime,
                "sentiment_score": sentiment.get("score", 0.0),
                "sentiment_label": sentiment.get("label", "neutral"),
                "ready": True,
            })
        except Exception:
            results.append({
                "ticker": t,
                "last_close": None,
                "predicted_close": None,
                "predicted_change": None,
                "predicted_change_pct": None,
                "direction": None,
                "regime": "Needs Ingestion",
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "ready": False,
            })
    return {"comparison": results}


# --- Pillar 4: Portfolio Optimization & Risk Endpoints ---

@app.post("/portfolio/optimize")
async def optimize_portfolio_endpoint(req: PortfolioOptimizeRequest) -> dict:
    try:
        return portfolio.optimize_portfolio(
            tickers=req.tickers,
            risk_free_rate=req.risk_free_rate if req.risk_free_rate is not None else 0.04,
            num_simulations=req.num_simulations if req.num_simulations is not None else 1200
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/portfolio/risk")
async def calculate_portfolio_risk_endpoint(req: PortfolioRiskRequest) -> dict:
    try:
        return portfolio.calculate_portfolio_risk(
            tickers=req.tickers,
            weights=req.weights,
            initial_investment=req.initial_investment if req.initial_investment is not None else 100000.0,
            time_horizon_days=req.time_horizon_days if req.time_horizon_days is not None else 1
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/portfolio/default")
async def default_portfolio() -> dict:
    try:
        return portfolio.optimize_portfolio(["AAPL", "MSFT"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# --- Pillar 3: Real-Time Live WebSocket Tick Stream ---

@app.websocket("/ws/stream/{ticker}")
async def websocket_stream(websocket: WebSocket, ticker: str):
    await manager.connect(websocket)
    clean_ticker = ticker.strip().upper()
    try:
        # Get baseline price
        conn = database.get_duckdb_connection()
        try:
            candles = database.fetch_candles(conn, clean_ticker, limit=1)
        finally:
            conn.close()

        current_price = float(candles[-1]["close"]) if candles else 100.0
        session_open = float(candles[-1]["open"]) if candles else current_price
        day_high = current_price
        day_low = current_price

        # Send initial handshake message
        await websocket.send_json({
            "type": "handshake",
            "ticker": clean_ticker,
            "base_price": round(current_price, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "connected"
        })

        # Continuous streaming loop
        while True:
            try:
                # Non-blocking check for client ping / commands
                client_raw = await asyncio.wait_for(websocket.receive_text(), timeout=1.8)
                client_msg = json.loads(client_raw)
                if client_msg.get("action") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    continue
            except asyncio.TimeoutError:
                pass  # normal tick trigger
            except json.JSONDecodeError:
                pass

            # Simulate realistic micro-volatility tick
            pct_move = random.gauss(0.0001, 0.0016)
            current_price = round(max(0.5, current_price * (1 + pct_move)), 2)
            day_high = max(day_high, current_price)
            day_low = min(day_low, current_price)
            change = round(current_price - session_open, 2)
            change_pct = round((change / session_open) * 100, 2)
            tick_volume = random.randint(100, 2400)
            spread = max(0.01, round(current_price * 0.0002, 2))
            bid = round(current_price - spread / 2, 2)
            ask = round(current_price + spread / 2, 2)

            tick_payload = {
                "type": "tick",
                "ticker": clean_ticker,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "price": current_price,
                "change": change,
                "change_pct": change_pct,
                "bid": bid,
                "ask": ask,
                "volume": tick_volume,
                "day_high": day_high,
                "day_low": day_low,
                "signal": "bullish" if change_pct > 0.3 else ("bearish" if change_pct < -0.3 else "neutral"),
            }
            await websocket.send_json(tick_payload)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Backend.src.main:app", host="0.0.0.0", port=8000, reload=True)
