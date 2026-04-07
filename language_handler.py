import re

# ===============================
# LANGUAGE CONFIGURATION
# ===============================

SUPPORTED_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".java": "java",
    ".c": "c"
}

# Comment styles for each language
COMMENT_STYLES = {
    "python": {
        "start": '"""',
        "end": '"""',
        "line_prefix": "",
        "fallback": "#",
    },
    "javascript": {
        "start": "/**",
        "end": " */",
        "line_prefix": " * ",
        "fallback": "//",
    },
    "java": {
        "start": "/**",
        "end": " */",
        "line_prefix": " * ",
        "fallback": "//",
    },
    "c": {
        "start": "/**",
        "end": " */",
        "line_prefix": " * ",
        "fallback": "//",
    }
}

# ===============================
# REGEX PATTERNS FOR FUNCTIONS
# ===============================

PATTERNS = {
    "javascript": [
        # Standard function: function name(...)
        r"(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)",
        # Arrow function: const name = (...) =>
        r"(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
        # Method in class/object: name(...) {
        r"^\s*([a-zA-Z0-9_$]+)\s*\(([^)]*)\)\s*\{"
    ],
    "java": [
        # Java method: [modifiers] ReturnType name(params) [throws ...] {
        r"^\s*(?:(?:public|private|protected|static|final|native|synchronized|abstract|transient)\s+)*[\w\<\>\[\]\.]+\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)[^{]*\{"
    ],
    "c": [
        # C function: [type] name(params) {
        r"^[ \t]*(?:[a-zA-Z_][a-zA-Z0-9_]*\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*\{?"
    ]
}

def get_comment_style(lang):
    return COMMENT_STYLES.get(lang, COMMENT_STYLES["python"])

def extract_function_body(code, search_start, lang="python"):
    """
    Finds the function implementation block.
    - If code[search_start:] contains '{', uses brace matching.
    - If lang is javascript and '=>' is found without a '{', captures the rest of the line.
    """
    
    # 1. Check for Braces { ... }
    first_brace = code.find("{", search_start)
    
    # In C/Java, the brace might be on a new line, but not too far
    # (e.g. 50 characters away max is a safe bet for a signature)
    limit = search_start + 100
    
    if first_brace != -1 and first_brace < limit:
        brace_count = 0
        end_index = -1

        for i in range(first_brace, len(code)):
            if code[i] == "{":
                brace_count += 1
            elif code[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_index = i + 1
                    break

        if end_index != -1:
            return code[first_brace:end_index]

    # 2. Check for Single-Line Arrow Functions (JS only)
    if lang == "javascript":
        arrow_pos = code.find("=>", search_start - 10)
        if arrow_pos != -1:
            # Capturing everything until the next semicolon or line end
            eol = code.find("\n", arrow_pos)
            next_semi = code.find(";", arrow_pos)
            
            end_pos = min(eol if eol != -1 else len(code), next_semi if next_semi != -1 else len(code))
            return code[arrow_pos:end_pos].strip()

    return ""

def parse_code_generically(code_text, lang):
    """
    Parses code for C, Java, and JS using Regex.
    Returns a list of dicts similar to what the AST parser returns for Python.
    """
    if lang == "python":
        import ast
        try:
            tree = ast.parse(code_text)
            parsed_data = []

            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    try:
                        function_code = ast.get_source_segment(code_text, node)
                    except:
                        function_code = ""

                    called_functions = [
                        n.func.id for n in ast.walk(node)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    ]
                    function_info = {
                        "name": node.name,
                        "parameters": [arg.arg for arg in node.args.args],
                        "returns_value": any(isinstance(n, ast.Return) for n in ast.walk(node)),
                        "called_functions": called_functions,
                        "function_code": function_code,
                        "type": "function",
                        "line": node.lineno
                    }
                    parsed_data.append(function_info)

                elif isinstance(node, ast.ClassDef):
                    for body_item in node.body:
                        if isinstance(body_item, ast.FunctionDef):
                            try:
                                method_code = ast.get_source_segment(code_text, body_item)
                            except:
                                method_code = ""

                            called_functions = [
                                n.func.id for n in ast.walk(body_item)
                                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            ]
                            method_info = {
                                "class_name": node.name,
                                "name": body_item.name,
                                "parameters": [arg.arg for arg in body_item.args.args],
                                "returns_value": any(isinstance(n, ast.Return) for n in ast.walk(body_item)),
                                "called_functions": called_functions,
                                "function_code": method_code,
                                "type": "class_method",
                                "line": body_item.lineno
                            }
                            parsed_data.append(method_info)
            return parsed_data
        except:
            return []

    pattern_list = PATTERNS.get(lang)
    if not pattern_list:
        return []

    # Ensure pattern_list is a list
    if isinstance(pattern_list, str):
        pattern_list = [pattern_list]

    parsed_data = []
    seen_lines = set()

    for pattern in pattern_list:
        matches = re.finditer(pattern, code_text, re.MULTILINE)

        for match in matches:
            name = None
            params = []
            return_type = "inferred"
            signature_line = match.group(0).strip()

            if lang == "javascript":
                name = match.group(1)
                params_raw = match.group(2)
                params = [p.strip() for p in params_raw.split(",") if p.strip()]
                return_type = "inferred from implementation"
            elif lang == "java":
                name = match.group(1)
                params_raw = match.group(2)
                params = [p.split()[-1].strip() for p in params_raw.split(",") if p.strip()]
                # Extract the return type: it's the word right before the method name
                # e.g. "public int multiply(" -> return type is "int"
                sig_before_name = signature_line[:signature_line.find(name)].strip()
                parts = sig_before_name.split()
                if parts:
                    return_type = parts[-1]  # last word before method name is the return type
            elif lang == "c":
                name = match.group(1)
                params_raw = match.group(2)
                params = [p.split()[-1].strip("* ") for p in params_raw.split(",") if p.strip() and p.strip() != "void"]
                # Extract the return type: words before the function name
                sig_before_name = signature_line[:signature_line.find(name)].strip()
                parts = sig_before_name.split()
                if parts:
                    return_type = parts[-1]  # e.g. "int" from "int add("
            
            if name is None:
                continue

            # Find line number and function body
            start_index = match.start()
            line_no = code_text[:start_index].count("\n") + 1

            if line_no not in seen_lines:
                seen_lines.add(line_no)
                
                # Extract body for context-aware AI
                function_code = extract_function_body(code_text, match.end(), lang)
                
                parsed_data.append({
                    "name": name,
                    "parameters": params,
                    "function_code": function_code,
                    "signature": signature_line,
                    "return_type": return_type,
                    "type": "function",
                    "line": line_no
                })

    return parsed_data

def get_language(filename):
    for ext, lang in SUPPORTED_LANGUAGES.items():
        if filename.endswith(ext):
            return lang
    return "unknown"