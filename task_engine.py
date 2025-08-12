import subprocess
import sys
import traceback
from typing import List
import datetime
import os
import io
import black  # For pretty-printing code

async def run_python_code(code: str, libraries: List[str], folder: str = "uploads") -> dict:
    def execute_code():
        # Capture stdout and stderr
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = io.StringIO(), io.StringIO()

        exec_globals = {}
        try:
            exec(code, exec_globals)
            output = sys.stdout.getvalue()
            errors = sys.stderr.getvalue()
            return output, errors
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

    # Step 1: Install all required libraries first
    for lib in libraries:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
        except Exception as install_error:
            return {"code": 0, "output": f"❌ Failed to install library '{lib}':\n{install_error}"}

    # Step 2: Execute the code after installation
    try:
        output, errors = execute_code()

        # Ensure folder exists
        os.makedirs(folder, exist_ok=True)

        # Pretty-print the code using black
        try:
            pretty_code = black.format_str(code, mode=black.Mode())
        except Exception:
            pretty_code = code  # Fallback if black fails

        # Create execution_result.txt
        result_file_path = os.path.join(folder, "execution_result.txt")
        with open(result_file_path, "a") as f:
            f.write("\n" + "=" * 50 + "\n")
            f.write(f"Execution Time: {datetime.datetime.now()}\n\n")
            f.write("Executed Code:\n")
            f.write(pretty_code + "\n")
            f.write("Output:\n")
            f.write(output if output else "[No output]\n")
            if errors:
                f.write("\nErrors:\n" + errors)

        return {"code": 1, "output": output if output else "✅ Code executed successfully (no output)."}

    except Exception:
        return {"code": 0, "output": f"❌ Error during code execution:\n{traceback.format_exc()}"}
