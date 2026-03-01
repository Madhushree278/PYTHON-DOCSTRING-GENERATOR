import ast

# ===============================
# STEP 7 – Generate Docstring from AI Output
# ===============================

def create_docstring_from_ai(ai_data, indent):
    purpose = ai_data["purpose"]
    parameters = ai_data["parameters"]
    returns = ai_data["returns"]

    parameters = {k: v for k, v in parameters.items() if k != "self"}

    doc_lines = [
        indent + '"""',
        indent + purpose,
        indent + "",
        indent + "Parameters:",
    ]

    if parameters:
        for param, desc in parameters.items():
            doc_lines.append(indent + f"    {param}: {desc}")
    else:
        doc_lines.append(indent + "    None")

    doc_lines += [
        indent + "",
        indent + "Returns:",
        indent + f"    {returns}",
        indent + '"""'
    ]

    return doc_lines


# ===============================
# STEP 8 – Insert Docstrings
# ===============================

def insert_docstrings_into_code(code, ai_understanding):
    tree = ast.parse(code)
    lines = code.split("\n")

    ai_map = {item["name"]: item for item in ai_understanding}

    functions = sorted(
        [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)],
        key=lambda x: x.lineno
    )

    offset = 0

    for node in functions:

        if ast.get_docstring(node):
            continue

        function_name = node.name

        if function_name not in ai_map:
            continue

        def_line = lines[node.lineno - 1 + offset]
        base_indent = len(def_line) - len(def_line.lstrip())
        indent = " " * (base_indent + 4)

        doc_lines = create_docstring_from_ai(ai_map[function_name], indent)

        insert_position = node.lineno + offset
        lines[insert_position:insert_position] = doc_lines

        offset += len(doc_lines)

    return "\n".join(lines)