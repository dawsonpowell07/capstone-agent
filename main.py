from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from agent.graph import builder

app = FastAPI()

# Create a checkpointer for persistence
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[dict]] = None
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    thread_id: str
    messages: List[Dict[str, Any]]
    interrupt: Optional[Dict[str, Any]] = None

def message_to_dict(msg: BaseMessage) -> Dict[str, Any]:
    """Convert LangChain message to dictionary"""
    return {
        "role": msg.type,  # "human", "ai", "system", etc.
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
    
@app.post("/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    
    # Generate or use provided thread_id
    thread_id = request.thread_id or str(uuid.uuid4())
    chat_history = request.chat_history or []
    message = request.message
    # Create config with proper typing
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    
    try:
        
        chat_history.append(HumanMessage(content=message))
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


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" or the rejection feedback
    
@app.post("/resume")
async def resume_endpoint(request: ResumeRequest) -> ChatResponse:
    """Resume a conversation after human approval/rejection"""
    
    config: RunnableConfig = {"configurable": {"thread_id": request.thread_id}}
    
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
                thread_id=request.thread_id,
                messages=messages,
                interrupt=extract_interrupt_data(interrupt_data)
            )
        
        # Extract the last AI message
        last_message = messages[-1] if messages else {"content": "No response"}
        
        return ChatResponse(
            response=last_message.get("content", ""),
            thread_id=request.thread_id,
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
            state_dict["messages"] = [message_to_dict(msg) for msg in state_dict["messages"]]
        
        return {
            "thread_id": thread_id,
            "state": state_dict,
            "next_steps": state.next
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)