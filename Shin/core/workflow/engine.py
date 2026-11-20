"""WorkflowEngine — Executes a WorkflowGraph in topological stages.
Supports parallel branch execution, loop guards, and automatic retries.
"""

from __future__ import annotations
import concurrent.futures
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from Shin.core.workflow.graph import WorkflowGraph
from Shin.core.workflow.types import (
    NodeType,
    WorkflowNode,
    WorkflowResult,
    WorkflowStepResult,
)

logger = logging.getLogger("shin.workflow")


class LoopGuard:
    """Guards against infinite loops during workflow DAG execution."""

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self._counts: Dict[str, int] = {}

    def tick(self, node_id: str) -> bool:
        """Increment count for node_id. Return True if safe, False if exceeded."""
        count = self._counts.get(node_id, 0) + 1
        self._counts[node_id] = count
        if count > self.max_iterations:
            logger.warning(
                f"[LoopGuard] Max iterations ({self.max_iterations}) exceeded for node '{node_id}'."
            )
            return False
        return True


class WorkflowEngine:
    """Executes DAG workflows with parallel stage support and safety guards."""

    def __init__(
        self,
        *,
        action_handler: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Any]] = None,
        max_parallel_workers: int = 4,
        max_loop_iterations: int = 10,
    ):
        self.action_handler = action_handler
        self.max_parallel_workers = max_parallel_workers
        self.max_loop_iterations = max_loop_iterations

    def run(
        self,
        graph: WorkflowGraph,
        initial_input: Any = None,
        context: Optional[Dict[str, Any]] = None,
        on_step_complete: Optional[Callable[[WorkflowStepResult], None]] = None,
    ) -> WorkflowResult:
        """Execute the DAG graph end-to-end."""
        start_time = time.monotonic()
        valid, msg = graph.validate()
        if not valid:
            return WorkflowResult(
                workflow_name=graph.name,
                success=False,
                error=f"Graph validation failed: {msg}",
                total_duration_ms=0.0,
            )

        outputs: Dict[str, Any] = {"_input": initial_input}
        ctx = dict(context or {})
        all_steps: Dict[str, WorkflowStepResult] = {}
        loop_guard = LoopGuard(max_iterations=self.max_loop_iterations)

        try:
            stages = graph.execution_stages()
        except Exception as e:
            return WorkflowResult(
                workflow_name=graph.name,
                success=False,
                error=f"Failed to calculate stages: {str(e)}",
                total_duration_ms=(time.monotonic() - start_time) * 1000,
            )

        for stage in stages:
            if len(stage) == 1:
                node_id = stage[0]
                node = graph.get_node(node_id)
                if not node:
                    continue
                step_res = self._execute_node(node, outputs, ctx, loop_guard)
                all_steps[node_id] = step_res
                outputs[node_id] = step_res.output
                if on_step_complete:
                    on_step_complete(step_res)
                if not step_res.success:
                    total_dur = (time.monotonic() - start_time) * 1000
                    return WorkflowResult(
                        workflow_name=graph.name,
                        success=False,
                        final_output=step_res.output,
                        steps=all_steps,
                        total_duration_ms=total_dur,
                        error=f"Node '{node_id}' failed: {step_res.error}",
                    )
            else:
                # Parallel execution of independent nodes in this stage
                workers = min(len(stage), self.max_parallel_workers)
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {
                        pool.submit(
                            self._execute_node,
                            graph.get_node(nid),
                            dict(outputs),
                            dict(ctx),
                            loop_guard,
                        ): nid
                        for nid in stage
                        if graph.get_node(nid) is not None
                    }

                    stage_success = True
                    for fut in concurrent.futures.as_completed(futures):
                        nid = futures[fut]
                        try:
                            step_res = fut.result()
                        except Exception as exc:
                            step_res = WorkflowStepResult(
                                node_id=nid,
                                success=False,
                                error=f"Unhandled exception in thread: {str(exc)}",
                            )

                        all_steps[nid] = step_res
                        outputs[nid] = step_res.output
                        if on_step_complete:
                            on_step_complete(step_res)

                        if not step_res.success:
                            stage_success = False

                    if not stage_success:
                        total_dur = (time.monotonic() - start_time) * 1000
                        return WorkflowResult(
                            workflow_name=graph.name,
                            success=False,
                            steps=all_steps,
                            total_duration_ms=total_dur,
                            error=f"One or more nodes in parallel stage {stage} failed.",
                        )

        total_duration = (time.monotonic() - start_time) * 1000
        # Final output is the output of the last executed node or stage
        last_node_id = stages[-1][-1] if stages and stages[-1] else None
        final_output = outputs.get(last_node_id) if last_node_id else outputs.get("_input")

        return WorkflowResult(
            workflow_name=graph.name,
            success=True,
            final_output=final_output,
            steps=all_steps,
            total_duration_ms=total_duration,
        )

    def _execute_node(
        self,
        node: WorkflowNode,
        outputs: Dict[str, Any],
        context: Dict[str, Any],
        loop_guard: LoopGuard,
    ) -> WorkflowStepResult:
        """Executes a single node with retries and condition checking."""
        t0 = time.monotonic()

        # Check loop guard
        if node.node_type == NodeType.LOOP:
            if not loop_guard.tick(node.id):
                return WorkflowStepResult(
                    node_id=node.id,
                    success=False,
                    error=f"LoopGuard triggered on '{node.id}': loop limit exceeded.",
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

        # Check condition expression if present
        if node.node_type == NodeType.CONDITION or node.condition_expr:
            expr = node.condition_expr or ""
            # Simple evaluation: check if expression key exists and evaluates truthy
            cond_val = outputs.get(expr, context.get(expr, True))
            if not cond_val:
                return WorkflowStepResult(
                    node_id=node.id,
                    success=True,
                    output=None,
                    error="Condition evaluated to False, branch skipped.",
                    duration_ms=(time.monotonic() - t0) * 1000,
                )

        # Execute with retry logic
        attempts = 0
        max_attempts = max(1, 1 + node.max_retries)
        last_err: Optional[str] = None

        while attempts < max_attempts:
            attempts += 1
            try:
                out = self._invoke_action(node, outputs, context)
                dur = (time.monotonic() - t0) * 1000
                return WorkflowStepResult(
                    node_id=node.id,
                    success=True,
                    output=out,
                    duration_ms=dur,
                )
            except Exception as e:
                last_err = str(e)
                logger.warning(
                    f"[WorkflowEngine] Node '{node.id}' attempt {attempts}/{max_attempts} failed: {last_err}"
                )
                if attempts < max_attempts:
                    time.sleep(0.1 * attempts)

        dur = (time.monotonic() - t0) * 1000
        return WorkflowStepResult(
            node_id=node.id,
            success=False,
            error=last_err or "Unknown execution error",
            duration_ms=dur,
        )

    def _invoke_action(
        self,
        node: WorkflowNode,
        outputs: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Any:
        """Invoke node action via handler or fallback."""
        # Resolve dynamic params: replace {{node_id}} placeholders with prior step outputs
        resolved_params = {}
        for k, v in node.params.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                ref_key = v[2:-2].strip()
                resolved_params[k] = outputs.get(ref_key, v)
            else:
                resolved_params[k] = v

        if node.node_type == NodeType.TERMINAL:
            # Aggregation step: return outputs map or specific field
            target_key = node.params.get("output_key")
            return outputs.get(target_key, outputs) if target_key else outputs

        if self.action_handler and node.action:
            return self.action_handler(node.action, resolved_params, context)

        # Default fallback echo if no handler attached
        return {
            "node_id": node.id,
            "action": node.action,
            "params": resolved_params,
        }
