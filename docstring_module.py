import streamlit as st
import ast
import json

st.set_page_config(page_title="AI Docstring Generator")

st.title("🤖 AI Automated Python Docstring Generator")
st.write("Upload a Python file and generate docstrings automatically.")


# ===============================
# STEP 7 – Generate Docstring from AI Output
# ===============================
def create_docstring_from_ai(ai_data, indent):
    purpose = ai_data["purpose"]
    parameters = ai_data["parameters"]
    returns = ai_data["returns"]

    # Remove 'self'
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

    # Convert list → dictionary for quick lookup
    ai_map = {item["name"]: item for item in ai_understanding}

    # Sort functions by line number
    functions = sorted(
        [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)],
        key=lambda x: x.lineno
    )

    offset = 0

    for node in functions:

        # Skip if docstring already exists
        if ast.get_docstring(node):
            continue

        function_name = node.name

        # Skip if AI didn’t analyze it
        if function_name not in ai_map:
            continue

        # Detect indentation
        def_line = lines[node.lineno - 1 + offset]
        base_indent = len(def_line) - len(def_line.lstrip())
        indent = " " * (base_indent + 4)

        # Create formatted docstring
        doc_lines = create_docstring_from_ai(ai_map[function_name], indent)

        # Insert after def line
        insert_position = node.lineno + offset
        lines[insert_position:insert_position] = doc_lines

        offset += len(doc_lines)

    return "\n".join(lines)


# ===============================
# Streamlit UI
# ===============================
uploaded_file = st.file_uploader("📂 Upload Python file", type=["py"])

json_input = st.text_area("Paste AI JSON Output Here:", height=250)

if uploaded_file is not None:

    original_code = uploaded_file.read().decode("utf-8")

    st.subheader("📄 Original Code")
    st.code(original_code, language="python")

    if st.button("Generate Docstrings"):

        if not json_input.strip():
            st.error("Please paste the AI JSON output before generating docstrings.")
        else:
            try:
                ai_understanding = json.loads(json_input)

                updated_code = insert_docstrings_into_code(
                    original_code,
                    ai_understanding
                )

                st.subheader("✅ Updated Code with Docstrings")
                st.code(updated_code, language="python")

                st.download_button(
                    label="⬇ Download Updated File",
                    data=updated_code,
                    file_name="documented_file.py",
                    mime="text/plain"
                )

            except json.JSONDecodeError:
                st.error("Invalid JSON format. Please check your AI output.")