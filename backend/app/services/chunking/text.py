"""Source coordinates and bounded splitting shared by AST and text fallback."""

from bisect import bisect_right


class SourceText:
    def __init__(self, source: str):
        self.text = source.replace("\r\n", "\n").replace("\r", "\n")
        self.starts = [0] + [i + 1 for i, char in enumerate(self.text) if char == "\n"]

    def line(self, offset: int) -> int:
        return bisect_right(self.starts, offset)

    def offset(self, line: int, byte_column: int = 0) -> int:
        start = self.starts[line - 1]
        end = self.starts[line] if line < len(self.starts) else len(self.text)
        # AST columns count UTF-8 bytes, not Unicode characters.
        prefix = self.text[start:end].encode("utf-8")[:byte_column].decode("utf-8")
        return start + len(prefix)

    def line_end(self, line: int) -> int:
        return self.starts[line] if line < len(self.starts) else len(self.text)


def partition_scopes(scopes, context, include_region=None):
    """Emit each scope's source once, excluding independently emitted children."""
    result = []
    for index, scope in enumerate(scopes):
        cursor = scope["start"]
        scope_context = context(index)
        children = sorted((scopes[i] for i in scope["children"]), key=lambda item: item["start"])
        for child in children:
            if cursor < child["start"] and (
                    include_region is None or include_region(scope, cursor, child["start"])):
                result.append((cursor, child["start"], scope["name"], scope["kind"], scope_context))
            cursor = max(cursor, child["end"])
        if cursor < scope["end"] and (
                include_region is None or include_region(scope, cursor, scope["end"])):
            result.append((cursor, scope["end"], scope["name"], scope["kind"], scope_context))
    return sorted(result, key=lambda item: item[0])


def split_region(source: SourceText, start: int, end: int, *, budget: int,
                 max_lines: int, boundaries: list[int]):
    """Prefer statement ends, then lines; hard-split long lines with no overlap."""
    while start < end:
        line_index = source.line(start) - 1
        line_cap = source.starts[line_index + max_lines] if line_index + max_lines < len(source.starts) else end
        stop = min(end, start + budget, line_cap)
        if stop < end:
            index = bisect_right(boundaries, stop) - 1
            if index >= 0 and boundaries[index] > start:
                stop = boundaries[index]
            else:
                newline = source.text.rfind("\n", start, stop)
                if newline >= start:
                    stop = newline + 1
                else:
                    space = source.text.rfind(" ", start + (stop - start) // 2, stop)
                    if space >= start:
                        stop = space + 1
        yield start, stop
        start = stop
