"""Discover Python symbols and partition source without duplicating bodies."""

import ast

from app.services.chunking.text import SourceText, partition_scopes


SYMBOLS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def regions(source: SourceText, context_chars: int):
    tree = ast.parse(source.text, mode="exec")  # Parse only; never execute.
    scopes = [{"node": tree, "name": "<module>", "kind": "module", "parent": None,
               "start": 0, "end": len(source.text), "children": []}]
    boundaries = set()
    stack = [(tree, 0)]
    count = 0
    while stack:
        node, parent = stack.pop()
        count += 1
        if count > 50000:
            raise ValueError("AST node limit exceeded")
        if isinstance(node, ast.stmt):
            boundaries.add(source.line_end(node.end_lineno))
        if isinstance(node, SYMBOLS):
            first_line = min([node.lineno] + [item.lineno for item in node.decorator_list])
            kind = "class" if isinstance(node, ast.ClassDef) else (
                "async_method" if scopes[parent]["kind"] == "class" and isinstance(node, ast.AsyncFunctionDef)
                else "method" if scopes[parent]["kind"] == "class"
                else "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function")
            name = node.name if parent == 0 else scopes[parent]["name"] + "." + node.name
            scope = {"node": node, "name": name, "kind": kind, "parent": parent,
                     "start": source.starts[first_line - 1], "end": source.line_end(node.end_lineno), "children": []}
            scopes[parent]["children"].append(len(scopes))
            parent = len(scopes)
            scopes.append(scope)
        stack.extend((child, parent) for child in reversed(list(ast.iter_child_nodes(node))))

    module_parts = []
    doc = ast.get_docstring(tree, clean=False)
    if doc:
        module_parts.append("Module doc: " + doc[:200])
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_parts.append(source.text[source.offset(node.lineno):source.line_end(node.end_lineno)][:200])
            if sum(map(len, module_parts)) >= context_chars:
                break
    module_context = "\n".join(module_parts)[:context_chars]

    def context(index):
        parts = []
        # Reserve space for module context; bound each scope so a method's
        # docstring cannot crowd out its enclosing class signature.
        scope_budget = context_chars * 2 // 3 if module_context else context_chars
        excerpt_size = max(1, scope_budget // 4)
        while index:
            scope = scopes[index]
            node = scope["node"]
            first = node.body[0]
            header = source.text[scope["start"]:source.offset(first.lineno, first.col_offset)][:excerpt_size]
            parts.append(header.rstrip())
            doc = ast.get_docstring(node, clean=False)
            if doc:
                parts.append("Doc: " + doc[:excerpt_size])
            if sum(map(len, parts)) >= scope_budget:
                break
            index = scope["parent"]
        scope_text = "\n".join(part for part in parts if part)[:scope_budget]
        return "\n".join(part for part in (scope_text, module_context) if part)[:context_chars]

    return partition_scopes(scopes, context), sorted(boundaries)
