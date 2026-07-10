"""Pydantic models for pipeline data: trade ideas and structured scores."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class TradeIdea(BaseModel):
    ticker: str
    company: str
    source: str = Field(description="Where the idea came from (publication, event, filing)")
    thesis: str = Field(description="One-line long thesis")


class QuarterGrowth(BaseModel):
    quarter: str = Field(description="Fiscal quarter label, e.g. 'Q1 FY2026'")
    revenue_yoy_pct: Optional[float] = Field(
        description="Revenue growth YoY in percent; null if not found"
    )
    source: Literal["yfinance", "web"] = Field(
        default="web", description="Where the number came from"
    )


class GrowthAssessment(BaseModel):
    quarters: list[QuarterGrowth] = Field(description="Last 4 reported quarters, oldest first")
    trend: Literal["accelerating", "decelerating", "mixed"]
    subscore: int = Field(ge=0, le=10)
    rationale: str


class MoatAssessment(BaseModel):
    competitors: list[str] = Field(description="Top 3 competitors")
    positioning: str = Field(description="How the company stacks up against each")
    subscore: int = Field(ge=0, le=10)
    rationale: str


class Catalyst(BaseModel):
    description: str
    timeframe: str = Field(description="When within the next 12 months")
    classification: Literal["real", "hype", "priced_in"]
    rationale: str


class CatalystAssessment(BaseModel):
    catalysts: list[Catalyst]
    subscore: int = Field(ge=0, le=10)
    rationale: str


class BearCase(BaseModel):
    description: str
    severity: int = Field(ge=1, le=10)
    rebuttal: str = Field(description="Strongest counter to this bear case, or 'none'")


class BearAssessment(BaseModel):
    bear_cases: list[BearCase]
    penalty: int = Field(ge=0, le=15, description="Points to subtract from conviction, 0-15")
    rationale: str


class PriceTargets(BaseModel):
    bull: float = Field(gt=0, description="12-month bull-case price target")
    base: float = Field(gt=0, description="12-month base-case price target")
    bear: float = Field(gt=0, description="12-month bear-case price target")
    current: float = Field(gt=0, description="Current share price")
    rationale: str = Field(description="How the targets were derived")

    @model_validator(mode="after")
    def _ordered(self):
        if not (self.bear < self.base <= self.bull):
            raise ValueError("targets must satisfy bear < base <= bull")
        return self


class StockScores(BaseModel):
    ticker: str
    targets: PriceTargets
    growth: GrowthAssessment
    moat: MoatAssessment
    catalysts: CatalystAssessment
    bear: BearAssessment
    summary: str = Field(description="Two-sentence overall verdict")

    @property
    def upside_pct(self) -> float:
        return (self.targets.base / self.targets.current - 1) * 100

    @property
    def downside_pct(self) -> float:
        return (self.targets.bear / self.targets.current - 1) * 100

    @property
    def reward_risk(self) -> float:
        """Upside over downside magnitude. If bear target is above the current
        price (no modeled downside), return a large cap rather than inf."""
        if self.downside_pct >= 0:
            return 10.0
        return self.upside_pct / abs(self.downside_pct)
