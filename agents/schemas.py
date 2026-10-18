"""Pydantic schemas for agent I/O and persisted records.

Three layers, never conflated:
  1. Analyst LLM output   -- AnalystOutputBase subclasses. The only thing an analyst call is
                             constrained to produce.
  2. PM LLM output        -- PortfolioManagerOutput. The PM never re-emits agent_signals itself.
  3. Persisted records    -- VerdictRecord, LLMCallTrace. Assembled in Python by the
                             orchestrator, never emitted directly by an LLM call.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Signal = Literal["bullish", "neutral", "bearish"]


def _normalize_enum_str(value):
    """Lowercase/strip before Literal validation runs. Anthropic's structured-output
    grammar constrains generation to the exact enum values in the schema, so drift is
    unlikely in practice -- this is a cheap defensive net, not a workaround for an
    observed failure. Must run as a `mode="before"` validator: once Literal validation
    fails, the call has already raised and there is no value left to normalize.
    """
    return value.strip().lower() if isinstance(value, str) else value


class AnalystOutputBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal: Signal
    confidence: float = Field(ge=0, le=1)
    drivers: list[str] = Field(max_length=3)

    @field_validator("signal", mode="before")
    @classmethod
    def _normalize_signal(cls, v):
        return _normalize_enum_str(v)


class FundamentalsOutput(AnalystOutputBase):
    pass


class TechnicalsOutput(AnalystOutputBase):
    pass


class NewsSentimentOutput(AnalystOutputBase):
    cited_article_ids: list[str] = Field(default_factory=list)
    no_news_data: bool = False


class RiskOutput(AnalystOutputBase):
    risk_flags: list[str] = Field(default_factory=list)
    position_caution_level: Literal["low", "medium", "high"]

    @field_validator("position_caution_level", mode="before")
    @classmethod
    def _normalize_caution(cls, v):
        return _normalize_enum_str(v)


class PortfolioManagerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: Signal
    horizon_days: Literal[1, 5, 20]
    p_outperform: float = Field(ge=0, le=1)
    rationale: str
    key_drivers: list[str] = Field(max_length=5)

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalize_verdict(cls, v):
        return _normalize_enum_str(v)


# --- Persisted records, assembled by the orchestrator, never LLM output directly ---

AgentName = Literal["fundamentals", "technicals", "news_sentiment", "risk"]


class AgentSignal(BaseModel):
    agent: AgentName
    signal: Signal
    confidence: float
    drivers: list[str]
    extra: dict = Field(default_factory=dict)  # risk_flags/position_caution_level or cited_article_ids


class VerdictRecord(BaseModel):
    run_id: str
    ticker: str
    as_of_ts: datetime
    verdict: Signal
    horizon_days: Literal[1, 5, 20]
    p_outperform: float
    rationale: str
    key_drivers: list[str]
    cited_inputs: list[str]  # snapshot_id, content_hash, and any cited news article IDs
    agent_signals: list[AgentSignal]
    prompt_version: str  # e.g. "portfolio_manager@v1"
    model: str  # response.model -- the dated ID actually served, not the config alias
    input_hash: str  # == snapshot content_hash this verdict was built from
    cost_usd: float  # sum of this ticker's 5 calls
    latency_ms: int  # end-to-end wall time for this ticker's verdict
    cache_hit: bool = False
    is_fallback: bool = False  # True if any of the 5 underlying calls used a synthetic
                                # fallback output (refusal, API error, or repeated schema
                                # failure) -- without this flag a systemic failure (bad
                                # key, bad model ID) silently produces plausible-looking
                                # neutral verdicts that are indistinguishable from real ones


class LLMCallTrace(BaseModel):
    run_id: str
    ticker: str
    agent: str  # one of AgentName or "portfolio_manager"
    model: str  # response.model
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    retries: int
    schema_validation_failed: bool
    stop_reason: Optional[str]
    cache_key: str
    timestamp: datetime
