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
from optimizer_module import run_code_optimization
from language_handler import get_language, parse_code_generically, SUPPORTED_LANGUAGES

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

app = FastAPI(title="Automated Multi-Language Docstring Generator")


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

def extract_imports(code_text, lang="python"):
    if lang != "python":
        # Simplified import extraction for other languages
        if lang in ["javascript", "java", "c"]:
            matches = re.findall(r"import\s+(['\"]?[\w\.]+'\"?|[\w\.*]+)", code_text)
            return list(set(matches))
        return []

    try:
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
    except:
        return []


# ==============================
# STEP 4: AST Parsing
# ==============================

def parse_source_code(code_text, lang="python"):
    return parse_code_generically(code_text, lang)


# ==============================
# STEP 5 & 6: AI Semantic Analysis
# ==============================

def clean_json_output(raw_output):
    """
    Cleaner that handles markdown, conversational filler, and trailing text.
    Ensures a valid JSON array is extracted for docstring generation.
    """
    raw_output = raw_output.strip()
    
    # ❌ Remove markdown code blocks if present
    if "```json" in raw_output:
        start = raw_output.find("```json") + 7
        end = raw_output.find("```", start)
        raw_output = raw_output[start:end].strip()
    elif "```" in raw_output:
        start = raw_output.find("```") + 3
        end = raw_output.find("```", start)
        raw_output = raw_output[start:end].strip()

    # ❌ Handle cases with conversational text before/after the JSON array
    start_bracket = raw_output.find("[")
    end_bracket = raw_output.rfind("]") + 1
    
    if start_bracket != -1 and end_bracket > start_bracket:
        return raw_output[start_bracket:end_bracket]
    
    return raw_output

