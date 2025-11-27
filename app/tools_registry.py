from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(
        self,
        parameters: dict[str, Any],
        name: str | None = None,
        description: str | None = None,
    ):
        """
        Decorator to register a function as a tool.
        """

        parameters = parameters or {"type": "object", "properties": {}, "required": []}

        def decorator(fn: Callable[..., Any]):
            tool_name = name or fn.__name__
            if tool_name in self.tools:
                raise ValueError(f"Tool '{tool_name}' already registered")
            self.tools[tool_name] = Tool(
                name=tool_name,
                description=description or fn.__doc__ or "",
                parameters=parameters,
                func=fn,
            )
            return fn

        return decorator

    def as_openai_tools(self) -> list[dict[str, Any]]:
        """Convert registry to OpenAI tools format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self.tools.values()
        ]

    def call(self, name: str, **kwargs: Any) -> Any:
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        return self.tools[name].func(**kwargs)

    async def call_async(self, name: str, **kwargs: Any) -> Any:
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        func = self.tools[name].func
        if not callable(func):
            raise ValueError(f"Tool '{name}' is not callable")
        return await func(**kwargs)

    def to_dict(self, name):
        match name:
            case "openai":
                return self.as_openai_tools()
            case _:
                raise ValueError(f"Unsupported provider for tools: {name}")
