import streamlit as st
import requests
import ast
import pandas as pd
import re
from language_handler import get_language, parse_code_generically, SUPPORTED_LANGUAGES

st.set_page_config(page_title="Docstring Generator", layout="centered")

st.title("🤖 Automated Docstring Generator")
st.write("Upload a code file and generate AI-powered docstrings automatically.")

# Supported extensions for the file uploader
supported_exts = [ext.strip(".") for ext in SUPPORTED_LANGUAGES.keys()]
uploaded_file = st.file_uploader(f"Upload a file ({', '.join(supported_exts)})", type=supported_exts)

# ===============================
# DETECT CODE STRUCTURE
# ===============================
def detect_structure(code, lang="python"):
    if lang == "python":
        try:
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
        except:
            # Fallback to generic if AST fails
            parsed = parse_code_generically(code, lang)
            return [f["name"] for f in parsed], [], []
    else:
        # Generic parsing for JS, Java, C
        parsed = parse_code_generically(code, lang)
        return [f["name"] for f in parsed], [], []


# ===============================
# CODE ANALYSIS HELPERS
# ===============================
def count_lines_breakdown(code, lang):
    """Counts total lines, code lines, comment lines, and blank lines."""
    lines = code.split("\n")
    total = len(lines)
    blank = sum(1 for l in lines if l.strip() == "")
    
    comment_lines = 0
    in_block_comment = False
    
    for line in lines:
        stripped = line.strip()
        
        # Block comments
        if lang in ["java", "javascript", "c"]:
            if "/*" in stripped:
                in_block_comment = True
            if in_block_comment:
                comment_lines += 1
            if "*/" in stripped:
                in_block_comment = False
                continue
            if stripped.startswith("//"):
                comment_lines += 1
        elif lang == "python":
            if stripped.startswith("#"):
                comment_lines += 1
            elif stripped.startswith('"""') or stripped.startswith("'''"):
                in_block_comment = not in_block_comment
                comment_lines += 1
            elif in_block_comment:
                comment_lines += 1
    
    code_lines = total - blank - comment_lines
    return total, code_lines, comment_lines, blank


def get_function_details(code, lang):
    """Get detailed info about each function for visualizations."""
    parsed = parse_code_generically(code, lang)
    details = []
    
    for func in parsed:
        name = func.get("name", "unknown")
        params = func.get("parameters", [])
        body = func.get("function_code", "")
        body_lines = len(body.split("\n")) if body else 0
        
        details.append({
            "Function": name,
            "Parameters": len(params),
            "Lines": body_lines,
        })
    
    return details


# ===============================
# VISUALIZATION SECTION
# ===============================
def show_code_visualizations(code, lang):
    """Display code analysis visualizations."""
    
    st.subheader("📊 Code Analysis")
    
    # --- Row 1: Overview Metrics ---
    total, code_lines, comment_lines, blank = count_lines_breakdown(code, lang)
    func_details = get_function_details(code, lang)
    num_functions = len(func_details)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Lines", total)
    col2.metric("Code Lines", code_lines)
    col3.metric("Comments", comment_lines)
    col4.metric("Functions", num_functions)
    
    if not func_details:
        return
    
    df = pd.DataFrame(func_details)
    
    # --- Row 2: Line Composition ---
    st.markdown("#### Line Composition")
    composition_df = pd.DataFrame({
        "Category": ["Code", "Comments", "Blank"],
        "Lines": [code_lines, comment_lines, blank]
    })
    composition_df = composition_df.set_index("Category")
    st.bar_chart(composition_df)

    # --- Row 3: Lines per Function ---
    if len(df) > 0:
        st.markdown("#### Lines per Function")
        lines_df = df[["Function", "Lines"]].set_index("Function")
        st.bar_chart(lines_df)
    
    # --- Row 4: Parameters per Function ---
    if len(df) > 0:
        st.markdown("#### Parameters per Function")
        params_df = df[["Function", "Parameters"]].set_index("Function")
        st.bar_chart(params_df)
    
    # --- Row 5: Summary Table ---
    with st.expander("📋 Function Details Table"):
        st.dataframe(df, use_container_width=True)


