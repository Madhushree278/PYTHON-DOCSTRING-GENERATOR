import os
import ast
import json
import time
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from groq import Groq
import uvicorn
import re


from quality_check import validate_ai_output
from docstring_module import insert_docstrings_into_code

def extract_valid_json(raw_output: str):
    try:
        # STEP 1: Extract JSON array
        start = raw_output.find('[')
        end = raw_output.rfind(']') + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON array found")

        json_str = raw_output[start:end]

        # STEP 2: Fix common AI JSON issues safely

        # remove trailing commas
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)

        # fix smart quotes (very important 🔥)
        json_str = json_str.replace("“", '"').replace("”", '"')

        # remove invisible control characters
        json_str = re.sub(r"[\x00-\x1F]+", " ", json_str)

        # STEP 3: Try parsing
        return json.loads(json_str)

    except Exception:
        print("\n❌ JSON ERROR DEBUG ----------------")
        print(raw_output)
        print("-----------------------------------\n")

        raise HTTPException(
            status_code=500,
            detail="AI returned invalid JSON"
        )
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
    name = name.split(".")[-1]
    name = name.strip()

    # ✅ Preserve special method names
    if name.startswith("__") and name.endswith("__"):
        return name.lower()

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
def smart_clean_explanations(explanations, parsed_result):

    code_map = {
        item["name"]: item.get("function_code", "")
        for item in parsed_result
    }

    for item in explanations:

        name = item.get("name", "")
        code = code_map.get(name, "")

        steps = item.get("step_by_step", [])
        edge_cases = item.get("edge_cases", [])

        code_lower = code.lower()

        # =========================
        # 🔥 CLEAN STEP-BY-STEP
        # =========================
        cleaned_steps = []

        for step in steps:
            step_lower = step.lower().strip()

            # ❌ remove fake validations
            if ("check if" in step_lower or "validate" in step_lower) and "if" not in code_lower:
                continue

            # ❌ remove incomplete steps
            if step_lower in ["if", "if not", "else"]:
                continue

            # ❌ remove hallucinated condition
            if step_lower.startswith("if") and "if" not in code_lower:
                continue

            cleaned_steps.append(step)

        item["step_by_step"] = cleaned_steps

        # =========================
        # 🔥 CLEAN EDGE CASES
        # =========================
        cleaned_edges = []
        seen = set()

        for edge in edge_cases:
            edge_lower = edge.lower().strip()

            # ❌ remove wrong logic (like "return first element if empty")
            if "return the first" in edge_lower and "empty" in edge_lower:
                continue

            # ✅ detect ZeroDivisionError
            if "/" in code_lower and "len(" in code_lower:
                if "zero" not in edge_lower:
                    edge = "May raise ZeroDivisionError if divisor is zero"
                    edge_lower = edge.lower()

            # ❌ remove duplicate ZeroDivisionError
            if "zerodivisionerror" in edge_lower:
                if any("zerodivisionerror" in e.lower() for e in cleaned_edges):
                    continue

            # ✅ detect IndexError
            if "[0]" in code_lower:
                if "empty" not in edge_lower:
                    edge = "May raise IndexError if input list is empty"
                    edge_lower = edge.lower()

            # ❌ remove fake type errors
            if ("type" in edge_lower or "string" in edge_lower or "invalid" in edge_lower):
                if "isinstance" not in code_lower and "type(" not in code_lower:
                    continue

            # ❌ remove fake empty string returns
            if "empty string" in edge_lower or "return empty" in edge_lower:
                if '""' not in code and "return ''" not in code:
                    continue

            # ❌ remove vague AI statements
            if ("incorrectly" in edge_lower or "may cause" in edge_lower):
                if "raise" not in edge_lower:
                    continue

            # ❌ remove fake padding logic
            if "pad" in edge_lower:
                if "len(" not in code_lower:
                    continue

            # ❌ remove duplicates
            if edge_lower in seen:
                continue

            seen.add(edge_lower)
            cleaned_edges.append(edge)

        item["edge_cases"] = cleaned_edges

    return explanations

