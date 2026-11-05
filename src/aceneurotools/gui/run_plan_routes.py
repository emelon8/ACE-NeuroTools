"""Run-plan routes: turn reviewed runs into a plan and its reproducible commands.

Batch runs, Output script and supercomputer export all start here, so they share
one description of what will run and one way of writing the equivalent commands.
"""

from __future__ import annotations

from aceneurotools.gui import run_plan
from aceneurotools.gui.csv_projects import ProjectError
from aceneurotools.gui.routes import Feature, Route

MAX_ENTRIES = 500


def preview(context):
    """Build a plan from review tokens. Body: ``reviews`` (list), optional ``mode`` and ``max_concurrent``."""
    tokens = context.value("reviews")
    if not isinstance(tokens, list) or not tokens or not all(isinstance(token, str) for token in tokens):
        raise ProjectError("Review at least one experiment first.")
    if len(tokens) > MAX_ENTRIES:
        raise ProjectError(f"Plan at most {MAX_ENTRIES} runs at once.")
    mode = context.value("mode", "sequential")
    limit = context.value("max_concurrent", 1)
    reviews = [context.server.runs.reviewed(context.project, token) for token in tokens]
    plan = run_plan.new_plan(
        project_id=context.project.id,
        project_path=str(context.project.path),
        versions=context.project.digests,
        entries=[run_plan.entry_from_review(review) for review in reviews],
        mode=mode,
        max_concurrent=limit,
    )
    invocations = [
        run_plan.invocation(entry, project_path=str(context.project.path), data_path=review["data_path"])
        for entry, review in zip(plan["entries"], reviews)
    ]
    return {"plan": plan, "blockers": run_plan.blockers(plan), "invocations": invocations}


FEATURE = Feature(
    name="run-plan",
    routes=(Route("POST", "/api/run-plan/preview", preview, scope="project"),),
)
