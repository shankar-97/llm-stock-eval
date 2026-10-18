"""Shared call-and-trace wrapper every agent (analyst or portfolio manager) uses.

Handles the two documented ways Anthropic's structured-output call can come back
off-schema while still returning HTTP 200 (stop_reason == "max_tokens" or "refusal"),
plus malformed/out-of-range output that fails pydantic validation client-side. One
retry on truncation (higher max_tokens); any other failure falls back to a caller-
supplied neutral/low-confidence default so one bad call never crashes the whole run.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

from agents.schemas import LLMCallTrace

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_ATTEMPTS = 2  # initial try + 1 retry
MAX_TOKENS_BUMP = 1.5


async def call_agent(
    *,
    client: AsyncAnthropic,
    run_id: str,
    ticker: str,
    agent_name: str,
    model: str,
    prompt_version: str,
    system_prompt: str,
    user_payload: dict,
    output_model: type[T],
    max_tokens: int,
    cache_key: str,
    pricing: dict,
    fallback: T,
) -> tuple[T, LLMCallTrace]:
    user_content = json.dumps(user_payload, default=str)
    attempt_max_tokens = max_tokens
    retries = 0
    stop_reason: str | None = None
    schema_failed = False
    parsed: T | None = None
    model_served = model
    usage_input_tokens = 0
    usage_output_tokens = 0

    start = time.monotonic()
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = await client.messages.parse(
                model=model,
                max_tokens=attempt_max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                output_format=output_model,
            )
        except ValidationError:
            logger.warning("%s/%s: output failed schema validation (attempt %d)", agent_name, ticker, attempt)
            schema_failed = True
            stop_reason = "schema_validation_error"
            if attempt + 1 < MAX_ATTEMPTS:
                retries += 1
                continue
            break
        except Exception:
            logger.exception("%s/%s: API call failed (attempt %d)", agent_name, ticker, attempt)
            schema_failed = True
            stop_reason = "api_error"
            if attempt + 1 < MAX_ATTEMPTS:
                retries += 1
                continue
            break

        model_served = response.model
        usage_input_tokens = response.usage.input_tokens
        usage_output_tokens = response.usage.output_tokens
        stop_reason = response.stop_reason

        if stop_reason == "max_tokens" and attempt + 1 < MAX_ATTEMPTS:
            attempt_max_tokens = int(attempt_max_tokens * MAX_TOKENS_BUMP)
            retries += 1
            continue

        if stop_reason == "refusal":
            schema_failed = True
            break

        parsed = response.parsed_output
        if parsed is None:
            schema_failed = True
            break
        break  # success

    latency_ms = int((time.monotonic() - start) * 1000)
    price = pricing.get(model_served, {"input": 0.0, "output": 0.0})
    cost_usd = (usage_input_tokens / 1_000_000) * price["input"] + (
        usage_output_tokens / 1_000_000
    ) * price["output"]

    if parsed is None:
        parsed = fallback
        schema_failed = True

    trace = LLMCallTrace(
        run_id=run_id,
        ticker=ticker,
        agent=agent_name,
        model=model_served,
        prompt_version=prompt_version,
        input_tokens=usage_input_tokens,
        output_tokens=usage_output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        retries=retries,
        schema_validation_failed=schema_failed,
        stop_reason=stop_reason,
        cache_key=cache_key,
        timestamp=datetime.now(timezone.utc),
    )
    return parsed, trace
