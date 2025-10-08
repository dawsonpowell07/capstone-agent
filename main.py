from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Security
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from agent.graph import builder
from utils import VerifyToken

app = FastAPI()
auth = VerifyToken()

# Create a checkpointer for persistence
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)


class ChatRequest(BaseModel):
    message: str


class ResumeRequest(BaseModel):
    decision: str  # "approve" or the rejection feedback


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    messages: List[Dict[str, Any]]
    interrupt: Optional[Dict[str, Any]] = None


class StreamMessage(BaseModel):
    type: str  # "node_start", "node_end", "message", "interrupt", "error", "complete"
    data: Dict[str, Any]
    thread_id: str


def message_to_dict(msg: BaseMessage) -> Dict[str, Any]:
    """Convert LangChain message to dictionary"""
    return {
        # "human", "ai", "system", etc.
        "role": msg.type,
        "content": msg.content,
    }


def extract_interrupt_data(interrupt_list) -> Optional[Dict[str, Any]]:
    """Extract interrupt data from the list format"""
    if not interrupt_list or not isinstance(interrupt_list, list):
        return None

    # Get the first interrupt
    first_interrupt = interrupt_list[0]

    # Handle different interrupt formats
    if hasattr(first_interrupt, 'value'):
        return first_interrupt.value
    elif isinstance(first_interrupt, dict):
        return first_interrupt
    else:
        return {"data": str(first_interrupt)}


@app.post("/chat/up/{thread_id}")
async def chat_endpoint_unprotected(thread_id: str, request: ChatRequest) -> ChatResponse:
    """Send a message to a specific thread"""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        # Invoke the graph with the user message (async)
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config=config
        )

        # Check if there's an interrupt
        interrupt_data = result.get("__interrupt__")

        # Convert messages to dictionaries
        messages = [message_to_dict(msg) for msg in result.get("messages", [])]

        if interrupt_data:
            # There's a human approval needed
            return ChatResponse(
                response="Approval needed",
                thread_id=thread_id,
                messages=messages,
                interrupt=extract_interrupt_data(interrupt_data)
            )

        # Extract the last AI message
        last_message = messages[-1] if messages else {"content": "No response"}

        return ChatResponse(
            response=last_message.get("content", ""),
            thread_id=thread_id,
            messages=messages,
            interrupt=None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/{thread_id}")
async def chat_endpoint(thread_id: str, request: ChatRequest, auth_result: str = Security(auth.verify)) -> ChatResponse:
    """Send a message to a specific thread"""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        # Invoke the graph with the user message (async)
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config=config
        )

        # Check if there's an interrupt
        interrupt_data = result.get("__interrupt__")

        # Convert messages to dictionaries
        messages = [message_to_dict(msg) for msg in result.get("messages", [])]

        if interrupt_data:
            # There's a human approval needed
            return ChatResponse(
                response="Approval needed",
                thread_id=thread_id,
                messages=messages,
                interrupt=extract_interrupt_data(interrupt_data)
            )

        # Extract the last AI message
        last_message = messages[-1] if messages else {"content": "No response"}

        return ChatResponse(
            response=last_message.get("content", ""),
            thread_id=thread_id,
            messages=messages,
            interrupt=None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resume/{thread_id}")
async def resume_endpoint(thread_id: str, request: ResumeRequest) -> ChatResponse:
    """Resume a conversation after human approval/rejection"""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        # Resume with the Command (async)
        result = await graph.ainvoke(
            Command(resume=request.decision),
            config=config
        )

        # Check if there's another interrupt
        interrupt_data = result.get("__interrupt__")

        # Convert messages to dictionaries
        messages = [message_to_dict(msg) for msg in result.get("messages", [])]

        if interrupt_data:
            return ChatResponse(
                response="Approval needed",
                thread_id=thread_id,
                messages=messages,
                interrupt=extract_interrupt_data(interrupt_data)
            )

        # Extract the last AI message
        last_message = messages[-1] if messages else {"content": "No response"}

        return ChatResponse(
            response=last_message.get("content", ""),
            thread_id=thread_id,
            messages=messages,
            interrupt=None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/thread/{thread_id}")
async def get_thread_state(thread_id: str):
    """Get the current state of a thread"""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        # Get state is synchronous, but we can wrap it if needed
        state = await graph.aget_state(config)

        # Convert messages in state to dicts
        state_dict = dict(state.values)
        if "messages" in state_dict:
            state_dict["messages"] = [message_to_dict(
                msg) for msg in state_dict["messages"]]

        return {
            "thread_id": thread_id,
            "state": state_dict,
            "next_steps": state.next
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat/{thread_id}")
async def websocket_chat(websocket: WebSocket, thread_id: str):
    """WebSocket endpoint for streaming agent outputs"""
    await websocket.accept()

    try:
        while True:
            # Wait for user message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")

            if not user_message:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"error": "Message is required"},
                    "thread_id": thread_id
                }))
                continue

            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

            try:
                # Stream the graph execution
                async for chunk in graph.astream(
                    {"messages": [{"role": "user", "content": user_message}]},
                    config=config
                ):
                    # Send node start/end events
                    for node_name, node_data in chunk.items():
                        if node_name == "__interrupt__":
                            # Handle interrupt
                            interrupt_msg = StreamMessage(
                                type="interrupt",
                                data=extract_interrupt_data(node_data) or {},
                                thread_id=thread_id
                            )
                            await websocket.send_text(interrupt_msg.model_dump_json())
                            break
                        else:
                            # Send node execution update
                            stream_msg = StreamMessage(
                                type="node_update",
                                data={
                                    "node": node_name,
                                    "messages": [message_to_dict(msg) for msg in node_data.get("messages", [])],
                                    "state": {k: v for k, v in node_data.items() if k != "messages"}
                                },
                                thread_id=thread_id
                            )
                            await websocket.send_text(stream_msg.model_dump_json())

                # Send completion message if no interrupt
                final_state = await graph.aget_state(config)
                if not final_state.next:
                    complete_msg = StreamMessage(
                        type="complete",
                        data={"final_state": dict(final_state.values)},
                        thread_id=thread_id
                    )
                    await websocket.send_text(complete_msg.model_dump_json())

            except Exception as e:
                error_msg = StreamMessage(
                    type="error",
                    data={"error": str(e)},
                    thread_id=thread_id
                )
                await websocket.send_text(error_msg.model_dump_json())

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for thread {thread_id}")
    except Exception as e:
        print(f"WebSocket error for thread {thread_id}: {e}")


