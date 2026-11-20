"""cloud_brain.py — Centralized Shin AI Brain Service for Cloud Deployment.
Runs headless in Linux Docker on Railway, Render, Fly.io, or any VPS:
  • Decouples AI routing, NLP, memory, and multi-turn state from local hardware
  • Secure WebSocket & REST API for thin local Windows desktop and mobile clients
  • Authenticated via Bearer token (SHIN_API_KEY)
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Path bootstrapping for cross-platform imports
_SERVER_DIR = Path(__file__).resolve().parent
_SHIN_DIR = _SERVER_DIR.parent
_PROJECT_ROOT = _SHIN_DIR.parent
_CORE_DIR = _SHIN_DIR / "core"

for _p in (str(_PROJECT_ROOT), str(_SHIN_DIR), str(_CORE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Security, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Core AI modules
import nlp as _nlp
from llm_router import get_router, get_status_info
from conversation_flow import ConversationFlowManager
from timemap import TimemapManager

logger = logging.getLogger("shin.cloud_brain")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Security
_API_KEY = os.getenv("SHIN_API_KEY", "").strip()
_security = HTTPBearer(auto_error=False)

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(_security)) -> bool:
    """Validate Bearer authentication token if configured."""
    if not _API_KEY:
        # Development mode without explicit key
        return True
    if not credentials or credentials.credentials != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Shin API authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True

# ── Local Action Intents ──────────────────────────────────────────────────────
# Intents that require physical execution on the local user's Windows machine
LOCAL_HARDWARE_INTENTS = {
    "open_app", "close_app", "kill_app",
    "volume_up", "volume_down", "set_volume", "mute_volume", "unmute_volume",
    "brightness_up", "brightness_down", "set_brightness",
    "screenshot", "run_terminal_command", "run_python_code",
    "scroll", "press_key", "click_text", "type_text",
    "window_minimize", "window_maximize", "window_minimize_all",
    "window_snap_left", "window_snap_right", "window_snap_quadrant",
    "open_folder", "open_file", "list_files", "find_files", "search_files", "search_pc",
    "read_clipboard", "copy_to_clipboard", "clipboard_search",
    "mate_dance", "mate_minimize", "mate_restore",
    "sleep_shutdown", "restart_pc", "lock_pc",
}

app = FastAPI(
    title="Shin Cloud Brain API",
    description="Decoupled AI Brain Service for Shin Voice Assistant",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_START_TIME = time.time()

class ChatRequest(BaseModel):
    text: str = Field(..., description="Spoken utterance or user query")
    client_id: str = Field("desktop-client", description="Client identifier")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Local machine telemetry")

class ChatResponse(BaseModel):
    state: str
    spoken_text: str
    intent: str
    args: Dict[str, Any]
    is_local_action: bool
    dynamic_island: Dict[str, Any]
    mate_state: str
    timestamp: float

@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Report Cloud Brain status and active configurations."""
    status_dict = get_status_info()
    return {
        "status": "healthy",
        "service": "Shin Cloud Brain",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "llm_router": status_dict,
        "auth_required": bool(_API_KEY),
    }

@app.post("/api/chat", response_model=ChatResponse)
def handle_chat_turn(req: ChatRequest, authorized: bool = Depends(verify_token)) -> ChatResponse:
    """Analyze utterance, classify intent, run conversational LLM or formulate local action."""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    logger.info("Processing turn from client '%s': %r", req.client_id, text)

    # 1. Intent classification via NLP engine
    intent_res = _nlp.parse_intent(text)
    intent_name = intent_res.get("intent", "chat")
    args = intent_res.get("args", {})
    confidence = intent_res.get("_confidence", 0.7)

    is_local_action = intent_name in LOCAL_HARDWARE_INTENTS
    convo_flow = ConversationFlowManager.get()

    spoken_text = ""
    mate_state = "speaking"

    if is_local_action:
        # For local hardware commands, provide prompt confirmation for speech
        # while delegating execution to the local client
        if intent_name == "open_app":
            target_app = args.get("app") or args.get("app_name", "application")
            spoken_text = f"Opening {target_app}, MJ!"
        elif intent_name == "run_terminal_command":
            spoken_text = "Running command on your desktop, MJ."
        elif intent_name in ("volume_up", "volume_down", "set_volume"):
            spoken_text = "Adjusting volume now, MJ."
        elif intent_name == "screenshot":
            spoken_text = "Taking screenshot on your screen, MJ!"
        elif intent_name == "mate_dance":
            spoken_text = "Let's dance, MJ! 🎵"
            mate_state = "dance"
        else:
            spoken_text = f"Executing {intent_name.replace('_', ' ')} on your PC, MJ!"
    elif intent_name == "chat":
        # Conversational LLM reply via Shin's Dual-mode Router
        if "response" in args and args["response"]:
            spoken_text = args["response"]
        else:
            router = get_router()
            system_prompt = convo_flow.build_system_prompt()
            messages = [{"role": "user", "content": text}]
            llm_res = router.query(messages, system_prompt=system_prompt, max_tokens=150)
            spoken_text = llm_res.get("content", "Arey MJ! I am here.")
    else:
        # Other computational intents (e.g., weather, time, jokes)
        spoken_text = args.get("response", f"Done, MJ! Checked {intent_name}.")

    # Dynamic Island payload
    island_body = spoken_text[:110] + "..." if len(spoken_text) > 110 else spoken_text
    dynamic_island = {
        "title": "🤖 Shin",
        "body": island_body,
        "duration": 4.5,
    }

    # Record turn in conversation flow memory
    try:
        convo_flow.record_turn(text, spoken_text)
    except Exception as exc:
        logger.debug("Failed recording turn in conversation flow: %s", exc)

    return ChatResponse(
        state="speaking",
        spoken_text=spoken_text,
        intent=intent_name,
        args=args,
        is_local_action=is_local_action,
        dynamic_island=dynamic_island,
        mate_state=mate_state,
        timestamp=time.time(),
    )

@app.websocket("/ws/shin")
async def websocket_shin_stream(websocket: WebSocket):
    """Bidirectional streaming session for local clients."""
    await websocket.accept()
    token = websocket.query_params.get("token", "")
    if _API_KEY and token != _API_KEY:
        await websocket.send_json({"type": "error", "message": "Unauthorized: invalid token"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    logger.info("Client connected to Shin WebSocket stream.")
    await websocket.send_json({
        "type": "welcome",
        "message": "Connected to Shin Cloud Brain",
        "timestamp": time.time(),
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "user_utterance")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
                continue

            if msg_type == "user_utterance":
                text = data.get("text", "").strip()
                if not text:
                    continue

                # Notify thinking state
                await websocket.send_json({
                    "type": "state_change",
                    "state": "processing",
                    "mate_state": "thinking",
                    "dynamic_island": {"title": "🤖 Shin", "body": "💭 Thinking... ✦", "duration": 3.0},
                })

                # Compute chat response
                req = ChatRequest(text=text, client_id=data.get("client_id", "ws-client"), context=data.get("context", {}))
                resp = handle_chat_turn(req, authorized=True)

                await websocket.send_json({
                    "type": "brain_response",
                    "data": resp.model_dump(),
                })
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket.")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
