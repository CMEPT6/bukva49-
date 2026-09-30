"""BUKVA-49: Единая точка входа и делегат к пакету src/bukva49.

Устраняет конфликт затенения пакета в корне репозитория (PEP 517 src-layout).
"""
from __future__ import annotations

import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parent / "src"
_pkg_dir = _src_root / "bukva49"
__path__ = [str(_pkg_dir)]

if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from bukva49.engine import (
    ALIASES,
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
from bukva49.pipeline import BukvaAgentPipeline, PipelineState
from bukva49.search import experiment, mutate, search
from bukva49.cli import main

__all__ = [
    "NAMES",
    "OPS",
    "DESCRIPTIONS",
    "ALIASES",
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
    "main",
]

if __name__ == "__main__":
    main()
