"""Bounded structural extraction; no source execution or parser downloads."""

from app.services.chunking.text import SourceText, partition_scopes


LANGUAGES = {".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
             ".tsx": "tsx", ".java": "java", ".cs": "csharp"}
SYMBOLS = {
    "function_declaration": "function", "function_expression": "function",
    "generator_function_declaration": "function", "generator_function": "function",
    "arrow_function": "function", "function_signature": "function",
    "local_function_statement": "function",
    "class_declaration": "class", "abstract_class_declaration": "class", "class": "class",
    "record_declaration": "class", "struct_declaration": "class",
    "interface_declaration": "interface",
    "method_definition": "method", "method_declaration": "method",
    "method_signature": "method", "abstract_method_signature": "method",
    "constructor_declaration": "constructor", "compact_constructor_declaration": "constructor",
    "construct_signature": "constructor",
    "namespace_declaration": "namespace", "internal_module": "namespace",
}
IMPORTS = {"import_statement", "import_declaration", "using_directive", "package_declaration"}


class ParseFallback(ValueError):
    """A safe, source-free diagnostic for the shared text fallback."""


def regions(source: SourceText, context_chars: int, language: str):
    # Lazy import keeps Python/text chunking independent of native parser setup.
    try:
        from tree_sitter_language_pack import get_parser
        parser = get_parser(language)  # Fresh parser: no shared mutable parse state.
    except (ImportError, OSError, LookupError, RuntimeError, ValueError) as exc:
        raise ParseFallback("tree_sitter_unavailable") from exc
    data = source.text.encode("utf-8")
    try:
        tree = parser.parse(data)
    except (ValueError, RuntimeError) as exc:
        raise ParseFallback("tree_sitter_parse_error") from exc
    if tree.root_node.has_error:
        # Do not misrepresent parser error recovery nodes as reliable symbols.
        raise ParseFallback("tree_sitter_syntax_error")

    # Tree-sitter uses UTF-8 bytes; the public contract uses Unicode characters.
    offsets = []
    for index, char in enumerate(source.text):
        offsets.extend([index] * len(char.encode("utf-8")))
    offsets.append(len(source.text))

    def excerpt(node, limit):
        return source.text[offsets[node.start_byte]:min(offsets[node.end_byte], offsets[node.start_byte] + limit)]

    scopes = [{"name": "<module>", "kind": "module", "parent": None,
               "start": 0, "end": len(source.text), "children": [], "header": ""}]
    boundaries, imports = set(), []
    import_length = 0
    stack, count = [(tree.root_node, 0)], 0
    while stack:
        node, parent = stack.pop()
        count += 1
        if count > 50000:
            raise ParseFallback("tree_sitter_node_limit")
        if node.type.endswith(("statement", "declaration")) or node.type in SYMBOLS:
            boundaries.add(offsets[node.end_byte])
        if node.type in IMPORTS and import_length < context_chars:
            part = excerpt(node, min(200, context_chars - import_length))
            imports.append(part)
            import_length += len(part) + 1
        kind = SYMBOLS.get(node.type)
        if kind:
            name_node = node.child_by_field_name("name")
            anchor = node
            if name_node is None and node.parent is not None:
                container = node.parent
                if container.type in {"variable_declarator", "pair", "public_field_definition",
                                      "field_definition", "assignment_expression"}:
                    name_node = (container.child_by_field_name("name")
                                 or container.child_by_field_name("key")
                                 or container.child_by_field_name("property")
                                 or container.child_by_field_name("left"))
                    anchor = container
            name = excerpt(name_node, 200) if name_node is not None else (
                "constructor" if kind == "constructor" else
                f"<anonymous@{node.start_point.row + 1}:{node.start_point.column + 1}>")
            if kind == "method" and name == "constructor" and language in {"javascript", "typescript", "tsx"}:
                kind = "constructor"
            if kind in {"method", "function"} and any(child.type == "async" for child in node.children):
                kind = "async_" + kind
            qualified = name if parent == 0 else scopes[parent]["name"] + "." + name
            body = node.child_by_field_name("body")
            header_end = offsets[body.start_byte] if body is not None else offsets[node.end_byte]
            header_start = offsets[anchor.start_byte]
            header = source.text[header_start:min(header_end, header_start + context_chars)]
            scopes[parent]["children"].append(len(scopes))
            scopes.append({"name": qualified, "kind": kind, "parent": parent,
                           "start": offsets[node.start_byte], "end": offsets[node.end_byte],
                           "children": [], "header": header})
            parent = len(scopes) - 1
        stack.extend((child, parent) for child in reversed(node.named_children))

    module_context = "\n".join(imports)[:context_chars]

    def context(index):
        budget = context_chars * 2 // 3 if module_context else context_chars
        parts, used = [], 0
        while index and used < budget:
            part = scopes[index]["header"][:max(1, budget // 4)].rstrip()
            parts.append(part)
            used += len(part) + 1
            index = scopes[index]["parent"]
        scope_text = "\n".join(parts)[:budget]
        return "\n".join(part for part in (scope_text, module_context) if part)[:context_chars]

    def meaningful_region(scope, start, end):
        """Skip container braces/headers once their child symbols carry context."""
        if not scope["children"] or scope["kind"] not in {"class", "interface", "namespace"}:
            return True
        remainder = source.text[start:end]
        header = scope["header"]
        if start == scope["start"] and remainder.startswith(header):
            remainder = remainder[len(header):]
        return bool(remainder.strip("{}; \t\r\n"))

    return partition_scopes(scopes, context, meaningful_region), sorted(boundaries)
