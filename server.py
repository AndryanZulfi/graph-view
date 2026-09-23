import json
import os
import random
import re
import time
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get('PORT', 8899))
# Base dir: use script directory or /app
BASE_DIR = os.environ.get('BASE_DIR', os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.environ.get('SKILLS_DIR', '/opt/data/skills' if os.path.exists('/opt/data/skills') else '/skills')
ACTIVE_EVENT_FILE = os.path.join(BASE_DIR, 'active_skill.json')
USAGE_JSON = '/opt/data/skills/.usage.json'   # updated by bump_use on every skill load
DEACTIVATE_DELAY = 15   # seconds after last use before deactivating

# Active skills tracked by usage-watcher
_usage_active: dict = {}   # skill_name -> last_used_at string
_usage_lock = threading.Lock()

# Active real-time transmissions (Hermes <-> 9Router, Honcho, Skills, Agents)
_active_transmissions: dict = {} # id -> transmission dict
_trans_lock = threading.Lock()

category_colors = {
    'core': '#38bdf8',         # Sky cyan (Hermes Core)
    'router': '#8b5cf6',       # Violet (9Router & Models)
    'memory': '#10b981',       # Emerald (Honcho & Storage)
    'mcp': '#3b82f6',          # Sapphire Blue (MCP Tools)
    'channel': '#f59e0b',      # Amber (WhatsApp, Telegram, Web UI)
    'monitoring': '#f43f5e',   # Rose (Prometheus, Grafana, cAdvisor)
    'network': '#06b6d4',      # Cyan (Tailscale, ai-network)
    'skills': '#a855f7',       # Purple (Hermes Skills)
    'agents': '#ec4899',       # Pink (Agency Specialists)
    'software-development': '#38bdf8',  # Sky / Slate Blue
    'productivity': '#34d399',          # Emerald / Sage
    'creative': '#fbbf24',              # Warm Amber
    'autonomous-ai-agents': '#818cf8',  # Indigo Slate
    'research': '#a78bfa',              # Iris Slate
    'apple': '#94a3b8',                 # Cool Platinum
    'media': '#fb923c',                 # Terracotta
    'email': '#2dd4bf',                 # Muted Teal
    'devops': '#60a5fa',                # Technical Blue
    'note-taking': '#10b981',           # Jade
    'social-media': '#cbd5e1',          # Silver
    'web': '#0ea5e9',                   # Deep Sky
    'agency-orchestration': '#f59e0b',  # Amber Gold
    'agency-engineering': '#38bdf8',    # Sky Blue
    'agency-qa-security': '#f43f5e',    # Rose Crimson
    'agency-product-design': '#ec4899', # Magenta Pink
    'agency-growth': '#10b981',         # Emerald Green
    'agency-domain': '#a78bfa'          # Iris Slate
}

# Subscribed SSE clients
clients = []
clients_lock = threading.Lock()

def discover_subskills(skill_root, skill_name, cat, max_subs=8):
    """Auto-detect subskills/sub-modules underneath any skill directory."""
    subs = []
    seen = set()
    
    # 1. Knowledge modules (highest priority: domain frameworks)
    kdir = os.path.join(skill_root, 'knowledge')
    if os.path.isdir(kdir):
        for f in sorted(os.listdir(kdir)):
            if f.endswith('.md') and not f.startswith('.'):
                slug = f[:-3]
                title = slug.replace('-', ' ').title()
                desc = f'{skill_name} domain: {title}'
                try:
                    with open(os.path.join(kdir, f), 'r', encoding='utf-8', errors='ignore') as fp:
                        for line in fp:
                            line = line.strip()
                            if line.startswith('#'):
                                raw = line.lstrip('#').strip()
                                if raw and len(raw) <= 28 and '—' not in raw and '(' not in raw:
                                    title = raw
                                break
                except Exception:
                    pass
                subs.append({
                    'id': f'{skill_name}-{slug}',
                    'label': title,
                    'type': 'subskill',
                    'category': cat,
                    'parent': skill_name,
                    'desc': desc
                })
                seen.add(slug)
                if len(subs) >= max_subs:
                    return subs

    # 1b. Governance Protocols (e.g. Vibe protocols)
    pdir = os.path.join(skill_root, 'protocols')
    if os.path.isdir(pdir) and len(subs) < max_subs:
        for f in sorted(os.listdir(pdir)):
            if f.endswith('.md') and not f.startswith('.'):
                slug = f[:-3]
                if slug in seen: continue
                title = slug.replace('-', ' ').title()
                desc = f'{skill_name} protocol: {title}'
                try:
                    with open(os.path.join(pdir, f), 'r', encoding='utf-8', errors='ignore') as fp:
                        for line in fp:
                            line = line.strip()
                            if line.startswith('#'):
                                raw = line.lstrip('#').strip()
                                if raw and len(raw) <= 28 and '—' not in raw and '(' not in raw:
                                    title = raw
                                break
                except Exception:
                    pass
                subs.append({
                    'id': f'{skill_name}-{slug}',
                    'label': title,
                    'type': 'subskill',
                    'category': cat,
                    'parent': skill_name,
                    'desc': desc
                })
                seen.add(slug)
                if len(subs) >= max_subs:
                    return subs

    # 2. Reference guides & documentation
    rdir = os.path.join(skill_root, 'references')
    if os.path.isdir(rdir) and len(subs) < max_subs:
        for f in sorted(os.listdir(rdir)):
            if f.endswith('.md') and not f.startswith('.'):
                slug = f[:-3]
                if slug in seen: continue
                title = slug.replace('-', ' ').title()
                desc = f'{skill_name} reference: {title}'
                try:
                    with open(os.path.join(rdir, f), 'r', encoding='utf-8', errors='ignore') as fp:
                        for line in fp:
                            line = line.strip()
                            if line.startswith('#'):
                                raw = line.lstrip('#').strip()
                                if raw and len(raw) <= 28 and '—' not in raw and '(' not in raw:
                                    title = raw
                                break
                except Exception:
                    pass
                subs.append({
                    'id': f'{skill_name}-{slug}',
                    'label': title,
                    'type': 'subskill',
                    'category': cat,
                    'parent': skill_name,
                    'desc': desc
                })
                seen.add(slug)
                if len(subs) >= max_subs:
                    return subs

    # 3. Executable tool scripts / CLI clients
    sdir = os.path.join(skill_root, 'scripts')
    if os.path.isdir(sdir) and len(subs) < max_subs:
        for f in sorted(os.listdir(sdir)):
            if f.endswith(('.py', '.sh', '.js')) and not f.startswith(('_', '.')):
                raw_slug = f.rsplit('.', 1)[0]
                if raw_slug in seen or raw_slug in ('setup', 'test', '__init__', 'conftest'): continue
                slug = raw_slug.replace('_', '-')
                title = raw_slug.replace('_', ' ').replace('-', ' ').title()
                subs.append({
                    'id': f'{skill_name}-{slug}',
                    'label': title,
                    'type': 'subskill',
                    'category': cat,
                    'parent': skill_name,
                    'desc': f'{skill_name} tool script: {f}'
                })
                seen.add(raw_slug)
                if len(subs) >= max_subs:
                    return subs

    # 4. Templates (if no other subskills found)
    if not subs:
        tdir = os.path.join(skill_root, 'templates')
        if os.path.isdir(tdir):
            for f in sorted(os.listdir(tdir)):
                if f.endswith('.md') and not f.startswith('.'):
                    slug = f[:-3]
                    title = slug.replace('-', ' ').title()
                    subs.append({
                        'id': f'{skill_name}-{slug}',
                        'label': title,
                        'type': 'subskill',
                        'category': cat,
                        'parent': skill_name,
                        'desc': f'{skill_name} template: {title}'
                    })
                    seen.add(slug)
                    if len(subs) >= max_subs:
                        return subs

    return subs

def get_skills_graph():
    """
    Returns the real, verified architecture and topology of the Hermes AI ecosystem.
    Includes Core, Services (9Router, Honcho), Capabilities (Skills, Agents),
    and their dependencies (Models, Storage/Memory, Individual Skills & Specialist Agents).
    """
    nodes = [
        # 1. ROOT / CORE
        {
            'id': 'hermes',
            'label': 'HERMES',
            'sublabel': 'AI CORE',
            'type': 'core',
            'tier': 'core',
            'category': 'core',
            'group': 'core',
            'role': 'Autonomous AI Engine & Core Brain',
            'status': 'online',
            'ports': '8642, 9119',
            'container': 'hermes',
            'network': 'ai-network',
            'desc': 'Nous Research Hermes Agent runtime with autonomous tool execution, persistent session management, and multi-platform gateway.',
            'in_hermes_subgraph': True,
            'initX': 0, 'initY': 0
        },

        # 2. CAPABILITIES (Directly under Hermes)
        {
            'id': 'service-skills',
            'label': 'Skills',
            'sublabel': 'CAPABILITY',
            'type': 'capability',
            'tier': 'capability',
            'category': 'skills',
            'group': 'skills',
            'role': 'Hermes Skills Hub',
            'status': 'online',
            'path': '/opt/data/skills',
            'desc': 'Modular capability ecosystem empowering Hermes with specialized engineering, devops, productivity, and agentic workflows.',
            'in_hermes_subgraph': True,
            'initX': 180, 'initY': -160
        },
        {
            'id': 'service-agents',
            'label': 'Agents',
            'sublabel': 'CAPABILITY',
            'type': 'capability',
            'tier': 'capability',
            'category': 'agents',
            'group': 'agents',
            'role': 'Specialist Agent Personas',
            'status': 'online',
            'path': '/opt/data/skills/.agents.json',
            'desc': 'Curated roster of domain specialist agent personas routed by division (engineering, security, testing, academic, sales, etc.).',
            'in_hermes_subgraph': True,
            'initX': 180, 'initY': 160
        },

        # 3. PRIMARY SERVICES
        {
            'id': 'service-9router',
            'label': '9Router',
            'sublabel': 'LLM GATEWAY',
            'type': 'service',
            'tier': 'service',
            'category': 'router',
            'group': 'router',
            'role': 'LLM Reverse Proxy & Model Router',
            'status': 'online',
            'ports': '20128',
            'container': '9router',
            'network': 'ai-network',
            'desc': 'High-performance LLM gateway and reverse proxy distributing inference calls to local routes and upstream providers.',
            'in_hermes_subgraph': True,
            'initX': -220, 'initY': -160
        },
        {
            'id': 'service-honcho',
            'label': 'Honcho',
            'sublabel': 'MEMORY ENGINE',
            'type': 'service',
            'tier': 'service',
            'category': 'memory',
            'group': 'memory',
            'role': 'Dialectic Persistent Memory Layer',
            'status': 'online',
            'ports': '8000, 8443',
            'container': 'honcho-api',
            'network': 'ai-network',
            'desc': 'Plastic Labs Honcho dialectic memory engine providing peer cards, context summaries, semantic search, and conclusions.',
            'in_hermes_subgraph': True,
            'initX': -220, 'initY': 160
        },

        # 4. FULL GRAPH SERVICES (Visible in Full Graph mode)
        {
            'id': 'service-mcp',
            'label': 'MCP GATEWAY',
            'sublabel': 'TOOL PROTOCOL',
            'type': 'service',
            'tier': 'service',
            'category': 'mcp',
            'group': 'mcp',
            'role': 'Model Context Protocol Client',
            'status': 'online',
            'ports': 'stdio / ipc',
            'container': 'hermes (mcp)',
            'desc': 'Standardized tool interface executing tools across Docker containers, GitHub repos, Notion workspaces, and Postgres DB.',
            'in_hermes_subgraph': True,
            'initX': 0, 'initY': -280
        },
        {
            'id': 'service-clients',
            'label': 'CLIENT CHANNELS',
            'sublabel': 'INTERACTION HUB',
            'type': 'service',
            'tier': 'service',
            'category': 'channel',
            'group': 'channel',
            'role': 'Multi-Channel Ingress & Egress',
            'status': 'online',
            'ports': '8642',
            'container': 'hermes',
            'desc': 'Bidirectional messaging gateway handling WhatsApp conversations, Telegram interactions, and Web Dashboard sessions.',
            'in_hermes_subgraph': False,
            'initX': 330, 'initY': 0
        },
        {
            'id': 'service-monitoring',
            'label': 'OBSERVABILITY',
            'sublabel': 'TELEMETRY STACK',
            'type': 'service',
            'tier': 'service',
            'category': 'monitoring',
            'group': 'monitoring',
            'role': 'Metrics & System Telemetry',
            'status': 'online',
            'ports': '9090, 3001',
            'container': 'prometheus / grafana',
            'network': 'monitoring',
            'desc': 'Prometheus time-series metric collector and Grafana visualization dashboard monitoring container health and resource usage.',
            'in_hermes_subgraph': False,
            'initX': -330, 'initY': 0
        },
        {
            'id': 'service-tailscale',
            'label': 'TAILSCALE EDGE',
            'sublabel': 'SECURE INGRESS',
            'type': 'gateway',
            'tier': 'service',
            'category': 'network',
            'group': 'network',
            'role': 'Encrypted Mesh & SSL Proxy',
            'status': 'online',
            'ports': '443, 8443, 8444',
            'desc': 'WireGuard-based encrypted mesh network (deb-zlf.tail38902e.ts.net) providing zero-trust public HTTPS endpoints.',
            'in_hermes_subgraph': False,
            'initX': 0, 'initY': 280
        },

        # 5. 9ROUTER MODELS & PROVIDERS (Dependencies)
        {
            'id': 'model-agy-combo',
            'label': 'agy-combo',
            'sublabel': 'DEFAULT MODEL',
            'type': 'model',
            'tier': 'dependency',
            'category': 'router',
            'group': 'router',
            'role': 'Primary Reasoning Model',
            'status': 'active',
            'provider': '9router / OpenRouter',
            'desc': 'Default high-intelligence reasoning model configured in config.yaml for primary chat, code generation, and decision making.',
            'in_hermes_subgraph': True,
            'initX': -380, 'initY': -220
        },
        {
            'id': 'model-agy-claude',
            'label': 'agy-claude',
            'sublabel': 'CLAUDE 3.5 SONNET',
            'type': 'model',
            'tier': 'dependency',
            'category': 'router',
            'group': 'router',
            'role': 'Claude 3.5 Sonnet Route',
            'status': 'configured',
            'provider': '9router / Anthropic',
            'desc': 'Specialized Claude 3.5 Sonnet endpoint for nuanced software architecture, tool execution, and vision tasks.',
            'in_hermes_subgraph': True,
            'initX': -330, 'initY': -280
        },
        {
            'id': 'model-nemotron',
            'label': 'nemotron-3-ultra',
            'sublabel': '550B FREE WEIGHTS',
            'type': 'model',
            'tier': 'dependency',
            'category': 'router',
            'group': 'router',
            'role': 'High-Param Open Weights',
            'status': 'configured',
            'provider': 'Nvidia Nemotron',
            'desc': 'Nvidia Nemotron 550B free-tier discovery model configured for high-volume background tasks and text analysis.',
            'in_hermes_subgraph': True,
            'initX': -240, 'initY': -290
        },
        {
            'id': 'provider-xkiro',
            'label': 'xkiro',
            'sublabel': 'OPENAI-COMPATIBLE API',
            'type': 'provider',
            'tier': 'dependency',
            'category': 'router',
            'group': 'router',
            'role': 'Custom OpenAI-Compatible API',
            'status': 'configured',
            'endpoint': 'https://api.xkiro.com/v1',
            'desc': 'Dedicated external inference endpoint configured under providers.xkiro in config.yaml.',
            'in_hermes_subgraph': True,
            'initX': -410, 'initY': -140
        },
        {
            'id': 'upstream-openrouter',
            'label': 'OpenRouter',
            'sublabel': 'CLOUD GATEWAY',
            'type': 'provider',
            'tier': 'dependency',
            'category': 'router',
            'group': 'router',
            'role': 'Upstream Global Provider',
            'status': 'connected',
            'endpoint': 'openrouter.ai',
            'desc': 'Multi-model cloud aggregator backing 9router routes with automated fallback and rate-limit buffering.',
            'in_hermes_subgraph': True,
            'initX': -430, 'initY': -70
        },

        # 6. HONCHO MEMORY & DATABASE (Dependencies)
        {
            'id': 'db-postgres',
            'label': 'PostgreSQL 15',
            'sublabel': 'VECTOR DB: 5432',
            'type': 'database',
            'tier': 'dependency',
            'category': 'memory',
            'group': 'memory',
            'role': 'pgvector & Relational Storage',
            'status': 'healthy',
            'ports': '5432',
            'container': 'honcho-database',
            'desc': 'PostgreSQL database container with pgvector extension storing high-dimensional semantic message embeddings and user entities.',
            'in_hermes_subgraph': True,
            'initX': -380, 'initY': 170
        },
        {
            'id': 'cache-redis',
            'label': 'Redis 8.2',
            'sublabel': 'CACHE: 6379',
            'type': 'database',
            'tier': 'dependency',
            'category': 'memory',
            'group': 'memory',
            'role': 'In-Memory State & Pub/Sub',
            'status': 'healthy',
            'ports': '6379',
            'container': 'honcho-redis',
            'desc': 'Redis 8.2 container providing sub-millisecond session state caching, distributed locks, and pub/sub messaging.',
            'in_hermes_subgraph': True,
            'initX': -370, 'initY': 250
        },
        {
            'id': 'svc-deriver',
            'label': 'Honcho Deriver',
            'sublabel': 'BACKGROUND WORKER',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'memory',
            'group': 'memory',
            'role': 'Dialectic Reasoning Worker',
            'status': 'online',
            'container': 'honcho-deriver',
            'desc': 'Asynchronous Python worker that observes message exchanges and derives persistent user profile conclusions and cards.',
            'in_hermes_subgraph': True,
            'initX': -310, 'initY': 290
        },
        {
            'id': 'svc-honcho-mcp',
            'label': 'Honcho MCP',
            'sublabel': 'MCP ADAPTER: 3000',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'memory',
            'group': 'memory',
            'role': 'Memory Protocol Adapter',
            'status': 'healthy',
            'ports': '3000',
            'container': 'honcho-mcp',
            'desc': 'Model Context Protocol server built with Bun, exposing Honcho profile retrieval and context tools to the agent.',
            'in_hermes_subgraph': True,
            'initX': -220, 'initY': 290
        },
        {
            'id': 'storage-memories',
            'label': 'MEMORY.md / USER.md',
            'sublabel': 'DURABLE FLATFILES',
            'type': 'storage',
            'tier': 'dependency',
            'category': 'memory',
            'group': 'memory',
            'role': 'Local Fast-Context Sync',
            'status': 'synced',
            'path': '/opt/data/memories/',
            'desc': 'Zero-latency durable markdown files injected into the beginning of every prompt turn for instant recall.',
            'in_hermes_subgraph': True,
            'initX': -140, 'initY': 250
        },

        # 7. MCP GATEWAY SERVERS (Full Graph)
        {
            'id': 'mcp-docker',
            'label': 'Docker MCP',
            'sublabel': 'CONTAINER OPS',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'mcp',
            'group': 'mcp',
            'role': 'Docker Daemon Controller',
            'status': 'enabled',
            'package': '@hypnosis/docker-mcp-server',
            'desc': 'Provides programmatic tools for inspecting containers, reading container logs, and restarting services via Docker socket.',
            'in_hermes_subgraph': False,
            'initX': -80, 'initY': -370
        },
        {
            'id': 'mcp-github',
            'label': 'GitHub MCP',
            'sublabel': 'REPO & CI/CD',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'mcp',
            'group': 'mcp',
            'role': 'GitHub API Integration',
            'status': 'enabled',
            'package': '@modelcontextprotocol/server-github',
            'desc': 'Provides tools for managing GitHub repositories, branches, pull requests, issues, and committing code changes directly.',
            'in_hermes_subgraph': False,
            'initX': 0, 'initY': -380
        },
        {
            'id': 'mcp-postgres',
            'label': 'Postgres MCP',
            'sublabel': 'SQL INSPECTOR',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'mcp',
            'group': 'mcp',
            'role': 'SQL Read-Only Client',
            'status': 'enabled',
            'target': 'honcho-database:5432',
            'desc': 'Provides read-only SQL querying against honcho-database for debugging and schema exploration.',
            'in_hermes_subgraph': False,
            'initX': 80, 'initY': -370
        },
        {
            'id': 'mcp-notion',
            'label': 'Notion MCP',
            'sublabel': 'KNOWLEDGE BASE',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'mcp',
            'group': 'mcp',
            'role': 'Notion API Workspace',
            'status': 'enabled',
            'package': 'notion-mcp-server',
            'desc': 'Connects Hermes to Notion workspaces for syncing product notes, task tracking, and document archives.',
            'in_hermes_subgraph': True,
            'initX': 150, 'initY': -340
        },

        # 8. CLIENT CHANNELS (Full Graph)
        {
            'id': 'client-whatsapp',
            'label': 'WhatsApp Bridge',
            'sublabel': '+628****4820',
            'type': 'channel',
            'tier': 'dependency',
            'category': 'channel',
            'group': 'channel',
            'role': 'Baileys Multi-Device Client',
            'status': 'connected',
            'channel_id': 'whatsapp:z',
            'desc': 'WhatsApp bridge daemon maintaining persistent socket connection, routing direct messages and group reminders to Hermes.',
            'in_hermes_subgraph': False,
            'initX': 440, 'initY': -50
        },
        {
            'id': 'client-telegram',
            'label': 'Telegram Gateway',
            'sublabel': 'BOT INTEGRATION',
            'type': 'channel',
            'tier': 'dependency',
            'category': 'channel',
            'group': 'channel',
            'role': 'Telegram Bot API Bridge',
            'status': 'connected',
            'desc': 'Hermes Telegram client delivering notifications and interactive commands to user channel.',
            'in_hermes_subgraph': False,
            'initX': 450, 'initY': 20
        },
        {
            'id': 'client-dashboard',
            'label': 'Web Dashboard',
            'sublabel': 'PORT: 9119',
            'type': 'channel',
            'tier': 'dependency',
            'category': 'channel',
            'group': 'channel',
            'role': 'Hermes Web Management UI',
            'status': 'online',
            'ports': '9119',
            'desc': 'Live web dashboard providing web chat, system diagnostics, session inspector, and real-time logs.',
            'in_hermes_subgraph': False,
            'initX': 430, 'initY': 90
        },

        # 9. MONITORING (Full Graph)
        {
            'id': 'mon-prometheus',
            'label': 'Prometheus TSDB',
            'sublabel': 'PORT: 9090',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'monitoring',
            'group': 'monitoring',
            'role': 'Time-Series Collector',
            'status': 'online',
            'ports': '9090',
            'container': 'prometheus',
            'desc': 'Scrapes metric endpoints from cadvisor, node-exporter, and Docker host every 15s with 15-day retention.',
            'in_hermes_subgraph': False,
            'initX': -440, 'initY': -50
        },
        {
            'id': 'mon-grafana',
            'label': 'Grafana',
            'sublabel': 'PORT: 3001',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'monitoring',
            'group': 'monitoring',
            'role': 'Observability Dashboards',
            'status': 'online',
            'ports': '3001',
            'container': 'grafana',
            'desc': 'Interactive telemetry dashboards graphing CPU, RAM, Docker container loads, and network latency.',
            'in_hermes_subgraph': False,
            'initX': -450, 'initY': 30
        },
        {
            'id': 'mon-cadvisor',
            'label': 'cAdvisor',
            'sublabel': 'PORT: 8080',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'monitoring',
            'group': 'monitoring',
            'role': 'Container Metrics',
            'status': 'healthy',
            'ports': '8080',
            'container': 'cadvisor',
            'desc': 'Analyzes and exposes resource usage (CPU, memory, disk, network) for all running containers on deb-zlf.',
            'in_hermes_subgraph': False,
            'initX': -420, 'initY': -110
        },
        {
            'id': 'mon-node-exporter',
            'label': 'Node Exporter',
            'sublabel': 'PORT: 9100',
            'type': 'dependency',
            'tier': 'dependency',
            'category': 'monitoring',
            'group': 'monitoring',
            'role': 'Host System Hardware',
            'status': 'online',
            'ports': '9100',
            'container': 'node_exporter',
            'desc': 'Exposes Linux kernel statistics, disk I/O, network bandwidth, and hardware health for deb-zlf.',
            'in_hermes_subgraph': False,
            'initX': -420, 'initY': 100
        }
    ]

    # Resolve real Hermes skills
    skills_dir = os.environ.get('SKILLS_DIR', '')
    if not skills_dir or not os.path.isdir(skills_dir):
        for candidate in ['/skills', '/opt/data/skills', os.path.join(BASE_DIR, 'skills')]:
            if os.path.isdir(candidate):
                skills_dir = candidate
                break

    real_skills = []
    if skills_dir and os.path.isdir(skills_dir):
        for root, dirs, files in os.walk(skills_dir):
            if 'SKILL.md' in files:
                rel = os.path.relpath(root, skills_dir)
                parts = rel.split(os.sep)
                cat = parts[0] if len(parts) > 1 else 'general'
                slug = parts[-1]
                if slug.startswith('.'): continue
                
                skill_path = os.path.join(root, 'SKILL.md')
                desc = f'Hermes skill: {slug}'
                try:
                    with open(skill_path, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.read(1500)
                        for line in content.splitlines():
                            if line.strip().startswith('description:'):
                                desc = line.split('description:', 1)[1].strip(' "\'\\t')
                                break
                except Exception:
                    pass
                
                real_skills.append({
                    'id': f'skill-{slug}',
                    'label': slug,
                    'sublabel': cat,
                    'type': 'skill',
                    'category': cat,
                    'group': 'skills',
                    'tier': 'dependency',
                    'role': f'{cat.replace("-", " ").title()} Skill',
                    'status': 'installed',
                    'desc': desc,
                    'in_hermes_subgraph': True
                })

    # Include all real, verified installed Hermes skills
    selected_skills = real_skills

    for i, sk in enumerate(selected_skills):
        sk['initX'] = 250 + (i % 8) * 40
        sk['initY'] = -280 + (i // 8) * 40
        nodes.append(sk)

    # Resolve real Agency specialist agents
    agents_path = os.environ.get('AGENTS_PATH', '')
    for candidate in [
        agents_path,
        os.path.join(skills_dir, '.agents.json') if skills_dir else '',
        '/skills/.agents.json',
        '/opt/data/galaxy-view/agents.json',
        '/opt/data/skills/.agents.json',
        '/opt/data/plugins/agency-agents-router/data/agents.json',
        os.path.join(BASE_DIR, 'agents.json')
    ]:
        if candidate and os.path.isfile(candidate):
            agents_path = candidate
            break

    selected_agents = []
    if agents_path and os.path.exists(agents_path):
        try:
            with open(agents_path, 'r', encoding='utf-8') as fp:
                all_agents = json.load(fp)
            
            target_slugs = [
                'code-reviewer', 'desktop-app-engineer', 'api-platform-engineer', 'autonomous-optimization-architect', 'pdf-engine-architect',
                'accessibility-auditor', 'api-tester', 'performance-benchmarker',
                'cloud-security-architect', 'compliance-auditor',
                'project-shepherd', 'senior-project-manager', 'product-manager', 'feedback-synthesizer',
                'persona-walkthrough-specialist', 'ui-designer', 'brand-guardian', 'image-prompt-engineer',
                'sales-coach', 'offer-lead-gen-strategist', 'agentic-search-optimizer',
                'research-synthesist', 'anthropologist', 'geographer',
                'infrastructure-maintainer', 'analytics-reporter'
            ]
            
            curated_agents = [a for a in all_agents if a.get('slug') in target_slugs]
            for j, ag in enumerate(curated_agents):
                div = ag.get('division', 'agency')
                agent_obj = {
                    'id': f'agent-{ag.get("slug")}',
                    'label': ag.get('name', ag.get('slug')),
                    'sublabel': div.upper(),
                    'type': 'agent',
                    'category': 'agents',
                    'group': 'agents',
                    'tier': 'dependency',
                    'division': div,
                    'role': f'{div.replace("-", " ").capitalize()} Agent',
                    'status': 'registered',
                    'desc': ag.get('description', '')[:220],
                    'in_hermes_subgraph': True,
                    'initX': 250 + (j % 5) * 45,
                    'initY': 140 + (j // 5) * 45
                }
                selected_agents.append(agent_obj)
                nodes.append(agent_obj)
        except Exception:
            pass

    # EDGES & TOPOLOGICAL CONNECTIONS
    links = [
        # Hermes Core → Primary Trunks (Main Request & Control)
        {'source': 'hermes', 'target': 'service-skills', 'kind': 'main', 'dir': 'both', 'label': 'Hermes Skills', 'value': 4, 'in_hermes_subgraph': True},
        {'source': 'hermes', 'target': 'service-agents', 'kind': 'main', 'dir': 'both', 'label': 'Specialist Agents', 'value': 4, 'in_hermes_subgraph': True},
        {'source': 'hermes', 'target': 'service-9router', 'kind': 'main', 'dir': 'out', 'label': 'LLM Inferences', 'value': 4, 'in_hermes_subgraph': True},
        {'source': 'hermes', 'target': 'service-honcho', 'kind': 'main', 'dir': 'both', 'label': 'Memory Context & Dialectic', 'value': 4, 'in_hermes_subgraph': True},
        {'source': 'hermes', 'target': 'service-mcp', 'kind': 'main', 'dir': 'both', 'label': 'Tool Protocol (Stdio/IPC)', 'value': 4, 'in_hermes_subgraph': True},
        {'source': 'service-clients', 'target': 'hermes', 'kind': 'main', 'dir': 'both', 'label': 'User Prompts & Delivery', 'value': 4, 'in_hermes_subgraph': False},

        # 9Router → Models & Upstream Providers
        {'source': 'service-9router', 'target': 'model-agy-combo', 'kind': 'dep', 'dir': 'out', 'label': 'Default Chat Route', 'value': 3, 'in_hermes_subgraph': True, 'active': True, 'is_active_model_route': True},
        {'source': 'service-9router', 'target': 'model-agy-claude', 'kind': 'dep', 'dir': 'out', 'label': 'Claude Route', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'service-9router', 'target': 'model-nemotron', 'kind': 'dep', 'dir': 'out', 'label': 'Nemotron 550B', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'service-9router', 'target': 'provider-xkiro', 'kind': 'dep', 'dir': 'out', 'label': 'Xkiro Endpoint', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'service-9router', 'target': 'upstream-openrouter', 'kind': 'dep', 'dir': 'out', 'label': 'Cloud Fallback', 'value': 3, 'in_hermes_subgraph': True},

        # Honcho → Storage, Cache, and Cognitive Deriver
        {'source': 'service-honcho', 'target': 'db-postgres', 'kind': 'dep', 'dir': 'both', 'label': 'SQL & pgvector (:5432)', 'value': 3, 'in_hermes_subgraph': True},
        {'source': 'service-honcho', 'target': 'cache-redis', 'kind': 'dep', 'dir': 'both', 'label': 'Session Cache (:6379)', 'value': 3, 'in_hermes_subgraph': True},
        {'source': 'service-honcho', 'target': 'svc-deriver', 'kind': 'dep', 'dir': 'both', 'label': 'Dialectic Worker', 'value': 3, 'in_hermes_subgraph': True},
        {'source': 'service-honcho', 'target': 'svc-honcho-mcp', 'kind': 'dep', 'dir': 'out', 'label': 'MCP Protocol (:3000)', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'service-honcho', 'target': 'storage-memories', 'kind': 'dep', 'dir': 'both', 'label': 'Flatfile Markdown Sync', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'db-postgres', 'target': 'svc-deriver', 'kind': 'dep', 'dir': 'both', 'label': 'Message Ingestion', 'value': 2, 'in_hermes_subgraph': True},

        # Cross-Connections (Skills & Agents to Dependencies)
        {'source': 'skill-honcho-memory-integration', 'target': 'service-honcho', 'kind': 'dep', 'dir': 'out', 'label': 'Honcho SDK & API', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'skill-claude-code', 'target': 'model-agy-claude', 'kind': 'dep', 'dir': 'out', 'label': 'Claude Route', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'skill-hermes-agent', 'target': 'hermes', 'kind': 'dep', 'dir': 'both', 'label': 'Self-Config & Runtime', 'value': 3, 'in_hermes_subgraph': True},
        {'source': 'skill-hermes-plugins', 'target': 'service-agents', 'kind': 'dep', 'dir': 'out', 'label': 'Agency Router Plugin', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-code-reviewer', 'target': 'skill-code-review-and-quality', 'kind': 'dep', 'dir': 'out', 'label': 'Quality Bar', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-api-platform-engineer', 'target': 'skill-api-and-interface-design', 'kind': 'dep', 'dir': 'out', 'label': 'API Contracts', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-cloud-security-architect', 'target': 'skill-security-and-hardening', 'kind': 'dep', 'dir': 'out', 'label': 'Hardening Specs', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-accessibility-auditor', 'target': 'skill-frontend-ui-engineering', 'kind': 'dep', 'dir': 'out', 'label': 'UI Standards', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-senior-project-manager', 'target': 'skill-planning-and-task-breakdown', 'kind': 'dep', 'dir': 'out', 'label': 'Task Breakdown', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-research-synthesist', 'target': 'skill-grounded-citations', 'kind': 'dep', 'dir': 'out', 'label': 'Fact Verification', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-image-prompt-engineer', 'target': 'skill-baoyu-infographic', 'kind': 'dep', 'dir': 'out', 'label': 'Visual Generation', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'agent-desktop-app-engineer', 'target': 'skill-systematic-debugging', 'kind': 'dep', 'dir': 'out', 'label': 'Systematic Debug', 'value': 2, 'in_hermes_subgraph': True},

        # Full Graph Links (MCP Gateway, Client Channels, Monitoring, Tailscale)
        {'source': 'service-mcp', 'target': 'mcp-docker', 'kind': 'dep', 'dir': 'out', 'label': 'Docker Control', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-mcp', 'target': 'mcp-github', 'kind': 'dep', 'dir': 'out', 'label': 'Repo Operations', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-mcp', 'target': 'mcp-postgres', 'kind': 'dep', 'dir': 'out', 'label': 'Direct SQL Read', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'mcp-postgres', 'target': 'db-postgres', 'kind': 'dep', 'dir': 'out', 'label': 'Query Database', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-mcp', 'target': 'mcp-notion', 'kind': 'dep', 'dir': 'out', 'label': 'Workspace Sync', 'value': 2, 'in_hermes_subgraph': True},
        {'source': 'skill-github', 'target': 'mcp-github', 'kind': 'dep', 'dir': 'out', 'label': 'GitHub CLI & MCP', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'skill-scheduled-chat-reminders', 'target': 'client-whatsapp', 'kind': 'dep', 'dir': 'out', 'label': 'WhatsApp Delivery', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'skill-browser-testing-with-devtools', 'target': 'mcp-docker', 'kind': 'dep', 'dir': 'out', 'label': 'Browser Container', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-clients', 'target': 'client-whatsapp', 'kind': 'dep', 'dir': 'both', 'label': 'Baileys Socket', 'value': 3, 'in_hermes_subgraph': False},
        {'source': 'service-clients', 'target': 'client-telegram', 'kind': 'dep', 'dir': 'both', 'label': 'Bot Webhook', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-clients', 'target': 'client-dashboard', 'kind': 'dep', 'dir': 'both', 'label': 'HTTP Gateway (:9119)', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-monitoring', 'target': 'mon-prometheus', 'kind': 'dep', 'dir': 'out', 'label': 'TSDB Storage', 'value': 3, 'in_hermes_subgraph': False},
        {'source': 'service-monitoring', 'target': 'mon-grafana', 'kind': 'dep', 'dir': 'out', 'label': 'Dashboards (:3001)', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'mon-grafana', 'target': 'mon-prometheus', 'kind': 'dep', 'dir': 'in', 'label': 'PromQL Queries', 'value': 3, 'in_hermes_subgraph': False},
        {'source': 'mon-prometheus', 'target': 'mon-cadvisor', 'kind': 'dep', 'dir': 'in', 'label': 'Scrape Stats (:8080)', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'mon-prometheus', 'target': 'mon-node-exporter', 'kind': 'dep', 'dir': 'in', 'label': 'Scrape Host (:9100)', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'mon-prometheus', 'target': 'hermes', 'kind': 'dep', 'dir': 'in', 'label': 'Agent Telemetry', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'mon-prometheus', 'target': 'service-9router', 'kind': 'dep', 'dir': 'in', 'label': 'Gateway Metrics', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'mon-prometheus', 'target': 'service-honcho', 'kind': 'dep', 'dir': 'in', 'label': 'Memory Health', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-tailscale', 'target': 'service-9router', 'kind': 'dep', 'dir': 'out', 'label': 'HTTPS (:443)', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-tailscale', 'target': 'service-honcho', 'kind': 'dep', 'dir': 'out', 'label': 'HTTPS (:8443)', 'value': 2, 'in_hermes_subgraph': False},
        {'source': 'service-tailscale', 'target': 'hermes', 'kind': 'dep', 'dir': 'out', 'label': 'Graph View (:8444)', 'value': 2, 'in_hermes_subgraph': False}
    ]

    # Dynamically connect Skills to service-skills hub
    for sk in selected_skills:
        links.append({
            'source': 'service-skills',
            'target': sk['id'],
            'kind': 'dep',
            'dir': 'out',
            'label': sk['sublabel'].upper(),
            'value': 2,
            'in_hermes_subgraph': True
        })

    # Dynamically connect Agents to service-agents hub
    for ag in selected_agents:
        links.append({
            'source': 'service-agents',
            'target': ag['id'],
            'kind': 'dep',
            'dir': 'out',
            'label': ag['sublabel'],
            'value': 2,
            'in_hermes_subgraph': True
        })

    return {'nodes': nodes, 'links': links, 'colors': category_colors, 'mode': 'graph-topology'}

def broadcast_event(data):
    msg = f"data: {json.dumps(data)}\n\n".encode('utf-8')
    with clients_lock:
        to_remove = []
        for wfile in clients:
            try:
                wfile.write(msg)
                wfile.flush()
            except Exception:
                to_remove.append(wfile)
        for dead in to_remove:
            if dead in clients:
                clients.remove(dead)

def event_watcher():
    last_mtime = 0
    while True:
        try:
            if os.path.exists(ACTIVE_EVENT_FILE):
                mtime = os.path.getmtime(ACTIVE_EVENT_FILE)
                if mtime != last_mtime:
                    last_mtime = mtime
                    with open(ACTIVE_EVENT_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    broadcast_event(data)
        except Exception:
            pass
        time.sleep(0.3)


def usage_watcher():
    """Watch .usage.json — fires activate/deactivate SSE whenever bump_use runs (any subagent)."""
    last_mtime = 0
    first_run = True
    deactivate_timers: dict = {}   # skill_name -> threading.Timer

    def _deactivate(skill_name):
        with _usage_lock:
            if skill_name in _usage_active:
                del _usage_active[skill_name]
        broadcast_event({'type': 'skill_deactivated', 'skill': skill_name})

    while True:
        try:
            if os.path.exists(USAGE_JSON):
                mtime = os.path.getmtime(USAGE_JSON)
                if mtime != last_mtime or first_run:
                    last_mtime = mtime
                    first_run = False
                    with open(USAGE_JSON, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    now_str = time.strftime('%Y-%m-%dT', time.gmtime())
                    for skill_name, rec in data.items():
                        used_at = rec.get('last_used_at', '')
                        if not used_at:
                            continue
                        # Only care about skills used in the last 30 seconds
                        try:
                            import datetime
                            dt = datetime.datetime.fromisoformat(used_at.replace('Z', '+00:00'))
                            age = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
                            if age > 30:
                                continue
                        except Exception:
                            continue

                        with _usage_lock:
                            prev = _usage_active.get(skill_name)
                            if prev != used_at:
                                _usage_active[skill_name] = used_at
                                # Cancel pending deactivation if any
                                old_timer = deactivate_timers.pop(skill_name, None)
                                if old_timer:
                                    old_timer.cancel()
                                # Broadcast activate
                                broadcast_event({'type': 'skill_activated', 'skill': skill_name})
                                # Schedule deactivation
                                t = threading.Timer(DEACTIVATE_DELAY, _deactivate, args=[skill_name])
                                t.daemon = True
                                t.start()
                                deactivate_timers[skill_name] = t
        except Exception:
            pass
        time.sleep(0.5)

class GalaxyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        # Prevent browser caching of HTML/JS so updates take effect immediately
        if hasattr(self, 'path') and self.path in ('/', '/index.html'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        if self.path.startswith('/api/active'):
            # Polling endpoint — returns currently active skills & live transmissions
            try:
                usage_data = {}
                if os.path.exists(USAGE_JSON):
                    with open(USAGE_JSON, 'r', encoding='utf-8') as f:
                        usage_data = json.load(f)
            except Exception:
                usage_data = {}
            with _usage_lock:
                active = list(_usage_active.keys())
            skills_info = []
            for s in active:
                use_count = usage_data.get(s, {}).get('use_count', 1)
                skills_info.append({'name': s, 'use_count': use_count})

            # Quick scan of total skills count (ignoring hidden dirs)
            total_skills = 0
            if os.path.exists(SKILLS_DIR):
                for _, dirs, files in os.walk(SKILLS_DIR):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    if 'SKILL.md' in files:
                        total_skills += 1

            # Prune and gather active transmissions
            now_ts = time.time()
            with _trans_lock:
                expired = [k for k, v in _active_transmissions.items() if v.get('expires_at', 0) <= now_ts]
                for k in expired:
                    _active_transmissions.pop(k, None)
                transmissions = list(_active_transmissions.values())

            payload = {
                'skills': active,
                'skills_info': skills_info,
                'total_skills': total_skills,
                'transmissions': transmissions
            }
            content = json.dumps(payload).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if self.path.startswith('/api/graph'):
            data = get_skills_graph()
            content = json.dumps(data).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if self.path == '/api/events':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            with clients_lock:
                clients.append(self.wfile)

            try:
                self.wfile.write(b"data: {\"type\": \"connected\"}\n\n")
                self.wfile.flush()
                while True:
                    time.sleep(15)
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                with clients_lock:
                    if self.wfile in clients:
                        clients.remove(self.wfile)
            return

        # Explicitly serve index.html for root /
        if self.path in ('/', '', '/index.html'):
            index_path = os.path.join(BASE_DIR, 'index.html')
            if os.path.exists(index_path):
                with open(index_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        super().do_GET()

    def do_POST(self):
        if self.path in ('/api/activate', '/api/deactivate'):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                payload = json.loads(body)
                raw_skills = payload.get('skills', [])
                if isinstance(raw_skills, list) and raw_skills:
                    skills_to_act = [s for s in raw_skills if s]
                elif payload.get('skill'):
                    skills_to_act = [payload.get('skill')]
                else:
                    skills_to_act = []

                if self.path == '/api/activate' and skills_to_act:
                    now_str = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    with _usage_lock:
                        for sn in skills_to_act:
                            _usage_active[sn] = now_str
                    # Auto-deactivate after delay
                    def _auto_deact_all(slist=list(skills_to_act)):
                        time.sleep(DEACTIVATE_DELAY)
                        with _usage_lock:
                            for sn in slist:
                                _usage_active.pop(sn, None)
                        for sn in slist:
                            broadcast_event({'type': 'skill_deactivated', 'skill': sn})
                    threading.Thread(target=_auto_deact_all, daemon=True).start()
                    for sn in skills_to_act:
                        broadcast_event({'type': 'skill_activated', 'skill': sn})
                elif self.path == '/api/deactivate' and skills_to_act:
                    with _usage_lock:
                        for sn in skills_to_act:
                            _usage_active.pop(sn, None)
                    for sn in skills_to_act:
                        broadcast_event({'type': 'skill_deactivated', 'skill': sn})
                else:
                    broadcast_event(payload)

                # Persist to active_skill.json
                with open(ACTIVE_EVENT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(payload, f)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
            return

        if self.path == '/api/telemetry':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                payload = json.loads(body)
                t_id = payload.get('id') or f"tx_{int(time.time()*1000)}_{random.randint(100,999)}"
                payload['id'] = t_id
                payload['type'] = 'telemetry'
                dur = float(payload.get('duration_s', 4.5))
                payload['duration_s'] = dur
                payload['expires_at'] = time.time() + dur

                with _trans_lock:
                    _active_transmissions[t_id] = payload

                # Broadcast via SSE
                broadcast_event(payload)

                # Auto cleanup thread
                def _cleanup_tx(tx_id=t_id, wait_dur=dur):
                    time.sleep(wait_dur)
                    with _trans_lock:
                        _active_transmissions.pop(tx_id, None)
                    broadcast_event({'type': 'telemetry_ended', 'id': tx_id})

                threading.Thread(target=_cleanup_tx, daemon=True).start()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'id': t_id}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
            return
        self.send_response(404)
        self.end_headers()

def run_server():
    server = ThreadingHTTPServer(('0.0.0.0', PORT), GalaxyHandler)
    print(f"Galaxy Server listening on port {PORT} serving {BASE_DIR}")
    server.serve_forever()

if __name__ == '__main__':
    t = threading.Thread(target=event_watcher, daemon=True)
    t.start()
    t2 = threading.Thread(target=usage_watcher, daemon=True)
    t2.start()
    run_server()
