import logging

import config
from llm_providers import OpenAIProvider

from setup_logger import setup as setup_logger
from tools import tools_registry

log_file = config.project_path / "data" / "logs" / "test_system_prompt_response_id.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
setup_logger(log_file)

logger = logging.getLogger(__name__)


system_response_id = config.SYSTEM_PROMPT_RESPONSE_ID
logger.info(f"system_response_id: {system_response_id}")
assert system_response_id is not None, "SYSTEM_RESPONSE_ID is not set in config"

def main():
    llm = OpenAIProvider(
        model=config.OPENAI_MODEL_NAME,
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
        system_prompt_response_id=system_response_id,
    )

    response = llm.response([{"role": "user", "content": "https://tds-llm-analysis.s-anand.net/demo2?email=22f3002671@study.ds.iitm.com"}],
                            tools=tools_registry.to_dict("openai_response_endpoint_tools"))
    logger.info(f"Response: {response}")
    if sum(output.type=="function_call" for output in response["outputs"])<1:
        raise ValueError("Expected tool_calls in the response")
    logger.info("Test passed: tool_calls found in the response")

if __name__ == '__main__':
    main()
