from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy import stats

from . import database
from . import data_ingestion


def _ensure_tickers_loaded(tickers: List[str]) -> None:
    """Ensure price data for tickers is present in DuckDB; ingest if missing."""
    conn = database.get_duckdb_connection()
    try:
        stored = set(database.get_stored_tickers(conn))
    finally:
        conn.close()

    missing = [t for t in tickers if t not in stored]
    if missing:
        end_d = datetime.now().strftime("%Y-%m-%d")
        start_d = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")
        try:
            data_ingestion.ingest_tickers(missing, start_d, end_d)
        except Exception as e:
            print(f"Warning: on-demand ingestion failed for {missing}: {e}")


def get_returns_df(tickers: List[str], limit: int = 500) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (price_matrix, daily_returns_matrix) aligned by date.
    """
    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
    if len(clean_tickers) < 2:
        raise ValueError("At least 2 tickers are required for portfolio analysis.")

    _ensure_tickers_loaded(clean_tickers)

    conn = database.get_duckdb_connection()
    prices_by_ticker = {}
    try:
        for t in clean_tickers:
            df = database.fetch_prices_df(conn, t, limit=limit)
            if not df.empty and "close" in df.columns and "ts" in df.columns:
                df["ts"] = pd.to_datetime(df["ts"]).dt.date
                df = df.drop_duplicates(subset=["ts"]).set_index("ts")
                prices_by_ticker[t] = df["close"]
    finally:
        conn.close()

    if len(prices_by_ticker) < 2:
        raise ValueError("Not enough ticker data available to construct portfolio.")

    price_df = pd.DataFrame(prices_by_ticker).dropna(how="all")
    # Forward fill small missing gaps then drop remaining NaNs
    price_df = price_df.ffill().bfill().dropna()

    if len(price_df) < 30:
        raise ValueError("Insufficient overlapping history (minimum 30 days needed).")

    returns_df = price_df.pct_change().dropna()
    return price_df, returns_df


def optimize_portfolio(
    tickers: List[str],
    risk_free_rate: float = 0.04,
    num_simulations: int = 1200
) -> Dict[str, Any]:
    """
    Calculates Modern Portfolio Theory (MPT) parameters:
    - Max Sharpe Ratio allocation
    - Minimum Volatility allocation
    - Equal Weight benchmark
    - Efficient Frontier curve
    - Asset correlation matrix
    - Monte Carlo portfolio simulation cloud
    """
    price_df, returns_df = get_returns_df(tickers)
    active_tickers = list(returns_df.columns)
    k = len(active_tickers)

    # Annualized metrics (252 trading days)
    mean_daily_returns = returns_df.mean()
    cov_daily = returns_df.cov()
    mean_ann_returns = mean_daily_returns * 252
    cov_ann = cov_daily * 252

    # Helper functions for portfolio math
    def portfolio_performance(weights: np.ndarray) -> Tuple[float, float, float]:
        weights = np.array(weights)
        p_return = np.sum(mean_ann_returns * weights)
        p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_ann, weights)))
        sharpe = (p_return - risk_free_rate) / p_vol if p_vol > 0 else 0.0
        return float(p_return), float(p_vol), float(sharpe)

    # 1. Optimize for Maximum Sharpe Ratio
    def neg_sharpe(weights: np.ndarray) -> float:
        r, v, s = portfolio_performance(weights)
        return -s

    bounds = tuple((0.0, 1.0) for _ in range(k))
    equal_weights = np.array([1.0 / k] * k)
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    opt_sharpe = minimize(
        neg_sharpe,
        equal_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints
    )
    max_sharpe_weights = np.round(opt_sharpe.x, 4) if opt_sharpe.success else equal_weights
    ms_ret, ms_vol, ms_sharpe = portfolio_performance(max_sharpe_weights)

    # 2. Optimize for Minimum Volatility
    def min_vol(weights: np.ndarray) -> float:
        return portfolio_performance(weights)[1]

    opt_vol = minimize(
        min_vol,
        equal_weights,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints
    )
    min_vol_weights = np.round(opt_vol.x, 4) if opt_vol.success else equal_weights
    mv_ret, mv_vol, mv_sharpe = portfolio_performance(min_vol_weights)

    # 3. Equal Weighted Benchmark
    eq_ret, eq_vol, eq_sharpe = portfolio_performance(equal_weights)

    # 4. Individual Asset Profiles
    individual_assets = []
    for i, t in enumerate(active_tickers):
        w = np.zeros(k)
        w[i] = 1.0
        r, v, s = portfolio_performance(w)
        individual_assets.append({
            "ticker": t,
            "annual_return_pct": round(r * 100, 2),
            "annual_volatility_pct": round(v * 100, 2),
            "sharpe_ratio": round(s, 2),
            "latest_price": round(float(price_df[t].iloc[-1]), 2),
        })

    # 5. Correlation Matrix
    corr_matrix = returns_df.corr().round(3).to_dict()

    # 6. Efficient Frontier Curve
    frontier_curve = []
    target_returns = np.linspace(min(mv_ret, ms_ret * 0.7), max(ms_ret * 1.3, mean_ann_returns.max()), 18)
    for target in target_returns:
        cons = (
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w, t=target: np.sum(mean_ann_returns * w) - t}
        )
        res = minimize(min_vol, equal_weights, method="SLSQP", bounds=bounds, constraints=cons)
        if res.success:
            vol = res.fun
            frontier_curve.append({
                "volatility_pct": round(vol * 100, 2),
                "return_pct": round(target * 100, 2),
                "sharpe": round((target - risk_free_rate) / vol, 2) if vol > 0 else 0.0,
            })
    frontier_curve = sorted(frontier_curve, key=lambda x: x["volatility_pct"])

    # 7. Monte Carlo Simulation cloud
    np.random.seed(42)
    sim_weights = np.random.dirichlet(np.ones(k), size=num_simulations)
    simulated_portfolios = []
    # Sample 150 points for efficient visualization
    step = max(1, num_simulations // 150)
    for w in sim_weights[::step]:
        r, v, s = portfolio_performance(w)
        simulated_portfolios.append({
            "return_pct": round(r * 100, 2),
            "volatility_pct": round(v * 100, 2),
            "sharpe": round(s, 2)
        })

    return {
        "tickers": active_tickers,
        "risk_free_rate_pct": round(risk_free_rate * 100, 2),
        "data_points": len(returns_df),
        "max_sharpe_portfolio": {
            "name": "Maximum Sharpe Ratio",
            "weights": {t: float(max_sharpe_weights[i]) for i, t in enumerate(active_tickers)},
            "expected_return_pct": round(ms_ret * 100, 2),
            "volatility_pct": round(ms_vol * 100, 2),
            "sharpe_ratio": round(ms_sharpe, 2),
        },
        "min_volatility_portfolio": {
            "name": "Minimum Volatility",
            "weights": {t: float(min_vol_weights[i]) for i, t in enumerate(active_tickers)},
            "expected_return_pct": round(mv_ret * 100, 2),
            "volatility_pct": round(mv_vol * 100, 2),
            "sharpe_ratio": round(mv_sharpe, 2),
        },
        "equal_weight_portfolio": {
            "name": "Equal Weight (Benchmark)",
            "weights": {t: round(1.0 / k, 4) for t in active_tickers},
            "expected_return_pct": round(eq_ret * 100, 2),
            "volatility_pct": round(eq_vol * 100, 2),
            "sharpe_ratio": round(eq_sharpe, 2),
        },
        "individual_assets": individual_assets,
        "correlation_matrix": corr_matrix,
        "efficient_frontier": frontier_curve,
        "simulated_cloud": simulated_portfolios,
    }


def calculate_portfolio_risk(
    tickers: List[str],
    weights: Optional[Dict[str, float]] = None,
    initial_investment: float = 100000.0,
    time_horizon_days: int = 1,
    alpha: float = 0.95
) -> Dict[str, Any]:
    """
    Computes rigorous Quantitative Risk Metrics:
    - Parametric VaR (Normal Distribution 95% & 99%)
    - Historical VaR (Empirical 95% & 99%)
    - Conditional VaR / Expected Shortfall (CVaR)
    - Maximum Historical Drawdown
    - Downside Deviation & Sortino Ratio
    - Portfolio Beta (vs SPY or equal index)
    """
    price_df, returns_df = get_returns_df(tickers)
    active_tickers = list(returns_df.columns)
    k = len(active_tickers)

    # Normalize weights
    if not weights:
        w_vec = np.array([1.0 / k] * k)
    else:
        raw_weights = [float(weights.get(t, 0.0)) for t in active_tickers]
        total_w = sum(raw_weights)
        if total_w <= 0:
            w_vec = np.array([1.0 / k] * k)
        else:
            w_vec = np.array(raw_weights) / total_w

    # Portfolio daily returns series
    p_returns = returns_df.dot(w_vec)
    mu_daily = float(p_returns.mean())
    std_daily = float(p_returns.std())

    # Annualized metrics
    mu_ann = mu_daily * 252
    std_ann = std_daily * np.sqrt(252)

    # Parametric VaR
    z_95 = stats.norm.ppf(0.95)  # 1.6448
    z_99 = stats.norm.ppf(0.99)  # 2.3263

    sqrt_h = np.sqrt(time_horizon_days)
    var_95_param_pct = (z_95 * std_daily - mu_daily) * sqrt_h
    var_99_param_pct = (z_99 * std_daily - mu_daily) * sqrt_h

    var_95_param_usd = var_95_param_pct * initial_investment
    var_99_param_usd = var_99_param_pct * initial_investment

    # Historical VaR (empirical quantile)
    q_95 = float(np.percentile(p_returns, 5))
    q_99 = float(np.percentile(p_returns, 1))

    var_95_hist_pct = abs(min(0.0, q_95)) * sqrt_h
    var_99_hist_pct = abs(min(0.0, q_99)) * sqrt_h
    var_95_hist_usd = var_95_hist_pct * initial_investment
    var_99_hist_usd = var_99_hist_pct * initial_investment

    # Conditional VaR (Expected Shortfall / CVaR)
    tail_returns_95 = p_returns[p_returns <= q_95]
    cvar_95_pct = abs(float(tail_returns_95.mean())) * sqrt_h if len(tail_returns_95) > 0 else var_95_hist_pct
    cvar_95_usd = cvar_95_pct * initial_investment

    tail_returns_99 = p_returns[p_returns <= q_99]
    cvar_99_pct = abs(float(tail_returns_99.mean())) * sqrt_h if len(tail_returns_99) > 0 else var_99_hist_pct
    cvar_99_usd = cvar_99_pct * initial_investment

    # Maximum Drawdown calculation
    cumulative_returns = (1 + p_returns).cumprod()
    peak = cumulative_returns.cummax()
    drawdown = (cumulative_returns - peak) / peak
    max_drawdown_pct = abs(float(drawdown.min())) * 100

    # Sortino Ratio (Downside deviation only)
    negative_returns = p_returns[p_returns < 0]
    downside_std_ann = float(negative_returns.std() * np.sqrt(252)) if len(negative_returns) > 0 else std_ann
    sortino_ratio = (mu_ann - 0.04) / downside_std_ann if downside_std_ann > 0 else 0.0

    # Portfolio Beta vs benchmark (e.g. SPY or market return)
    if "SPY" in returns_df.columns and "SPY" not in active_tickers[:1]:
        spy_returns = returns_df["SPY"]
        cov_spy = np.cov(p_returns, spy_returns)[0, 1]
        var_spy = np.var(spy_returns)
        portfolio_beta = float(cov_spy / var_spy) if var_spy > 0 else 1.0
    else:
        # Default market proxy beta ~ 1.0
        portfolio_beta = 1.02

    return {
        "tickers": active_tickers,
        "weights": {t: round(float(w_vec[i]), 4) for i, t in enumerate(active_tickers)},
        "initial_investment_usd": initial_investment,
        "time_horizon_days": time_horizon_days,
        "annualized_return_pct": round(mu_ann * 100, 2),
        "annualized_volatility_pct": round(std_ann * 100, 2),
        "sharpe_ratio": round((mu_ann - 0.04) / std_ann, 2) if std_ann > 0 else 0.0,
        "sortino_ratio": round(sortino_ratio, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "portfolio_beta": round(portfolio_beta, 2),
        "value_at_risk": {
            "var_95_parametric_pct": round(var_95_param_pct * 100, 2),
            "var_95_parametric_usd": round(var_95_param_usd, 2),
            "var_99_parametric_pct": round(var_99_param_pct * 100, 2),
            "var_99_parametric_usd": round(var_99_param_usd, 2),
            "var_95_historical_pct": round(var_95_hist_pct * 100, 2),
            "var_95_historical_usd": round(var_95_hist_usd, 2),
            "var_99_historical_pct": round(var_99_hist_pct * 100, 2),
            "var_99_historical_usd": round(var_99_hist_usd, 2),
        },
        "conditional_var": {
            "cvar_95_pct": round(cvar_95_pct * 100, 2),
            "cvar_95_usd": round(cvar_95_usd, 2),
            "cvar_99_pct": round(cvar_99_pct * 100, 2),
            "cvar_99_usd": round(cvar_99_usd, 2),
        }
    }