if uploaded_file is not None:
    code = uploaded_file.getvalue().decode("utf-8")
    lang = get_language(uploaded_file.name)
    
    # Default style
    style = "google"

    # ===============================
    # PYTHON SPECIFIC UI: STYLE & STRUCTURE
    # ===============================
    if lang == "python":
        st.info("🐍 Python detected: Full features enabled (Docstrings, Explain, Optimize, Structure).")
        
        # STYLE SELECTOR (Only for Python)
        style = st.selectbox(
            "Choose Docstring Style",
            ["google", "numpy", "sphinx"]
        )

        try:
            functions, classes, methods = detect_structure(code, lang)

            # SHOW DETECTED STRUCTURE (Only for Python)
            st.subheader("🔎 Detected Code Structure")

            col1, col2, col3 = st.columns(3)

            col1.metric("Functions", len(functions))
            col2.metric("Classes", len(classes))
            col3.metric("Methods", len(methods))

            if functions:
                with st.expander("Show Functions"):
                    st.code("\n".join(functions), language=lang)

            if classes:
                with st.expander("Show Classes"):
                    st.code("\n".join(classes), language=lang)

            if methods:
                with st.expander("Show Methods"):
                    st.code("\n".join(methods), language=lang)

        except Exception as e:
            st.error(f"Code parsing error: {str(e)}")
    else:
        st.info(f"📁 {lang.capitalize()} detected: Docstring generation enabled.")

    # ===============================
    # CODE VISUALIZATIONS (All Languages)
    # ===============================
    show_code_visualizations(code, lang)

    st.markdown("---")

    # ===============================
    # BUTTONS SECTION
    # ===============================
    
    # 1. GENERATE DOCSTRINGS (All Languages)
    if st.button("✨ Generate Docstrings"):
        with st.spinner(f"Processing {lang} with AI..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            try:
                response = requests.post(
                    f"http://127.0.0.1:8000/process-code/?style={style}",
                    files=files
                )

                if response.status_code == 200:
                    result = response.json()
                    st.success("Docstrings generated successfully!")
                    st.subheader("📄 Updated Code")
                    st.code(result["documented_code"], language=lang)
                    st.download_button(
                        label="⬇ Download Documented File",
                        data=result["documented_code"],
                        file_name=f"documented_{uploaded_file.name}",
                        mime="text/plain"
                    )
                else:
                    st.error(response.json()["detail"])
            except Exception as e:
                st.error(f"Connection Error: {str(e)}")

    # 2. EXPLAIN & OPTIMIZE (Only for Python)
    if lang == "python":
        st.markdown("---")
        # EXPLAIN CODE SECTION
        if st.button("🧠 Explain Code"):
            with st.spinner("Analyzing code with AI..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                try:
                    response = requests.post("http://127.0.0.1:8000/explain-code/", files=files)
                    if response.status_code == 200:
                        result = response.json()
                        st.success("Code explained successfully!")
                        st.subheader("🧠 AI Explanation Mode")
                        for item in result["explanations"]:
                            with st.expander(f"📌 {item['name']}"):
                                st.write(item["simple_explanation"])
                                st.write("### 🔍 Step-by-step")
                                for step in item["step_by_step"]:
                                    st.write(f"- {step}")
                                if item.get("example"):
                                    st.write("### 💡 Example")
                                    st.code(item["example"], language=lang)
                                if item.get("edge_cases"):
                                    st.write("### ⚠️ Edge Cases")
                                    for edge in item["edge_cases"]:
                                        st.write(f"- {edge}")
                    else:
                        st.error(response.json()["detail"])
                except Exception as e:
                    st.error(f"Connection Error: {str(e)}")

        st.markdown("---")
        # OPTIMIZE CODE SECTION
        if st.button("⚡ Optimize Code"):
            with st.spinner("Optimizing code with AI..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                try:
                    response = requests.post("http://127.0.0.1:8000/optimize-code/", files=files)
                    if response.status_code == 200:
                        result = response.json()
                        st.success("Code optimized successfully!")
                        st.subheader("⚡ Code Comparison")
                        c1, c2 = st.columns(2)
                        with c1: 
                            st.markdown("### 📄 Original")
                            st.code(code, language=lang)
                        with c2: 
                            st.markdown("### 🚀 Optimized")
                            st.code(result["optimized_code"], language=lang)
                        
                        st.subheader("📊 Improvements")
                        for imp in result["improvements"]: st.write(f"✅ {imp}")
                    else:
                        st.error(response.json()["detail"])
                except Exception as e:
                    st.error(f"Connection Error: {str(e)}")