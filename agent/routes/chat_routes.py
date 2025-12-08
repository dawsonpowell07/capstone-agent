from fastapi import APIRouter, Security, HTTPException, Depends
from fastapi.responses import JSONResponse
from agent.graph import supervisor_agent, mongo_client
from langchain_core.messages import AIMessage
from models.models import ChatRequest
from typing import Dict, Any
from langchain_core.messages import (
    HumanMessage,
    BaseMessage,
    messages_from_dict,
)
from utils.utils import VerifyToken
from utils.user_profile import fetch_user_profile
import logging
from langgraph.checkpoint.mongodb import MongoDBSaver
from datetime import datetime

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router with common prefix and OpenAPI tags
router = APIRouter(prefix="/api/chat", tags=["Chat"])
# Auth0 JWT token verifier for protected endpoints
auth = VerifyToken()


def format_message_for_frontend(msg: BaseMessage, thread_id: str, msg_idx: int) -> Dict[str, Any]:
    # Determine message role based on LangChain message type
    role = "assistant"
    if msg.__class__.__name__ == "HumanMessage":
        role = "user"
    elif msg.__class__.__name__ == "ToolMessage":
        role = "tool"

    # Extract or generate timestamp for message ordering
    created_at = getattr(msg, "created_at", None)
    if created_at is None:
        created_at = datetime.utcnow()
    elif isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)

    # Build content array (frontend expects list of content blocks)
    content = []

    # Handle text content (can be string or list of blocks)
    if isinstance(msg.content, str) and msg.content:
        content.append({
            "type": "text",
            "text": msg.content
        })
    elif isinstance(msg.content, list):
        # Handle content that's already structured as blocks
        for block in msg.content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    content.append({
                        "type": "text",
                        "text": block.get("text", "")
                    })
            elif isinstance(block, str):
                # Plain string in list
                content.append({
                    "type": "text",
                    "text": block
                })

    # Handle tool calls (present in assistant messages when agent calls tools)
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tool_call in msg.tool_calls:
            content.append({
                "type": "tool_use",
                "tool_use": {
                    "id": tool_call.get("id", ""),
                    "name": tool_call.get("name", ""),
                    "input": tool_call.get("args", {})
                }
            })

    # Handle tool results (present in ToolMessage responses from tool executions)
    if msg.__class__.__name__ == "ToolMessage":
        content.append({
            "type": "tool_result",
            "tool_result": {
                "tool_use_id": getattr(msg, "tool_call_id", ""),
                "output": msg.content if isinstance(msg.content, str) else str(msg.content)
            }
        })

    # Return formatted message in frontend-compatible structure
    return {
        "id": f"{thread_id}_msg_{msg_idx}",
        "role": role,
        "content": content,
        "createdAt": created_at.isoformat()
    }


@router.post("/{thread_id}")
async def chat_completions(thread_id: str, request: ChatRequest):
    try:
        logger.info(
            f"Received message for thread {thread_id}: {request.content}")
        print(request)

        # Fetch user profile from CosmosDB for personalization (if userId provided)
        user_info = {}
        user_id = request.userId

        if user_id:
            user_profile = await fetch_user_profile(user_id)
            if user_profile:
                user_info = user_profile
            else:
                logger.warning(
                    f"Could not fetch user profile for user_id: {user_id}")
        else:
            logger.info("No userId provided in request body")

        # Convert simple message format to LangChain message
        user_message = HumanMessage(content=request.content)

        # Configure agent invocation with thread_id for state persistence
        config = {
            "configurable": {
                "thread_id": thread_id,  # MongoDB checkpointer uses this for persistence
            },
            "recursion_limit": 15  # Prevent infinite loops - max 15 agent steps
        }

        # Extract itinerary context for trip-specific operations
        itinerary_id = request.itineraryId

        # Invoke supervisor agent with message and runtime context
        result = await supervisor_agent.ainvoke(
            {"messages": [user_message], "user_info": user_info},
            context={"user_info": user_info, "user_id": user_id,
                     "itinerary_id": itinerary_id},
            config=config
        )

        # Extract all messages from agent execution (includes tool calls and results)
        messages = result.get("messages", [])

        # Find the last assistant message (the final response to return)
        assistant_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                assistant_message = msg
                break

        if not assistant_message:
            raise HTTPException(
                status_code=500, detail="No assistant response generated")

        # Transform LangChain message to frontend format
        formatted_message = format_message_for_frontend(
            assistant_message,
            thread_id,
            len(messages) - 1
        )

        return JSONResponse(formatted_message)

    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pc/{thread_id}")
