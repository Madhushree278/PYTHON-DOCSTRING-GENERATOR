import ast

# ===============================
# Helper: split type + description
# ===============================
def split_type_desc(text):

    if not text:
        return "Any", ""

    text = text.strip()

    lower = text.lower()

    if "true" in lower or "false" in lower:
        return "bool", text

    if lower == "none":
        return "None", ""

    if "," in text:
        t, d = text.split(",", 1)
        return t.strip(), d.strip()

    return "Any", text


# ===============================
# STEP 7 – Generate Docstring
# ===============================
def create_docstring_from_ai(ai_data, indent, style):

    purpose = ai_data["purpose"]
    parameters = ai_data["parameters"]
    returns = ai_data["returns"]

    parameters = {k: v for k, v in parameters.items() if k != "self"}

    doc_lines = [
        indent + '"""',
        indent + purpose,
        indent + ""
    ]

    # ================= GOOGLE =================
    if style == "google":

        doc_lines.append(indent + "Parameters:")

        if parameters:
            for param, desc in parameters.items():
                doc_lines.append(indent + f"    {param}: {desc}")
        else:
            doc_lines.append(indent + "    None")

        doc_lines += [
            indent + "",
            indent + "Returns:",
            indent + f"    {returns}"
        ]

    # ================= NUMPY =================
    elif style == "numpy":

        doc_lines.append(indent + "Parameters")
        doc_lines.append(indent + "----------")

        if parameters:
            for param, desc in parameters.items():

                ptype, pdesc = split_type_desc(desc)

                doc_lines.append(indent + f"{param} : {ptype}")

                if pdesc:
                    doc_lines.append(indent + f"    {pdesc}")
        else:
            doc_lines.append(indent + "None")

        doc_lines += [
            indent + "",
            indent + "Returns",
            indent + "-------"
        ]

        rtype, rdesc = split_type_desc(returns)

        doc_lines.append(indent + rtype)

        if rdesc and rtype != "None":
            doc_lines.append(indent + f"    {rdesc}")

    # ================= SPHINX =================
    elif style == "sphinx":

        if parameters:
            for param, desc in parameters.items():

                ptype, pdesc = split_type_desc(desc)

                doc_lines.append(indent + f":param {param}: {pdesc}")
                doc_lines.append(indent + f":type {param}: {ptype}")

        rtype, rdesc = split_type_desc(returns)

        if rdesc:
            doc_lines.append(indent + f":return: {rdesc}")
        else:
            doc_lines.append(indent + f":return: None")

        doc_lines.append(indent + f":rtype: {rtype}")

    # ✅ CRITICAL FIX — close docstring
    doc_lines.append(indent + '"""')

    return doc_lines


# ===============================
# STEP 8 – Insert Docstrings
# ===============================
def insert_docstrings_into_code(code, ai_understanding, style="google"):

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

        doc_lines = create_docstring_from_ai(
            ai_map[function_name],
            indent,
            style
        )

        insert_position = node.lineno + offset
        lines[insert_position:insert_position] = doc_lines

        offset += len(doc_lines)

    return "\n".join(lines)