import base64
import json
import mimetypes
import os
import subprocess
import tempfile
import time
from pathlib import Path

import openai
from playwright.sync_api import sync_playwright

import config
import assemblyai as aai

from config import OPENAI_SUPPORTED_FILE_MIME_TYPES


def scrape_with_playwright(url: str, script: str | None = None,
                           screenshot_required: bool = False,
                           headless: bool = True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(url)
        if script:
            script_result: str = page.evaluate(script)
        if screenshot_required:
            screenshot_bytes = page.screenshot()

        content = page.content()
    return content, script_result if script else None, screenshot_bytes if screenshot_required else None


def submit_answer(quiz_url: str, answer_endpoint: str, answer: str):
    import requests
    response = requests.post(answer_endpoint,
                             json={"answer": answer, "email": config.STUDENT_EMAIL_ID, "secret": config.SECRET_KEY,
                                   "url": quiz_url})
    return response.status_code, response.text


aai.settings.api_key = config.ASSEMBLYAI_API_KEY
transcription_config = aai.TranscriptionConfig(speech_models=["universal"])
transcriber = aai.Transcriber(config=transcription_config)


def transcribe_audio(file: str):
    try:
        print(f"[DEBUG] Audio transcription from file started... {file}")
        transcript = transcriber.transcribe(file)

        print("[DEBUG] Audio transcription completed.")
        if transcript.status == "error":
            print(f"[DEBUG] Transcription error: {transcript.error}")
            return {"error": f"Transcription error: {transcript.error}"}
        print(f"[DEBUG] Transcription completed successfully: {transcript.text}")
        return {"transcription_text": transcript.text}
    except Exception as e:
        print(f"[DEBUG] Error decoding Base64", e)
        return {"error": f"Error decoding Base64: {e}"}


MAX_SAFE_SIZE = 10 * 1024 * 1024  # 25 MB

def download_file(file_name: str, url: str):
    import requests
    import mimetypes
    import os

    download_dir = next(iter(ALLOWED_DIRS))  # pick downloads dir
    target_path = _safe_resolve_path(os.path.join(download_dir, file_name))

    if not _is_in_allowed_dirs(target_path):
        return {"error": "Invalid file_name: path escapes allowed directories."}

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except Exception as e:
        return {"error": f"Download failed: {e}"}

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(response.content)

    size = os.path.getsize(target_path)
    mime, _ = mimetypes.guess_type(target_path)
    ext = os.path.splitext(target_path)[1]

    return {
        "file_path": target_path,
        "file_name": file_name,
        "mime_type": mime or "application/octet-stream",
        "file_extension": ext,
        "file_size": size,
    }


# List of directories the LLM is allowed to access
ALLOWED_DIRS = {
    str(config.project_path / "data" / "downloads"),
}


def _safe_resolve_path(path: str) -> str:
    """
    Resolve a path safely:
      - collapse .. and .
      - resolve symlinks
      - return a clean absolute path
    """
    return os.path.abspath(os.path.realpath(path))

def _is_in_allowed_dirs(path: str, allowed_dirs: set[str] | None = None) -> bool:
    """True only if path is inside one of ALLOWED_DIRS."""
    safe = _safe_resolve_path(path)

    if allowed_dirs is None:
        allowed_dirs = ALLOWED_DIRS

    for allowed in allowed_dirs:
        if safe.startswith(allowed + os.sep):
            return True
    return False

def get_local_file(file_path: str, allow_large: bool):
    safe = _safe_resolve_path(file_path)

    # Core safety: path containment
    if not _is_in_allowed_dirs(safe):
        return {
            "error": "Access denied. File is outside allowed directories.",
            "file_path": file_path,
            "allowed_dirs": list(ALLOWED_DIRS),
        }

    # Normal checks
    if not os.path.exists(safe):
        return {"error": f"File not found: {file_path}"}

    size = os.path.getsize(safe)
    mime, _ = mimetypes.guess_type(safe)

    if mime not in OPENAI_SUPPORTED_FILE_MIME_TYPES:
        return {
            "error": f"Unsupported file type: {mime}. Supported types: {OPENAI_SUPPORTED_FILE_MIME_TYPES}",
            "file_path": safe,
            "file_size": size,
            "mime_type": mime or "application/octet-stream",
        }

    if size > MAX_SAFE_SIZE and not allow_large:
        return {
            "error": "File too large. Set allow_large=true to override.",
            "file_path": safe,
            "file_size": size,
            "max_safe_size": MAX_SAFE_SIZE,
            "mime_type": mime or "application/octet-stream",
        }

    return {
        "file_path": safe,
        "file_size": size,
        "mime_type": mime or "application/octet-stream",
    }

SAFE_WRAPPER = r'''
import builtins, os, sys, importlib

# ------------------------------------------------------------
# Safe open: no absolute paths, no writing
# ------------------------------------------------------------
_real_open = open
def safe_open(path, mode="r", *args, **kwargs):
    if os.path.isabs(path):
        raise PermissionError("Absolute paths not allowed.")
    if any(m in mode for m in ("w", "a", "+")):
        raise PermissionError("Write operations not allowed.")
    return _real_open(path, mode, *args, **kwargs)

# ------------------------------------------------------------
# Block dangerous modules (HF safe only)
# ------------------------------------------------------------
_blocked = {"os", "sys", "subprocess", "shutil", "pathlib"}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in _blocked:
        raise ImportError(f"Import of '{name}' is blocked.")
    return importlib.__import__(name, globals, locals, fromlist, level)

builtins.open = safe_open
builtins.__import__ = safe_import

# ------------------------------------------------------------
# Execute user code inside wrapper
# ------------------------------------------------------------
USER_CODE = """
{code}
"""
exec(USER_CODE)
'''

def python_execute_code(file_name: str, code: str):
    try:
        # ----------------------------------------------------
        # 1. Archive permanent copy (with safe path)
        # ----------------------------------------------------
        archive_dir = Path(config.project_path) / "data" / "executed_python_files"
        archive_dir.mkdir(parents=True, exist_ok=True)

        raw_path = archive_dir / file_name
        archive_path = Path(_safe_resolve_path(str(raw_path)))

        if not _is_in_allowed_dirs(str(archive_path), {str(archive_dir),}):
            return {"error": "Invalid file_name: escapes archive directory."}

        archive_path.write_text(code)


        # ----------------------------------------------------
        # 2. Sandbox directory for execution
        # ----------------------------------------------------
        sandbox = Path(tempfile.mkdtemp(prefix="pyexec_"))
        exec_path = sandbox / file_name

        # Write wrapper+code in sandbox ONLY
        exec_path.write_text(SAFE_WRAPPER.format(code=code))


        # ----------------------------------------------------
        # 3. Execute inside sandbox only
        # ----------------------------------------------------
        result = subprocess.run(
            ["python3", str(exec_path)],
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            timeout=15,
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "archive_path": str(archive_path),
            "sandbox_path": str(exec_path),
        }

    except Exception as e:
        return {"error": str(e)}


_send_answer_custom_func_tool = {
    "type": "function",
    "name": "submit_answer",
    "strict": True,
    "description": "To submit the answer to the mentioned endpoint in the quiz page."
                   "For the answer submission you are going to give the value for answer field only."
                   "I Have email, secret and quiz url from constants.",
    "parameters": {
        "type": "object",
        "properties": {
            "answer_endpoint": {
                "type": "string",
                "description": "The endpoint URL in the page to submit the answer.",
            },
            "answer": {
                "type": "string",
                "description": "The answer to submit.",
            },
        },
        "required": ["answer_endpoint", "answer"],
        "additionalProperties": False,
    },
}

_transcribe_audio_custom_func_tool = {
    "type": "function",
    "name": "transcribe_audio",
    "strict": True,
    "description": "To transcribe audio content from a given audio file URL. We are using AssemblyAI for transcription.",
    "parameters": {
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "description": "An URL, a local file (as path)",
            },
        },
        "required": ["file"],
        "additionalProperties": False,
    },
}

