# ai_service/src/agentic/tools/base_async_tool.py
import asyncio
import nest_asyncio
from typing import Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel

class BaseAsyncTool(BaseTool):
    """
    A custom base tool that handles running asynchronous methods from a synchronous context.
    """
    async def _arun(self, *args, **kwargs) -> Any:
        """
        Asynchronous run method. To be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement the _arun method.")

    def _run(self, **kwargs: Any) -> Any:
        """
        Synchronous wrapper that correctly handles the asyncio event loop.
        """
        tool_input = self.args_schema(**kwargs)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            nest_asyncio.apply()

        return loop.run_until_complete(self._arun(tool_input))