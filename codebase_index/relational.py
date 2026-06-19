"""
Relational Index: Call graph and dependency relationships.

Provides:
- Call graph: function -> functions it calls
- Reverse call graph: function -> callers
- Import dependencies
- Impact analysis
"""

import ast
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import Entity, EntityKind
from .structural import StructuralIndex


class CallGraphVisitor(ast.NodeVisitor):
    """AST visitor that extracts function calls."""

    def __init__(self):
        self.calls: Set[str] = set()
        self.current_class: Optional[str] = None

    def visit_Call(self, node: ast.Call) -> None:
        """Extract the name of the called function."""
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # For method calls like self.foo() or obj.bar()
            self.calls.add(node.func.attr)
        self.generic_visit(node)


class RelationalIndex:
    """
    Relational index providing call graph and dependency analysis.

    Built on top of the structural index, adds relationship edges.
    """

    def __init__(self, structural_index: StructuralIndex):
        self.structural = structural_index
        self.root_path = structural_index.root_path

        # Call graph edges
        self.calls: Dict[str, Set[str]] = defaultdict(set)  # entity_id -> called entity_ids
        self.called_by: Dict[str, Set[str]] = defaultdict(set)  # entity_id -> caller entity_ids

        # Import graph
        self.imports: Dict[str, Set[str]] = defaultdict(set)  # file -> imported files
        self.imported_by: Dict[str, Set[str]] = defaultdict(set)  # file -> importing files

    def build(self) -> None:
        """Build the relational index."""
        self._build_call_graph()
        self._build_import_graph()
        self._update_entities()

    def _build_call_graph(self) -> None:
        """Build call graph by analyzing function bodies."""
        for entity_id, entity in self.structural.entities.items():
            if entity.kind not in (EntityKind.FUNCTION, EntityKind.METHOD):
                continue

            if not entity.source:
                continue

            try:
                # Dedent source to handle indented methods
                dedented_source = textwrap.dedent(entity.source)
                tree = ast.parse(dedented_source)
            except SyntaxError:
                continue

            visitor = CallGraphVisitor()
            visitor.visit(tree)

            # Resolve calls to entity IDs
            for called_name in visitor.calls:
                # Try to find the called entity
                called_entities = self.structural.find_by_name(called_name)
                for called_entity in called_entities:
                    self.calls[entity_id].add(called_entity.id)
                    self.called_by[called_entity.id].add(entity_id)

    def _build_import_graph(self) -> None:
        """Build import dependency graph between files."""
        for file_path, file_info in self.structural.files.items():
            for imported in file_info.imports:
                # Try to map import to local file
                # This is a simplified version - real implementation would handle
                # relative imports, package structure, etc.
                possible_paths = [
                    imported.replace(".", "/") + ".py",
                    imported.replace(".", "/") + "/__init__.py",
                ]
                for possible_path in possible_paths:
                    if possible_path in self.structural.files:
                        self.imports[file_path].add(possible_path)
                        self.imported_by[possible_path].add(file_path)
                        break

    def _update_entities(self) -> None:
        """Update entities with relationship information."""
        for entity_id, entity in self.structural.entities.items():
            entity.calls = list(self.calls.get(entity_id, []))
            entity.called_by = list(self.called_by.get(entity_id, []))

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def what_calls(self, entity_id: str) -> List[Entity]:
        """Find all entities that call this entity."""
        caller_ids = self.called_by.get(entity_id, set())
        return [self.structural.entities[cid] for cid in caller_ids if cid in self.structural.entities]

    def what_does_call(self, entity_id: str) -> List[Entity]:
        """Find all entities that this entity calls."""
        callee_ids = self.calls.get(entity_id, set())
        return [self.structural.entities[cid] for cid in callee_ids if cid in self.structural.entities]

    def impact_analysis(self, entity_id: str, depth: int = 3) -> Dict[str, List[Entity]]:
        """
        Find all entities that would be affected by changing this entity.

        Returns dict with:
        - "direct_callers": Entities that directly call this
        - "indirect_callers": Entities that call the callers (up to depth)
        - "all_affected": Union of all affected entities
        """
        direct = set(self.called_by.get(entity_id, set()))
        all_affected = set(direct)

        current_level = direct
        for _ in range(depth - 1):
            next_level = set()
            for eid in current_level:
                callers = self.called_by.get(eid, set())
                next_level.update(callers)
            all_affected.update(next_level)
            current_level = next_level

        return {
            "direct_callers": [self.structural.entities[eid] for eid in direct if eid in self.structural.entities],
            "indirect_callers": [
                self.structural.entities[eid]
                for eid in (all_affected - direct)
                if eid in self.structural.entities
            ],
            "all_affected": [self.structural.entities[eid] for eid in all_affected if eid in self.structural.entities],
        }

    def find_path(self, from_id: str, to_id: str, max_depth: int = 5) -> Optional[List[str]]:
        """Find a call path from one entity to another using BFS."""
        if from_id == to_id:
            return [from_id]

        visited = {from_id}
        queue = [(from_id, [from_id])]

        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue

            for callee_id in self.calls.get(current, set()):
                if callee_id == to_id:
                    return path + [callee_id]
                if callee_id not in visited:
                    visited.add(callee_id)
                    queue.append((callee_id, path + [callee_id]))

        return None

    def get_connected_component(self, entity_id: str, max_size: int = 50) -> Set[str]:
        """Get all entities connected to this one (bidirectional)."""
        component = {entity_id}
        frontier = {entity_id}

        while frontier and len(component) < max_size:
            next_frontier = set()
            for eid in frontier:
                # Add callers and callees
                next_frontier.update(self.calls.get(eid, set()))
                next_frontier.update(self.called_by.get(eid, set()))

            next_frontier -= component
            component.update(next_frontier)
            frontier = next_frontier

        return component

    def get_entry_points(self) -> List[Entity]:
        """Find entities that are called but don't call others (potential entry points)."""
        entry_points = []
        for entity_id, entity in self.structural.entities.items():
            if entity.kind not in (EntityKind.FUNCTION, EntityKind.METHOD):
                continue
            # Has callers but doesn't call anything significant
            if not self.calls.get(entity_id) and self.called_by.get(entity_id):
                entry_points.append(entity)
        return entry_points

    def get_central_entities(self, top_k: int = 10) -> List[Tuple[Entity, int]]:
        """Find the most connected entities (by total edges)."""
        scores = []
        for entity_id, entity in self.structural.entities.items():
            if entity.kind not in (EntityKind.FUNCTION, EntityKind.METHOD, EntityKind.CLASS):
                continue
            in_degree = len(self.called_by.get(entity_id, set()))
            out_degree = len(self.calls.get(entity_id, set()))
            scores.append((entity, in_degree + out_degree))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_file_dependencies(self, file_path: str) -> Dict[str, List[str]]:
        """Get files that this file depends on and files that depend on it."""
        return {
            "depends_on": list(self.imports.get(file_path, set())),
            "depended_by": list(self.imported_by.get(file_path, set())),
        }

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def stats(self) -> Dict[str, int]:
        """Get relational index statistics."""
        total_call_edges = sum(len(callees) for callees in self.calls.values())
        total_import_edges = sum(len(imports) for imports in self.imports.values())

        return {
            "call_edges": total_call_edges,
            "import_edges": total_import_edges,
            "entities_with_callers": len([e for e in self.called_by if self.called_by[e]]),
            "entities_with_callees": len([e for e in self.calls if self.calls[e]]),
        }
