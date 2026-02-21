from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn
import ast

app = FastAPI(title="Automated Python Docstring Generator")


@app.get("/")
def home():
    return {"message": "API is running. Go to /docs"}


def parse_code_with_ast(code_text: str):
    """
    STEP 4: Parse Code using AST
    - Identify top-level functions
    - Identify class methods
    - Avoid duplication
    """

    tree = ast.parse(code_text)
    parsed_data = []

    # Only inspect top-level nodes
    for node in tree.body:

        # Top-level standalone functions
        if isinstance(node, ast.FunctionDef):
            function_info = {
                "function_name": node.name,
                "parameters": [arg.arg for arg in node.args.args],
                "returns_value": any(
                    isinstance(n, ast.Return) for n in ast.walk(node)
                ),
                "type": "function"
            }
            parsed_data.append(function_info)

        # Class definitions
        elif isinstance(node, ast.ClassDef):
            for body_item in node.body:
                if isinstance(body_item, ast.FunctionDef):
                    method_info = {
                        "class_name": node.name,
                        "method_name": body_item.name,
                        "parameters": [arg.arg for arg in body_item.args.args],
                        "returns_value": any(
                            isinstance(n, ast.Return) for n in ast.walk(body_item)
                        ),
                        "type": "class_method"
                    }
                    parsed_data.append(method_info)

    return parsed_data
@app.post("/process-code/")
async def upload_and_process_python_file(file: UploadFile = File(...)):

    if not file.filename.endswith('.py'):
        raise HTTPException(
            status_code=400,
            detail="Validation Failed: Only .py files are accepted."
        )

    try:
        content = await file.read()
        code_text = content.decode("utf-8")

        if not code_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Format Check: The file is empty."
            )

        # STEP 4: AST Parsing
        parsed_result = parse_code_with_ast(code_text)

        return {
            "status": "Success",
            "filename": file.filename,
            "parsed_structure": parsed_result,
            "next_step": "Ready for AI Understanding (Step 5)"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
