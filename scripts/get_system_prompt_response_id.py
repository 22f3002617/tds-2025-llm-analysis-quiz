from itertools import count

from app.llm_providers import OpenAIProvider
from app import config, tools

import logging
from setup_logger import setup as setup_logger
from tools_registry import ToolsRegistry

log_file = config.project_path / "data" / "logs" / "get_system_prompt_response_id.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
setup_logger(log_file)

logger = logging.getLogger(__name__)

def get_system_prompt_response_id(system_prompt: str, tool_registry: ToolsRegistry) -> int:
    """
    Get the response ID of a system prompt by sending it to the OpenAI API.
    """
    provider = OpenAIProvider(
        model=config.OPENAI_MODEL_NAME,
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
    )
    logger.info(f"System prompt ID: {system_prompt}")
    logger.info(f"Using tools: {tool_registry.to_dict("openai_response_endpoint_tools")}")
    response = provider.response(
        input_messages=[{"role": "system", "content": system_prompt}],
        tools=tool_registry.to_dict("openai_response_endpoint_tools"),
        tool_choice="none",
    )
    logger.info(f"System prompt response: {response}")
    response_id = response["response_id"]
    logger.info("System prompt response ID: %s", response_id)

    if sum(output.type=="function_call" for output in response["outputs"])>0:
        raise ValueError("Tools selected on init system prompt")
    return response_id

def main():
    system_prompt = config.LLM_AGENT_SYSTEM_PROMPT

    print(f"System prompt {get_system_prompt_response_id(system_prompt, tools.tools_registry)}")

if __name__ == "__main__":
    main()