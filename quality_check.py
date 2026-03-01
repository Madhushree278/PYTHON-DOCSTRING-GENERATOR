import json

def validate_ai_output(parsed_structure, ai_output):
    try:
        ai_data = json.loads(ai_output)
    except json.JSONDecodeError:
        return False, "Invalid JSON returned by AI."

    parsed_names = {item["name"] for item in parsed_structure}
    ai_names = {item["name"] for item in ai_data}

    missing = parsed_names - ai_names

    if missing:
        return False, f"AI did not document: {list(missing)}"

    return True, "AI output passed validation."
