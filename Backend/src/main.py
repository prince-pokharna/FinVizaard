from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import data_ingestion
from . import hmm_model
from . import xgboost_model
from . import shap_explainer
from . import claude_narrator
from . import database
from . import sentiment_analyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist on startup
    conn = database.get_duckdb_connection()
    conn.close()
    yield


app = FastAPI(title="FinVizaard Backend", version="0.2.0", lifespan=lifespan)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Backend.src.main:app", host="0.0.0.0", port=8000, reload=True)


