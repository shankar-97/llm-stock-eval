from dataclasses import asdict

from anthropic import AsyncAnthropic

from agents.base_agent import call_agent
from agents.prompt_loader import load_prompt
from agents.schemas import LLMCallTrace, TechnicalsOutput
from ingest.snapshot import Snapshot, agent_cache_key

PROMPT_VERSION = "technicals@v1"


async def run_technicals_agent(
    client: AsyncAnthropic,
    run_id: str,
    snapshot: Snapshot,
    model: str,
    token_budget: int,
    pricing: dict,
) -> tuple[TechnicalsOutput, LLMCallTrace]:
    payload = {
        "ticker": snapshot.ticker,
        "sector": snapshot.sector,
        "technicals": asdict(snapshot.technicals),
    }
    cache_key = agent_cache_key("technicals", PROMPT_VERSION, model, payload)
    fallback = TechnicalsOutput(
        signal="neutral", confidence=0.0, drivers=["fallback: agent call did not return a usable output"]
    )
    return await call_agent(
        client=client,
        run_id=run_id,
        ticker=snapshot.ticker,
        agent_name="technicals",
        model=model,
        prompt_version=PROMPT_VERSION,
        system_prompt=load_prompt(PROMPT_VERSION),
        user_payload=payload,
        output_model=TechnicalsOutput,
        max_tokens=token_budget,
        cache_key=cache_key,
        pricing=pricing,
        fallback=fallback,
    )
