import streamlit as st
import requests

st.set_page_config(page_title="Docstring Generator", layout="centered")

st.title("🤖 Automated Python Docstring Generator")
st.write("Upload a Python file and generate AI-powered docstrings automatically.")

uploaded_file = st.file_uploader("Upload a .py file", type=["py"])

if uploaded_file is not None:

    if st.button("Generate Docstrings"):

        with st.spinner("Processing with AST + AI..."):

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