import logging
import os
import sys
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from commons.constants import OPENAI_API_KEY, OPENAI_TERRA_MODEL
from t13_final_task.task.agent.clients.http_mcp_client import HttpMcpClient
from t13_final_task.task.agent.clients.stdio_mcp_client import StdioMcpClient
from t13_final_task.task.agent.conversation_manager import ConversationManager
from t13_final_task.task.agent.tools.base import BaseTool
from t13_final_task.task.agent.tools.mcp_tool import McpTool
from t13_final_task.task.agent.tools.read_skill_tool import ReadSkillTool
from t13_final_task.task.agent.ums_agent import UMSAgent
from t13_final_task.task.agent.models import SkillMetadata, load_skills, Message

SKILLS_DIR = Path(__file__).parent.parent / "_skills"

UMS_MCP_URL = os.getenv("UMS_MCP_URL", "http://localhost:8005/mcp")
DDG_DOCKER_IMAGE = "khshanovskyi/ddg-mcp-server:latest"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


def _build_available_skills_xml(skills: list[SkillMetadata]) -> str:
    root = ET.Element("available_skills")
    for skill in skills:
        el = ET.SubElement(root, "skill", attrib={"name": skill.name})
        ET.SubElement(el, "description").text = skill.description
        if skill.license:
            ET.SubElement(el, "license").text = skill.license
        if skill.compatibility:
            ET.SubElement(el, "compatibility").text = skill.compatibility
        if skill.metadata:
            meta = ET.SubElement(el, "metadata")
            for k, v in skill.metadata.items():
                ET.SubElement(meta, k).text = str(v)
        if skill.allowed_tools:
            ET.SubElement(el, "allowed-tools").text = " ".join(skill.allowed_tools)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode")


def build_system_prompt(skills: list[SkillMetadata]) -> str:
    return f"""\
You are an AI assistant with access to agent skills.

{_build_available_skills_xml(skills)}

## How to use skills

When the user's request matches a skill, activate it:
1. Call `read_skill` with the skill's SKILL.md path (e.g. path="/<skill-name>/SKILL.md") to load
   its full instructions.
2. Follow the instructions in the loaded SKILL.md precisely.

Always read the relevant SKILL.md before performing the task.\
"""

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

conversation_manager: Optional[ConversationManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP clients, Redis, and ConversationManager on startup"""
    global conversation_manager

    skills = load_skills(SKILLS_DIR)
    if not skills:
        raise RuntimeError(f"No valid skills found in {SKILLS_DIR}")
    logger.info("Loaded skills: %s", [skill.name for skill in skills])
    system_prompt = build_system_prompt(skills)

    tools: list[BaseTool] = [ReadSkillTool(skills_dir=SKILLS_DIR)]

    ums_mcp_client = await HttpMcpClient.create(UMS_MCP_URL)
    for mcp_tool_model in await ums_mcp_client.get_tools():
        tools.append(McpTool(client=ums_mcp_client, mcp_tool_model=mcp_tool_model))

    ddg_mcp_client = await StdioMcpClient.create(DDG_DOCKER_IMAGE)
    for mcp_tool_model in await ddg_mcp_client.get_tools():
        tools.append(McpTool(client=ddg_mcp_client, mcp_tool_model=mcp_tool_model))

    logger.info("Agent tools: %s", [tool.name for tool in tools])

    ums_agent = UMSAgent(
        api_key=OPENAI_API_KEY,
        model=OPENAI_TERRA_MODEL,
        tools=tools,
    )

    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    await redis_client.ping()
    logger.info("Connected to Redis at %s:%s", REDIS_HOST, REDIS_PORT)

    conversation_manager = ConversationManager(
        ums_agent=ums_agent,
        redis_client=redis_client,
        system_prompt=system_prompt,
    )

    yield

    await redis_client.aclose()
    logger.info("Redis connection closed")


app = FastAPI(
    title="UMS Agent",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatRequest(BaseModel):
    message: Message
    stream: bool = True


class ChatResponse(BaseModel):
    content: str
    conversation_id: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class CreateConversationRequest(BaseModel):
    title: str = None


# Endpoints
@app.get("/health")
async def health():
    """Health check endpoint"""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "conversation_manager_initialized": conversation_manager is not None
    }

@app.post("/conversations")
async def create_conversation(request: CreateConversationRequest = None):
    """Create a new conversation"""
    title = (request.title if request and request.title else None) or "New Conversation"
    return await conversation_manager.create_conversation(title)


@app.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations():
    """List all conversations sorted by last update time"""
    return await conversation_manager.list_conversations()


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get the full conversation with its messages"""
    conversation = await conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    deleted = await conversation_manager.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": f"Conversation {conversation_id} deleted successfully"}


@app.post("/conversations/{conversation_id}/chat")
async def chat(conversation_id: str, request: ChatRequest):
    """Process a chat message, streaming (SSE) or not"""
    try:
        result = await conversation_manager.chat(
            user_message=request.message,
            conversation_id=conversation_id,
            stream=request.stream,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if request.stream:
        return StreamingResponse(result, media_type="text/event-stream")
    return ChatResponse(**result)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8011,
        log_level="debug",
    )