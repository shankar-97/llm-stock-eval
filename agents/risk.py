from dataclasses import asdict

from anthropic import AsyncAnthropic

from agents.base_agent import call_agent
from agents.prompt_loader import load_prompt
from agents.schemas import LLMCallTrace, RiskOutput
from ingest.snapshot import Snapshot, agent_cache_key

PROMPT_VERSION = "risk@v1"


async def run_risk_agent(
    client: AsyncAnthropic,
    run_id: str,
    snapshot: Snapshot,
    model: str,
    token_budget: int,
    pricing: dict,
) -> tuple[RiskOutput, LLMCallTrace]:
    payload = {
        "ticker": snapshot.ticker,
        "sector": snapshot.sector,
        "risk_stats": asdict(snapshot.risk_stats),
    }
    cache_key = agent_cache_key("risk", PROMPT_VERSION, model, payload)
    fallback = RiskOutput(
        signal="neutral",
        confidence=0.0,
        drivers=["fallback: agent call did not return a usable output"],
        risk_flags=["agent_call_failed"],
        position_caution_level="medium",
    )
    return await call_agent(
        client=client,
        run_id=run_id,
        ticker=snapshot.ticker,
        agent_name="risk",
        model=model,
        prompt_version=PROMPT_VERSION,
        system_prompt=load_prompt(PROMPT_VERSION),
        user_payload=payload,
        output_model=RiskOutput,
        max_tokens=token_budget,
        cache_key=cache_key,
        pricing=pricing,
        fallback=fallback,
    )
