import streamlit as st
import ast

st.set_page_config(page_title="AI Docstring Generator")

st.title("🤖 AI Automated Python Docstring Generator")
st.write("Upload a Python file and generate docstrings automatically.")

# ===============================
# STEP 7 – Docstring Creation Module
# ===============================
def create_docstring(function_name, parameters):
    """
    Creates a formatted docstring for a function.
    """
    doc = f'"""\n    Function: {function_name}\n\n    Parameters:\n'

    if parameters:
        for param in parameters:
            doc += f"        {param}: Description\n"
    else:
        doc += "        None\n"

    doc += "\n    Returns:\n        Description\n    \"\"\""

    return doc


# ===============================
# STEP 8 – Docstring Insertion Module
# ===============================
def insert_docstrings_into_code(code):
    """
    Inserts generated docstrings into all functions in the code.
    """
    tree = ast.parse(code)
    lines = code.split("\n")

    offset = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):

            function_name = node.name
            parameters = [arg.arg for arg in node.args.args]

            docstring = create_docstring(function_name, parameters)

            insert_position = node.lineno + offset
            lines.insert(insert_position, docstring)

            offset += len(docstring.split("\n"))

    return "\n".join(lines)


# ===============================
# Streamlit UI
# ===============================
uploaded_file = st.file_uploader("📂 Upload Python file", type=["py"])

if uploaded_file is not None:

    original_code = uploaded_file.read().decode("utf-8")

    st.subheader("📄 Original Code")
    st.code(original_code, language="python")

    if st.button("Generate Docstrings"):

        updated_code = insert_docstrings_into_code(original_code)

        st.subheader("✅ Updated Code with Docstrings")
        st.code(updated_code, language="python")

        st.download_button(
            label="⬇ Download Updated File",
            data=updated_code,
            file_name="documented_file.py",
            mime="text/plain"
        )