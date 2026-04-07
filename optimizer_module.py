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
def optimize_with_ai(client, parsed_structure, code_text, imports, lang="python"):

    prompt = f"""
You are a senior {lang} performance and software architecture engineer.

Analyze and optimize the following {lang} code for:
1.  **Time Complexity**: Avoid nested loops and redundant calculations.
2.  **Memory Management**: Reduce allocations and avoid deep copying where possible.
3.  **Readability vs Performance**: Prioritize professional {lang} idioms that improve both.

CRITICAL RULES (MUST FOLLOW):
- DO NOT change public function signatures.
- DO NOT introduce external libraries.
- Focus on actual {lang} best practices.

LANGUAGE-SPECIFIC PRESERVATION RULES:

For Python:
- NEVER replace built-in functions (max, min, sum, sorted, len, any, all, zip, map, filter, enumerate) with manual loops. Built-ins are implemented in C and are FASTER than Python loops.
- NEVER replace slice operations (e.g., text[::-1], list[1:]) with manual loops. Slicing runs at C speed.
- NEVER replace direct boolean returns (e.g., "return x == y") with if/else blocks returning True/False. Direct returns are more Pythonic and equally fast.
- NEVER replace f-strings with string concatenation. f-strings are faster.
- NEVER replace .clear() with = []. .clear() modifies in-place and preserves references.
- PREFER list comprehensions over manual append loops.
- PREFER generator expressions for large datasets.

For C:
- Better pointer usage and avoiding stack overflows.

For Java:
- Primitive arrays vs. Collections, avoiding autoboxing.
- Use Streams API where appropriate.

For JavaScript:
- Non-blocking asynchronous patterns and memory-efficient closures.
- Use Array methods (map, filter, reduce) over manual loops.

Parsed Structure:
{parsed_structure}

Imports/Headers:
{imports}

Full Code:
{code_text}

RETURN ONLY VALID JSON.
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"You are a {lang} optimization expert."},
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
def analyze_code_with_ai(client, code_text, lang="python"):
    prompt = f"""
You are a senior software engineer.

Analyze the following {lang} code and suggest optimization steps.

CRITICAL: For Python, NEVER suggest replacing built-in functions (max, min, sum, sorted, len, any, all, zip, enumerate) with manual loops — built-ins are C-optimized and faster.
NEVER suggest replacing slice operations (e.g., [::-1]) or direct boolean returns (e.g., return x == y) with verbose alternatives.
Only suggest optimizations that genuinely improve performance or fix real issues.

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

CRITICAL PRESERVATION RULES (PYTHON):
- NEVER replace max(), min(), sum(), sorted(), len(), any(), all() with manual loops
- NEVER replace slice operations (text[::-1]) with manual loops
- NEVER replace "return expression" with "if expression: return True; return False"
- NEVER replace f-strings with string concatenation
- NEVER replace .clear() with = []
- If the original code already uses best practices, return it UNCHANGED and say "No significant optimizations needed"

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
# DE-OPTIMIZATION GUARD
# ===============================

# Python built-in functions that should NEVER be replaced with manual loops
PYTHON_BUILTINS_TO_PRESERVE = [
    "max(", "min(", "sum(", "sorted(", "len(",
    "any(", "all(", "zip(", "map(", "filter(", "enumerate("
]

# Python idioms that should NEVER be replaced with verbose alternatives
PYTHON_IDIOMS_TO_PRESERVE = [
    "[::-1]",       # string/list reversal via slice
    ".clear()",     # in-place clearing
]

