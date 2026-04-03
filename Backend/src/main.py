from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from . import data_ingestion
from . import hmm_model
from . import xgboost_model
from . import shap_explainer
from . import claude_narrator
from . import database


app = FastAPI(title="ClearAlpha Backend", version="0.1.0")


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
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(req: IngestRequest) -> dict:
    try:
        n_rows = data_ingestion.ingest_tickers(
            tickers=req.tickers, start_date=req.start_date, end_date=req.end_date
        )
    except Exception as exc:  # pragma: no cover - basic guardrail
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"rows_ingested": n_rows}


@app.post("/predict")
async def predict(req: PredictRequest) -> dict:
    try:
        regime = hmm_model.predict_regime(req.ticker, req.as_of)
        price_pred = xgboost_model.predict_price(req.ticker, req.as_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ticker": req.ticker, "as_of": req.as_of, "regime": regime, "price_prediction": price_pred}


@app.post("/explain")
async def explain(req: ExplainRequest) -> dict:
    try:
        explanation = shap_explainer.explain_prediction(req.ticker, req.as_of)
        narrative = claude_narrator.narrate_explanation(explanation)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ticker": req.ticker, "as_of": req.as_of, "explanation": explanation, "narrative": narrative}


@app.get("/candles/{ticker}")
async def candles(ticker: str, limit: int = 300) -> dict:
    try:
        conn = database.get_duckdb_connection()
        try:
            data = database.fetch_candles(conn, ticker.strip().upper(), limit=limit)
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ticker": ticker.strip().upper(), "candles": data}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