def analyze_with_ai(parsed_structure, code_text, imports, lang="python"):
    
    # 🩹 CONTEXT SAFETY: Trim overly large function bodies before sending
    processed_structure = []
    for item in parsed_structure:
        new_item = item.copy()
        fcode = new_item.get("function_code", "")
        
        # If body is > 2000 chars, trim it to save tokens and prevent context overflow
        if len(fcode) > 2000:
            new_item["function_code"] = fcode[:2000] + "\n... [TRUNCATED DUE TO SIZE]"
        
        processed_structure.append(new_item)

    prompt = f"""
You are a senior {lang} developer and software architecture expert.

Your task is to analyze the provided {lang} code and generate high-confidence docstring information.

INSTRUCTIONS:
1.  **Infer Purpose**: Use the `function_code` to understand the logic (e.g., `a + b` implies addition, `return a * b` implies multiplication — NOT printing).
2.  **USE the `return_type` field**: Each function has a `return_type` field extracted from its signature. Use it EXACTLY. If return_type is "void", the function returns nothing. If return_type is "int", the function returns an integer. Do NOT contradict the return_type.
3.  **Logic-Based Typing**: Deduce parameter types from HOW they are USED in the function body:
    - If a parameter uses string slicing (e.g., `param[:3]`, `param[3:6]`), it is a `str`, NOT `int`.
    - If a parameter uses numeric operators (`+`, `-`, `*`, `/`, `%`), it is likely `int` or `float`.
    - If a parameter is compared with `==` to a string literal, it is a `str`.
    - If a parameter is iterated over with `for x in param`, it is likely `list` or `iterable`.
    - If a parameter is used as `param.append()`, it is a `list`.
    - ALWAYS check actual usage in the function body, not just the parameter name.
4.  **Accuracy Over Caution**: Only use "undetermined" if the function body is genuinely empty.

Required JSON format:

[
  {{
    "name": "function_name",
    "purpose": "A clear, professional description based on implementation logic. Describe what it ACTUALLY does, not what other functions do.",
    "parameters": {{
      "param1": "type - meaning (derived from logic)"
    }},
    "returns": "return_type - description of the returned value"
  }}
]

Analyze this structure:
{processed_structure}
"""

    try:

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"You are a {lang} code analysis expert. You MUST document EVERY function in the provided list. DO NOT skip any."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=4096
        )

        raw_output = completion.choices[0].message.content.strip()
        cleaned_json = clean_json_output(raw_output)

        # Validate bracket matching
        if "[" not in cleaned_json or "]" not in cleaned_json:
            raise HTTPException(
                status_code=500,
                detail="AI response was incomplete or missing JSON array."
            )

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

        # Ensure code is a string
        if not isinstance(code, str):
            code = str(code)
        code_lower = code.lower()

        # =========================
        # 🔥 CLEAN STEP-BY-STEP
        # =========================
        cleaned_steps = []

        for step in steps:
            # Handle dictionary returned by AI
            if isinstance(step, dict):
                step = next(iter(step.values())) if step else ""
            
            if not isinstance(step, str):
                step = str(step)

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
            # Handle dictionary returned by AI
            if isinstance(edge, dict):
                edge = next(iter(edge.values())) if edge else ""

            if not isinstance(edge, str):
                edge = str(edge)

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
                if any("zerodivisionerror" in str(e).lower() for e in cleaned_edges):
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
def explain_code_with_ai(parsed_structure, code_text, imports, lang="python"):

    prompt = f"""
You are an expert {lang} mentor and lead architect.

Explain the following {lang} code for a professional developer audience.

Here is the parsed structure with function names, parameters, and implementation:
{parsed_structure}

Here are the imports used:
{imports}

Full source code:
{code_text}

For EACH function, provide:
- name: the exact function name
- simple_explanation: 1-2 sentence summary of what it does
- step_by_step: list of strings describing the logic flow
- example: a concrete "Input -> Output" example
- edge_cases: list of strings with potential issues or failure points

Respond ONLY with a valid JSON array of objects. No text outside the JSON.
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"You are a {lang} expert teacher. You MUST explain EVERY function. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4096
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ==============================
# Upload Endpoint
# ==============================

@app.post("/process-code/")
async def upload_and_process_file(
    file: UploadFile = File(...),
    style: str = "google"
):
    lang = get_language(file.filename)
    if lang == "unknown":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {list(SUPPORTED_LANGUAGES.keys())}"
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
        imports = extract_imports(code_text, lang)

        # Parsing
        parsed_result = parse_source_code(code_text, lang)

        if not parsed_result:
            raise HTTPException(
                status_code=400,
                detail="No functions or classes found in file."
            )

        # AI Analysis
        ai_result = analyze_with_ai(parsed_result, code_text, imports, lang)

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
        updated_code = insert_docstrings_into_code(code_text, ai_data, parsed_result, lang, style)

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
    lang = get_language(file.filename)
    if lang == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported file type")

    try:
        content = await file.read()
        code_text = content.decode("utf-8")

        imports = extract_imports(code_text, lang)
        parsed_result = parse_source_code(code_text, lang)

        if not parsed_result:
            raise HTTPException(status_code=400, detail="No functions found")

        # 🔥 CHUNK PROCESSING
        all_explanations = []

        for chunk in chunk_list(parsed_result, 3):
            ai_result = explain_code_with_ai(chunk, code_text, imports, lang)

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
    


@app.post("/optimize-code/")
async def optimize_code(file: UploadFile = File(...)):
    lang = get_language(file.filename)
    if lang == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported file type")

    try:
        content = await file.read()
        code_text = content.decode("utf-8")

        if not code_text.strip():
            raise HTTPException(status_code=400, detail="File is empty")

        imports = extract_imports(code_text, lang)
        parsed_result = parse_source_code(code_text, lang)

        if not parsed_result:
            raise HTTPException(status_code=400, detail="No functions found")

        result = run_code_optimization(
            client,
            parsed_result,
            code_text,
            imports,
            lang
        )

        # ✅ 🔥 STEP 4 FIX (VERY IMPORTANT)
        optimized_code = result["optimized_code"].replace("\\n", "\n")

        return {
            "status": "success",
            "optimized_code": optimized_code,   # 👈 FIXED
            "improvements": result["improvements"],
            "explanations": result["explanations"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ==============================
# Run Server
# ==============================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
