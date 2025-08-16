import os
import sys
from io import StringIO
import traceback
from openai import OpenAI

# Initialize DeepSeek API client
client = OpenAI(
    #api_key=os.getenv("AIPIPE_API_KEY"),
    api_key="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",
    base_url="https://openrouter.ai/api/v1",
)
model = "openai/gpt-4.1-nano"

def extract_code_from_response(response):
    """
    Extract Python code from markdown code blocks in the assistant's response.
    """
    code_blocks = []
    in_code_block = False
    current_block = []
    
    for line in response.split('\n'):
        if line.startswith('```python'):
            in_code_block = True
            current_block = []
        elif line.startswith('```') and in_code_block:
            in_code_block = False
            code_blocks.append('\n'.join(current_block))
        elif in_code_block:
            current_block.append(line)
    
    return '\n\n'.join(code_blocks) if code_blocks else None

def execute_code(code, env=None):
    """
    Execute Python code in a safe environment and capture output/errors.
    Returns a tuple (success: bool, output: str, updated_env: dict)
    """
    if env is None:
        env = {
            '__builtins__': {
                'print': print,
                'range': range,
                'list': list,
                'dict': dict,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'enumerate': enumerate,
                'zip': zip
            },
            'math': __import__('math'),
            'datetime': __import__('datetime')
        }
    
    # Capture standard output and errors
    stdout = StringIO()
    stderr = StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    try:
        sys.stdout = stdout
        sys.stderr = stderr
        
        # Execute the code
        exec(code, env)
        success = True
    except Exception as e:
        # Capture exception information
        stderr.write(traceback.format_exc())
        success = False
    finally:
        # Restore standard streams
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    
    return success, stdout.getvalue() + stderr.getvalue(), env

def chat_with_deepseek():
    """
    Interactive chat with DeepSeek that can write and execute Python code.
    Maintains conversation history and automatically improves code based on errors.
    """
    chat_history = []
    execution_env = None
    consecutive_errors = 0
    
    print("DeepSeek Python REPL Assistant")
    print("Type 'exit' to quit or 'reset' to clear environment\n")
    
    while True:
        # Get user input
        try:
            #user_input = input(">>> ").strip()
            user_input = """Scrape the list of highest grossing films from Wikipedia. It is at the URL:
https://en.wikipedia.org/wiki/List_of_highest-grossing_films

Answer the following questions and respond with a JSON array of strings containing the answer.

1. How many $2 bn movies were released before 2000?
2. Which is the earliest film that grossed over $1.5 bn?
3. What's the correlation between the Rank and Peak?
4. Draw a scatterplot of Rank and Peak along with a dotted red regression line through it.
   Return as a base-64 encoded data URI, `"data:image/png;base64,iVBORw0KG..."` under 100,000 bytes.
"""
        except EOFError:
            print("\nExiting...")
            break
        
        if user_input.lower() in ['exit', 'quit']:
            break
        elif user_input.lower() == 'reset':
            execution_env = None
            consecutive_errors = 0
            print("Environment reset")
            continue
        
        # Add user message to history
        chat_history.append({"role": "user", "content": user_input})
        
        # Get response from DeepSeek
        response = client.chat.completions.create(
            model=model,
            messages=chat_history,
            temperature=0.7,
            stream=False,
        )
        
        assistant_message = response.choices[0].message.content
        chat_history.append({"role": "assistant", "content": assistant_message})
        
        # Extract and execute code if available
        code = extract_code_from_response(assistant_message)
        if code:
            print("\nGenerated code:")
            print(code)
            
            success, output, execution_env = execute_code(code, execution_env)
            
            print("\nExecution result:")
            print(output if output else "No output")
            
            # Handle errors
            if not success:
                consecutive_errors += 1
                if consecutive_errors < 3:
                    error_msg = f"Previous code failed with error:\n{output}\nPlease fix the code."
                    chat_history.append({"role": "user", "content": error_msg})
                    print("\nSending error to assistant for correction...")
                else:
                    print("\nToo many consecutive errors. Please modify your request.")
                    consecutive_errors = 0
            else:
                consecutive_errors = 0
        else:
            print("\nAssistant response:")
            print(assistant_message)

if __name__ == "__main__":
    chat_with_deepseek()