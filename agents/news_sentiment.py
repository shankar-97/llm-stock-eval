from dataclasses import asdict

from anthropic import AsyncAnthropic

from agents.base_agent import call_agent
from agents.prompt_loader import load_prompt
from agents.schemas import LLMCallTrace, NewsSentimentOutput
from ingest.snapshot import Snapshot, agent_cache_key

PROMPT_VERSION = "news_sentiment@v1"
MAX_ARTICLES = 20  # newest-first cap to respect the agent's token budget


async def run_news_sentiment_agent(
    client: AsyncAnthropic,
    run_id: str,
    snapshot: Snapshot,
    model: str,
    token_budget: int,
    pricing: dict,
) -> tuple[NewsSentimentOutput, LLMCallTrace]:
    articles = sorted(snapshot.news, key=lambda a: a.published_at, reverse=True)[:MAX_ARTICLES]
    payload = {
        "ticker": snapshot.ticker,
        "as_of_ts": snapshot.as_of_ts,
        "no_news_data": snapshot.no_news_data,
        "articles": [asdict(a) for a in articles],
    }
    cache_key = agent_cache_key("news_sentiment", PROMPT_VERSION, model, payload)
    fallback = NewsSentimentOutput(
        signal="neutral",
        confidence=0.0,
        drivers=["fallback: agent call did not return a usable output"],
        cited_article_ids=[],
        no_news_data=snapshot.no_news_data,
    )
    return await call_agent(
        client=client,
        run_id=run_id,
        ticker=snapshot.ticker,
        agent_name="news_sentiment",
        model=model,
        prompt_version=PROMPT_VERSION,
        system_prompt=load_prompt(PROMPT_VERSION),
        user_payload=payload,
        output_model=NewsSentimentOutput,
        max_tokens=token_budget,
        cache_key=cache_key,
        pricing=pricing,
        fallback=fallback,
    )
