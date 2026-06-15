"""
Auto-documentation script powered by Anthropic Claude.

Scans Python files in a target directory, detects undocumented classes and
functions, and uses Claude to generate docstrings matching the style of a
reference script.
"""

import ast
import argparse
import os
import sys
import textwrap
from pathlib import Path

import anthropic


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def has_docstring(node: ast.AST) -> bool:
    """Check whether a function or class node already has a docstring.

    Args:
        node: An AST node (expected to be AsyncFunctionDef, FunctionDef, or
            ClassDef).

    Returns:
        True if the node's first statement is a string constant (docstring),
        False otherwise.
    """
    return (
        isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef))
        and bool(node.body)
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )


def collect_undocumented(source: str) -> list[dict]:
    """Parse *source* and return metadata for every undocumented definition.

    Only top-level and class-level definitions are considered (nested
    functions are skipped intentionally to avoid noise).

    Args:
        source: Raw Python source code as a string.

    Returns:
        A list of dicts, each with the keys:
            - ``type`` (``"function"`` | ``"class"``)
            - ``name`` (str)
            - ``lineno`` (int, 1-based start line)
            - ``end_lineno`` (int, 1-based end line)
            - ``snippet`` (str, the raw source lines for that definition)
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"  [skip] SyntaxError while parsing: {exc}")
        return []

    lines = source.splitlines()
    results = []

    def _visit(node: ast.AST, depth: int) -> None:
        if depth > 1:          # skip deeply nested definitions
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not has_docstring(node):
                snippet_lines = lines[node.lineno - 1 : node.end_lineno]
                # Truncate very long snippets sent to the model
                if len(snippet_lines) > 80:
                    snippet_lines = snippet_lines[:80] + ["    # … (truncated)"]
                results.append(
                    {
                        "type": "class" if isinstance(node, ast.ClassDef) else "function",
                        "name": node.name,
                        "lineno": node.lineno,
                        "end_lineno": node.end_lineno,
                        "snippet": "\n".join(snippet_lines),
                    }
                )
        for child in ast.iter_child_nodes(node):
            _visit(child, depth + (1 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else 0))

    for child in ast.iter_child_nodes(tree):
        _visit(child, 0)

    return results


# ---------------------------------------------------------------------------
# Docstring insertion
# ---------------------------------------------------------------------------

def insert_docstring(source: str, lineno: int, raw_docstring: str, indent: str) -> str:
    """Insert *raw_docstring* into *source* right after the ``def``/``class`` line.

    Args:
        source: The full source code of the file.
        lineno: 1-based line number of the ``def`` or ``class`` statement.
        raw_docstring: The docstring text returned by the model (may or may
            not be wrapped in triple-quotes already).
        indent: Whitespace string to prepend to every line of the docstring.

    Returns:
        The modified source code with the docstring inserted.
    """
    lines = source.splitlines(keepends=True)

    # Find the line that ends the signature (handles multi-line signatures)
    sig_end = lineno - 1          # 0-based index of the def/class line
    for i in range(sig_end, len(lines)):
        stripped = lines[i].rstrip()
        if stripped.endswith(":"):
            sig_end = i
            break

    # Clean up whatever the model returned
    text = raw_docstring.strip()
    if text.startswith('"""') or text.startswith("'''"):
        text = text[3:]
    if text.endswith('"""') or text.endswith("'''"):
        text = text[:-3]
    text = text.strip()

    # Re-indent every line of the docstring body
    doc_lines = text.splitlines()
    formatted_lines = [f'{indent}"""{doc_lines[0]}\n']
    for dl in doc_lines[1:]:
        formatted_lines.append(f"{indent}{dl}\n" if dl.strip() else "\n")
    formatted_lines.append(f'{indent}"""\n')

    # Splice in right after the signature line
    insert_at = sig_end + 1
    lines[insert_at:insert_at] = formatted_lines

    return "".join(lines)


def body_indent(source: str, def_lineno: int) -> str:
    """Infer the indentation that the body of a definition uses.

    Args:
        source: Full source code string.
        def_lineno: 1-based line number of the ``def``/``class`` line.

    Returns:
        A string of spaces (or tabs) matching the body indentation.
    """
    lines = source.splitlines()
    # Look ahead for the first non-empty body line
    for line in lines[def_lineno:]:          # def_lineno is already 0-based +1
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#"):
            return line[: len(line) - len(stripped)]
    return "    "                            # sensible default


# ---------------------------------------------------------------------------
# Claude interaction
# ---------------------------------------------------------------------------

