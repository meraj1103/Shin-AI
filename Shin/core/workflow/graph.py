"""WorkflowGraph — Directed Acyclic Graph (DAG) for Shin tasks."""

from __future__ import annotations
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from Shin.core.workflow.types import WorkflowNode, NodeType


class WorkflowGraph:
    """Manages dependencies, cycle detection, and stage scheduling for nodes."""

    def __init__(self, name: str = "ShinWorkflow"):
        self.name = name
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: Dict[str, List[str]] = defaultdict(list)  # parent -> children
        self.in_degree: Dict[str, int] = defaultdict(int)

    def add_node(self, node: WorkflowNode) -> WorkflowGraph:
        """Add a node to the graph and register dependencies."""
        if node.id in self.nodes:
            raise ValueError(f"Node '{node.id}' already exists in workflow '{self.name}'.")
        self.nodes[node.id] = node
        if node.id not in self.in_degree:
            self.in_degree[node.id] = 0

        # Wire dependencies as edges: dep -> node.id
        for dep in node.dependencies:
            self.edges[dep].append(node.id)
            self.in_degree[node.id] += 1
        return self

    def add_edge(self, from_node: str, to_node: str) -> WorkflowGraph:
        """Add explicit directed edge from parent to child."""
        if from_node not in self.nodes or to_node not in self.nodes:
            raise KeyError(f"Both nodes must exist in graph: {from_node} -> {to_node}")
        self.edges[from_node].append(to_node)
        self.in_degree[to_node] += 1
        if from_node not in self.nodes[to_node].dependencies:
            self.nodes[to_node].dependencies.append(from_node)
        return self

    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        return self.nodes.get(node_id)

    def validate(self) -> Tuple[bool, str]:
        """Verify the graph has no dangling dependencies and is strictly acyclic (DAG)."""
        if not self.nodes:
            return False, "Workflow contains no nodes."

        # Verify all dependencies exist in nodes
        for nid, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    return False, f"Node '{nid}' references non-existent dependency '{dep}'."

        # Cycle detection using Kahn's algorithm
        in_deg = dict(self.in_degree)
        queue = deque([nid for nid, deg in in_deg.items() if deg == 0])
        visited_count = 0

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for child in self.edges.get(curr, []):
                in_deg[child] -= 1
                if in_deg[child] == 0:
                    queue.append(child)

        if visited_count != len(self.nodes):
            return False, "Cycle detected in workflow graph dependencies."

        return True, "Valid DAG"

    def execution_stages(self) -> List[List[str]]:
        """Return topological execution stages.
        Nodes within the same stage have no interdependencies and can run concurrently.
        """
        valid, msg = self.validate()
        if not valid:
            raise ValueError(f"Cannot compute execution stages: {msg}")

        in_deg = dict(self.in_degree)
        queue = deque([nid for nid, deg in in_deg.items() if deg == 0])
        stages: List[List[str]] = []

        while queue:
            stage_size = len(queue)
            current_stage: List[str] = []
            next_stage_candidates = []

            for _ in range(stage_size):
                curr = queue.popleft()
                current_stage.append(curr)
                for child in self.edges.get(curr, []):
                    in_deg[child] -= 1
                    if in_deg[child] == 0:
                        next_stage_candidates.append(child)

            stages.append(current_stage)
            for cand in next_stage_candidates:
                queue.append(cand)

        return stages
