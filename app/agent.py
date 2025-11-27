import asyncio
import json
import logging
import os
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from openai.types.chat import ChatCompletionMessage

import config
from llm_providers import LLMProvider
from scraper import ScrapedDetails
from tools_registry import ToolRegistry


logger = logging.getLogger(__name__)

# this logger intended to log each agent request into a separate folder
class AgentLogger:
    _default_instance: "AgentLogger | None" = None

    def __init__(self, request_id):
        self.agent_log_dir = config.AGENT_LOG_BASE_PATH / request_id
        os.makedirs(self.agent_log_dir, exist_ok=True)
        log_file = self.agent_log_dir / f"agent.log"

        # file handler for logger
        filehandler = logging.FileHandler(log_file)
        filehandler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        filehandler.setFormatter(formatter)

        self.logger = logging.getLogger(f"[AgentLogger::{request_id}]")
        self.logger.setLevel(logging.INFO)
        # Remove other handlers to avoid duplicate logs
        for handler in self.logger.handlers:
            self.logger.removeHandler(handler)
        self.logger.addHandler(filehandler)

        self.log(f"AgentLogger initialized, logging to {log_file}")

    def log(self, message: str, level: int = logging.INFO):
        # logger.log(level, message)
        self.logger.log(level, message)

    @classmethod
    def get_default(cls):
        if cls._default_instance is None:
            cls._default_instance = AgentLogger("default")
        return cls._default_instance

    def save_scraped_details(self, url, scraped_details: ScrapedDetails) -> Path:
        """Save scraped details to a JSON file in the agent log directory."""
        from urllib.parse import urlparse, quote

        parsed_url = urlparse(url)
        safe_netloc = quote(parsed_url.netloc, safe='')
        safe_path = quote(parsed_url.path.replace('/', '_'), safe='')
        filename = f"{safe_netloc}{safe_path or '_root'}.txt" # use .txt as base, will add respective suffixes
        file_path = self.agent_log_dir / filename

        content = scraped_details["html_content"]

        with open(file_path.with_suffix('.html'), "w", encoding="utf-8") as f:
            f.write(content)
        self.log(f"HTML content saved to {file_path.with_suffix('.html')}")

        if scraped_details["screenshot"] is not None:
            screenshot: bytes = scraped_details["screenshot"]  # type: ignore
            with open(file_path.with_suffix('.png'), "wb") as f:
                f.write(screenshot)
            self.log(f"Screenshot saved to {file_path.with_suffix('.png')}")

        if scraped_details["script_result"] is not None:
            with open(file_path.with_suffix('.script.txt'), "w", encoding="utf-8") as f:
                f.write(str(scraped_details["script_result"]))
            self.log(f"Script result saved to {file_path.with_suffix('.script.txt')}")

        return file_path


    def save_downloaded_file(self, file_name, data):
        """Save downloaded file to the agent log directory."""

        # parsed_url = urlparse(file_url)
        # safe_netloc = quote(parsed_url.netloc, safe='')
        # safe_path = quote(parsed_url.path.replace('/', '_'), safe='')
        # filename = f"{safe_netloc}{safe_path or '_file'}"
        file_path = self.agent_log_dir / file_name

        with open(file_path, "wb") as f:
            f.write(data)

        self.log(f"Downloaded file saved to {file_path}")
        return file_path

    def save_python_script(self, script_name: str, script_content: str) -> Path:
        """Save a Python script to the agent log directory."""
        file_path = self.agent_log_dir / script_name
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        self.log(f"Python script saved to {file_path}")
        return file_path