def detect_deoptimization(original_code, optimized_code, lang="python"):
    """
    Detects if the AI has replaced efficient constructs with slower alternatives.
    Returns True if a de-optimization is detected (meaning we should REVERT).
    """
    if lang != "python":
        return False

    original_lower = original_code.lower()
    optimized_lower = optimized_code.lower()

    # Check 1: Built-in functions removed
    for builtin in PYTHON_BUILTINS_TO_PRESERVE:
        if builtin in original_lower and builtin not in optimized_lower:
            print(f"⚠️ DE-OPTIMIZATION DETECTED: '{builtin}' was removed from optimized code")
            return True

    # Check 2: Pythonic idioms removed
    for idiom in PYTHON_IDIOMS_TO_PRESERVE:
        if idiom in original_lower and idiom not in optimized_lower:
            print(f"⚠️ DE-OPTIMIZATION DETECTED: '{idiom}' was removed from optimized code")
            return True

    # Check 3: Direct boolean returns replaced with if/else True/False
    import re
    # Count "return True" / "return False" patterns
    orig_direct_returns = len(re.findall(r'return\s+\w+.*==', original_lower))
    opt_return_true = len(re.findall(r'return\s+true', optimized_lower))
    opt_return_false = len(re.findall(r'return\s+false', optimized_lower))

    if orig_direct_returns > 0 and (opt_return_true + opt_return_false) > orig_direct_returns:
        print("⚠️ DE-OPTIMIZATION DETECTED: Direct boolean returns replaced with if/else blocks")
        return True

    # Check 4: f-strings replaced with concatenation
    orig_fstrings = original_lower.count('f"') + original_lower.count("f'")
    opt_fstrings = optimized_lower.count('f"') + optimized_lower.count("f'")
    if orig_fstrings > 0 and opt_fstrings < orig_fstrings:
        print("⚠️ DE-OPTIMIZATION DETECTED: f-strings replaced with concatenation")
        return True

    return False


# ===============================
# MAIN OPTIMIZATION PIPELINE
# ===============================
import json

def run_code_optimization(client, parsed_structure, code_text, imports, lang="python"):

    # STEP 1: ANALYZE
    analysis_raw = analyze_code_with_ai(client, code_text, lang)

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

    # STEP 2.5 🛡️ DE-OPTIMIZATION GUARD
    # Revert if AI replaced efficient constructs with slower alternatives
    if detect_deoptimization(code_text, result.get("optimized_code", ""), lang):
        print("🛡️ DE-OPTIMIZATION REVERTED: Keeping original code")
        return {
            "optimized_code": code_text,
            "improvements": ["No optimizations needed — original code already uses efficient built-in functions and Pythonic idioms"],
            "explanations": ["The original code correctly uses Python built-ins (max, sum, etc.), slice operations, and direct boolean returns which are already optimal"]
        }

    # STEP 3 🔥 AUTO CHANGE DETECTION

    # Detect differences
    changes = detect_code_changes(code_text, result["optimized_code"])

    # Generate improvements from actual changes
    auto_improvements, auto_explanations = generate_improvements_from_changes(changes, lang)

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

def generate_improvements_from_changes(changes, lang="python"):
    improvements = []
    explanations = []

    for change_type, line in changes:
        line_lower = line.lower()

        if lang == "python":
            if "max(" in line_lower:
                improvements.append("Replaced manual loop with built-in max()")
                explanations.append("max() is optimized and improves readability")
            elif "sum(" in line_lower:
                improvements.append("Replaced manual summation with built-in sum()")
                explanations.append("sum() reduces complexity and is faster")
            elif "**" in line_lower:
                improvements.append("Used exponent operator **")
                explanations.append("Cleaner and more Pythonic than multiplication")
        
        elif lang == "javascript":
            if "=>" in line_lower:
                improvements.append("Used arrow function")
                explanations.append("Arrow functions are more concise and handle 'this' lexically")
            elif ".map(" in line_lower or ".filter(" in line_lower:
                improvements.append("Used functional array methods")
                explanations.append("Methods like map and filter improve readability and maintainability")
        
        elif lang == "java":
            if "stream()" in line_lower:
                improvements.append("Used Java Streams API")
                explanations.append("Streams allow for more expressive and potentially parallelizable data processing")
        
        elif lang == "c":
            if "memcpy" in line_lower:
                improvements.append("Used memcpy for block memory operations")
                explanations.append("memcpy is highly optimized for memory copying")

    return improvements, explanations