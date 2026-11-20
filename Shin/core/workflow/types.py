"""Workflow Types for Shin DAG Execution Engine.
Inspired by OpenJarvis architecture.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class NodeType(str, Enum):
    ACTION = "action"          # Direct command/tool execution
    LLM = "llm"                # LLM reasoning or text generation
    CONDITION = "condition"    # Branching decision predicate
    LOOP = "loop"              # Bounded iteration over items
    TERMINAL = "terminal"      # Terminal/aggregation step


@dataclass
class WorkflowNode:
    """Represents a discrete executable unit in a WorkflowGraph."""
    id: str
    node_type: NodeType = NodeType.ACTION
    action: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    condition_expr: Optional[str] = None  # Key in previous outputs or python expression
    timeout_seconds: float = 30.0
    max_retries: int = 1
    description: str = ""


@dataclass
class WorkflowStepResult:
    """Outcome of a single node's execution."""
    node_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class WorkflowResult:
    """Aggregated output and telemetry for an entire workflow run."""
    workflow_name: str
    success: bool
    final_output: Any = None
    steps: Dict[str, WorkflowStepResult] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    error: Optional[str] = None
