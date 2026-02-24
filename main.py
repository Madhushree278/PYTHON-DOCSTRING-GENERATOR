import os
import ast
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from groq import Groq
import uvicorn

# ==============================
# Load Environment Variables
# ==============================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=GROQ_API_KEY)

# ==============================
# FastAPI App
# ==============================

app = FastAPI(title="Automated Python Docstring Generator")


@app.get("/")
def home():
    return {"message": "API is running successfully 🚀"}


# ==============================
# STEP 4: AST Parsing
# ==============================

def parse_code_with_ast(code_text: str):

    tree = ast.parse(code_text)
    parsed_data = []

    for node in tree.body:

        if isinstance(node, ast.FunctionDef):
            function_info = {
                "name": node.name,
                "parameters": [arg.arg for arg in node.args.args],
                "returns_value": any(
                    isinstance(n, ast.Return) for n in ast.walk(node)
                ),
                "type": "function"
            }
            parsed_data.append(function_info)

        elif isinstance(node, ast.ClassDef):
            for body_item in node.body:
                if isinstance(body_item, ast.FunctionDef):
                    method_info = {
                        "class_name": node.name,
                        "name": body_item.name,
                        "parameters": [arg.arg for arg in body_item.args.args],
                        "returns_value": any(
                            isinstance(n, ast.Return) for n in ast.walk(body_item)
                        ),
                        "type": "class_method"
                    }
                    parsed_data.append(method_info)

    return parsed_data


# ==============================
# STEP 5 & 6: AI Semantic Analysis
# ==============================

def analyze_with_ai(parsed_structure, code_text):

    prompt = f"""
You are a Python code analysis expert.

Parsed structure:
{parsed_structure}

Full source code:
{code_text}

For each function or method:
1. Explain clearly what the function does.
2. Describe each parameter and its likely type.
3. Describe what the function returns.

Respond strictly in valid JSON format like:

[
  {{
    "name": "",
    "purpose": "",
    "parameters": {{
        "param1": "type and meaning"
    }},
    "returns": ""
  }}
]
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a Python code analysis expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=800
        )

        return completion.choices[0].message.content

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Groq API Error: {str(e)}"
        )


# ==============================
# Upload Endpoint
# ==============================

@app.post("/process-code/")
async def upload_and_process_python_file(file: UploadFile = File(...)):

    if not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=400,
            detail="Only .py files are allowed."
        )

    try:
        content = await file.read()
        code_text = content.decode("utf-8")

        if not code_text.strip():
            raise HTTPException(
                status_code=400,
                detail="File is empty."
            )

        parsed_result = parse_code_with_ast(code_text)

        if not parsed_result:
            raise HTTPException(
                status_code=400,
                detail="No functions or classes found in file."
            )

        ai_result = analyze_with_ai(parsed_result, code_text)

        return {
            "status": "Success",
            "filename": file.filename,
            "parsed_structure": parsed_result,
            "ai_analysis": ai_result
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )


# ==============================
# Run Server
# ==============================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
