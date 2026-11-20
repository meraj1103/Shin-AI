"""
planner.py — Explicit Planning & Reflection Module for Shin
===========================================================
Implements:
- Plan creation with step decomposition
- Dependency-aware execution (DAG)
- Reflection & critique after execution
- Adaptive strategy selection
- Learning from failures
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TypedDict
from collections import defaultdict, deque

# Project imports
import sys
from pathlib import Path as P
_ROOT = P(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_CORE = _ROOT / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from core.shin_agent import DualModeLLMRouter, HardwareProfile, build_shin_system_prompt
from core.agent_orchestrator import AgentOrchestrator, AgentContext, AgentType

logger = logging.getLogger("shin.planner")


# ═══════════════════════════════════════════════════════════════════════════════
# Plan Data Structures
# ═══════════════════════════════════════════════════════════════════════════════

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    id: str
    description: str
    agent_type: AgentType
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Step IDs this depends on
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """An execution plan with multiple steps."""
    id: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: str = "created"  # created, executing, completed, failed
    context: Optional[AgentContext] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_ready_steps(self) -> List[PlanStep]:
        """Get steps that are ready to execute (dependencies met)."""
        ready = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            deps_met = all(
                self.get_step(dep_id) and self.get_step(dep_id).status == StepStatus.COMPLETED
                for dep_id in step.dependencies
            )
            if deps_met:
                ready.append(step)
        return ready
    
    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)
    
    def has_failed(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)
    
    def get_execution_order(self) -> List[List[PlanStep]]:
        """Get steps grouped by execution wave (parallelizable groups)."""
        waves = []
        remaining = {s.id: s for s in self.steps}
        completed = set()
        
        while remaining:
            wave = []
            for step_id, step in list(remaining.items()):
                if all(dep in completed for dep in step.dependencies):
                    wave.append(step)
            
            if not wave:
                # Circular dependency or missing deps - execute remaining
                wave = list(remaining.values())
            
            waves.append(wave)
            for step in wave:
                completed.add(step.id)
                del remaining[step.id]
        
        return waves


@dataclass
class Reflection:
    """Post-execution reflection and critique."""
    plan_id: str
    success: bool
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    strategy_adjustments: List[str] = field(default_factory=list)
    confidence_score: float = 0.0  # 0-1
    created_at: datetime = field(default_factory=datetime.now)


# ═══════════════════════════════════════════════════════════════════════════════
# Planner
# ═══════════════════════════════════════════════════════════════════════════════

class Planner:
    """
    Creates execution plans from high-level goals.
    Uses LLM to decompose goals into actionable steps.
    """
    
    def __init__(self, router: DualModeLLMRouter, orchestrator: AgentOrchestrator):
        self.router = router
        self.orchestrator = orchestrator
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## Planner Role
You are Shin's Strategic Planner. Your job is to decompose high-level goals into 
concrete, executable steps that can be handled by specialized agents.

## Available Agents & Their Capabilities:
1. **OS Agent**: Windows operations (launch apps, files, volume, brightness, power)
2. **Web Agent**: Search, GitHub, Reddit, YouTube, Twitter intelligence
3. **Code Agent**: Code generation, debugging, tool synthesis
4. **Memory Agent**: Fact storage/recall, todo management
5. **Predictive Agent**: Routine predictions, clipboard analysis, proactive suggestions
6. **Vision Agent**: Screen inspection, UI interaction, bug diagnosis
7. **Communication Agent**: WhatsApp, email, notifications

## Planning Rules:
- Break complex goals into atomic steps
- Identify dependencies between steps (what must happen before what)
- Assign each step to the most appropriate agent
- Include tool names and arguments when possible
- Keep steps small and verifiable
- Consider parallel execution where steps are independent

## Output Format (JSON):
{
  "goal": "High-level goal description",
  "steps": [
    {
      "id": "step_1",
      "description": "What this step does",
      "agent_type": "os|web|code|memory|predictive|vision|communication",
      "tool_name": "specific_tool_name_or_null",
      "tool_args": {"arg": "value"},
      "dependencies": ["step_id_that_must_complete_first"],
      "max_retries": 3
    }
  ]
}
"""
    
    def create_plan(self, goal: str, context: Optional[AgentContext] = None) -> Plan:
        """Create an execution plan from a high-level goal."""
        if context is None:
            context = AgentContext()
        
        # Build context summary for the planner
        context_summary = self._build_context_summary(context)
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Goal: {goal}\n\nContext:\n{context_summary}"},
        ]
        
        resp = self.router.call_llm(messages, tools=None)
        content = resp.get("content", "")
        
        # Parse JSON from response
        plan_data = self._parse_plan_json(content)
        if not plan_data:
            # Fallback: create simple single-step plan
            plan_data = self._create_fallback_plan(goal)
        
        # Create Plan object
        plan = Plan(
            id=str(uuid.uuid4())[:8],
            goal=goal,
            context=context,
        )
        
        for step_data in plan_data.get("steps", []):
            step = PlanStep(
                id=step_data.get("id", str(uuid.uuid4())[:8]),
                description=step_data.get("description", ""),
                agent_type=AgentType(step_data.get("agent_type", "os")),
                tool_name=step_data.get("tool_name"),
                tool_args=step_data.get("tool_args", {}),
                dependencies=step_data.get("dependencies", []),
                max_retries=step_data.get("max_retries", 3),
            )
            plan.steps.append(step)
        
        logger.info(f"Created plan {plan.id} with {len(plan.steps)} steps for goal: {goal}")
        return plan
    
    def _build_context_summary(self, context: AgentContext) -> str:
        lines = []
        if context.active_app:
            lines.append(f"Active App: {context.active_app}")
        if context.screen_content:
            lines.append(f"Screen Content: {context.screen_content[:500]}")
        if context.clipboard_content:
            lines.append(f"Clipboard: {context.clipboard_content[:200]}")
        if context.battery_status:
            lines.append(f"Battery: {context.battery_status.get('percent', '?')}% {'(plugged)' if context.battery_status.get('plugged') else '(on battery)'}")
        if context.pending_tasks:
            lines.append(f"Pending Tasks: {', '.join(context.pending_tasks[:5])}")
        if context.memories:
            lines.append(f"Relevant Memories: {len(context.memories)} items")
        return "\n".join(lines) if lines else "No additional context."
    
    def _parse_plan_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON from LLM response."""
        # Try to find JSON block
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try parsing entire content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _create_fallback_plan(self, goal: str) -> Dict[str, Any]:
        """Create a simple fallback plan when JSON parsing fails."""
        return {
            "goal": goal,
            "steps": [
                {
                    "id": "step_1",
                    "description": goal,
                    "agent_type": "os",
                    "tool_name": None,
                    "tool_args": {},
                    "dependencies": [],
                }
            ]
        }
    
    def refine_plan(self, plan: Plan, feedback: str, context: Optional[AgentContext] = None) -> Plan:
        """Refine an existing plan based on feedback."""
        if context is None:
            context = plan.context or AgentContext()
        
        # Serialize current plan
        plan_json = {
            "goal": plan.goal,
            "steps": [
                {
                    "id": s.id,
                    "description": s.description,
                    "agent_type": s.agent_type.value,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args,
                    "dependencies": s.dependencies,
                }
                for s in plan.steps
            ]
        }
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Current Plan:\n{json.dumps(plan_json, indent=2)}\n\nFeedback: {feedback}\n\nRefine the plan to address the feedback."},
        ]
        
        resp = self.router.call_llm(messages, tools=None)
        content = resp.get("content", "")
        plan_data = self._parse_plan_json(content)
        
        if plan_data:
            # Create new refined plan
            new_plan = Plan(
                id=str(uuid.uuid4())[:8],
                goal=plan.goal,
                context=context,
                metadata={"refined_from": plan.id, "feedback": feedback},
            )
            for step_data in plan_data.get("steps", []):
                step = PlanStep(
                    id=step_data.get("id", str(uuid.uuid4())[:8]),
                    description=step_data.get("description", ""),
                    agent_type=AgentType(step_data.get("agent_type", "os")),
                    tool_name=step_data.get("tool_name"),
                    tool_args=step_data.get("tool_args", {}),
                    dependencies=step_data.get("dependencies", []),
                )
                new_plan.steps.append(step)
            return new_plan
        
        return plan


# ═══════════════════════════════════════════════════════════════════════════════
# Plan Executor
# ═══════════════════════════════════════════════════════════════════════════════

class PlanExecutor:
    """
    Executes plans with dependency management, parallel execution,
    retries, and error handling.
    """
    
    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
        self.execution_history: deque = deque(maxlen=100)
    
    async def execute(self, plan: Plan) -> Plan:
        """Execute a plan completely."""
        plan.status = "executing"
        plan.updated_at = datetime.now()
        
        logger.info(f"Starting execution of plan {plan.id}: {plan.goal}")
        
        # Get execution waves (parallelizable groups)
        waves = plan.get_execution_order()
        
        for wave_idx, wave in enumerate(waves):
            logger.info(f"Executing wave {wave_idx + 1}/{len(waves)} with {len(wave)} steps")
            
            # Execute steps in wave in parallel
            tasks = [self._execute_step(step, plan) for step in wave]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for step, result in zip(wave, results):
                if isinstance(result, Exception):
                    step.status = StepStatus.FAILED
                    step.error = str(result)
                    step.end_time = time.time()
                    logger.error(f"Step {step.id} failed with exception: {result}")
                # Step status already updated in _execute_step
            
            # Check if any critical step failed
            failed_steps = [s for s in wave if s.status == StepStatus.FAILED]
            if failed_steps:
                # Check if we should continue or abort
                if self._should_abort(plan, failed_steps):
                    plan.status = "failed"
                    plan.updated_at = datetime.now()
                    logger.error(f"Plan {plan.id} aborted due to critical failures")
                    break
        
        if plan.status == "executing":
            plan.status = "completed" if not plan.has_failed() else "partial"
        
        plan.updated_at = datetime.now()
        self.execution_history.append({
            "plan_id": plan.id,
            "goal": plan.goal,
            "status": plan.status,
            "steps": len(plan.steps),
            "completed": sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED),
            "failed": sum(1 for s in plan.steps if s.status == StepStatus.FAILED),
            "time": datetime.now().isoformat(),
        })
        
        logger.info(f"Plan {plan.id} finished with status: {plan.status}")
        return plan
    
    async def _execute_step(self, step: PlanStep, plan: Plan) -> None:
        """Execute a single plan step."""
        step.status = StepStatus.RUNNING
        step.start_time = time.time()
        
        logger.info(f"Executing step {step.id}: {step.description}")
        
        for attempt in range(step.max_retries + 1):
            if attempt > 0:
                step.retry_count = attempt
                logger.info(f"Retry {attempt}/{step.max_retries} for step {step.id}")
                await asyncio.sleep(1.0 * attempt)  # Exponential backoff
            
            try:
                # Build context with results from completed steps
                context = self._build_step_context(step, plan)
                
                # Execute via orchestrator
                if step.tool_name:
                    # Direct tool execution
                    agent = self.orchestrator.agents.get(step.agent_type)
                    if agent:
                        result = agent._execute_tool(step.tool_name, step.tool_args)
                    else:
                        # Fallback to orchestrator
                        task = f"{step.description}. Use {step.tool_name} with args: {step.tool_args}"
                        agent_result = await self.orchestrator.execute(task, context)
                        result = agent_result.content
                else:
                    # General task execution
                    agent_result = await self.orchestrator.execute(step.description, context)
                    result = agent_result.content
                
                step.result = result
                step.status = StepStatus.COMPLETED
                step.end_time = time.time()
                logger.info(f"Step {step.id} completed successfully")
                return
                
            except Exception as exc:
                step.error = str(exc)
                logger.warning(f"Step {step.id} attempt {attempt + 1} failed: {exc}")
                
                if attempt >= step.max_retries:
                    step.status = StepStatus.FAILED
                    step.end_time = time.time()
                    logger.error(f"Step {step.id} failed after {step.max_retries + 1} attempts")
                    return
    
    def _build_step_context(self, step: PlanStep, plan: Plan) -> AgentContext:
        """Build context for step execution including results from dependencies."""
        context = plan.context or AgentContext()
        
        # Add results from dependency steps
        dep_results = {}
        for dep_id in step.dependencies:
            dep_step = plan.get_step(dep_id)
            if dep_step and dep_step.result is not None:
                dep_results[dep_id] = dep_step.result
        
        # Create enhanced context
        enhanced_context = AgentContext(
            user_id=context.user_id,
            conversation_history=context.conversation_history,
            active_app=context.active_app,
            screen_content=context.screen_content,
            clipboard_content=context.clipboard_content,
            battery_status=context.battery_status,
            time_of_day=context.time_of_day,
            pending_tasks=context.pending_tasks,
            memories=context.memories,
            metadata={**context.metadata, "dependency_results": dep_results, "current_step": step.id},
        )
        
        return enhanced_context
    
    def _should_abort(self, plan: Plan, failed_steps: List[PlanStep]) -> bool:
        """Determine if plan should be aborted based on failures."""
        # Abort if any step with no dependents failed (leaf failure)
        # Or if more than 50% of steps failed
        total_steps = len(plan.steps)
        failed_count = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)
        
        if failed_count / total_steps > 0.5:
            return True
        
        # Check if failed steps block other steps
        for failed in failed_steps:
            # Find steps that depend on this failed step
            blocked = [s for s in plan.steps if failed.id in s.dependencies and s.status == StepStatus.PENDING]
            if blocked:
                return True
        
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Reflector
# ═══════════════════════════════════════════════════════════════════════════════

class Reflector:
    """
    Performs post-execution reflection to learn from successes and failures.
    Generates insights for future planning improvements.
    """
    
    def __init__(self, router: DualModeLLMRouter):
        self.router = router
        self.system_prompt = self._build_system_prompt()
        self.reflections: List[Reflection] = []
    
    def _build_system_prompt(self) -> str:
        base = build_shin_system_prompt()
        return base + """
