from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    horizon_days: int = Field(default=30, ge=7, le=365)


class GoalPlanRequest(BaseModel):
    current_balance: float = Field(..., ge=0)
    monthly_contribution: float = Field(..., ge=0)
    target_amount: float = Field(..., ge=1)
    years: float = Field(..., ge=0.5, le=40)
    annual_return_mean: float = Field(default=0.08, ge=-0.5, le=0.8)
    annual_volatility: float = Field(default=0.16, ge=0.01, le=1.0)
    simulations: int = Field(default=5000, ge=500, le=20000)


class MacroSnapshot(BaseModel):
    as_of: date
    vix_close: float
    fed_funds_rate: float
    cpi_year_over_year: float


class LoginRequest(BaseModel):
    email: str
    name: str = "User"


class ProfileRequest(BaseModel):
    name: str
    email: str
    risk_tolerance: str = Field(default="balanced")
    goals: list[dict[str, object]] = Field(default_factory=list)


class PortfolioRequest(BaseModel):
    name: str
    assets: list[dict[str, object]]


class AllocationRequest(BaseModel):
    tickers: list[str] = Field(min_length=1, max_length=10)
    risk_tolerance: str = Field(default="balanced")


