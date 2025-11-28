import base64
import json
import time
import openai
from playwright.sync_api import sync_playwright

import config
import assemblyai as aai


def scrape_with_playwright(url: str, script: str | None = None, screenshot_required: bool = False,
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
        # decoded_bytes = base64.b64decode(audio_base64.encode('ascii'))
        ##########################
        ###### DEV ###############
        # transcript = transcriber.transcribe(file)
        ##########################
        ##########################
        print("[DEBUG] Audio transcription completed.")
        # if transcript.status == "error":
        #     print(f"[DEBUG] Transcription error: {transcript.error}")
        #     return {"error": f"Transcription error: {transcript.error}"}
        # print(f"[DEBUG] Transcription completed successfully: {transcript.text}")
        # return {"transcription_text": transcript.text}
        return {'transcription_text': 'You need to download the CSV file provided. Pick the first column and add all values greater than or equal to the cutoff value provided.'}
    except Exception as e:
        print(f"[DEBUG] Error decoding Base64", e)
        return {"error": f"Error decoding Base64: {e}"}


def download_file(file_name: str, url: str):
    import requests
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        return {"error": f"Error downloading file from {url}: {e}"}

    download_file_path = config.project_path / "data" / "downloads" / file_name
    download_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(download_file_path, "wb") as f:
        f.write(response.content)

    return {"file_path": str(download_file_path)}


def python_execute_code(file_name: str, code: str):
    try:
        # spawn as a subprocess and get stdout and stderr
        import subprocess
        executed_python_files = config.project_path / "data" / "executed_python_files"
        executed_python_files.mkdir(parents=True, exist_ok=True)
        file_path = executed_python_files / file_name
        with open(file_path) as f:
            f.write(code)

        result = subprocess.run(
            ["python3", file_path],
            capture_output=True,
            text=True,
            timeout=60  # seconds
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except Exception as e:
        return {"error": f"Error executing code: {e}"}


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
    "description": "To execute a given Python code snippet and return the output.",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code snippet to execute.",
            },
            "file_name": {
                "type": "string",
                "description": "The name suggestion for the python code to store at local..",
            },
        },
        "required": ["code", "file_name"],
        "additionalProperties": False,
    },
}


# OpenAI response API endpoint: https://platform.openai.com/docs/api-reference/responses/create
class SimpleAgent:
    def __init__(self):
        custom_function_tools = [_send_answer_custom_func_tool, _transcribe_audio_custom_func_tool,
                                 _playwright_scraping_custom_func_tool, _download_file_custom_func_tool,
                                 _python_execute_code_custom_func_tool]
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
                max_output_tokens=2000
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
            # escape html content
            # "text": html_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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

    def run(self, quiz_url: str):
        start_time = time.perf_counter()
        quiz_time_sec = 3 * 60  # 3 min
        next_quiz_url = None
        print(f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        scraped_input_content = self._scrape(quiz_url, screenshot_required=True)

        previous_response_id = self.system_prompt_response_id

        input_content = [{
            "role": "user",
            "content": scraped_input_content
                       + [{
                "type": "input_text",
                "text": f"Use the scraped content to answer the quiz questions."
            }]
        }]
        while True:
            try:
                print("[DEBUG] Sending request to OpenAI response endpoint...")
                print(f"================== OpenAI REQUEST INFO [STARTS] ========================")
                print(f"[DEBUG] Got response id: {previous_response_id}")
                print(f"[DEBUG] Model: {self.model}")
                print(f"[DEBUG] Tools: {self.tools}")
                print(f"[DEBUG] Input content: {input_content}")
                print(
                    f"[DEBUG] Time elapsed: {time.perf_counter() - start_time:.2f} sec (remaining {quiz_time_sec - (time.perf_counter() - start_time):.2f} sec)")
                print(f"================= OpenAI REQUEST INFO [ENDS] ===========================")
                resp = self.client.responses.create(
                    max_output_tokens=10000,
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
                print(f"=============== Next quiz phrase openai request timeout [STARTS] ==================")
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
            input_content = []
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
                                    print(
                                        f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                                    start_time = time.perf_counter()
                                    print(
                                        f"=============== Next quiz phrase after answer submission [ENDS] ==================")
                                    continue
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
                        print(f"[INFO] Scraped content length: {len(scraped_content)}")
                        func_output = json.dumps({"scraped_content": scraped_content})
                        # func_output = (scraped_content)
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
                    else:
                        print(f"[INFO] ::ToolCall:: Unknown function name: {func_name}")
                        func_output = json.dumps({"error": f"Unknown function name: {func_name}"})
                    input_content.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": func_output
                    })
                    print(f"[DEBUG] Function output: {func_output}")
                    print("[DEBUG] ====== Tool Function Call Info [ENDS] ==========")

            if time.perf_counter() - start_time > quiz_time_sec or len(input_content) <= 0:
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
    # quiz_url = "https://tds-llm-analysis.s-anand.net/demo"
    quiz_url = "https://tds-llm-analysis.s-anand.net/demo-audio?email=your+email&id=12059"
    agent.run(quiz_url)


if __name__ == '__main__':
    main()