def build_prompt(reference_source: str, item: dict) -> str:
    """Construct the prompt sent to Claude for a single undocumented item.

    Args:
        reference_source: Full source of the reference (already documented)
            file, used to infer style.
        item: Metadata dict as returned by :func:`collect_undocumented`.

    Returns:
        A ready-to-send prompt string.
    """
    return textwrap.dedent(f"""
        You are a Python documentation expert. Your task is to write a docstring
        for the {item['type']} shown below.

        ## Style reference
        Study the docstring style used in this already-documented file and
        replicate it exactly (format, sections, indentation, tone):

        ```python
        {reference_source}
        ```

        ## Target {item['type']} to document
        ```python
        {item['snippet']}
        ```

        ## Instructions
        - Write ONLY the raw docstring content (no triple-quotes, no code fences,
          no explanation).
        - Match the style, sections, and verbosity of the reference file.
        - If the {item['type']} has parameters or return values, document them.
        - Be concise but complete.
        - Do NOT repeat the function/class signature.
    """).strip()


def generate_docstring(client: anthropic.Anthropic, reference_source: str, item: dict) -> str:
    """Call Claude to generate a docstring for *item*.

    Args:
        client: An authenticated :class:`anthropic.Anthropic` client.
        reference_source: Source of the reference file (style guide).
        item: Metadata dict for the undocumented definition.

    Returns:
        The generated docstring text (without surrounding triple-quotes).

    Raises:
        anthropic.APIError: On any API-level failure.
    """
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": build_prompt(reference_source, item)}],
    )
    return message.content[0].text.strip()


# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------

def process_file(path: Path, reference_source: str, client: anthropic.Anthropic, dry_run: bool) -> int:
    """Document all undocumented definitions inside a single Python file.

    The file is modified in-place (unless *dry_run* is True). Definitions are
    processed from bottom to top so that line numbers remain valid after each
    insertion.

    Args:
        path: Absolute or relative path to the ``.py`` file.
        reference_source: Source of the reference file used for style.
        client: Authenticated Anthropic client.
        dry_run: When True, changes are printed but the file is not written.

    Returns:
        The number of docstrings that were (or would be) added.
    """
    source = path.read_text(encoding="utf-8")
    items = collect_undocumented(source)

    if not items:
        print(f"  ✓ Nothing to document in {path}")
        return 0

    print(f"  Found {len(items)} undocumented item(s) in {path}")

    # Process bottom-up so earlier line numbers stay valid
    items.sort(key=lambda x: x["lineno"], reverse=True)

    count = 0
    for item in items:
        print(f"    → Documenting {item['type']} '{item['name']}' (line {item['lineno']})")
        try:
            docstring = generate_docstring(client, reference_source, item)
            indent = body_indent(source, item["lineno"])
            if dry_run:
                print(f"      [dry-run] Would insert:\n{textwrap.indent(docstring, ' ' * 8)}")
            else:
                source = insert_docstring(source, item["lineno"], docstring, indent)
            count += 1
        except Exception as exc:          # noqa: BLE001
            print(f"      [error] Skipping '{item['name']}': {exc}")

    if not dry_run:
        path.write_text(source, encoding="utf-8")
        print(f"  ✏  Wrote updated file: {path}")

    return count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and orchestrate the documentation run."""
    parser = argparse.ArgumentParser(
        description="Auto-document Python files using Claude."
    )
    parser.add_argument("--directory", required=True, help="Target directory with scripts to document.")
    parser.add_argument("--reference", required=True, help="Path to the already-documented reference script.")
    parser.add_argument("--dry-run", default="false", choices=["true", "false"],
                        help="Print changes without writing files.")
    args = parser.parse_args()

    dry_run = args.dry_run.lower() == "true"
    target_dir = Path(args.directory)
    reference_path = Path(args.reference)

    # Validate inputs
    if not target_dir.is_dir():
        print(f"Error: target directory '{target_dir}' does not exist.")
        sys.exit(1)
    if not reference_path.is_file():
        print(f"Error: reference script '{reference_path}' does not exist.")
        sys.exit(1)

    reference_source = reference_path.read_text(encoding="utf-8")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    py_files = [
        p for p in sorted(target_dir.rglob("*.py"))
        if p.resolve() != reference_path.resolve()
    ]

    if not py_files:
        print(f"No Python files found in '{target_dir}'.")
        sys.exit(0)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Documenting {len(py_files)} file(s) in '{target_dir}' "
          f"using '{reference_path}' as style reference.\n")

    total = 0
    for py_file in py_files:
        print(f"Processing: {py_file}")
        total += process_file(py_file, reference_source, client, dry_run)

    print(f"\nDone. {total} docstring(s) {'would be' if dry_run else 'were'} added.")


if __name__ == "__main__":
    main()