from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import aiofiles
import json
import logging
from fastapi.responses import HTMLResponse
import difflib
import aiofiles
import time

from task_engine import run_python_code
from gemini import parse_question_with_llm

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    with open("frontend.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Helper funtion to show last 25 words of string s
def last_n_words(s, n=100):
    s = str(s)
    words = s.split()
    return ' '.join(words[-n:])

def is_csv_empty(csv_path):
    return not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0



@app.post("/api")
async def analyze(request: Request):
    # Create a unique folder for this request
    request_id = str(uuid.uuid4())
    request_folder = os.path.join(UPLOAD_DIR, request_id)
    os.makedirs(request_folder, exist_ok=True)

    # Setting up file for llm response
    llm_response_file_path = os.path.join(request_folder, "llm_response.txt")
    
    # Setup logging for this request
    log_path = os.path.join(request_folder, "app.log")
    logger = logging.getLogger(request_id)
    logger.setLevel(logging.INFO)
    # Remove previous handlers if any (avoid duplicate logs)
    if logger.hasHandlers():
        logger.handlers.clear()
    file_handler = logging.FileHandler(log_path)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # Also log to console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("Step-1: Folder created: %s", request_folder)

    form = await request.form()
    question_text = None
    saved_files = {}

    # Save all uploaded files to the request folder
    for field_name, value in form.items():
        if hasattr(value, "filename") and value.filename:  # It's a file
            file_path = os.path.join(request_folder, value.filename)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(await value.read())
            saved_files[field_name] = file_path

            # If it's questions.txt, read its content
            if field_name == "question.txt":
                async with aiofiles.open(file_path, "r") as f:
                    question_text = await f.read()
        else:
            saved_files[field_name] = value

    # Fallback: If no questions.txt, use the first file as question
    

    if question_text is None and saved_files:
        target_name = "question.txt"
        file_names = list(saved_files.keys())

        # Find the closest matching filename
        closest_matches = difflib.get_close_matches(target_name, file_names, n=1, cutoff=0.6)
        if closest_matches:
            selected_file_key = closest_matches[0]
        else:
            selected_file_key = next(iter(saved_files.keys()))  # fallback to first file

        selected_file_path = saved_files[selected_file_key]

        async with aiofiles.open(selected_file_path, "r") as f:
            question_text = await f.read()

    user_prompt = f"""<user_prompt>
    I know nothing about data analytics, to solving this question, what we will do is this:
    Step-1: I will give you a question statement which has data sources and questions. You will break that into tasks. First task is getting required info.You will give me code that extracts the basic info about the data scource.like
        - If it is a url: give code for scraping the basic info like tables names and other important info.The scraped data should be not long it take max 100 tokens.
        - If it is a csv: give code to get its first 3 rows.
    step-2: you download the required data and save it in this ({request_folder}) folder location.
    step-3: I will give you the info that i obtain. and then you give me the code for solving those questions and saving answer in a {request_folder}/result.txt file.
    step-4: I will pass you the content of {request_folder}/result.txt, and you tell me if it is wrong or not. If found wrong we will start again.

    lastly, if any error occurs at a given step. I will give you the error message and you correct that if it still not works then you give me fresh new code.
    
    you answer me strictly in JSON format. Like this
    {{
       "code": "<python_code_here_to_run_in_REPL>",
       "libraries": ["list", "of", "external_libraries"],
       "run_this": 0 or 1: give me 1 if you want me to execute the code and tell you the output. Give me 0, when all the steps are done and I had provided you the result and you had verified it to be correct.If not correct give me a final code that makes that correct.
   }}

   and save the code results in {request_folder}/metadata.txt. So i will read that and send you the info that you had collected.

- External libraries must be listed; built-ins should not be listed.
- Use the provided Gemini API key when additional reasoning or code generation is needed mid-process.

for image processing use python and don't use gemini vision model it is not working.If you other error then first solve that, then move next
all files that you need are in {request_folder}. so please add this before accesing any file like {request_folder}/filename.
also only append required data in {request_folder}/metadata.txt. as i pass that to you it will consume tokens.
use the pip install names for libraries as they are going to installed using pip.(don;t include libraries that are buildin)
</userprompt>"""


    question_text = str("<question>") +  question_text+ "</question>"  + str(user_prompt)
    logger.info("Step-2: File sent %s", saved_files)

    """
    Orchestrates the LLM-driven analytical workflow.
    """
    session_id = request_id
    retry_message = None
    start_time = time.time()

    # Ensure folder exists
    os.makedirs("uploads", exist_ok=True)

    runner = 1


    # Step 1: Get code from LLM
    response = await parse_question_with_llm(
        question_text=question_text,
        uploaded_files=saved_files,
        folder=request_folder,
        session_id=session_id,
        retry_message=retry_message
    )

    # Loops to ensure we get a valid json reponse
    max_attempts = 3
    attempt = 0
    response = None
    error_occured = 0
    
    while attempt < max_attempts:
        logger.info("Step-3: Getting scrap code and metadata from llm. Tries count = %d", attempt)
        try:
            if error_occured == 0:
                response = await parse_question_with_llm(
                            question_text=question_text,
                            uploaded_files=saved_files,
                            folder=request_folder,
                            session_id=session_id,
                            retry_message=retry_message
                        )
            else:
                response = await parse_question_with_llm(retry_message=retry_message, folder=request_folder, session_id=request_id)
            # Check if response is a valid dict (parsed JSON)
            if isinstance(response, dict):
                break
        except Exception as e:
            error_occured = 1
            retry_message = last_n_words(str(e), 100) + str("Provide a valid JSON response")
            logger.error("Step-3: Error in parsing the result. %s", retry_message)
        attempt += 1


    if not isinstance(response, dict):
        logger.error("Error: Could not get valid response from LLM after retries.")
        return JSONResponse({"message": "Error_first_llm_call: Could not get valid response from LLM after retries."})

    code_to_run = response.get("code", "")
    required_libraries = response.get("libraries", [])
    runner = response.get("run_this", 1)

    while runner == 1:
        # Check timeout
        if time.time() - start_time > 500:
            print("⏳ Timeout: 150 seconds exceeded.")
            break

               

        # Step 2: Run the generated code
        execution_result =await run_python_code(
            code=code_to_run,
            libraries=required_libraries,
            folder=request_folder
        )

        # Step 3: Check if execution failed
        if execution_result["code"] == 0:
            print("❌ Code execution failed. Retrying...")
            retry_message =str("<error_snippet>") + last_n_words(execution_result["output"]) + str("</error_snippet>") +str("Solve this error or give me new freash code")
        else:
            # Read metadata
            metadata_file = os.path.join(request_folder, "metadata.txt")
            if not os.path.exists(metadata_file):
                print("❌ metadata.txt not found.")
                continue
            
            with open(metadata_file, "r") as f:
                metadata = f.read()


            retry_message =str("<metadata>") + metadata + str("</metadata>")

        print(retry_message)
        

        # Loops to ensure we get a valid json reponse
        max_attempts = 3
        attempt = 0
        response = None
        error_occured = 0

        while attempt < max_attempts:
            logger.info("Step-3: Getting scrap code and metadata from llm. Tries count = %d", attempt)
            try:
                if error_occured == 0:
                    response = await parse_question_with_llm(
                    retry_message=retry_message,
                    folder=request_folder,
                    session_id=session_id
                    )
                else:
                    response = await parse_question_with_llm(retry_message=retry_message, folder=request_folder, session_id=request_id)
                # Check if response is a valid dict (parsed JSON)
                if isinstance(response, dict):
                    break
            except Exception as e:
                error_occured = 1
                retry_message = last_n_words(str(e), 100) + str("Provide a valid JSON response")
                logger.error("Step-3: Error in parsing the result. %s", retry_message)
            attempt += 1


        if not isinstance(response, dict):
            logger.error("Error: Could not get valid response from LLM after retries.")
            return JSONResponse({"message": "Error_Inside_loop_call: Could not get valid response from LLM after retries."})

        code_to_run = response.get("code", "")
        required_libraries = response.get("libraries", [])
        runner = response.get("run_this", 1)

        # Checking if result.txt exists
        result_file = os.path.join(request_folder, "result.txt")
        if not os.path.exists(result_file):
            print("❌ result.txt not found.")
            continue

        # Code for reading result.txt
        with open(result_file, "r") as f:
            result = f.read()

        print("✅ Checking results")
        # Step 4: Verify the answer with the LLM
        verification =await parse_question_with_llm(
            question_text=f"Is this answer correct? Just see the result and see if they are looking correct. If you think they might not be the answer, please provide the new correct code. And if yes, then set 'run_this' to 0. <result> {result} </result> and don;t take too much time for this. And if in the question you found any Answer format, write the answers in {request_folder}/result.json, if some values are missing match the json structure and input random value in it.Also keep the 'run_this' set to 0 for this task.Only set 'run_this' to 1, if you this we had to calculate all this things again and you had provided the code for that.",
            uploaded_files=saved_files,
            folder=request_folder,
            session_id=session_id,
            retry_message=None
        )

        # Loops to ensure we get a valid json reponse
        max_attempts = 3
        attempt = 0
        response = None
        error_occured = 0

        while attempt < max_attempts:
            logger.info("Step-3: Getting scrap code and metadata from llm. Tries count = %d", attempt)
            try:
                if error_occured == 0:
                    verification =await parse_question_with_llm(
                    retry_message=f"Is this answer correct? Just see the result and see if they are looking correct. If you think they might not be the answer, please provide the new correct code. And if yes, then set 'run_this' to 0. <result> {result} </result> and don;t take too much time for this. And if in the question you found any Answer format, write the answers in {request_folder}/result.json, if some values are missing match the json structure and input random value in it.Also keep the 'run_this' set to 0 for this task.Only set 'run_this' to 1, if you this we had to calculate all this things again and you had provided the code for that.",
                    uploaded_files=saved_files,
                    folder=request_folder,
                    session_id=session_id,
                    )
                else:
                    verification = await parse_question_with_llm(retry_message=retry_message, folder=request_folder, session_id=request_id)
                # Check if response is a valid dict (parsed JSON)
                if isinstance(response, dict):
                    break
            except Exception as e:
                error_occured = 1
                retry_message =str("Your previous code has errors: <error>") +   last_n_words(str(e) + str("</error>"), 100) + str("Provide a valid JSON response")
                logger.error("Step-3: Error in parsing the result. %s", retry_message)
            attempt += 1


        if not isinstance(response, dict):
            logger.error("Error: Could not get valid response from LLM after retries.")
            return JSONResponse({"message": "Error_verification_call: Could not get valid response from LLM after retries."})
        

        code_to_run = verification.get("code", "")
        required_libraries = verification.get("libraries", [])
        runner = verification.get("run_this", 0)  # Assume True if not provided


    try:
        #Running final code
        execution_result =await run_python_code(
            code=code_to_run,
            libraries=required_libraries,
            folder=request_folder
        )
        if execution_result["code"] == 0:
            logger.error("Step-6: Final code execution failed: %s", last_n_words(execution_result["output"]))
            print("❌ Final code execution failed. Please check the logs.")
    except Exception as e:
        logger.error("Step-6: Error occurred while running final code: %s", last_n_words(e))
        print("❌ Error occurred while running final code. Please check the logs.")

    # Final step: send the response back by reading the result.txt in JSON format



    result_path = os.path.join(request_folder, "result.json")

    if not os.path.exists(result_path):
        # Checking if result.txt exists
        result_file = os.path.join(request_folder, "result.txt")
        if not os.path.exists(result_file):
            print("❌ result.txt not found.")

        # Code for reading result.txt
        with open(result_file, "r") as f:
            result = f.read()
        # Change result.txt content to result.json if possible
        try:
            result_path = os.path.join(request_folder, "result.json")
            with open(result_path, "w") as f:
                f.write(result)
        except Exception as e:
            logger.error("Step-7: Error occurred while writing result.json: %s", last_n_words(e))

    else:
        with open(result_path, "r") as f:
            try:
                data = json.load(f)
                logger.info("Step-7: send result back")
                return JSONResponse(content=data)
            except Exception as e:
                logger.error("Step-7: Error occur while sending result: %s", last_n_words(e))
                # Return raw content if JSON parsing fails
                f.seek(0)
                raw_content = f.read()
                return JSONResponse({"message": f"Error occured while processing result.json: {e}", "raw_result": raw_content})