@app.websocket("/ws/resume/{thread_id}")
async def websocket_resume(websocket: WebSocket, thread_id: str):
    """WebSocket endpoint for resuming after interrupts"""
    await websocket.accept()

    try:
        # Wait for decision
        data = await websocket.receive_text()
        decision_data = json.loads(data)
        decision = decision_data.get("decision", "")

        if not decision:
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"error": "Decision is required"},
                "thread_id": thread_id
            }))
            return

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        try:
            # Stream the resumed execution
            async for chunk in graph.astream(
                Command(resume=decision),
                config=config
            ):
                # Send updates similar to chat endpoint
                for node_name, node_data in chunk.items():
                    if node_name == "__interrupt__":
                        interrupt_msg = StreamMessage(
                            type="interrupt",
                            data=extract_interrupt_data(node_data) or {},
                            thread_id=thread_id
                        )
                        await websocket.send_text(interrupt_msg.model_dump_json())
                        break
                    else:
                        stream_msg = StreamMessage(
                            type="node_update",
                            data={
                                "node": node_name,
                                "messages": [message_to_dict(msg) for msg in node_data.get("messages", [])],
                                "state": {k: v for k, v in node_data.items() if k != "messages"}
                            },
                            thread_id=thread_id
                        )
                        await websocket.send_text(stream_msg.model_dump_json())

            # Send completion if no more interrupts
            final_state = await graph.aget_state(config)
            if not final_state.next:
                complete_msg = StreamMessage(
                    type="complete",
                    data={"final_state": dict(final_state.values)},
                    thread_id=thread_id
                )
                await websocket.send_text(complete_msg.model_dump_json())

        except Exception as e:
            error_msg = StreamMessage(
                type="error",
                data={"error": str(e)},
                thread_id=thread_id
            )
            await websocket.send_text(error_msg.model_dump_json())

    except WebSocketDisconnect:
        print(f"Resume WebSocket disconnected for thread {thread_id}")
    except Exception as e:
        print(f"Resume WebSocket error for thread {thread_id}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