## Reflector Role
You are Shin's Reflection Engine. After plan execution, analyze what happened:
- What worked well?
- What failed and why?
- What patterns emerge?
- How should future plans be adjusted?

Be honest, specific, and actionable. Focus on systemic improvements.
"""
    
    def reflect(self, plan: Plan) -> Reflection:
        """Generate a reflection on plan execution."""
        # Prepare execution summary
        summary = self._build_execution_summary(plan)
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Plan Execution Summary:\n{summary}\n\nProvide a structured reflection."},
        ]
        
        resp = self.router.call_llm(messages, tools=None)
        content = resp.get("content", "")
        
        # Parse reflection
        reflection = self._parse_reflection(content, plan.id, plan.status == "completed")
        self.reflections.append(reflection)
        
        logger.info(f"Generated reflection for plan {plan.id}: confidence={reflection.confidence_score:.2f}")
        return reflection
    
    def _build_execution_summary(self, plan: Plan) -> str:
        lines = [
            f"Plan ID: {plan.id}",
            f"Goal: {plan.goal}",
            f"Status: {plan.status}",
            f"Total Steps: {len(plan.steps)}",
            f"Completed: {sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)}",
            f"Failed: {sum(1 for s in plan.steps if s.status == StepStatus.FAILED)}",
            "",
            "Step Details:",
        ]
        
        for step in plan.steps:
            duration = ""
            if step.start_time and step.end_time:
                duration = f" ({(step.end_time - step.start_time)*1000:.0f}ms)"
            lines.append(
                f"  - {step.id}: {step.description} [{step.status.value}]{duration}"
                + (f" - Error: {step.error}" if step.error else "")
            )
        
        return "\n".join(lines)
    
    def _parse_reflection(self, content: str, plan_id: str, success: bool) -> Reflection:
        """Parse reflection from LLM response."""
        # Simple parsing - in production, use structured output
        reflection = Reflection(
            plan_id=plan_id,
            success=success,
        )
        
        # Extract sections
        sections = {
            "what_worked": [],
            "what_failed": [],
            "lessons_learned": [],
            "strategy_adjustments": [],
        }
        
        current_section = None
        for line in content.split("\n"):
            line = line.strip()
            lower = line.lower()
            
            if "what worked" in lower or "success" in lower:
                current_section = "what_worked"
            elif "what failed" in lower or "failure" in lower:
                current_section = "what_failed"
            elif "lesson" in lower or "learn" in lower:
                current_section = "lessons_learned"
            elif "strategy" in lower or "adjust" in lower or "improve" in lower:
                current_section = "strategy_adjustments"
            elif line.startswith("-") or line.startswith("•") or line.startswith("*"):
                if current_section:
                    sections[current_section].append(line.lstrip("-•* ").strip())
        
        reflection.what_worked = sections["what_worked"]
        reflection.what_failed = sections["what_failed"]
        reflection.lessons_learned = sections["lessons_learned"]
        reflection.strategy_adjustments = sections["strategy_adjustments"]
        
        # Calculate confidence based on success and reflection quality
        base_confidence = 1.0 if success else 0.3
        reflection.confidence_score = min(1.0, base_confidence + len(reflection.lessons_learned) * 0.1)
        
        return reflection
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get aggregated learning from all reflections."""
        if not self.reflections:
            return {"total_reflections": 0}
        
        total = len(self.reflections)
        successful = sum(1 for r in self.reflections if r.success)
        
        all_lessons = []
        all_adjustments = []
        for r in self.reflections:
            all_lessons.extend(r.lessons_learned)
            all_adjustments.extend(r.strategy_adjustments)
        
        # Count frequency
        from collections import Counter
        lesson_counts = Counter(all_lessons)
        adjustment_counts = Counter(all_adjustments)
        
        return {
            "total_reflections": total,
            "success_rate": successful / total,
            "avg_confidence": sum(r.confidence_score for r in self.reflections) / total,
            "top_lessons": lesson_counts.most_common(5),
            "top_adjustments": adjustment_counts.most_common(5),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Planning Engine (Integrated)
# ═══════════════════════════════════════════════════════════════════════════════

class PlanningEngine:
    """
    Integrated planning engine combining Planner, Executor, and Reflector.
    Provides a complete plan-execute-reflect loop.
    """
    
    def __init__(self, hardware: Optional[HardwareProfile] = None):
        self.hardware = hardware or HardwareProfile()
        self.router = DualModeLLMRouter(self.hardware)
        self.orchestrator = AgentOrchestrator(self.hardware)
        
        self.planner = Planner(self.router, self.orchestrator)
        self.executor = PlanExecutor(self.orchestrator)
        self.reflector = Reflector(self.router)
        
        self.active_plan: Optional[Plan] = None
    
    async def run(self, goal: str, context: Optional[AgentContext] = None) -> Dict[str, Any]:
        """
        Run the complete plan-execute-reflect cycle for a goal.
        Returns execution results and reflection.
        """
        # Create plan
        plan = self.planner.create_plan(goal, context)
        self.active_plan = plan
        
        # Execute plan
        executed_plan = await self.executor.execute(plan)
        
        # Reflect
        reflection = self.reflector.reflect(executed_plan)
        
        # Compile results
        return {
            "plan_id": plan.id,
            "goal": goal,
            "status": executed_plan.status,
            "steps": [
                {
                    "id": s.id,
                    "description": s.description,
                    "agent": s.agent_type.value,
                    "status": s.status.value,
                    "result": str(s.result)[:200] if s.result else None,
                    "error": s.error,
                    "duration_ms": (s.end_time - s.start_time) * 1000 if s.start_time and s.end_time else None,
                }
                for s in executed_plan.steps
            ],
            "reflection": {
                "what_worked": reflection.what_worked,
                "what_failed": reflection.what_failed,
                "lessons_learned": reflection.lessons_learned,
                "strategy_adjustments": reflection.strategy_adjustments,
                "confidence": reflection.confidence_score,
            },
            "learning_summary": self.reflector.get_learning_summary(),
        }
    
    async def run_with_refinement(self, goal: str, context: Optional[AgentContext] = None, max_refinements: int = 2) -> Dict[str, Any]:
        """Run with automatic refinement based on reflection."""
        result = await self.run(goal, context)
        
        for i in range(max_refinements):
            if result["status"] == "completed" and result["reflection"]["confidence"] > 0.8:
                break
            
            if not result["reflection"]["strategy_adjustments"]:
                break
            
            # Refine plan based on reflection
            feedback = "; ".join(result["reflection"]["strategy_adjustments"])
            logger.info(f"Refining plan (iteration {i+1}): {feedback}")
            
            refined_plan = self.planner.refine_plan(self.active_plan, feedback, context)
            self.active_plan = refined_plan
            
            executed_plan = await self.executor.execute(refined_plan)
            reflection = self.reflector.reflect(executed_plan)
            
            result = {
                "plan_id": refined_plan.id,
                "goal": goal,
                "status": executed_plan.status,
                "steps": [
                    {
                        "id": s.id,
                        "description": s.description,
                        "agent": s.agent_type.value,
                        "status": s.status.value,
                        "result": str(s.result)[:200] if s.result else None,
                        "error": s.error,
                    }
                    for s in executed_plan.steps
                ],
                "reflection": {
                    "what_worked": reflection.what_worked,
                    "what_failed": reflection.what_failed,
                    "lessons_learned": reflection.lessons_learned,
                    "strategy_adjustments": reflection.strategy_adjustments,
                    "confidence": reflection.confidence_score,
                },
                "learning_summary": self.reflector.get_learning_summary(),
            }
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Global Instance & Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

_GLOBAL_PLANNING_ENGINE: Optional[PlanningEngine] = None


def get_planning_engine() -> PlanningEngine:
    global _GLOBAL_PLANNING_ENGINE
    if _GLOBAL_PLANNING_ENGINE is None:
        _GLOBAL_PLANNING_ENGINE = PlanningEngine()
    return _GLOBAL_PLANNING_ENGINE


async def run_planner(goal: str, context: Optional[AgentContext] = None) -> Dict[str, Any]:
    """Entry point for running the planning engine."""
    engine = get_planning_engine()
    return await engine.run(goal, context)


# ═══════════════════════════════════════════════════════════════════════════════
# Testing
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    async def test():
        engine = PlanningEngine()
        
        # Test simple goal
        result = await engine.run("Open Chrome and search for Python tutorials")
        print(json.dumps(result, indent=2, default=str))
    
    asyncio.run(test())