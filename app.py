import streamlit as st
import requests

st.set_page_config(page_title="Docstring Generator", layout="centered")

st.title("Automated Python Docstring Generator")
st.write("Upload a Python file to analyze its structure using AST and AI.")

uploaded_file = st.file_uploader("Upload a .py file", type=["py"])

if uploaded_file is not None:
    if st.button("Analyze Code"):

        with st.spinner("Analyzing code using AST and AI..."):

            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue())
            }

            try:
                response = requests.post(
                    "http://127.0.0.1:8000/process-code/",
                    files=files
                )

                if response.status_code == 200:
                    result = response.json()

                    st.success("Analysis completed successfully!")

                    # STEP 4 Output
                    st.subheader("Parsed Structure (AST)")
                    st.json(result["parsed_structure"])

                    # STEP 5 & 6 Output
                    st.subheader("AI Understanding (Step 5 & 6)")
                    st.write(result["ai_analysis"])

                else:
                    st.error("Backend Error:")
                    st.json(response.json())

            except Exception as e:
                st.error(f"Connection Error: {str(e)}")