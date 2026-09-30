"""BUKVA-49: Zero-dependency neuro-symbolic cognitive pipeline & DSL.

A deterministic finite-state cognitive architecture based on the 7x7 matrix.
"""
from __future__ import annotations

from .engine import (
    DESCRIPTIONS,
    EVOLVED,
    FULL,
    NAMES,
    OPS,
    P297,
    Offer,
    ProgramError,
    State,
    Task,
    evaluate,
    execute,
    make_tasks,
    parse,
)
from .pipeline import BukvaAgentPipeline, PipelineState, TaskConstraints, TaskSpecification
from .search import experiment, mutate, search

__version__ = "0.7.3"
__all__ = [
    "NAMES",
    "OPS",
    "DESCRIPTIONS",
    "P297",
    "FULL",
    "EVOLVED",
    "Offer",
    "Task",
    "State",
    "ProgramError",
    "parse",
    "execute",
    "evaluate",
    "make_tasks",
    "mutate",
    "search",
    "experiment",
    "BukvaAgentPipeline",
    "PipelineState",
    "TaskConstraints",
    "TaskSpecification",
]
