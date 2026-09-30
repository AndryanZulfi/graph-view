import json

with open('/opt/data/skills_graph.json') as f:
    data = json.load(f)

json_str = json.dumps(data)

html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Skills Constellation</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            background-color: #030712;
            color: #f3f4f6;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            overflow: hidden;
            width: 100vw;
            height: 100vh;
        }
        #canvas-container {
            width: 100vw;
            height: 100vh;
            position: absolute;
            top: 0;
            left: 0;
        }
        /* HUD Header */
        .hud-header {
            position: absolute;
            top: 24px;
            left: 28px;
            z-index: 10;
            pointer-events: none;
        }
        .hud-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(14, 165, 233, 0.15);
            border: 1px solid rgba(56, 189, 248, 0.4);
            padding: 5px 12px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.1em;
            color: #38bdf8;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .hud-badge .pulse-dot {
            width: 8px;
            height: 8px;
            background: #38bdf8;
            border-radius: 50%;
            box-shadow: 0 0 10px #38bdf8;
            animation: blink 1.5s infinite ease-in-out;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.3; transform: scale(0.7); }
        }
        h1 {
            font-size: 28px;
            font-weight: 900;
            letter-spacing: -0.03em;
            background: linear-gradient(135deg, #ffffff 40%, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hud-subtitle {
            font-size: 13px;
            color: #64748b;
            margin-top: 4px;
        }

        /* Detail Card */
        #detail-card {
            position: absolute;
            bottom: 28px;
            right: 28px;
            width: 340px;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(18px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 16px;
            padding: 20px;
            z-index: 10;
            box-shadow: 0 24px 50px rgba(0, 0, 0, 0.7);
            pointer-events: auto;
            transition: all 0.25s ease;
        }
        .card-tag {
            font-size: 10px;
            text-transform: uppercase;
            font-weight: 800;
            letter-spacing: 0.08em;
            padding: 4px 10px;
            border-radius: 6px;
            display: inline-block;
            margin-bottom: 10px;
        }
        .card-title {
            font-size: 19px;
            font-weight: 800;
            color: #f8fafc;
            margin-bottom: 8px;
            word-break: break-word;
        }
        .card-desc {
            font-size: 13px;
            color: #94a3b8;
            line-height: 1.55;
            max-height: 160px;
            overflow-y: auto;
        }
        .card-stats {
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #64748b;
            font-weight: 600;
        }

        /* Constellation Stats Footer */
        .hud-stats {
            position: absolute;
            bottom: 28px;
            left: 28px;
            display: flex;
            gap: 14px;
            z-index: 10;
            pointer-events: none;
        }
        .stat-box {
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 10px 16px;
            border-radius: 12px;
        }
        .stat-num {
            font-size: 20px;
            font-weight: 800;
            color: #38bdf8;
        }
        .stat-label {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #64748b;
            margin-top: 2px;
            font-weight: 700;
        }

        /* SVG Elements */
        line.link {
            stroke-opacity: 0.22;
            transition: stroke-opacity 0.2s, stroke-width 0.2s;
        }
        circle.node {
            cursor: pointer;
            transition: r 0.2s, filter 0.2s;
        }
        text.label {
            font-size: 10px;
            font-family: inherit;
            pointer-events: none;
            user-select: none;
            fill: #94a3b8;
            font-weight: 500;
        }
        text.cluster-label {
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.08em;
            fill: #e2e8f0;
        }
        text.core-label {
            font-size: 14px;
            font-weight: 900;
            letter-spacing: 0.12em;
            fill: #ffffff;
        }
    </style>
</head>
<body>
    <div class="hud-header">
        <div class="hud-badge">
            <span class="pulse-dot"></span>
            Hermes Neural Constellation
        </div>
        <h1>HERMES SKILL UNIVERSE</h1>
        <div class="hud-subtitle">61 Mounted Skills across 12 Functional Clusters</div>
    </div>

    <div class="hud-stats">
        <div class="stat-box">
            <div class="stat-num">61</div>
            <div class="stat-label">Active Skills</div>
        </div>
        <div class="stat-box">
            <div class="stat-num">12</div>
            <div class="stat-label">Galactic Clusters</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color: #34d399;">ONLINE</div>
            <div class="stat-label">Orchestrator</div>
        </div>
    </div>

    <div id="detail-card">
        <span class="card-tag" id="card-tag" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8;">CORE</span>
        <div class="card-title" id="card-title">HERMES CORE</div>
        <div class="card-desc" id="card-desc">Hover atau klik bintang/node mana saja untuk melihat rincian instruksi dan fungsinya. Kamu juga bisa drag node untuk mengatur posisi orbit.</div>
        <div class="card-stats">
            <span id="card-status">STATUS: ONLINE</span>
            <span id="card-cat">CLUSTER: ROOT</span>
        </div>
    </div>

    <div id="canvas-container"></div>

    <script>
        const graphData = GRAPH_DATA_PLACEHOLDER;

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#canvas-container")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .call(d3.zoom().scaleExtent([0.2, 4]).on("zoom", (event) => {
                g.attr("transform", event.transform);
            }));

        const defs = svg.append("defs");
        
        // Deep space star pattern
        const pattern = defs.append("pattern")
            .attr("id", "grid")
            .attr("width", 70)
            .attr("height", 70)
            .attr("patternUnits", "userSpaceOnUse");
            
        pattern.append("circle")
            .attr("cx", 35)
            .attr("cy", 35)
            .attr("r", 1)
            .attr("fill", "rgba(255, 255, 255, 0.08)");

        svg.append("rect")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("fill", "url(#grid)");

        const g = svg.append("g");

        // Force simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(d => {
                if (d.source.id === 'core' || d.target.id === 'core') return 220;
                return 80;
            }))
            .force("charge", d3.forceManyBody().strength(d => {
                if (d.type === 'core') return -1800;
                if (d.type === 'cluster') return -600;
                return -150;
            }))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => {
                if (d.type === 'core') return 70;
                if (d.type === 'cluster') return 40;
                return 20;
            }));

        // Render Links
        const link = g.append("g")
            .selectAll("line")
            .data(graphData.links)
            .join("line")
            .attr("class", "link")
            .attr("stroke", d => {
                const cat = d.target.category || d.source.category;
                return graphData.colors[cat] || "#475569";
            })
            .attr("stroke-width", d => (d.source.type === 'core' ? 2 : 1))
            .attr("stroke-dasharray", d => (d.source.type === 'core' ? "4 4" : "none"));

        // Render Nodes Container
        const node = g.append("g")
            .selectAll("g")
            .data(graphData.nodes)
            .join("g")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        // Node Circles
        node.append("circle")
            .attr("class", "node")
            .attr("r", d => {
                if (d.type === 'core') return 28;
                if (d.type === 'cluster') return 15;
                return 7.5;
            })
            .attr("fill", d => {
                if (d.type === 'core') return '#ffffff';
                return graphData.colors[d.category] || '#94a3b8';
            })
            .attr("fill-opacity", d => (d.type === 'skill' ? 0.75 : 0.95))
            .attr("stroke", d => {
                if (d.type === 'core') return '#38bdf8';
                return graphData.colors[d.category] || '#ffffff';
            })
            .attr("stroke-width", d => (d.type === 'core' ? 5 : 2));

        // Outer glow ring for Core
        const coreNode = node.filter(d => d.type === 'core');
        coreNode.append("circle")
            .attr("r", 40)
            .attr("fill", "none")
            .attr("stroke", "#38bdf8")
            .attr("stroke-width", 1.5)
            .attr("stroke-opacity", 0.5)
            .attr("stroke-dasharray", "6 4");

        // Labels
        node.append("text")
            .attr("class", d => {
                if (d.type === 'core') return 'label core-label';
                if (d.type === 'cluster') return 'label cluster-label';
                return 'label';
            })
            .attr("dx", d => (d.type === 'core' ? 0 : (d.type === 'cluster' ? 20 : 12)))
            .attr("dy", d => (d.type === 'core' ? 54 : 4))
            .attr("text-anchor", d => (d.type === 'core' ? 'middle' : 'start'))
            .text(d => d.label);

        // Interactions
        node.on("mouseenter", function(event, d) {
            d3.select(this).select("circle")
                .transition().duration(200)
                .attr("r", d.type === 'core' ? 34 : (d.type === 'cluster' ? 20 : 12))
                .attr("fill-opacity", 1);

            link.attr("stroke-opacity", l => (l.source.id === d.id || l.target.id === d.id ? 0.95 : 0.08))
                .attr("stroke-width", l => (l.source.id === d.id || l.target.id === d.id ? 2.5 : 1));

            updateCard(d);
        })
        .on("mouseleave", function(event, d) {
            d3.select(this).select("circle")
                .transition().duration(200)
                .attr("r", d.type === 'core' ? 28 : (d.type === 'cluster' ? 15 : 7.5))
                .attr("fill-opacity", d.type === 'skill' ? 0.75 : 0.95);

            link.attr("stroke-opacity", 0.22)
                .attr("stroke-width", l => (l.source.type === 'core' ? 2 : 1));
        })
        .on("click", function(event, d) {
            updateCard(d);
        });

        function updateCard(d) {
            const card = document.getElementById('detail-card');
            const color = graphData.colors[d.category] || '#38bdf8';
            
            document.getElementById('card-tag').style.background = color + '33';
            document.getElementById('card-tag').style.color = color;
            document.getElementById('card-tag').innerText = d.type.toUpperCase();
            
            document.getElementById('card-title').innerText = d.label;
            document.getElementById('card-desc').innerText = d.desc;
            document.getElementById('card-cat').innerText = 'CLUSTER: ' + d.category.toUpperCase();
            document.getElementById('card-status').innerText = 'STATUS: MOUNTED';
        }

        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => "translate(" + d.x + "," + d.y + ")");
        });

        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }

        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }

        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }

        window.addEventListener('resize', () => {
            const w = window.innerWidth;
            const h = window.innerHeight;
            svg.attr("width", w).attr("height", h);
            simulation.force("center", d3.forceCenter(w / 2, h / 2));
            simulation.alpha(0.3).restart();
        });
    </script>
</body>
</html>
"""

html_final = html_template.replace('GRAPH_DATA_PLACEHOLDER', json_str)

with open('/opt/data/galaxy-view/index.html', 'w', encoding='utf-8') as f:
    f.write(html_final)

print("SUCCESS: /opt/data/galaxy-view/index.html written cleanly!")
