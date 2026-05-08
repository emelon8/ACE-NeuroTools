from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO
import sys


@dataclass(frozen=True)
class ErrorContext:
    """Structured metadata attached to user-facing errors."""

    stage: str | None = None
    line_num: int | None = None
    project_path: str | Path | None = None
    data_path: str | Path | None = None
    hint: str | None = None


class AceNeuroError(Exception):
    """Base exception with optional structured context."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        line_num: int | None = None,
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.context = ErrorContext(
            stage=stage,
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            hint=hint,
        )


class ConfigurationError(AceNeuroError):
    """Invalid configuration parameters or missing config files."""


class DataNotFoundError(AceNeuroError):
    """Expected data/resource was not found."""


class DataFormatError(AceNeuroError):
    """Data exists but does not match expected format."""


class PipelineExecutionError(AceNeuroError):
    """A pipeline stage failed due to an underlying runtime exception."""


# Backward-compatible aliases used across existing modules.
class ExperimentAnalysisError(AceNeuroError):
    """Legacy base exception alias for backwards compatibility."""


class DataImportError(DataNotFoundError):
    """Failed to load raw data or metadata."""


class ProcessingError(PipelineExecutionError):
    """Error during signal/video processing algorithms (CaImAn, filtering, etc)."""


class DataIntegrityError(DataFormatError):
    """Issues with data shape, corrupted files, or NaN/Inf values."""


def format_error_message(error: BaseException, *, include_cause: bool = False) -> str:
    """Create concise, actionable error output for CLI users."""
    header = f"{error.__class__.__name__}: {error}"
    lines = [header]
    if isinstance(error, AceNeuroError):
        ctx = error.context
        details: list[str] = []
        if ctx.stage:
            details.append(f"stage={ctx.stage}")
        if ctx.line_num is not None:
            details.append(f"line_num={ctx.line_num}")
        if ctx.project_path is not None:
            details.append(f"project_path={ctx.project_path}")
        if ctx.data_path is not None:
            details.append(f"data_path={ctx.data_path}")
        if details:
            lines.append("Context: " + ", ".join(details))
        if ctx.hint:
            lines.append("Next action: " + ctx.hint)
    if include_cause and getattr(error, "__cause__", None) is not None:
        lines.append(f"Cause: {error.__cause__}")
    return "\n".join(lines)


def print_cli_error(
    error: BaseException,
    *,
    stream: TextIO | None = None,
    include_cause: bool = False,
) -> None:
    """Print consistent error output for CLI entry points."""
    if stream is None:
        stream = sys.stderr
    print(format_error_message(error, include_cause=include_cause), file=stream)
