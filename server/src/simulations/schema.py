from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SimulationLaunchRequest(BaseModel):
    """Payload describing how a simulation run should be configured."""

    scenario: str = Field(default="worldsim_prime_timeline", description="Scenario identifier")
    start: date = Field(default=date(2025, 9, 20), description="Inclusive start date")
    until: date = Field(default=date(2030, 9, 20), description="Inclusive end date")
    step: Literal["day", "week"] = Field(default="day")
    seed: int = Field(default=1337, description="Deterministic RNG seed")
    view: Literal["narrative", "concise", "mixed"] = Field(default="narrative")
    verbosity: Literal["quiet", "normal", "detailed"] = Field(default="normal")
    story_length: Literal["short", "medium", "long", "adaptive"] = Field(default="adaptive")
    story_tone: Literal["neutral", "drama", "casual", "journalistic"] = Field(default="neutral")
    max_lines: int = Field(default=80, ge=20, le=180)
    fast: bool = Field(default=True, description="Reduce console output while still generating files")
    interactive: bool = Field(default=False, description="Enable branching choices at end of day")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional client metadata")

    @model_validator(mode="after")
    def _validate_range(self) -> "SimulationLaunchRequest":
        if self.until < self.start:
            raise ValueError("until must be on or after start")
        return self

    @field_validator("max_lines")
    @classmethod
    def _clean_max_lines(cls, value: int) -> int:
        return int(value)


class SimulationRunStatus(BaseModel):
    """Represents the lifecycle state of a simulation run."""

    run_id: str
    scenario: str
    status: Literal["queued", "running", "completed", "failed"]
    submitted_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    parameters: SimulationLaunchRequest
    result: Optional[Dict[str, Any]] = None


__all__ = ["SimulationLaunchRequest", "SimulationRunStatus"]
