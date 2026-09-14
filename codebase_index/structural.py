"""
Structural Index: AST-based parsing and symbol extraction.

Provides:
- Symbol table (name -> location, kind, signature)
- Multi-level signatures (L0-L4)
- Grep-like pattern search
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import Entity, EntityKind, FileInfo


class StructuralIndex:
    """
    AST-based structural index for Python codebases.

    Extracts functions, classes, methods, and their signatures.
    Supports multiple detail levels for progressive disclosure.
    """

    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.entities: Dict[str, Entity] = {}
        self.files: Dict[str, FileInfo] = {}
        self.symbols: Dict[str, List[str]] = {}  # name -> list of entity IDs

    def build(self, exclude_patterns: Optional[List[str]] = None) -> None:
        """Build the structural index by parsing all Python files."""
        exclude_patterns = exclude_patterns or [
            r"\.git",
            r"__pycache__",
            r"\.pyc$",
            r"node_modules",
            r"venv",
            r"\.env",
        ]

        for py_file in self.root_path.rglob("*.py"):
            rel_path = py_file.relative_to(self.root_path)

            # Check exclusions
            skip = False
            for pattern in exclude_patterns:
                if re.search(pattern, str(rel_path)):
                    skip = True
                    break
            if skip:
                continue

            self._parse_file(py_file)

    def _parse_file(self, file_path: Path) -> None:
        """Parse a single Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError) as e:
            return

        rel_path = str(file_path.relative_to(self.root_path))
        lines = source.split("\n")

        # Create file info
        file_info = FileInfo(
            path=str(file_path),
            relative_path=rel_path,
            language="python",
            line_count=len(lines),
        )

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    file_info.imports.append(node.module)

        # Extract entities
        self._extract_entities(tree, source, lines, rel_path, file_info)

        self.files[rel_path] = file_info

    def _extract_entities(
        self,
        tree: ast.AST,
        source: str,
        lines: List[str],
        file_path: str,
        file_info: FileInfo,
        parent_id: Optional[str] = None
    ) -> None:
        """Extract entities from AST."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                entity = self._create_class_entity(node, source, lines, file_path, parent_id)
                self._register_entity(entity, file_info)
                # Recursively extract methods
                self._extract_entities(node, source, lines, file_path, file_info, entity.id)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                entity = self._create_function_entity(node, source, lines, file_path, parent_id)
                self._register_entity(entity, file_info)

    def _create_class_entity(
        self,
        node: ast.ClassDef,
        source: str,
        lines: List[str],
        file_path: str,
        parent_id: Optional[str]
    ) -> Entity:
        """Create entity for a class definition."""
        entity_id = f"{file_path}:{node.name}"
        if parent_id:
            entity_id = f"{parent_id}.{node.name}"

        # Get bases
        bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
        signature = f"class {node.name}({bases})" if bases else f"class {node.name}"

        # Get docstring
        docstring = ast.get_docstring(node)

        # Get source
        entity_source = "\n".join(lines[node.lineno - 1:node.end_lineno])

        return Entity(
            id=entity_id,
            kind=EntityKind.CLASS,
            name=node.name,
            qualified_name=entity_id.replace(":", ".").replace("/", "."),
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=signature,
            docstring=docstring,
            source=entity_source,
            contained_by=parent_id,
        )

    def _create_function_entity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
        lines: List[str],
        file_path: str,
        parent_id: Optional[str]
    ) -> Entity:
        """Create entity for a function/method definition."""
        entity_id = f"{file_path}:{node.name}"
        if parent_id:
            entity_id = f"{parent_id}.{node.name}"

        # Build signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        signature = f"{prefix} {node.name}({', '.join(args)})"

        if node.returns:
            signature += f" -> {ast.unparse(node.returns)}"

        # Get docstring
        docstring = ast.get_docstring(node)

        # Get source
        entity_source = "\n".join(lines[node.lineno - 1:node.end_lineno])

        kind = EntityKind.METHOD if parent_id else EntityKind.FUNCTION

        return Entity(
            id=entity_id,
            kind=kind,
            name=node.name,
            qualified_name=entity_id.replace(":", ".").replace("/", "."),
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            signature=signature,
            docstring=docstring,
            source=entity_source,
            contained_by=parent_id,
        )

    def _register_entity(self, entity: Entity, file_info: FileInfo) -> None:
        """Register an entity in the index."""
        self.entities[entity.id] = entity
        file_info.entities.append(entity.id)

        # Index by name
        if entity.name not in self.symbols:
            self.symbols[entity.name] = []
        self.symbols[entity.name].append(entity.id)

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        return self.entities.get(entity_id)

    def find_by_name(self, name: str) -> List[Entity]:
        """Find entities by name (exact match)."""
        entity_ids = self.symbols.get(name, [])
        return [self.entities[eid] for eid in entity_ids]

    def find_by_pattern(self, pattern: str) -> List[Entity]:
        """Find entities matching a regex pattern in their name or source."""
        regex = re.compile(pattern, re.IGNORECASE)
        results = []

        for entity in self.entities.values():
            if regex.search(entity.name):
                results.append(entity)
            elif entity.source and regex.search(entity.source):
                results.append(entity)

        return results

    def grep(self, pattern: str, file_pattern: Optional[str] = None) -> List[Tuple[Entity, List[int]]]:
        """
        Search for pattern in source code, return entities with matching line numbers.

        Returns list of (entity, [line_numbers]) tuples.
        """
        regex = re.compile(pattern, re.IGNORECASE)
        file_regex = re.compile(file_pattern) if file_pattern else None
        results = []

        for file_path, file_info in self.files.items():
            if file_regex and not file_regex.search(file_path):
                continue

            try:
                with open(file_info.path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except:
                continue

            matching_lines = []
            for i, line in enumerate(lines, 1):
                if regex.search(line):
                    matching_lines.append(i)

            if matching_lines:
                # Find which entity contains these lines
                for entity_id in file_info.entities:
                    entity = self.entities[entity_id]
                    entity_lines = [
                        ln for ln in matching_lines
                        if entity.line_start <= ln <= entity.line_end
                    ]
                    if entity_lines:
                        results.append((entity, entity_lines))

        return results

    def get_file_entities(self, file_path: str) -> List[Entity]:
        """Get all entities in a file."""
        file_info = self.files.get(file_path)
        if not file_info:
            return []
        return [self.entities[eid] for eid in file_info.entities]

    def get_all_files(self) -> List[str]:
        """Get all indexed file paths."""
        return list(self.files.keys())

    def get_file_info(self, file_path: str) -> Optional[FileInfo]:
        """Get file info."""
        return self.files.get(file_path)

    # -------------------------------------------------------------------------
    # Materialization Methods
    # -------------------------------------------------------------------------

    def materialize(self, entity: Entity, level: int) -> str:
        """
        Materialize an entity at the specified detail level.

        Levels:
        - 0: Just name and kind
        - 1: Signature
        - 2: Signature + docstring
        - 3: Signature + docstring + relationships (requires relational index)
        - 4: Full source
        """
        if level == 0:
            return f"{entity.kind.value} {entity.name}"

        if level == 1:
            return entity.signature or f"{entity.kind.value} {entity.name}"

        if level == 2:
            result = entity.signature or f"{entity.kind.value} {entity.name}"
            if entity.docstring:
                result += f'\n    """{entity.docstring}"""'
            return result

        if level == 3:
            result = self.materialize(entity, 2)
            # Add relationship info if available
            if entity.calls:
                result += f"\n    # Calls: {', '.join(entity.calls[:5])}"
            if entity.called_by:
                result += f"\n    # Called by: {', '.join(entity.called_by[:5])}"
            return result

        # Level 4: full source
        return entity.source or self.materialize(entity, 2)

    def get_file_summary(self, file_path: str) -> str:
        """Get a summary of a file (all entity signatures)."""
        entities = self.get_file_entities(file_path)
        if not entities:
            return f"# {file_path} (no entities found)"

        lines = [f"# {file_path}"]
        for entity in entities:
            indent = "  " if entity.contained_by else ""
            lines.append(f"{indent}{self.materialize(entity, 1)}")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def stats(self) -> Dict[str, int]:
        """Get index statistics."""
        kind_counts = {}
        for entity in self.entities.values():
            kind_counts[entity.kind.value] = kind_counts.get(entity.kind.value, 0) + 1

        return {
            "files": len(self.files),
            "entities": len(self.entities),
            "symbols": len(self.symbols),
            **kind_counts,
        }
