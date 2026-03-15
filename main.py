import os
import ast
import json
import time
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from groq import Groq
import uvicorn

from quality_check import validate_ai_output
from docstring_module import insert_docstrings_into_code


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
# NORMALIZE FUNCTION NAMES FOR BETTER AI UNDERSTANDING
# ==============================

def normalize_name(name):
    # remove class prefix if present
    name = name.split(".")[-1]

    # handle __init__ vs init
    name = name.replace("__", "")

    return name.lower()


# ==============================
# Extract Imports (Context Feature)
# ==============================

def extract_imports(code_text):

    tree = ast.parse(code_text)
    imports = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module if node.module else ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")

    return imports


# ==============================
# STEP 4: AST Parsing
# ==============================

def parse_code_with_ast(code_text):

    tree = ast.parse(code_text)
    parsed_data = []

    for node in tree.body:

        if isinstance(node, ast.FunctionDef):

            function_code = ast.get_source_segment(code_text, node)

            called_functions = [
                n.func.id for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            ]

            function_info = {
                "name": node.name,
                "parameters": [arg.arg for arg in node.args.args],
                "returns_value": any(
                    isinstance(n, ast.Return) for n in ast.walk(node)
                ),
                "called_functions": called_functions,
                "function_code": function_code,
                "type": "function"
            }

            parsed_data.append(function_info)

        elif isinstance(node, ast.ClassDef):

            for body_item in node.body:

                if isinstance(body_item, ast.FunctionDef):

                    method_code = ast.get_source_segment(code_text, body_item)

                    called_functions = [
                        n.func.id for n in ast.walk(body_item)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    ]

                    method_info = {
                        "class_name": node.name,
                        "name": body_item.name,
                        "parameters": [arg.arg for arg in body_item.args.args],
                        "returns_value": any(
                            isinstance(n, ast.Return) for n in ast.walk(body_item)
                        ),
                        "called_functions": called_functions,
                        "function_code": method_code,
                        "type": "class_method"
                    }

                    parsed_data.append(method_info)

    return parsed_data


# ==============================
# STEP 5 & 6: AI Semantic Analysis
# ==============================

def analyze_with_ai(parsed_structure, code_text, imports):

    prompt = f"""
You are a senior Python developer and static code analysis expert.

Your task is to analyze Python code and generate accurate docstring information.

Use ALL available context to understand each function or method:

- Function name
- Parameters
- Function implementation
- Class relationships
- Called functions
- Full file context
- Imported libraries

Parsed structure extracted using AST:
{parsed_structure}

Imports used in this file:
{imports}

Full source code of the file:
{code_text}

IMPORTANT RULES:

1. You MUST generate documentation for EVERY item in parsed_structure.
2. Each item may be:
   - a standalone function
   - a class method
3. DO NOT skip any function or method.
4. Ignore the parameter "self" when documenting parameters.
5. Infer parameter types based on usage when possible.
6. If a function does not return anything, set return description to "None".
7. If return type is obvious (int, str, bool, list, dict), include it.
8. The number of objects in your JSON output MUST match the number of items in parsed_structure.

Total functions/methods to document: {len(parsed_structure)}

For each function or class method return:

- name
- purpose (1–2 clear sentences explaining the function behavior)
- parameters (dictionary of parameter name → description)
- returns (description of returned value)

Respond ONLY with valid JSON.

Do NOT include:
- explanations
- markdown
- comments
- text outside JSON

Required JSON format:

[
  {{
    "name": "function_name",
    "purpose": "Clear explanation of what the function does.",
    "parameters": {{
      "param1": "type and meaning"
    }},
    "returns": "description of returned value"
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
            max_tokens=900
        )

        raw_output = completion.choices[0].message.content.strip()

        # Extract JSON safely
        start = raw_output.find("[")
        end = raw_output.rfind("]") + 1

        if start == -1 or end == 0:
            raise HTTPException(
                status_code=500,
                detail="AI did not return valid JSON."
            )

        cleaned_json = raw_output[start:end]

        return cleaned_json

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Groq API Error: {str(e)}"
        )


# ==============================
# Upload Endpoint
# ==============================

@app.post("/process-code/")
async def upload_and_process_python_file(
    file: UploadFile = File(...),
    style: str = "google"
):

    if not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=400,
            detail="Only .py files are allowed."
        )

    try:

        start_time = time.time()

        content = await file.read()
        code_text = content.decode("utf-8")

        if not code_text.strip():
            raise HTTPException(
                status_code=400,
                detail="File is empty."
            )

        # Extract imports for context
        imports = extract_imports(code_text)

        # AST Parsing
        parsed_result = parse_code_with_ast(code_text)

        if not parsed_result:
            raise HTTPException(
                status_code=400,
                detail="No functions or classes found in file."
            )

                # AI Analysis
        ai_result = analyze_with_ai(parsed_result, code_text, imports)

        # Parse AI JSON safely
        try:
            ai_data = json.loads(ai_result)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="AI returned invalid JSON."
            )

        # Normalize function names (fix validation mismatch)
        for item in parsed_result:
            item["name"] = normalize_name(item["name"])

        for item in ai_data:
            item["name"] = normalize_name(item["name"])

        # Validate AI output
        is_valid, message = validate_ai_output(parsed_result, json.dumps(ai_data))

        if not is_valid:
            raise HTTPException(
                status_code=500,
                detail=f"Validation Failed: {message}"
            )

        # Insert docstrings
        updated_code = insert_docstrings_into_code(code_text, ai_data, style)

        end_time = time.time()

        return {
            "status": "Success",
            "filename": file.filename,
            "processing_time_seconds": round(end_time - start_time, 2),
            "documented_code": updated_code
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
