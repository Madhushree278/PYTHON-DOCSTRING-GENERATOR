const vscode = require('vscode');

/*
---------------------------------------
Docstring Generator Function
---------------------------------------
*/
function generateDocstrings(code) {

    const lines = code.split("\n");
    let updatedLines = [];

    for (let i = 0; i < lines.length; i++) {

        let line = lines[i];
        updatedLines.push(line);

        // Detect Python function
        let match = line.match(/def\s+(\w+)\((.*?)\):/);

        if (match) {

            let functionName = match[1];
            let params = match[2].split(",").map(p => p.trim()).filter(p => p);

            let docstring = [];
            docstring.push('    """');
            docstring.push(`    Function: ${functionName}`);
            docstring.push('');
            docstring.push('    Parameters:');

            if (params.length > 0) {
                params.forEach(param => {
                    docstring.push(`        ${param}: Description`);
                });
            } else {
                docstring.push('        None');
            }

            docstring.push('');
            docstring.push('    Returns:');
            docstring.push('        Description');
            docstring.push('    """');

            updatedLines.push(...docstring);
        }
    }

    return updatedLines.join("\n");
}

/*
---------------------------------------
VS Code Extension Activation
---------------------------------------
*/
function activate(context) {

    let disposable = vscode.commands.registerCommand(
        'docstring.generate',
        function () {

            const editor = vscode.window.activeTextEditor;

            if (!editor) {
                vscode.window.showErrorMessage("No file open");
                return;
            }

            const code = editor.document.getText();

            const updatedCode = generateDocstrings(code);

            const fullRange = new vscode.Range(
                editor.document.positionAt(0),
                editor.document.positionAt(code.length)
            );

            editor.edit(editBuilder => {
                editBuilder.replace(fullRange, updatedCode);
            });

            vscode.window.showInformationMessage("Docstrings Generated Successfully!");
        }
    );

    context.subscriptions.push(disposable);
}

/*
---------------------------------------
Deactivate Extension
---------------------------------------
*/
function deactivate() {}

module.exports = {
    activate,
    deactivate
};