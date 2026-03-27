import json
import re
from fastapi import HTTPException


# ===============================
# CLEAN AI JSON RESPONSE
# ===============================
def clean_ai_json(raw_output: str):
    try:
        import json, re

        # Remove markdown
        raw_output = re.sub(r"```.*?```", "", raw_output, flags=re.DOTALL)

        # Extract JSON
        start = raw_output.find("{")
        end = raw_output.rfind("}") + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON found")

        json_str = raw_output[start:end]

        # ✅ MUST BE INSIDE try
        json_str = json_str.strip()

        # Fix common issues
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)
        json_str = json_str.replace("“", '"').replace("”", '"')

        return json.loads(json_str)

    except Exception:
        print("\n❌ RAW AI OUTPUT:\n", raw_output)
        raise

# ===============================
# AI OPTIMIZATION ENGINE
# ===============================
def optimize_with_ai(client, parsed_structure, code_text, imports):

    prompt = f"""
You are a senior Python performance engineer.

Your task is to analyze and optimize Python code.

DO NOT change functionality.

Parsed Structure:
{parsed_structure}

Imports:
{imports}

Full Code:
{code_text}

RETURN ONLY VALID JSON.

CRITICAL RULES:
- Escape newlines using \\n
- Do NOT include markdown
- Response must start with {{ and end with }}

Example:

{{
  "optimized_code": "def add(a, b):\\n    return a + b",
  "improvements": ["Used direct return"],
  "explanations": ["Simplified function"]
}}
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a Python optimization expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1200
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



import json


# ===============================
# ANALYZE CODE
# ===============================
def analyze_code_with_ai(client, code_text):
    prompt = f"""
You are a senior software engineer.

Analyze the following Python code and suggest optimization steps.

Return ONLY JSON:

{{
  "optimization_plan": ["step1", "step2"]
}}

Code:
{code_text}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


# ===============================
# OPTIMIZE CODE WITH RETRY
# ===============================
def optimize_code_with_plan(client, code_text, plan_json):

    prompt = f"""
You are a strict JSON generator.

STRICT RULES:
- Return ONLY valid JSON
- DO NOT write any explanation outside JSON
- DO NOT use markdown
- DO NOT use triple quotes
- optimized_code MUST be a SINGLE STRING
- Escape newlines using \\n
- DO NOT return object/dictionary for code

STRICT CONSISTENCY RULE:

- ONLY list improvements that are actually applied in the optimized_code
- DO NOT mention improvements that are not present in the code
- Ensure improvements and explanations EXACTLY match the changes made

CORRECT FORMAT:

{{
  "optimized_code": "def add(a,b):\\n    return a+b",
  "improvements": ["point1"],
  "explanations": ["reason1"]
}}

PLAN:
{plan_json}

CODE:
{code_text}
"""

    for attempt in range(3):  # 🔥 RETRY
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You ONLY return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            output = response.choices[0].message.content.strip()

            # 🔥 HARD VALIDATION (VERY IMPORTANT)
            if '"""' in output:
                raise ValueError("Invalid triple quotes")

            if '"optimized_code": {' in output:
                raise ValueError("Code returned as object instead of string")

            # Parse safely
            parsed = clean_ai_json(output)

            return parsed  # ✅ RETURN DICT (NOT STRING)

        except Exception:
            print(f"Retry {attempt+1} failed...")

    # 🔴 FINAL FALLBACK
    return {
        "optimized_code": code_text,
        "improvements": ["Optimization failed after retries"],
        "explanations": ["AI could not return valid JSON"]
    }


def filter_fake_improvements(result):
    code = result.get("optimized_code", "")
    improvements = result.get("improvements", [])
    explanations = result.get("explanations", [])

    filtered_improvements = []
    filtered_explanations = []

    for imp, exp in zip(improvements, explanations):
        imp_lower = imp.lower()

        # Check if keywords from improvement exist in code
        if any(word in code.lower() for word in imp_lower.split()):
            filtered_improvements.append(imp)
            filtered_explanations.append(exp)

    result["improvements"] = filtered_improvements
    result["explanations"] = filtered_explanations

    return result


# ===============================
# MAIN OPTIMIZATION PIPELINE
# ===============================
import json

def run_code_optimization(client, parsed_structure, code_text, imports):

    # STEP 1: ANALYZE
    analysis_raw = analyze_code_with_ai(client, code_text)

    analysis = safe_json_parse(analysis_raw, {
        "optimization_plan": ["Improve code using best practices"]
    })

    # STEP 2: OPTIMIZE
    optimize_raw = optimize_code_with_plan(
        client,
        code_text,
        json.dumps(analysis, indent=2)
    )

    # ❌ If AI fails
    if not isinstance(optimize_raw, dict):
        return {
            "optimized_code": code_text,
            "improvements": ["Optimization failed"],
            "explanations": ["AI returned invalid format"]
        }

    result = optimize_raw

    # STEP 3 🔥 AUTO CHANGE DETECTION

    # Detect differences
    changes = detect_code_changes(code_text, result["optimized_code"])

    # Generate improvements from actual changes
    auto_improvements, auto_explanations = generate_improvements_from_changes(changes)

    # Override AI output ONLY if real changes found
    if auto_improvements:
        result["improvements"] = auto_improvements
        result["explanations"] = auto_explanations
    else:
        result["improvements"] = ["No significant optimizations applied"]
        result["explanations"] = ["The original code was already efficient"]

    return result

def safe_json_parse(raw_output, default_value):
    try:
        return clean_ai_json(raw_output)
    except:
        return default_value
import difflib

def detect_code_changes(original_code, optimized_code):
    changes = []

    diff = difflib.ndiff(
        original_code.splitlines(),
        optimized_code.splitlines()
    )

    for line in diff:
        if line.startswith("- "):
            changes.append(("removed", line[2:]))
        elif line.startswith("+ "):
            changes.append(("added", line[2:]))

    return changes

def generate_improvements_from_changes(changes):
    improvements = []
    explanations = []

    for change_type, line in changes:

        line_lower = line.lower()

        if "max(" in line_lower:
            improvements.append("Replaced manual loop with built-in max()")
            explanations.append("max() is optimized and improves readability")

        elif "sum(" in line_lower:
            improvements.append("Replaced manual summation with built-in sum()")
            explanations.append("sum() reduces complexity and is faster")

        elif "return username" in line_lower:
            improvements.append("Simplified boolean return")
            explanations.append("Direct return avoids unnecessary conditionals")

        elif "**" in line_lower:
            improvements.append("Used exponent operator **")
            explanations.append("Cleaner and more Pythonic than multiplication")
        
        elif ".clear()" in line_lower:
            improvements.append("Used list.clear() instead of reassigning list")
            explanations.append("clear() modifies list in-place and is more efficient")

    return improvements, explanations
