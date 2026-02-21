import streamlit as st
import requests

st.set_page_config(page_title="Docstring Generator", layout="centered")

st.title("Automated Python Docstring Generator")
st.write("Upload a Python file to analyze its structure using AST.")

uploaded_file = st.file_uploader("Upload a .py file", type=["py"])

if uploaded_file is not None:
    if st.button("Analyze Code"):

        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue())
        }

        response = requests.post(
            "http://127.0.0.1:8000/process-code/",
            files=files
        )

        if response.status_code == 200:
            result = response.json()
            st.success("Code parsed successfully!")

            st.subheader("Parsed Structure:")
            st.json(result["parsed_structure"])

        else:
            st.error("Error occurred")
            st.json(response.json())
