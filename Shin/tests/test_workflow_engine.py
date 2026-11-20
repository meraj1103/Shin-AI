"""Unit tests for Shin DAG Workflow Engine."""

import time
import pytest
from Shin.core.workflow.types import NodeType, WorkflowNode
from Shin.core.workflow.graph import WorkflowGraph
from Shin.core.workflow.engine import WorkflowEngine, LoopGuard


def test_linear_workflow_execution():
    """Verify sequential execution of dependent nodes."""
    graph = WorkflowGraph(name="LinearTest")
    graph.add_node(WorkflowNode(id="step1", action="fetch_data", params={"key": "test_input"}))
    graph.add_node(WorkflowNode(id="step2", action="process_data", params={"raw": "{{step1}}"}, dependencies=["step1"]))
    graph.add_node(WorkflowNode(id="step3", action="summarize", params={"processed": "{{step2}}"}, dependencies=["step2"]))

    def mock_action_handler(action, params, ctx):
        if action == "fetch_data":
            return {"data": [1, 2, 3]}
        elif action == "process_data":
            return {"sum": sum(params["raw"]["data"])}
        elif action == "summarize":
            return f"Total is {params['processed']['sum']}"
        return None

    engine = WorkflowEngine(action_handler=mock_action_handler)
    res = engine.run(graph)

    assert res.success is True
    assert res.workflow_name == "LinearTest"
    assert res.final_output == "Total is 6"
    assert len(res.steps) == 3
    assert res.steps["step1"].success is True
    assert res.steps["step2"].success is True
    assert res.steps["step3"].success is True


def test_parallel_stage_execution():
    """Verify independent nodes run in the same stage concurrently."""
    graph = WorkflowGraph(name="ParallelTest")
    graph.add_node(WorkflowNode(id="fetch_weather", action="weather", params={"city": "Delhi"}))
    graph.add_node(WorkflowNode(id="fetch_news", action="news", params={"topic": "tech"}))
    graph.add_node(WorkflowNode(id="combine", action="combine", params={"w": "{{fetch_weather}}", "n": "{{fetch_news}}"}, dependencies=["fetch_weather", "fetch_news"]))

    stages = graph.execution_stages()
    assert len(stages) == 2
    assert set(stages[0]) == {"fetch_weather", "fetch_news"}
    assert stages[1] == ["combine"]

    def slow_action_handler(action, params, ctx):
        time.sleep(0.05)
        return f"result_of_{action}"

    engine = WorkflowEngine(action_handler=slow_action_handler, max_parallel_workers=2)
    t0 = time.monotonic()
    res = engine.run(graph)
    dur = time.monotonic() - t0

    assert res.success is True
    assert len(res.steps) == 3
    # If parallel, stage 0 takes ~0.05s instead of ~0.10s
    assert dur < 0.25


def test_cycle_detection():
    """Verify cycle detection rejects invalid circular graphs."""
    graph = WorkflowGraph(name="CycleTest")
    graph.add_node(WorkflowNode(id="nodeA", action="a", dependencies=["nodeB"]))
    graph.add_node(WorkflowNode(id="nodeB", action="b", dependencies=["nodeA"]))

    valid, msg = graph.validate()
    assert valid is False
    assert "Cycle detected" in msg

    engine = WorkflowEngine()
    res = engine.run(graph)
    assert res.success is False
    assert "Graph validation failed" in res.error


def test_loop_guard():
    """Verify LoopGuard halts runaway iterative loops."""
    guard = LoopGuard(max_iterations=3)
    assert guard.tick("nodeX") is True
    assert guard.tick("nodeX") is True
    assert guard.tick("nodeX") is True
    assert guard.tick("nodeX") is False  # 4th tick triggers guard
