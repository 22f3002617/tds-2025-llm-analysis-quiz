import abc
import json
from typing import override, Any, Literal

import config

import logging

from config import project_path
from setup_logger import setup as setup_logger

logger = logging.getLogger(__name__)


class LLMProvider(abc.ABC):
    def __init__(self, name, system_prompt_response_id: int | None = None):
        self._name = name
        self.system_prompt_response_id = system_prompt_response_id

    @abc.abstractmethod
    def chat(self, messages: list[dict[str, Any]],
             tools: list[dict[str, Any]] | None = None,
             tool_choice: Literal["auto", "none"] = "auto") -> dict[str, Any]:
        pass

    @abc.abstractmethod
    def response(self, input_messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                 tool_choice: Literal["auto", "none"] = "auto", previous_response_id: int | None = None) -> dict[
        str, Any]:
        pass

    @property
    def name(self) -> str:
        return self._name


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str, system_prompt_response_id: int | None = None):
        import openai
        super().__init__(name="openai", system_prompt_response_id=system_prompt_response_id)
        self.model = model
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    @override
    def chat(self, messages: list[dict[str, Any]],
             tools: list[dict[str, Any]] | None = None,
             tool_choice: Literal["auto", "none"] = "auto") -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        resp = self.client.chat.completions.create(**kwargs)
        print(resp)
        logger.info("(%s) Number of tokens burned: %s (detailed %s)", self.name, resp.usage.total_tokens,
                    json.dumps(resp.usage.to_dict()))
        choice = resp.choices[0].message
        return {
            "raw": resp,
            "message": choice,
            "tool_calls": getattr(choice, "tool_calls", None),
        }

    @override
    def response(self, input_messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, tool_choice: Literal["auto", "none", "required"] = "auto", previous_response_id: int | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": input_messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id
            logger.info("Using previous_response_id: %s", previous_response_id)
        else:
            logger.info("No previous response_id provided.")
            if self.system_prompt_response_id:
                logger.info("Using system_prompt_response_id: %s", self.system_prompt_response_id)
                kwargs["previous_response_id"] = self.system_prompt_response_id
            else:
                logger.info("No system_prompt_response_id set.")

        resp = self.client.responses.create(**kwargs)
        output = resp.output
        return {
            "raw": resp,
            "response_id": resp.id,
            "outputs": output,
        }


def main():
    setup_logger()

    provider = OpenAIProvider(
        model=config.OPENAI_MODEL_NAME,
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL
    )

    response = provider.chat(messages=[
        {"role": "user", "content": "Hello, world!"}
    ])
    print(response)

if __name__ == "__main__":
    main()