class LLMAgent:
    def __init__(
            self,
            provider: LLMProvider,
            tools_registry: ToolRegistry,
            timeout_ms: int,
            agent_logs_dir: Path
    ):
        self.provider = provider
        self.tools = tools_registry
        self.timeout_ms = timeout_ms
        self.agent_logs_dir = agent_logs_dir
        os.makedirs(agent_logs_dir, exist_ok=True)
        self.system_prompt = config.LLM_AGENT_SYSTEM_PROMPT
        self.worker_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm-agent-worker")

    async def ask(self, user_input: str, request_id: str | None = None) -> Any:
        try:
            loop = asyncio.get_running_loop()

            def worker(coro):
                fut = asyncio.run_coroutine_threadsafe(coro, loop)
                return fut.result()

            if request_id is None:
                request_id = f"req_{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}"

            # submit the _ask coroutine to the worker pool
            f = self.worker_pool.submit(worker, self._ask(user_input, request_id))

            # wrap the future to be awaitable
            af = asyncio.wrap_future(f, loop=loop)
            return await asyncio.wait_for(af, timeout=self.timeout_ms)

        except Exception as e:
            logger.exception("Error during agent processing")
            return f"Error during processing: {str(e)}"

    # Note for the Project 2 consider the user_input just and url only
    async def _ask(self, user_input: str, request_id: str) -> Any:
        agent_logger = AgentLogger(request_id)
        agent_logger.log(f"User input: {user_input} using {self.provider.name} LLM Provider")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]

        start_time = datetime.now()
        # TODO: check do the timeout needed because it's alone going to handle all the quizzes for the request
        agent_logger.log(f"Start the agent with: {messages}")
        agent_logger.log(f"Available tools: {self.tools.to_dict(self.provider.name)}")
        while start_time + timedelta(milliseconds=self.timeout_ms) > datetime.now():
            # TODO: use async client
            agent_logger.log("Sending messages to LLM provider...")
            agent_logger.log(f"llm call at with {len(messages)} messages {messages}")
            resp = self.provider.chat(
                messages=messages,
                tools=self.tools.to_dict(self.provider.name),
                tool_choice="auto",
            )
            msg: ChatCompletionMessage = resp["message"]
            tool_calls = resp["tool_calls"]

            agent_logger.log(f"LLM response message: {msg}")
            agent_logger.log(f"Tool calls: {tool_calls}")

            # If no tool calls, just return content
            if not tool_calls:
                agent_logger.log(f"No tools call, so will break the loop with message: {msg}")
                break

            # 2. Execute tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [tc.model_dump() for tc in tool_calls]
                    if hasattr(tool_calls, "model_dump")
                    else [tc for tc in tool_calls],
                }
            )

            tool_results = []
            for tc in tool_calls:
                tool_name = tc.function.name
                args_json = tc.function.arguments
                args = json.loads(args_json) if isinstance(args_json, str) else args_json
                result = await self.tools.call_async(tool_name, agent_logger=agent_logger, **args)

                # Normalize to string for the tool message
                content = result if isinstance(result, str) else json.dumps(result)

                # if tool_name is submit_answer and if we got a correct true in response json, only keep default system prompt and url if exists in the response
                if tool_name == "sent_answer":
                    try:
                        result_json = json.loads(content)
                        if isinstance(result_json, dict) and result_json.get("correct") is True:
                            agent_logger.log("Answer submitted correctly.")
                            if "url" in result_json:
                                messages = [
                                    {"role": "system", "content": self.system_prompt},
                                    {"role": "user", "content": f'Next quiz {result_json["url"]}'},
                                ]
                                agent_logger.log(f"have next quiz {result_json['url']}, resetting messages for next quiz. messages {messages}")
                                continue
                            else:
                                agent_logger.log("No more quizzes, finishing the agent loop.")
                                agent_logger.log(f"final info messages: {messages}, tool_results: {tool_results}, llm response: {msg}, tool calls: {tool_calls}")
                                return messages
                        else:
                            agent_logger.log("Answer submitted incorrectly, continuing the agent loop.")
                    except Exception as e:
                        agent_logger.log(f"Error parsing submit_answer result: {str(e)}")

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tool_name,
                    "content": content,
                }
                messages.append(tool_msg)
                tool_results.append(tool_msg)
                agent_logger.log(f"Executed tool '{tool_name}' with args {args}, result: {content}")
            agent_logger.log(f"Tool results appended to messages: {tool_results}")
        else:
            agent_logger.log("Timeout reached during agent processing.")
            return messages

        return messages


async def main():
    from llm_providers import OpenAIProvider
    import config
    from setup_logger import setup as logger_setup

    logger_setup()

    llm_provider = OpenAIProvider(
        model=config.OPENAI_MODEL_NAME,
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
    )

    from tools import tools_registry

    agent = LLMAgent(
        provider=llm_provider,
        tools_registry=tools_registry,
        timeout_ms=config.TIMEOUT_MS,
        agent_logs_dir=config.AGENT_LOG_BASE_PATH,
    )
    request_id = f"demo_{len(list(config.AGENT_LOG_BASE_PATH.iterdir()))}"
    response = await agent.ask("https://tds-llm-analysis.s-anand.net/demo", request_id=request_id)
    print(response)


if __name__ == "__main__":
    exit(asyncio.run(main()))
