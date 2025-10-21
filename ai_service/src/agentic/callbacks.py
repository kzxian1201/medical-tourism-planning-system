# src/agentic/callbacks.py
import json
import asyncio 
from typing import Any, Dict, List, Union, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult, GenerationChunk
from langchain_core.agents import AgentAction, AgentFinish 

# This handler will be used to stream agent progress back to the client via SSE
class StreamingCallbackHandler(BaseCallbackHandler):
    """
    A custom LangChain callback handler that captures agent's thoughts, actions,
    and observations and yields them as JSON strings for Server-Sent Events (SSE).
    This allows real-time progress updates to the frontend.
    """
    def __init__(self, queue: asyncio.Queue):
        # We use an asyncio Queue to pass messages from the callback methods
        # (which run in the agent's execution context) to the streaming function.
        self.queue = queue
        self.current_message = "" # To build up messages if they come in chunks

    def _format_message(self, event_type: str, content: Any) -> str:
        """Helper to format messages as JSON for SSE."""
        # Ensure content is stringifiable
        if isinstance(content, dict):
            content_str = json.dumps(content)
        elif isinstance(content, str):
            content_str = content
        else:
            content_str = str(content)

        # Return as a JSON string, which will be prefixed with "data: " for SSE
        return json.dumps({"event": event_type, "content": content_str})

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Run when LLM starts running."""
        # Optional: You can send a message when LLM starts, but it can be noisy.
        # await self.queue.put(self._format_message("llm_start", "Agent is thinking..."))
        pass

    async def on_llm_new_token(
        self,
        token: str,
        *,
        chunk: Optional[GenerationChunk] = None,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run on new LLM token. This is often used for streaming LLM responses."""
        # For agent step updates, we might not need token-level streaming,
        # but for final report generation, it could be used.
        # For now, we'll focus on action/observation granularity.
        pass

    async def on_llm_end(
        self, response: LLMResult, **kwargs: Any
    ) -> None:
        """Run when LLM ends running."""
        # Optional: You can send a message when LLM finishes.
        pass

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Run when chain starts running."""
        if serialized.get("lc_kwargs", {}).get("name") == "AgentExecutor":
            await self.queue.put(self._format_message("agent_start", "Starting AI Agent plan generation..."))
        # You could also put the initial input here:
        # await self.queue.put(self._format_message("input_received", inputs.get("input", "")))

    async def on_chain_end(
        self, outputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Run when chain ends running."""
        if outputs.get("output"):
            # When the entire agent chain finishes, send the final report.
            # This is the final message, so we signal completion.
            await self.queue.put(self._format_message("final_report", outputs["output"]))
            await self.queue.put(None) # Signal completion for the stream

    async def on_chain_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when chain errors."""
        await self.queue.put(self._format_message("error", f"Agent chain error: {error}"))
        await self.queue.put(None) # Signal completion for the stream

    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Run when tool starts running."""
        tool_name = serialized.get("name", "Unknown Tool")
        await self.queue.put(self._format_message("tool_start", f"Invoking {tool_name} with: {input_str}"))

    async def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """Run when tool ends running."""
        # Only send a summary of the tool's output to avoid flooding the frontend with too much data.
        # The full report will contain all details.
        await self.queue.put(self._format_message("tool_end", f"Tool output received (length {len(output)}). Agent is thinking..."))

    async def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when tool errors."""
        await self.queue.put(self._format_message("error", f"Tool error: {error}"))

    async def on_agent_action(
        self, action: AgentAction, **kwargs: Any
    ) -> Any:
        """Run on agent action."""
        # This captures the 'Thought' and 'Action' from the agent
        await self.queue.put(self._format_message("agent_action", f"Thought: {action.log}"))

    async def on_agent_finish(
        self, finish: AgentFinish, **kwargs: Any
    ) -> None:
        """Run on agent end."""
        # This is where the final answer from an intermediate step might come.
        # The final_report event from on_chain_end will handle the main output.
        pass
