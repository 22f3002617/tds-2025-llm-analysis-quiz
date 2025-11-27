import abc
from typing import override, Any, Literal


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

        choice = resp.choices[0].message
        return {
            "raw": resp,
            "message": choice,
            "tool_calls": getattr(choice, "tool_calls", None),
        }