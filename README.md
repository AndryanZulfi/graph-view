# Graph View — Hermes System Topology & Real-Time Telemetry

Interactive force-directed topology visualizer and real-time telemetry dashboard for the [Hermes Agent](https://hermes-agent.nousresearch.com) ecosystem, powered by D3 physics, SSE (Server-Sent Events), and HTML5 Canvas.

![Graph View Topology](https://raw.githubusercontent.com/AndryanZulfi/graph-view/main/assets/preview.png)

---

## Features

- **Dynamic Force-Directed Graph Layout:** Physics simulation with elastic collision detection, spring attraction, Coulomb repulsion, and smooth drag-and-drop.
- **Hierarchical Node Categorization:**
  - **Core:** Hermes Central Agent Node
  - **Capabilities:** Skills Hub (91 real skills auto-discovered) & Agents Hub (26 specialist agents)
  - **Services:** 9Router LLM Gateway, Honcho Memory Server, Tailscale Mesh
  - **Dependencies:** Model endpoints (`GLM-5`, `Claude`, `Gemini`, `MiniMax`, etc.), Databases (`PostgreSQL 15`, `Redis`), and Storage
- **Two Viewing Modes:**
  - `[ Full Graph ]`: Comprehensive infrastructure topology (148 nodes).
  - `[ Hermes Connections ]`: Dedicated subgraph focused exclusively on direct Hermes operations (133 nodes).
- **Real-Time Live Telemetry & Synaptic Cable Pulses:**
  - **Laser Beams & Traveling Photons:** Cables light up with high-intensity bloom and fast streaming data packets during live LLM routing, memory retrieval, or tool executions.
  - **Radar/Sonar Ripple Rings:** Target nodes pulse rhythmically with expanding rings when actively processing requests.
  - **Live HUD Badge:** Real-time indicator displaying active transmissions and model/tool details.
- **Hermes Plugin Integration:** Includes `galaxy-telemetry` plugin hooking into `pre_api_request`, `pre_tool_call`, and `on_skill_lifecycle`.

---

## Quick Start (Docker)

### 1. Run with Docker Compose
```bash
docker compose up -d
```

### 2. Access the Dashboard
Open your browser and navigate to:
```text
http://localhost:8899
```

---

## API Endpoints

- `GET /api/graph`: Returns the complete nodes and links topology graph JSON.
- `GET /api/events`: Server-Sent Events (SSE) stream for instant real-time telemetry broadcasts.
- `GET /api/active`: Polling endpoint returning active skills and in-flight transmissions.
- `POST /api/telemetry`: Ingests real-time communication events:
  ```json
  {
    "action": "route_llm",
    "from": "hermes",
    "to": "service-9router",
    "target": "model-glm-5",
    "label": "9Router: GLM-5",
    "detail": "Streaming tokens from 9Router GLM-5",
    "color": "#8b5cf6",
    "duration_s": 15.0
  }
  ```

---

## License

MIT License.
