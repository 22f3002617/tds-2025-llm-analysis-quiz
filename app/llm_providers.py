import abc
import json
from typing import override, Any, Literal

import config

import logging
from setup_logger import setup as setup_logger

logger = logging.getLogger(__name__)

class LLMProvider(abc.ABC):
    def __init__(self, name):
        self._name = name

    @abc.abstractmethod
    def chat(self, messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Literal["auto", "none"] = "auto") -> dict[str, Any]:
        pass

    @property
    def name(self) -> str:
        return self._name

class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str):
        import openai
        super().__init__(name="openai")
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
        logger.info("(%s) Number of tokens burned: %s (detailed %s)", self.name, resp.usage.total_tokens, json.dumps(resp.usage.to_dict()))
        choice = resp.choices[0].message
        return {
            "raw": resp,
            "message": choice,
            "tool_calls": getattr(choice, "tool_calls", None),
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