_playwright_scraping_custom_func_tool = {
    "type": "function",
    "name": "scrape_with_playwright",
    "strict": True,
    "description": "To scrape web page content using Playwright. If you want to execute any JavaScript on the page (for some kind of click or move actions), provide the script.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the web page to scrape.",
            },
            "script": {
                "type": ["string", "null"],
                "description": "Optional JavaScript code to execute on the page.",
            },
            "screenshot_required": {
                "type": "boolean",
                "description": "Whether a screenshot of the page is required, in case of visual content analysis.",
            },
        },
        "required": ["url", "script", "screenshot_required"],
        "additionalProperties": False,
    },
}

_download_file_custom_func_tool = {
    "type": "function",
    "name": "download_file",
    "strict": True,
    "description": "To download a file from a given URL and save it locally.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "The name to save the downloaded file as.",
            },
            "url": {
                "type": "string",
                "description": "The URL of the file to download.",
            },
        },
        "required": ["file_name", "url"],
        "additionalProperties": False,
    },
}

_python_execute_code_custom_func_tool = {
    "type": "function",
    "name": "python_execute_code",
    "strict": True,
    "description": (
        "Execute Python code inside an isolated sandbox with strict safety limits. "
        "The code runs in a temporary directory and cannot access or modify the "
        "system. Absolute file paths are blocked. Write operations outside the "
        "sandbox are denied. Dangerous modules such as os, sys, subprocess, shutil, "
        "and pathlib cannot be imported. No system commands or subprocesses are "
        "allowed. No network access is permitted. A read-only archived copy of the "
        "submitted code is stored for reference."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "Name to assign to the Python script in the archive and sandbox."
            },
            "code": {
                "type": "string",
                "description": "The Python code to execute within the sandbox."
            }
        },
        "required": ["file_name", "code"],
        "additionalProperties": False
    }
}

