from language_handler import get_comment_style

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
def create_docstring_from_ai(ai_data, indent, style, original_params=None, lang="python"):

    purpose = ai_data["purpose"]
    parameters = ai_data.get("parameters", {})
    returns = ai_data.get("returns", "None")

    # Ensure parameters is a dictionary
    if isinstance(parameters, list):
        # Convert list to dictionary if AI returns a list
        new_params = {}
        for p in parameters:
            if isinstance(p, dict) and "name" in p:
                new_params[p["name"]] = p.get("description", "Any")
            else:
                new_params[str(p)] = "Any"
        parameters = new_params
    elif not isinstance(parameters, dict):
        parameters = {}

    # 🔥 HALLUCINATION FILTER: Only keep params that are in the actual source code signature
    if original_params is not None:
        valid_params = set(original_params)
        parameters = {k: v for k, v in parameters.items() if k in valid_params and k != "self"}
    else:
        parameters = {k: v for k, v in parameters.items() if k != "self"}

    # 🐍 PYTHON FIX: Normalize "void" to "None" for Python docstrings
    if lang == "python" and isinstance(returns, str):
        returns_lower = returns.lower().strip()
        if returns_lower.startswith("void"):
            returns = returns.replace("void", "None", 1).replace("VOID", "None", 1).replace("Void", "None", 1)

    comment_style = get_comment_style(lang)
    start_delim = comment_style["start"]
    end_delim = comment_style["end"]
    line_prefix = comment_style["line_prefix"]

    doc_lines = [
        indent + start_delim,
        indent + line_prefix + purpose,
        indent + line_prefix
    ]

    # ================= GOOGLE =================
    if style == "google":

        doc_lines.append(indent + line_prefix + "Parameters:")

        if parameters:
            for param, desc in parameters.items():
                doc_lines.append(indent + line_prefix + f"    {param}: {desc}")
        else:
            doc_lines.append(indent + line_prefix + "    None")

        doc_lines += [
            indent + line_prefix,
            indent + line_prefix + "Returns:",
            indent + line_prefix + f"    {returns}"
        ]

    # ================= NUMPY =================
    elif style == "numpy":

        doc_lines.append(indent + line_prefix + "Parameters")
        doc_lines.append(indent + line_prefix + "----------")

        if parameters:
            for param, desc in parameters.items():

                ptype, pdesc = split_type_desc(desc)

                doc_lines.append(indent + line_prefix + f"{param} : {ptype}")

                if pdesc:
                    doc_lines.append(indent + line_prefix + f"    {pdesc}")
        else:
            doc_lines.append(indent + line_prefix + "None")

        doc_lines += [
            indent + line_prefix,
            indent + line_prefix + "Returns",
            indent + line_prefix + "-------"
        ]

        rtype, rdesc = split_type_desc(returns)

        doc_lines.append(indent + line_prefix + rtype)

        if rdesc and rtype != "None":
            doc_lines.append(indent + line_prefix + f"    {rdesc}")

    # ================= SPHINX =================
    elif style == "sphinx":

        if parameters:
            for param, desc in parameters.items():

                ptype, pdesc = split_type_desc(desc)

                doc_lines.append(indent + line_prefix + f":param {param}: {pdesc}")
                doc_lines.append(indent + line_prefix + f":type {param}: {ptype}")

        rtype, rdesc = split_type_desc(returns)

        if rdesc:
            doc_lines.append(indent + line_prefix + f":return: {rdesc}")
        else:
            doc_lines.append(indent + line_prefix + f":return: None")

        doc_lines.append(indent + line_prefix + f":rtype: {rtype}")

    # ✅ Close docstring
    doc_lines.append(indent + end_delim)

    return doc_lines


# ===============================
# STEP 8 – Insert Docstrings
# ===============================
def insert_docstrings_into_code(code, ai_understanding, parsed_result, lang="python", style="google"):

    lines = code.split("\n")
    ai_map = {item["name"]: item for item in ai_understanding}
    
    # Sort by line number descending to avoid offset issues when removing/inserting
    sorted_functions = sorted(parsed_result, key=lambda x: x["line"], reverse=True)

    for func in sorted_functions:
        function_name = func["name"]
        line_no = func["line"]
        idx = line_no - 1  # 0-indexed line number

        if function_name not in ai_map or idx >= len(lines):
            continue

        # ===============================
        # 1. REMOVE EXISTING DOCSTRING
        # ===============================
        
        if lang == "python":
            # For Python, docstring is AFTER 'def'
            check_idx = idx + 1
            if check_idx < len(lines) and '"""' in lines[check_idx]:
                start_rm = check_idx
                end_rm = check_idx
                # Find end of docstring
                if lines[check_idx].strip() == '"""':
                    for i in range(check_idx + 1, len(lines)):
                        if '"""' in lines[i]:
                            end_rm = i
                            break
                elif lines[check_idx].count('"""') == 1:
                    for i in range(check_idx + 1, len(lines)):
                        if '"""' in lines[i]:
                            end_rm = i
                            break
                # Remove lines
                del lines[start_rm:end_rm + 1]
        else:
            # For C, Java, JS, docstring is BEFORE the signature
            check_idx = idx - 1
            if check_idx >= 0 and "*/" in lines[check_idx]:
                end_rm = check_idx
                start_rm = check_idx
                # Find start of docstring
                for i in range(check_idx, -1, -1):
                    if "/**" in lines[i] or "/*" in lines[i]:
                        start_rm = i
                        break
                # Remove lines
                del lines[start_rm:end_rm + 1]
                # Adjust idx for insertion after deletion
                idx = start_rm

        # ===============================
        # 2. INSERT NEW DOCSTRING
        # ===============================
        
        def_line = lines[idx] if idx < len(lines) else ""
        base_indent = len(def_line) - len(def_line.lstrip())
        
        if lang == "python":
            indent = " " * (base_indent + 4)
            insert_position = idx + 1
        else:
            indent = " " * base_indent
            insert_position = idx

        doc_lines = create_docstring_from_ai(
            ai_data=ai_map[function_name],
            indent=indent,
            style=style,
            original_params=func.get("parameters", []),
            lang=lang
        )

        lines[insert_position:insert_position] = doc_lines

    return "\n".join(lines)