#ai explanation
def explain_code_with_ai(parsed_structure, code_text, imports):

    prompt = f"""
You are a senior Python developer and an expert teacher.

Your task is to explain Python code in a very clear, beginner-friendly way.

Use the following data:

Parsed Structure:
{parsed_structure}

Imports:
{imports}


INSTRUCTIONS:

1. Explain EVERY function or method.
2. Keep explanations SIMPLE and STEP-BY-STEP.
3. Avoid technical jargon unless necessary.
4. Ignore "self" parameter.

For each function return:

- name
- simple_explanation (1–2 lines)
- step_by_step (list of steps)
- example (input → output)
- edge_cases (possible issues)

Edge cases must be logically correct and reflect actual behavior of the code.
Edge cases must be clearly explained.
Ensure all examples and edge cases are logically correct and mathematically accurate.
- Only describe behavior that is explicitly present in the code
- Do NOT assume validations or checks unless clearly implemented
- Do NOT invent edge cases

IMPORTANT:
- Ensure all examples are logically correct
- Ensure edge cases are accurate
- Do NOT give incorrect statements

STRICT RULES:

- Return ONLY valid JSON
- Your response MUST start with [
- Your response MUST end with ]
- Do NOT include any explanation outside JSON
- Do NOT include comments
- Do NOT include trailing commas
- Use double quotes for all keys and strings
- Ensure JSON is perfectly valid and parseable

FORMAT:

[
  {{
    "name": "function_name",
    "simple_explanation": "What this function does",
    "step_by_step": ["step1", "step2"],
    "example": "func(1,2) → 3",
    "edge_cases": ["possible issue"]
  }}
]
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful coding tutor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )

        # ✅ Just return raw output (DO NOT process here)
        return completion.choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
def chunk_list(data, size=3):
    for i in range(0, len(data), size):
        yield data[i:i + size]


# ===============================explain code section
@app.post("/explain-code/")
async def explain_code(file: UploadFile = File(...)):

    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files allowed")

    try:
        content = await file.read()
        code_text = content.decode("utf-8")

        imports = extract_imports(code_text)
        parsed_result = parse_code_with_ast(code_text)

        if not parsed_result:
            raise HTTPException(status_code=400, detail="No functions found")

        # 🔥 CHUNK PROCESSING
        all_explanations = []

        for chunk in chunk_list(parsed_result, 3):
            ai_result = explain_code_with_ai(chunk, code_text, imports)

            try:
                chunk_explanations = extract_valid_json(ai_result)

                if isinstance(chunk_explanations, list):
                    all_explanations.extend(chunk_explanations)

            except:
                continue  # skip broken chunk safely

        # ✅ FALLBACK
        if not all_explanations:
            explanations = [
                {
                    "name": "Error",
                    "simple_explanation": "AI response formatting failed.",
                    "step_by_step": ["Please try again"],
                    "example": "",
                    "edge_cases": ["Invalid JSON returned by AI"]
                }
            ]

        else:
            explanations = all_explanations

            # 🔥 NAME FIX + SAFE DEFAULTS
            for item in explanations:

                if not isinstance(item, dict):
                    continue

                ai_name = item.get("name", "")
                normalized_ai = ai_name.lower().replace("_", "").strip()

                # ✅ HANDLE __init__
                if normalized_ai == "init":
                    item["name"] = "__init__"

                else:
                    matched_name = None

                    for parsed in parsed_result:
                        original_name = parsed.get("name", "")
                        normalized_parsed = original_name.lower().replace("__", "")

                        if (
                            normalized_ai == normalized_parsed
                            or normalized_ai == original_name.lower()
                        ):
                            matched_name = original_name
                            break

                    if matched_name:
                        item["name"] = matched_name
                    else:
                        item["name"] = ai_name if ai_name else "unknown"

                # ✅ SAFE DEFAULTS
                item.setdefault("simple_explanation", "No explanation provided")
                item.setdefault("step_by_step", [])
                item.setdefault("example", "")
                item.setdefault("edge_cases", [])

            # ✅ CLEAN ONLY VALID AI OUTPUT
            explanations = smart_clean_explanations(explanations, parsed_result)

        return {
            "status": "success",
            "explanations": explanations
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ==============================
# Run Server
# ==============================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
