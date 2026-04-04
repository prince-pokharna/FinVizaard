import os
import json
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from newsapi import NewsApiClient

# Module-level cache: {(ticker, date): sentiment_dict}
_sentiment_cache = {}

def _load_env():
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")

def fetch_news(ticker: str) -> list[dict]:
    _load_env()
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return []
    
    newsapi = NewsApiClient(api_key=api_key)
    try:
        response = newsapi.get_everything(
            q=ticker,
            language='en',
            sort_by='publishedAt',
            page_size=10
        )
        articles = response.get('articles', [])
        return [
            {
                "title": a.get("title"),
                "description": a.get("description"),
                "publishedAt": a.get("publishedAt")
            }
            for a in articles
        ]
    except Exception:
        return []

def score_sentiment(articles: list[dict], ticker: str) -> dict:
    if not articles:
        return {
            "label": "neutral",
            "score": 0.0,
            "top_reason": "No news found",
            "article_count": 0
        }

    _load_env()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "label": "neutral",
            "score": 0.0,
            "top_reason": "Anthropic API key missing",
            "article_count": len(articles)
        }

    articles_text = "\n\n".join([
        f"Title: {a['title']}\nDescription: {a['description']}"
        for a in articles
    ])

    prompt = f"""Analyze the sentiment of the following news articles for the ticker {ticker}.
Return ONLY a JSON object with the following structure:
{{
  "label": "bullish" | "neutral" | "bearish",
  "score": float between -1 and 1,
  "top_reason": "one sentence summary of why this sentiment was chosen",
  "article_count": {len(articles)}
}}

Articles:
{articles_text}
"""

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            content = data.get("content", [])
            if not content:
                raise ValueError("Empty response from Anthropic")
            
            text = content[0].get("text", "").strip()
            # Try to find JSON in the response if there's preamble
            if "{" in text:
                text = text[text.find("{"):text.rfind("}")+1]
            
            sentiment = json.loads(text)
            return sentiment
    except Exception as e:
        return {
            "label": "neutral",
            "score": 0.0,
            "top_reason": f"Error scoring sentiment: {str(e)}",
            "article_count": len(articles)
        }

def get_ticker_sentiment(ticker: str) -> dict:
    date_str = datetime.now().strftime("%Y-%m-%d")
    cache_key = (ticker, date_str)
    
    if cache_key in _sentiment_cache:
        return _sentiment_cache[cache_key]
    
    articles = fetch_news(ticker)
    sentiment = score_sentiment(articles, ticker)
    
    _sentiment_cache[cache_key] = sentiment
    return sentiment