async def protected_chat_completions(
    thread_id: str,
    request: ChatRequest,
    auth_result: str = Security(auth.verify)
):
    try:
        logger.info(
            f"Received protected message for thread {thread_id}: {request.content}")

        # Extract user ID from Auth0 token's 'sub' (subject) claim
        user_id = auth_result.get("sub") if isinstance(
            auth_result, dict) else None

        # Fetch user profile from CosmosDB for personalization
        user_info = {}
        if user_id:
            user_profile = await fetch_user_profile(user_id)
            if user_profile:
                user_info = user_profile
            else:
                logger.warning(
                    f"Could not fetch user profile for user_id: {user_id}")
        else:
            logger.warning("No user ID found in Auth0 token")

        # Create HumanMessage from the simple request
        user_message = HumanMessage(content=request.content)

        # Invoke the graph with the new message and user info
        config = {
            "configurable": {
                "thread_id": thread_id
            },
            "recursion_limit": 15
        }

        itinerary_id = request.itineraryId

        result = await supervisor_agent.ainvoke(
            {"messages": [user_message], "user_info": user_info},
            context={"user_info": user_info, "user_id": user_id,
                     "itinerary_id": itinerary_id},
            config=config
        )

        # Get all messages from the result
        messages = result.get("messages", [])

        # Find the last assistant message (the response)
        assistant_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                assistant_message = msg
                break

        if not assistant_message:
            raise HTTPException(
                status_code=500, detail="No assistant response generated")

        # Format the response message
        formatted_message = format_message_for_frontend(
            assistant_message,
            thread_id,
            len(messages) - 1
        )

        return JSONResponse(formatted_message)

    except Exception as e:
        logger.error(f"Error in protected chat completion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def get_checkpointer():
    return MongoDBSaver(mongo_client, db_name="agent-database-v2")


@router.get("/pc/threads/{thread_id}/messages")
async def get_thread_messages_protected(
    thread_id: str,
    checkpointer: MongoDBSaver = Depends(get_checkpointer),
    auth_result: str = Security(auth.verify)
) -> Dict[str, Any]:
    try:
        # Build config for checkpoint lookup
        config = {"configurable": {"thread_id": thread_id}}

        # Retrieve all checkpoints for this thread (ordered by timestamp, newest first)
        checkpoints = list(checkpointer.list(config))

        if not checkpoints:
            # No conversation history found
            return {"messages": []}

        # Get the latest checkpoint which contains full message history
        latest_checkpoint = checkpoints[0]

        # Extract messages from the checkpoint's channel values
        raw_messages = latest_checkpoint.checkpoint.get(
            "channel_values", {}).get("messages", [])

        # Messages are already LangChain BaseMessage objects
        messages = raw_messages

        # Transform each message to frontend format
        formatted_messages = []
        for idx, msg in enumerate(messages):
            # Skip system messages (internal prompts, not shown to users)
            if msg.__class__.__name__ == "SystemMessage":
                continue

            formatted_msg = format_message_for_frontend(msg, thread_id, idx)
            formatted_messages.append(formatted_msg)

        return {
            "thread_id": thread_id,
            "messages": formatted_messages
        }

    except Exception as e:
        logger.error(
            f"Error fetching messages for thread {thread_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching messages: {str(e)}")


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(
    thread_id: str,
    checkpointer: MongoDBSaver = Depends(get_checkpointer)
) -> Dict[str, Any]:
    try:
        # Build config for checkpoint lookup
        config = {"configurable": {"thread_id": thread_id}}

        # Retrieve all checkpoints for this thread (ordered by timestamp, newest first)
        checkpoints = list(checkpointer.list(config))

        if not checkpoints:
            # No conversation history found
            return {"messages": []}

        # Get the latest checkpoint which contains full message history
        latest_checkpoint = checkpoints[0]

        # Extract messages from the checkpoint's channel values
        raw_messages = latest_checkpoint.checkpoint.get(
            "channel_values", {}).get("messages", [])

        # Messages are already LangChain BaseMessage objects
        messages = raw_messages

        # Transform each message to frontend format
        formatted_messages = []
        for idx, msg in enumerate(messages):
            # Skip system messages (internal prompts, not shown to users)
            if msg.__class__.__name__ == "SystemMessage":
                continue

            formatted_msg = format_message_for_frontend(msg, thread_id, idx)
            formatted_messages.append(formatted_msg)

        return {
            "thread_id": thread_id,
            "messages": formatted_messages
        }

    except Exception as e:
        logger.error(
            f"Error fetching messages for thread {thread_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching messages: {str(e)}")
