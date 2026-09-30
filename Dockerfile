FROM python:3.12-alpine

WORKDIR /app

# Copy server script and frontend assets
COPY server.py /app/server.py
COPY index.html /app/index.html
COPY skills_graph.json /app/skills_graph.json

# Environment default: mount point for Hermes skills
ENV SKILLS_DIR=/skills

EXPOSE 8899

CMD ["python", "server.py"]
