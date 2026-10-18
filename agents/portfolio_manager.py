from anthropic import AsyncAnthropic

from agents.base_agent import call_agent
from agents.prompt_loader import load_prompt
from agents.schemas import (
    FundamentalsOutput,
    LLMCallTrace,
    NewsSentimentOutput,
    PortfolioManagerOutput,
    RiskOutput,
    TechnicalsOutput,
)
from ingest.snapshot import agent_cache_key

PROMPT_VERSION = "portfolio_manager@v1"


async def run_portfolio_manager_agent(
    client: AsyncAnthropic,
    run_id: str,
    ticker: str,
    fundamentals: FundamentalsOutput,
    technicals: TechnicalsOutput,
    news_sentiment: NewsSentimentOutput,
    risk: RiskOutput,
    model: str,
    token_budget: int,
    pricing: dict,
) -> tuple[PortfolioManagerOutput, LLMCallTrace]:
    payload = {
        "ticker": ticker,
        "analyst_reports": {
            "fundamentals": fundamentals.model_dump(),
            "technicals": technicals.model_dump(),
            "news_sentiment": news_sentiment.model_dump(),
            "risk": risk.model_dump(),
        },
    }
    cache_key = agent_cache_key("portfolio_manager", PROMPT_VERSION, model, payload)
    fallback = PortfolioManagerOutput(
        verdict="neutral",
        horizon_days=5,
        p_outperform=0.5,
        rationale="fallback: agent call did not return a usable output",
        key_drivers=[],
    )
    return await call_agent(
        client=client,
        run_id=run_id,
        ticker=ticker,
        agent_name="portfolio_manager",
        model=model,
        prompt_version=PROMPT_VERSION,
        system_prompt=load_prompt(PROMPT_VERSION),
        user_payload=payload,
        output_model=PortfolioManagerOutput,
        max_tokens=token_budget,
        cache_key=cache_key,
        pricing=pricing,
        fallback=fallback,
    )
