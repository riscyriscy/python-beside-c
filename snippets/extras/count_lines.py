"""Count code lines of the two apps: no blank lines, comment-only lines or module docstring."""

import ast
import sys

for path in sys.argv[1:]:
    with open(path) as f:
        text = f.read()
    tree = ast.parse(text)
    skip = set()
    first = tree.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        skip = set(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    n = sum(
        1
        for i, line in enumerate(text.splitlines(), 1)
        if i not in skip and line.strip() and not line.strip().startswith("#")
    )
    print(f"{path:<16}{n} lines")
