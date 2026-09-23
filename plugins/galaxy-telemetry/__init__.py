"""
galaxy-telemetry plugin
Posts real-time skill activation, LLM routing, Honcho memory query,
and agent delegation telemetry signals to the Galaxy View server (port 8899).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)

# Primary and fallback endpoints
GALAXY_HOSTS = ("hermes-galaxy-view:8899", "172.20.0.1:8899", "127.0.0.1:8899")


def _send_telemetry(payload: dict) -> None:
    """Fire-and-forget telemetry packet dispatch across available endpoints."""
    def _dispatch():
        try:
            data = json.dumps(payload).encode("utf-8")
            for host in GALAXY_HOSTS:
                try:
                    url = f"http://{host}/api/telemetry"
                    req = urllib.request.Request(
                        url,
                        data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        if resp.status == 200:
                            return
                except Exception:
                    continue
        except Exception as e:
            logger.debug("galaxy-telemetry dispatch error: %s", e)

    t = threading.Thread(target=_dispatch, daemon=True)
    t.start()


def _send_skill_activate(skill_name: str) -> None:
    """Send skill activate signal to legacy endpoint."""
    def _dispatch():
        data = json.dumps({"skill": skill_name}).encode("utf-8")
        for host in GALAXY_HOSTS:
            try:
                url = f"http://{host}/api/activate"
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                continue

    threading.Thread(target=_dispatch, daemon=True).start()


def on_skill_lifecycle(**kwargs) -> None:
    """Fired when a skill is loaded or invoked."""
    action = kwargs.get("action", "")
    skill_name = kwargs.get("skill_name", "")
    if skill_name and action == "loaded":
        _send_skill_activate(skill_name)
        _send_telemetry({
            "action": "skill_activated",
            "from": "hermes",
            "to": "service-skills",
            "target": f"skill-{skill_name}",
            "label": f"Skill: {skill_name}",
            "detail": f"Active skill execution: {skill_name}",
            "color": "#a855f7",
            "duration_s": 15.0,
        })


def pre_api_request(**kwargs) -> None:
    """Fired right before calling LLM API (9Router)."""
    model = kwargs.get("model", "agy-combo")
    model_str = str(model)
    target_id = "model-agy-combo"
    model_lower = model_str.lower()
    if "claude" in model_lower:
        target_id = "model-agy-claude"
    elif "nemotron" in model_lower:
        target_id = "model-nemotron"
    elif "openrouter" in model_lower:
        target_id = "upstream-openrouter"
    elif "xkiro" in model_lower:
        target_id = "provider-xkiro"
    elif "combo" in model_lower or "agy" in model_lower:
        target_id = "model-agy-combo"

    _send_telemetry({
        "action": "route_llm",
        "from": "hermes",
        "to": "service-9router",
        "target": target_id,
        "label": f"9Router: {model_str}",
        "detail": f"Routing prompt to {model_str} via 9Router",
        "color": "#8b5cf6",
        "duration_s": 5.0,
    })


def post_api_request(**kwargs) -> None:
    """Fired when LLM API returns tokens/response."""
    model = kwargs.get("model", "agy-combo")
    model_str = str(model)
    target_id = "model-agy-combo"
    model_lower = model_str.lower()
    if "claude" in model_lower:
        target_id = "model-agy-claude"
    elif "nemotron" in model_lower:
        target_id = "model-nemotron"
    elif "openrouter" in model_lower:
        target_id = "upstream-openrouter"
    elif "xkiro" in model_lower:
        target_id = "provider-xkiro"

    duration = kwargs.get("api_duration", 0.0)
    _send_telemetry({
        "action": "llm_response",
        "from": target_id,
        "to": "service-9router",
        "target": "hermes",
        "label": f"Streaming {model_str}",
        "detail": f"Model tokens responded in {duration:.1f}s",
        "color": "#8b5cf6",
        "duration_s": 4.0,
    })


def pre_tool_call(**kwargs) -> None:
    """Fired when Hermes executes any tool."""
    tool_name = kwargs.get("tool_name", "")
    args = kwargs.get("args", {})

    if tool_name.startswith("honcho_"):
        # Memory query via Honcho
        _send_telemetry({
            "action": "honcho_query",
            "from": "hermes",
            "to": "service-honcho",
            "target": "dep-honcho-db",
            "label": f"Honcho: {tool_name}",
            "detail": f"Executing {tool_name} memory access",
            "color": "#10b981",
            "duration_s": 5.0,
        })
    elif tool_name == "skill_view":
        s_name = args.get("name", "skill") if isinstance(args, dict) else "skill"
        _send_telemetry({
            "action": "skill_activated",
            "from": "hermes",
            "to": "service-skills",
            "target": f"skill-{s_name}",
            "label": f"Skill: {s_name}",
            "detail": f"Loading skill {s_name}",
            "color": "#06b6d4",
            "duration_s": 5.0,
        })
    elif "notion" in tool_name.lower():
        _send_telemetry({
            "action": "mcp_query",
            "from": "hermes",
            "to": "service-mcp",
            "target": "mcp-notion",
            "label": "Notion MCP",
            "detail": f"Executing {tool_name}",
            "color": "#3b82f6",
            "duration_s": 5.0,
        })
    elif tool_name.startswith("mcp__"):
        parts = tool_name.split("__")
        mcp_svc = parts[1] if len(parts) > 1 else "gateway"
        _send_telemetry({
            "action": "mcp_query",
            "from": "hermes",
            "to": "service-mcp",
            "target": f"mcp-{mcp_svc}",
            "label": f"MCP: {mcp_svc}",
            "detail": f"Executing {tool_name}",
            "color": "#3b82f6",
            "duration_s": 5.0,
        })
    elif tool_name == "delegate_task":
        # Agent delegation
        tasks = args.get("tasks", []) if isinstance(args, dict) else []
        agent_goal = "Specialist"
        if tasks and isinstance(tasks, list) and len(tasks) > 0 and isinstance(tasks[0], dict):
            agent_goal = tasks[0].get("goal", "Specialist")[:22]
        _send_telemetry({
            "action": "agent_activated",
            "from": "hermes",
            "to": "service-agents",
            "target": "service-agents",
            "label": "Agent Task",
            "detail": f"Delegated: {agent_goal}",
            "color": "#ec4899",
            "duration_s": 6.0,
        })
    else:
        # Generic Tool / Skill execution
        skill_id = f"skill-{tool_name}"
        _send_telemetry({
            "action": "tool_exec",
            "from": "hermes",
            "to": "service-skills",
            "target": skill_id,
            "label": f"Tool: {tool_name}",
            "detail": f"Calling tool {tool_name}",
            "color": "#a855f7",
            "duration_s": 3.5,
        })
    return None


def register(ctx) -> None:
    """Register telemetry hooks with Hermes plugin manager."""
    ctx.register_hook("on_skill_lifecycle", on_skill_lifecycle)
    ctx.register_hook("pre_api_request", pre_api_request)
    ctx.register_hook("post_api_request", post_api_request)
    ctx.register_hook("pre_tool_call", pre_tool_call)
    logger.info("galaxy-telemetry registered with live routing & memory hooks")
