import streamlit as st
import requests
import ast

st.set_page_config(page_title="Docstring Generator", layout="centered")

st.title("🤖 Automated Python Docstring Generator")
st.write("Upload a Python file and generate AI-powered docstrings automatically.")

# STYLE SELECTOR
style = st.selectbox(
    "Choose Docstring Style",
    ["google", "numpy", "sphinx"]
)

uploaded_file = st.file_uploader("Upload a .py file", type=["py"])


# ===============================
# DETECT CODE STRUCTURE
# ===============================
def detect_structure(code):

    tree = ast.parse(code)

    # Attach parent nodes
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    functions = []
    classes = []
    methods = []

    for node in ast.walk(tree):

        if isinstance(node, ast.ClassDef):
            classes.append(node.name)

        elif isinstance(node, ast.FunctionDef):

            if hasattr(node, "parent") and isinstance(node.parent, ast.ClassDef):
                methods.append(node.name)
            else:
                functions.append(node.name)

    return functions, classes, methods


if uploaded_file is not None:

    code = uploaded_file.getvalue().decode("utf-8")

    try:

        functions, classes, methods = detect_structure(code)

        # ===============================
        # SHOW DETECTED STRUCTURE
        # ===============================
        st.subheader("🔎 Detected Code Structure")

        col1, col2, col3 = st.columns(3)

        col1.metric("Functions", len(functions))
        col2.metric("Classes", len(classes))
        col3.metric("Methods", len(methods))

        if functions:
            st.write("### Functions")
            st.code("\n".join(functions), language="python")

        if classes:
            st.write("### Classes")
            st.code("\n".join(classes), language="python")

        if methods:
            st.write("### Methods")
            st.code("\n".join(methods), language="python")

    except Exception as e:
        st.error(f"Code parsing error: {str(e)}")

    # ===============================
    # GENERATE DOCSTRINGS
    # ===============================
    if st.button("Generate Docstrings"):

        with st.spinner("Processing with AST + AI..."):

            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue())
            }

            try:

                response = requests.post(
                    f"http://127.0.0.1:8000/process-code/?style={style}",
                    files=files
                )

                if response.status_code == 200:

                    result = response.json()

                    st.success("Docstrings generated successfully!")

                    st.subheader("📄 Updated Code")
                    st.code(result["documented_code"], language="python")

                    st.download_button(
                        label="⬇ Download Documented File",
                        data=result["documented_code"],
                        file_name="documented_file.py",
                        mime="text/plain"
                    )

                    st.info(
                        f"⏱️ Processing Time: {result['processing_time_seconds']} seconds"
                    )

                else:
                    st.error(response.json()["detail"])

            except Exception as e:
                st.error(f"Connection Error: {str(e)}")