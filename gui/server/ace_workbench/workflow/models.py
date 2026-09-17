"""Transport-independent workflow values and validated request contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class InputFile(RequestModel):
    path: str = Field(min_length=1, max_length=512)
    size: StrictInt = Field(ge=0, le=100 * 1024**3)


class BeginImport(RequestModel):
    files: list[InputFile] = Field(min_length=1, max_length=10000)


class Selection(RequestModel):
    candidate: str = Field(max_length=128)
    pipeline: str = Field(max_length=64)
    answers: dict[str, Any] = Field(default_factory=dict)


class Setup(Selection):
    destination: str = Field(max_length=64)  # "new" or registered workspace ID
    name: str = Field(default="", max_length=100)


class Preflight(RequestModel):
    workspace: str = Field(max_length=64)
    configuration: str = Field(max_length=512)


class Launch(RequestModel):
    plan: str = Field(pattern=r"^[a-f0-9]{32}$")


@dataclass
class Candidate:
    id: str
    format: str
    label: str
    directory: str
    files: list[str]
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Question:
    key: str
    label: str
    kind: str = "text"
    help: str = ""
    default: Any = None
    choices: list[dict[str, str]] = field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    required: bool = True

    def to_dict(self) -> dict:
        return asdict(self)