_get_local_file_custom_func_tool = {
    "type": "function",
    "name": "get_local_file",
    "strict": True,
    "description": "To get a local file's path and size, ensuring it is within allowed directories.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path of the local file to access.",
            },
            "allow_large": {
                "type": "boolean",
                "description": "Whether to allow files larger than the safe size limit.",
            },
        },
        "required": ["file_path", "allow_large"],
        "additionalProperties": False,
    },
}


# OpenAI response API endpoint: https://platform.openai.com/docs/api-reference/responses/create
class SimpleAgent:
    def __init__(self, system_prompt_response_id: str | None = None):
        custom_function_tools = [_send_answer_custom_func_tool,
                                 _transcribe_audio_custom_func_tool,
                                 _playwright_scraping_custom_func_tool,
                                 _download_file_custom_func_tool,
                                 _python_execute_code_custom_func_tool,
                                 _get_local_file_custom_func_tool
                                ]
        self.custom_function_tools_mapping = {
            "submit_answer": submit_answer,
            "transcribe_audio": transcribe_audio,
            "scrape_with_playwright": scrape_with_playwright,
            "download_file": download_file,
            "python_execute_code": python_execute_code,
        }
        # openai_tools = [{"type": "web_search"}, {"type": "code_interpreter"}]
        openai_tools = [{"type": "web_search"}]

        self.tools = custom_function_tools + openai_tools
        self.model = config.OPENAI_MODEL_NAME
        self.client = openai.Client(
            base_url=config.OPENAI_BASE_URL,
            api_key=config.OPENAI_API_KEY,
        )
        if system_prompt_response_id is not None:
            self.system_prompt_response_id = system_prompt_response_id
            print(f"[DEBUG] Using provided system prompt response id: {self.system_prompt_response_id}")
        else:
            try:
                print("=========== Generating system prompt response id [STARTS] ==============")
                print(f"[DEBUG] Model: {self.model}")
                system_prompt_input = [{
                    "role": "developer",
                    "content": config.LLM_AGENT_SYSTEM_PROMPT
                }]
                print("[INFO] Generate system prompt reponse id")
                response = self.client.responses.create(
                    model=self.model,
                    tools=self.tools,
                    tool_choice="none",
                    input=system_prompt_input,
                    max_output_tokens=1024
                )

                self.system_prompt_response_id = response.id
                print(f"[DEBUG] Got system prompt response id: {self.system_prompt_response_id}")
                print("=========== Generating system prompt response id [ENDS] ==============")
            except:
                print("[ERROR] Got error while get system prompt response id")
                print("=========== Generating system prompt response id [ENDS] ==============")
                raise

    @staticmethod
    def _as_base64(data: bytes, mimetype: str | None = None) -> str:
        base64_content = base64.b64encode(data).decode("utf-8")
        if mimetype is None:
            return base64_content
        else:
            return f"data:{mimetype};base64," + base64_content

    def _scrape(self, url, script: str | None = None, screenshot_required: bool = False):
        try:
            html_content, script_result, screenshot = scrape_with_playwright(url, script, screenshot_required)
        except Exception as e:
            openai_input_content = [
                {
                    "type": "input_text",
                    "text": f"Error while scraping the URL {url}: {str(e)}"
                }
            ]
            return openai_input_content

        openai_input_content = [{
            "type": "input_text",
            "text": html_content
        }]

        # openai_input_content = [{
        #     "type": "input_file",
        #     "file_data": self._as_base64(html_content.encode("utf-8"))
        # }]

        if script_result and script is not None:
            openai_input_content.append({
                "type": "input_text",
                "text": script_result
            })

        if screenshot_required and screenshot is not None:
            openai_input_content.append({
                "type": "input_image",
                "detail": "high",
                "image_url": self._as_base64(screenshot, "image/png")
            })

        return openai_input_content

    def run(self, message: str = "", quiz_url: str | None=""):
        start_time = time.perf_counter()
        quiz_time_sec = 3 * 60  # 3 min
        next_quiz_url = None
        print(f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        input_content = [{
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": message
            }]
        }]

        if quiz_url is not None:
            scraped_input_content = self._scrape(quiz_url, screenshot_required=False)
            input_content[0]["content"].extend(scraped_input_content)

        previous_response_id = self.system_prompt_response_id

        print(f"[DEBUG] Tools: {self.tools}")
        while True:
            try:
                print("[DEBUG] Sending request to OpenAI response endpoint...")
                print(f"================== OpenAI REQUEST INFO [STARTS] ========================")
                print(f"[DEBUG] Got response id: {previous_response_id}")
                print(f"[DEBUG] Model: {self.model}")
                print(f"[DEBUG] Input content: {input_content}")
                print(
                    f"[DEBUG] Time elapsed: {time.perf_counter() - start_time:.2f} sec (remaining {quiz_time_sec - (time.perf_counter() - start_time):.2f} sec)")
                print(f"================= OpenAI REQUEST INFO [ENDS] ===========================")
                resp = self.client.responses.create(
                    max_output_tokens=1024,
                    previous_response_id=previous_response_id,
                    model=self.model,
                    tools=self.tools,
                    tool_choice="auto",
                    input=input_content,
                    timeout=quiz_time_sec - (time.perf_counter() - start_time)
                    # To avoid more stuck with quiz after time expire
                )
                previous_response_id = resp.id
                print(f"[DEBUG] Received response: {resp}")
            except TimeoutError:
                print(f"=============== LLM request Timeout Error Handle [STARTS] ==================")
                if next_quiz_url is not None:
                    print(f"[INFO] Time is up, moving to next quiz: {next_quiz_url}")
                    quiz_url = next_quiz_url
                    print(f"[INFO] Moving to next quiz: {quiz_url}")
                    next_quiz_url = None
                    scraped_input_content = self._scrape(quiz_url, screenshot_required=True)

                    previous_response_id = self.system_prompt_response_id

                    input_content = [{
                        "role": "user",
                        "content": scraped_input_content + [{
                            "type": "input_text",
                            "text": f"Start the work on scraped content of {quiz_url}"
                        }]
                    }]
                    print("[INFO] Resetting timer for next quiz.")
                    print(f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                    start_time = time.perf_counter()
                    print(f"=============== Next quiz phrase openai request timeout [ENDS] ==================")
                    continue
                else:
                    print(f"[INFO] Time is up, no next quiz found, exiting.")
                    print(f"=============== Next quiz phrase openai request timeout [ENDS] ==================")
                    break

            print(f"[DEBUG] Got new response id: {resp.id}")
            input_content = resp.output
            tools_content = []
            for item in resp.output:
                print(f"[DEBUG] Processing output item: {item}")
                # Note: got item as None and "'dict' object has no attribute 'type'" so have these checks
                if item.type == "function_call":

                    func_name = item.name
                    func_args = json.loads(item.arguments)
                    print("====== Tool Function Call Info [STARTS] ==========")
                    print(f"[DEBUG] Function Name: {func_name}")
                    print(f"[DEBUG] Function Arguments: {func_args}")
                    if func_name == "submit_answer":
                        print("[INFO] ::ToolCall:: Submit answer tool invoked")
                        func_args["quiz_url"] = quiz_url
                        status_code, response_text = submit_answer(**func_args)
                        print(f"[INFO] Submitted answer, status code: {status_code}, response: {response_text}")
                        func_output = json.dumps({
                            "response_status_code": status_code,
                            "response_text": response_text
                        })
                        if response_text != "":
                            try:
                                response_json = json.loads(response_text)
                                if "url" in response_json:
                                    next_quiz_url = response_json["url"]
                                    print(f"[INFO] Found next quiz URL: {next_quiz_url}")
                                if "correct" in response_json and next_quiz_url is not None:
                                    print(
                                        "=============== Next quiz phrase after answer submission [STARTS] ==================")
                                    print(f"[INFO] Answer correctness: {response_json['correct']}")
                                    if response_json["correct"]:
                                        quiz_url = next_quiz_url
                                        print(f"[INFO] Moving to next quiz: {quiz_url}")
                                        next_quiz_url = None
                                        scraped_input_content = self._scrape(quiz_url, screenshot_required=False)

                                        previous_response_id = self.system_prompt_response_id

                                        input_content = []

                                        tools_content = [{
                                            "role": "user",
                                            "content": scraped_input_content + [{
                                                "type": "input_text",
                                                "text": f"Start the work on scraped content of {quiz_url}"
                                            }]
                                        }]
                                        print("[INFO] Resetting timer for next quiz.")
                                        print(
                                            f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                                        start_time = time.perf_counter()
                                        print(
                                            f"=============== Next quiz phrase after answer submission [ENDS] ==================")
                                        break
                                    else:
                                        print(f"[INFO] Answer was incorrect, staying on the same quiz.")
                                else:
                                    print(
                                        f"[CRITICAL] Answer correct or wrong details not present in the submission reponse")
                            except json.JSONDecodeError:
                                print("[INFO] Response text is not a valid JSON.")
                    elif func_name == "transcribe_audio":
                        print("[INFO] ::ToolCall:: Transcribing audio tool invoked")
                        transcription_result = transcribe_audio(**func_args)
                        print(f"[INFO] Transcription result: {transcription_result}")
                        func_output = json.dumps(transcription_result)
                    elif func_name == "scrape_with_playwright":
                        print("[INFO] ::ToolCall:: Playwright scraping tool invoked")
                        scraped_content = self._scrape(**func_args)
                        tools_content.extend(scraped_content)
                        print(f"[INFO] Scraped content length: {len(scraped_content)}")
                        func_output = json.dumps({"message": "attached the scraped content in input"})
                    elif func_name == "download_file":
                        print("[INFO] ::ToolCall:: Download file tool invoked")
                        download_result = download_file(**func_args)
                        print(f"[INFO] Download result: {download_result}")
                        func_output = json.dumps(download_result)
                    elif func_name == "python_execute_code":
                        print("[INFO] ::ToolCall:: Python execute code tool invoked")
                        execution_result = python_execute_code(**func_args)
                        print(f"[INFO] Execution result: {execution_result}")
                        func_output = json.dumps(execution_result)
                    elif func_name == "get_local_file":
                        print("[INFO] ::ToolCall:: Get local file tool invoked")
                        local_file_result = get_local_file(**func_args)
                        if "error" not in local_file_result:
                            file_path = local_file_result["file_path"]
                            file_size = local_file_result["file_size"]
                            print(f"[INFO] Reading local file: {file_path} of size {file_size} bytes")
                            with open(file_path, "rb") as f:
                                file_data = f.read()
                            if "mime_type" in local_file_result and local_file_result["mime_type"].startswith("image"):
                                tools_content.append({
                                    "type": "input_image",
                                    "detail": "high",
                                    "image_url": self._as_base64(file_data, local_file_result["mime_type"])
                                })
                            else:
                                tools_content.append({"type": "input_file", "file_data": self._as_base64(file_data),})
                            # local_file_result["file_data_base64"] = self._as_base64(file_data)
                        print(f"[INFO] Local file result: {local_file_result}")
                        func_output = json.dumps(local_file_result)
                    else:
                        print(f"[INFO] ::ToolCall:: Unknown function name: {func_name}")
                        func_output = json.dumps({"error": f"Unknown function name: {func_name}"})
                    tools_content.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": func_output
                    })
                    print(f"[DEBUG] Function output: {func_output}")
                    print("[DEBUG] ====== Tool Function Call Info [ENDS] ==========")
            input_content += tools_content
            if time.perf_counter() - start_time > quiz_time_sec or len(tools_content) <= 0:
                print(
                    f"=============== Next quiz phrase general timeout or no new input content as next hint [STARTS] ==================")
                print(f"[DEBUG] Time elapsed: {time.perf_counter() - start_time:.2f} sec")
                print(f"[DEBUG] Start time: {start_time:.2f} sec")
                print(f"[DEBUG] Current time: {time.perf_counter():.2f} sec")
                if next_quiz_url is not None:
                    print(f"[INFO] Time is up, moving to next quiz: {next_quiz_url}")
                    quiz_url = next_quiz_url
                    print(f"[INFO] Moving to next quiz: {quiz_url}")
                    next_quiz_url = None
                    scraped_input_content = self._scrape(quiz_url, screenshot_required=True)

                    previous_response_id = self.system_prompt_response_id

                    input_content = [{
                        "role": "user",
                        "content": scraped_input_content + [{
                            "type": "input_text",
                            "text": f"Start the work on scraped content of {quiz_url}"
                        }]
                    }]
                    print("[INFO] Resetting timer for next quiz.")
                    print(f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                    start_time = time.perf_counter()
                    print(f"=============== Next quiz phrase general timeout [ENDS] ===================")
                    continue
                else:
                    print(f"[INFO] Time is up, no next quiz found, exiting.")
                    print(f"=============== Next quiz phrase general timeout [ENDS] ===================")
                    break


def main():
    agent = SimpleAgent()
    # quiz_url = "https://tds-llm-analysis.s-anand.net/demo-video?email=your+email&id=12060"
    quiz_url = "https://tds-llm-analysis.s-anand.net/demo"
    agent.run(quiz_url=quiz_url, message="Print top 3 people from people-100.csv")


if __name__ == '__main__':
    main()
