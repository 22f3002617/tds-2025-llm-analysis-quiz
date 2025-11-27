import json
import logging

from typing import Literal

import aiohttp

from agent import AgentLogger
import config
from tools_registry import ToolRegistry
from scraper import ScraperFactory, ScrapedDetails
import base64

tools_registry = ToolRegistry()

logger = logging.getLogger(__name__)

@tools_registry.register(
    name="browser",
    description="Scrape content from a given URL. Using playwright, useful when javascript based rendering is needed.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to scrape.",
            },
            "script": {
                "type": "string",
                "description": "Optional JavaScript code to execute on the page after it loads.",
            },
            "screenshot_required": {
                "type": "boolean",
                "description": "Whether a screenshot of the page is required.",
                "default": False,
            }
        },
        "required": ["url"],
    },
)
async def scraper(url: str, script: str | None = None, screenshot_required: bool = False, agent_logger: AgentLogger|None=None) -> str:
    try:
        if agent_logger is None:
            agent_logger = AgentLogger.get_default()
        agent_logger.log(f"Scraping {url}")
        scraper_instance = ScraperFactory.get(config.SCRAPER_TYPE)
        scraped_details: ScrapedDetails = await scraper_instance.scrape(url, script, screenshot_required)

        scraped_details_response = {"html_content": scraped_details["html_content"]}
        if scraped_details["script_result"] is not None:
            scraped_details_response["script_result"] = str(scraped_details["script_result"])
        if scraped_details["screenshot"] is not None:
            data: bytes = scraped_details["screenshot"] # type: ignore
            scraped_details_response["screenshot"] = base64.b64encode(data).decode('utf-8')

        agent_logger.save_scraped_details(url, scraped_details)
        return json.dumps(scraped_details_response)
    except Exception as e:
        return f"Error scraping {url}: {str(e)}"

Kind = Literal["boolean", "number", "string", "file", "json"]
def prepare_answer(answer: str, kind: Kind) -> bool | float | str | dict:
    match kind:
        case "boolean":
            return bool(answer)
        case "number":
            return float(answer)
        case "file" | "string":
            return answer  # Assuming answer is a base64 URI of a file attachment
        case "json":
            import json
            return json.loads(answer)

@tools_registry.register(
    name="sent_answer",
    description="If you received a quiz page, after process and find the answer, use this tool to send the answer back to the answer endpoint provided in the quiz. becarefull with email and secret token those are sensitive to be correct otherwise the response will be 'correct: False'.",
    parameters={
        "type": "object",
        "properties": {
            "submission_url": {
                "type": "string",
                "description": "The URL of the quiz page where the answer should be sent.",
            },
            "answer": {
                "type": "string",
                "description": "The answer to send back to the quiz page. Can be boolean, number, string, base64 URI of a file attachment, or a JSON object with a combination of these.",
            },
            "kind": {
                "type": "string",
                "description": "The kind of the answer being sent ('boolean', 'number', 'string', 'file', 'json')."
            },
            "quiz_url": {
                "type": "string",
                "description": "The URL of the quiz page we solving.",
            },
            "email": {
                "type": "string",
                "description": "Email id mentioned quiz page for quiz submission url, (default: from config).",
            },
            "secret": {
                "type": "string",
                "description": "The secret token to authenticate the submission url from the quiz page, (default: None).",
            }
        },
        "required": ["submission_url", "answer", "kind", "quiz_url"],
        # "required": ["submission_url", "quiz_url"],
    },
)
async def sent_answer(submission_url: str, answer: str, kind: Kind, quiz_url: str,
                      email: str | None = None, secret: str | None = None,
                      agent_logger: AgentLogger|None=None) -> str:
    try:
        if agent_logger is None:
            agent_logger = AgentLogger.get_default()
        agent_logger.log(f"Sending answer to {submission_url} for quiz {quiz_url}")
        agent_logger.log(f"answer: {answer}, kind: {kind}, email: {email}, secret: {secret}")
        if not email:
            email = config.STUDENT_EMAIL_ID
        if not secret:
            secret = config.SECRET_KEY
        agent_logger.log(f"answer: {answer}, kind: {kind}, email: {email}, secret: {secret}")

        answer = prepare_answer(answer, kind)
        agent_logger.log(f"prepared answer: {answer}")
        async with aiohttp.ClientSession() as session:
            payload = {"answer": answer, "url": quiz_url, "email": email, "secret": secret}
            agent_logger.log(f"sending payload: {payload}")
            async with session.post(submission_url, json=payload) as resp:
                response_json = await resp.json()
                agent_logger.log(f"received answer: {response_json}")
                return json.dumps(response_json)
    except Exception as e:
        return f"Error sending answer: {str(e)}"

# tool to download a file from a given URL
@tools_registry.register(
    name="download_file",
    description="Download a file from a given URL and return the path it was saved to. Use this only if preview needed, otherwise include the download logic in the python script itself with processing script.",
    parameters={
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "The name to save the downloaded file as.",
            },
            "file_url": {
                "type": "string",
                "description": "The URL of the file to download.",
            },
        },
        "required": ["file_name", "file_url"],
    },
)
async def download_file(file_name: str, file_url: str, agent_logger: AgentLogger|None=None) -> str:
    try:
        if agent_logger is None:
            agent_logger = AgentLogger.get_default()
        agent_logger.log(f"Downloading file from {file_url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                if resp.status != 200:
                    return f"Error downloading file: HTTP {resp.status}"
                data = await resp.read()
                file_path = agent_logger.save_downloaded_file(file_name, data)
                # encoded_data = base64.b64encode(data).decode('utf-8')
                # agent_logger.log(f"Downloaded file size: {len(data)} bytes")
                return str(file_path)
    except Exception as e:
        return f"Error downloading file: {str(e)}"

# Tools to execute python script for analysis
@tools_registry.register(
    name="execute_python",
    description="Execute a Python script for data analysis and return stdout output.",
    parameters={
        "type": "object",
        "properties": {
            "script_name": {
                "type": "string",
                "description": "The name of the Python script file to save.",
            },
            "script": {
                "type": "string",
                "description": "The Python script to execute.",
            },
        },
        "required": ["script"],
    },
)
async def execute_python(script_name: str, script: str, agent_logger: AgentLogger|None=None) -> str:
    try:
        if agent_logger is None:
            agent_logger = AgentLogger.get_default()
        agent_logger.log(f"Executing python script.")
        script_path = agent_logger.save_python_script(script_name, script)
        # execute as subprocess get an output
        import subprocess
        result = subprocess.check_output(['python3', script_path], universal_newlines=True)

        agent_logger.log(f"Script executed successfully. Result: {result}")
        return str(result)
    except Exception as e:
        return f"Error executing python script: {str(e)}"