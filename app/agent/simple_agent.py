import base64
import json
import logging

import time
from time import strftime

import openai

from app import config
from app import setup_logger
from app.agent.agent_logger import AgentLogger
from app.agent.tools.schema import _send_answer_custom_func_tool, _transcribe_audio_custom_func_tool, \
    _playwright_scraping_custom_func_tool, _download_file_custom_func_tool, _python_execute_code_custom_func_tool, \
    _get_local_file_custom_func_tool, _get_video_frames_custom_func_tool

from app.agent.tools.tools import submit_answer, transcribe_audio, scrape_with_playwright, download_file, \
    execute_python_in_sandbox, get_local_file, get_video_frames


logger = logging.getLogger(__name__)

# OpenAI response API endpoint: https://platform.openai.com/docs/api-reference/responses/create
class SimpleAgent:
    @staticmethod
    def log(log_msg: str, **kwargs):
        logger.info(log_msg, **kwargs)
        print(log_msg, **kwargs)
    def __init__(self, system_prompt_response_id: str | None = None):
        custom_function_tools = [_send_answer_custom_func_tool,
                                 _transcribe_audio_custom_func_tool,
                                 _playwright_scraping_custom_func_tool,
                                 _download_file_custom_func_tool,
                                 _python_execute_code_custom_func_tool,
                                 _get_local_file_custom_func_tool,
                                 _get_video_frames_custom_func_tool
                                 ]
        self.custom_function_tools_mapping = {
            "submit_answer": submit_answer,
            "transcribe_audio": transcribe_audio,
            "scrape_with_playwright": scrape_with_playwright,
            "download_file": download_file,
            "python_execute_code": execute_python_in_sandbox,
            "get_local_file": get_local_file,
            "get_video_frames": get_video_frames,
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

            self.log(f"[DEBUG] Using provided system prompt response id: {self.system_prompt_response_id}")
        else:
            try:
                self.log("=========== Generating system prompt response id [STARTS] ==============")
                self.log(f"[DEBUG] Model: {self.model}")
                system_prompt_input = [{
                    "role": "developer",
                    "content": config.LLM_AGENT_SYSTEM_PROMPT
                }]
                self.log("[INFO] Generate system prompt reponse id")
                response = self.client.responses.create(
                    model=self.model,
                    tools=self.tools,
                    tool_choice="none",
                    input=system_prompt_input,
                    max_output_tokens=8192
                )

                self.system_prompt_response_id = response.id
                self.log(f"[DEBUG] Got system prompt response id: {self.system_prompt_response_id}")
                self.log("=========== Generating system prompt response id [ENDS] ==============")
            except:
                logger.exception(f"Got error while get system prompt response id")
                self.log("[ERROR] Got error while get system prompt response id")
                self.log("=========== Generating system prompt response id [ENDS] ==============")
                raise

    @staticmethod
    def _as_base64(data: bytes, mimetype: str | None = None) -> str:
        base64_content = base64.b64encode(data).decode("utf-8")
        if mimetype is None:
            return base64_content
        else:
            return f"data:{mimetype};base64," + base64_content

    def _scrape(self, url, script: str | None = None, screenshot_required: bool = False):
        openai_input_content = []
        try:
            status, html_content, script_result, screenshot = scrape_with_playwright(url, script, screenshot_required)
            openai_input_content.append(
                {
                    "type": "input_text",
                    "text": f"Scraped content from URL {url} with status {status}"
                }
            )
        except Exception as e:
            logger.exception(f"Error while scraping the URL {url}: {str(e)}")
            self.log(f"[ERROR] Error while scraping the URL {url}: {str(e)}")
            traceback_str = '\n'.join(e.__traceback__.format())
            self.log(traceback_str)
            openai_input_content = [
                {
                    "type": "input_text",
                    "text": f"Error while scraping the URL {url}: {str(e)}"
                }
            ]
            return openai_input_content

        openai_input_content.append({
            "type": "input_text",
            "text": html_content
        })

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

    def run(self, message: str = "", quiz_url: str | None = ""):
        agent_logger = AgentLogger(request_id=f"simple-agent-{strftime('%Y-%m-%dT%H:%M:%S')}")
        agent_logger.log("SimpleAgent run started")

        def log(log_msg, **kwargs):
            agent_logger.log(log_msg, **kwargs)
            print(log_msg)

        start_time = time.perf_counter()
        quiz_time_sec = 3 * 60  # 3 min
        next_quiz_url = None

        log(f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
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

        log(f"[DEBUG] Tools: {self.tools}")
        reasoning_retry_count = 0
        while True:
            try:
                log("[DEBUG] Sending request to OpenAI response endpoint...")
                log(f"================== OpenAI REQUEST INFO [STARTS] ========================")
                log(f"[DEBUG] Got response id: {previous_response_id}")
                log(f"[DEBUG] Model: {self.model}")
                log(f"[DEBUG] Input content: {input_content}")
                log(
                    f"[DEBUG] Time elapsed: {time.perf_counter() - start_time:.2f} sec (remaining {quiz_time_sec - (time.perf_counter() - start_time):.2f} sec)")
                log(f"================= OpenAI REQUEST INFO [ENDS] ===========================")
                resp = self.client.responses.create(
                    max_output_tokens=2048,
                    previous_response_id=previous_response_id,
                    model=self.model,
                    tools=self.tools,
                    tool_choice="auto",
                    input=input_content,
                    timeout=quiz_time_sec - (time.perf_counter() - start_time)
                    # To avoid more stuck with quiz after time expire
                )
                previous_response_id = resp.id
                log(f"[DEBUG] Received response: {resp}")
            except TimeoutError:
                logger.exception(f"TimeoutError: LLM request timed out.")
                log(f"=============== LLM request Timeout Error Handle [STARTS] ==================")
                if next_quiz_url is not None:
                    log(f"[INFO] Time is up, moving to next quiz: {next_quiz_url}")
                    quiz_url = next_quiz_url
                    log(f"[INFO] Moving to next quiz: {quiz_url}")
                    next_quiz_url = None
                    scraped_input_content = self._scrape(quiz_url, screenshot_required=True)

                    previous_response_id = self.system_prompt_response_id

                    input_content = [{
                        "role": "user",
                        "content": scraped_input_content + [{
                            "type": "input_text",
                            "text": f"solve the quiz from scraped content"
                        }]
                    }]
                    log("[INFO] Resetting timer for next quiz.")
                    log(f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                    start_time = time.perf_counter()
                    log(f"=============== Next quiz phrase openai request timeout [ENDS] ==================")
                    continue
                else:
                    log(f"[INFO] Time is up, no next quiz found, exiting.")
                    log(f"=============== Next quiz phrase openai request timeout [ENDS] ==================")
                    break

            log(f"[DEBUG] Got new response id: {resp.id}")
            input_content = []
            tools_content = []
            for item in resp.output:
                log(f"[DEBUG] Processing output item: {item}")
                # Note: got item as None and "'dict' object has no attribute 'type'" so have these checks
                if item.type == "function_call":
                    reasoning_retry_count = 0
                    func_name = item.name
                    func_args = json.loads(item.arguments)
                    log("====== Tool Function Call Info [STARTS] ==========")
                    log(f"[DEBUG] Function Name: {func_name}")
                    log(f"[DEBUG] Function Arguments: {func_args}")
                    if func_name == "submit_answer":
                        log("[INFO] ::ToolCall:: Submit answer tool invoked")
                        func_args["quiz_url"] = quiz_url
                        status_code, response_text = submit_answer(**func_args)
                        log(f"[INFO] Submitted answer, status code: {status_code}, response: {response_text}")
                        func_output = json.dumps({
                            "response_status_code": status_code,
                            "response_text": response_text
                        })
                        if response_text != "":
                            try:
                                response_json = json.loads(response_text)
                                if "url" in response_json:
                                    next_quiz_url = response_json["url"]
                                    log(f"[INFO] Found next quiz URL: {next_quiz_url}")
                                if "correct" in response_json and next_quiz_url is not None:
                                    log(
                                        "=============== Next quiz phrase after answer submission [STARTS] ==================")
                                    log(f"[INFO] Answer correctness: {response_json['correct']}")
                                    if response_json["correct"]:
                                        quiz_url = next_quiz_url
                                        log(f"[INFO] Moving to next quiz: {quiz_url}")
                                        next_quiz_url = None
                                        scraped_input_content = self._scrape(quiz_url, screenshot_required=False)

                                        previous_response_id = self.system_prompt_response_id

                                        input_content = []

                                        tools_content = [{
                                            "role": "user",
                                            "content": scraped_input_content + [{
                                                "type": "input_text",
                                                "text": f"solve the quiz from scraped content"
                                            }]
                                        }]
                                        log("[INFO] Resetting timer for next quiz.")
                                        log(
                                            f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                                        start_time = time.perf_counter()
                                        log(
                                            f"=============== Next quiz phrase after answer submission [ENDS] ==================")
                                        break
                                    else:
                                        log(f"[INFO] Answer was incorrect, staying on the same quiz.")
                                else:
                                    log(
                                        f"[CRITICAL] Answer correct or wrong details not present in the submission reponse")
                            except json.JSONDecodeError:
                                logger.exception(f"Response text is not a valid JSON: {response_text}")
                                log("[INFO] Response text is not a valid JSON.")
                    elif func_name == "transcribe_audio":
                        log("[INFO] ::ToolCall:: Transcribing audio tool invoked")
                        transcription_result = transcribe_audio(**func_args)
                        log(f"[INFO] Transcription result: {transcription_result}")
                        func_output = json.dumps(transcription_result)
                    elif func_name == "scrape_with_playwright":
                        log("[INFO] ::ToolCall:: Playwright scraping tool invoked")
                        scraped_content = self._scrape(**func_args)
                        tools_content.extend(scraped_content)
                        log(f"[INFO] Scraped content length: {len(scraped_content)}")
                        func_output = json.dumps({"message": "attached the scraped content in input"})
                    elif func_name == "download_file":
                        log("[INFO] ::ToolCall:: Download file tool invoked")
                        download_result = download_file(**func_args)
                        log(f"[INFO] Download result: {download_result}")
                        func_output = json.dumps(download_result)
                    elif func_name == "python_execute_code":
                        log("[INFO] ::ToolCall:: Python execute code tool invoked")
                        execution_result = execute_python_in_sandbox(**func_args)
                        log(f"[INFO] Execution result: {execution_result}")
                        func_output = json.dumps(execution_result)
                    elif func_name == "get_local_file":
                        log("[INFO] ::ToolCall:: Get local file tool invoked")
                        local_file_result = get_local_file(**func_args)
                        if "error" not in local_file_result:
                            file_path = local_file_result["file_path"]
                            file_size = local_file_result["file_size"]
                            log(f"[INFO] Reading local file: {file_path} of size {file_size} bytes")
                            with open(file_path, "rb") as f:
                                file_data = f.read()
                            if "mime_type" in local_file_result and local_file_result["mime_type"].startswith("image"):
                                tools_content.append({
                                    "type": "input_image",
                                    "detail": "high",
                                    "image_url": self._as_base64(file_data, local_file_result["mime_type"])
                                })
                            else:
                                tools_content.append({"type": "input_file", "file_data": self._as_base64(file_data), })
                            # local_file_result["file_data_base64"] = self._as_base64(file_data)
                        log(f"[INFO] Local file result: {local_file_result}")
                        func_output = json.dumps(local_file_result)
                    elif func_name == "get_video_frames":
                        log("[INFO] ::ToolCall:: Get video frames tool invoked")
                        video_frames_result = get_video_frames(**func_args)
                        log(f"[INFO] Video frames result: {video_frames_result}")
                        for idx, frame_data in enumerate(video_frames_result.get("frames", [])):
                            tools_content.append({
                                "type": "input_image",
                                "detail": "high",
                                "image_url": self._as_base64(frame_data, "image/png"),
                                "description": f"Frame {idx} from video"
                            })
                        func_output = json.dumps({
                            "num_frames": len(video_frames_result.get("frames", []))
                        })
                    else:
                        log(f"[INFO] ::ToolCall:: Unknown function name: {func_name}")
                        func_output = json.dumps({"error": f"Unknown function name: {func_name}"})
                    tools_content.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": func_output
                    })
                    log(f"[DEBUG] Function output: {func_output}")
                    log("[DEBUG] ====== Tool Function Call Info [ENDS] ==========")
            input_content += tools_content
            if time.perf_counter() - start_time > quiz_time_sec or len(tools_content) <= 0:
                if reasoning_retry_count<2:
                    reasoning_retry_count +=1
                    log(f"[INFO] No tool calls made in this response, retrying reasoning step {reasoning_retry_count}/2.")
                    input_content += [{
                        "role": "user",
                        "content": [{
                            "type": "input_text",
                            "text": f"Remember you are on autonomous agent, proceed with what best for answer the quiz. Answer it or move to the next quiz."
                        }]
                    }]
                    continue

                log(
                    f"=============== Next quiz phrase general timeout or no new input content as next hint [STARTS] ==================")
                log(f"[DEBUG] Time elapsed: {time.perf_counter() - start_time:.2f} sec")
                log(f"[DEBUG] Start time: {start_time:.2f} sec")
                log(f"[DEBUG] Current time: {time.perf_counter():.2f} sec")
                if next_quiz_url is not None:
                    log(f"[INFO] Time is up, moving to next quiz: {next_quiz_url}")
                    quiz_url = next_quiz_url
                    log(f"[INFO] Moving to next quiz: {quiz_url}")
                    next_quiz_url = None
                    scraped_input_content = self._scrape(quiz_url, screenshot_required=True)

                    previous_response_id = self.system_prompt_response_id

                    input_content = [{
                        "role": "user",
                        "content": scraped_input_content + [{
                            "type": "input_text",
                            "text": f"solve the quiz from scraped content"
                        }]
                    }]
                    log("[INFO] Resetting timer for next quiz.")
                    log(f"[INFO] quiz started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                    start_time = time.perf_counter()
                    log(f"=============== Next quiz phrase general timeout [ENDS] ===================")
                    continue
                else:
                    log(f"[INFO] Time is up, no next quiz found, exiting.")
                    log(f"=============== Next quiz phrase general timeout [ENDS] ===================")
                    break


def main():
    setup_logger.setup()
    agent = SimpleAgent()
    # quiz_url = "https://tds-llm-analysis.s-anand.net/demo-video?email=your+email&id=12060"
    quiz_url = "https://tds-llm-analysis.s-anand.net/demo"
    agent.run(quiz_url=quiz_url, message="solve the quiz from scraped content")


if __name__ == '__main__':
    main()
