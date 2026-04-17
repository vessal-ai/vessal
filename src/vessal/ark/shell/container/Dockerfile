# Vessal container Shell — Docker image for running a Vessal agent.
#
# Build: vessal build [agent_dir]
# Run:   vessal run [name] --port 8420
#
# Build context layout (assembled by vessal build):
#   vessal/     Vessal source package
#   agent/      Agent definition (SOUL.md, hull.toml, skills/)

FROM python:3.12-slim

# tini — PID 1 signal forwarding + zombie process reaping
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# Install Vessal runtime
COPY vessal/ /opt/vessal/
RUN pip install --no-cache-dir /opt/vessal/

# Stage agent definition at /opt/agent-image/
# entry.py syncs this to /app/agent/ (volume mount) at container start
COPY agent/ /opt/agent-image/

# Install agent dependencies (skills may declare extra requirements)
RUN if [ -f /opt/agent-image/requirements.txt ]; then \
        pip install --no-cache-dir -r /opt/agent-image/requirements.txt; \
    fi

WORKDIR /app/agent

# /app/agent is the volume mount point (logs/, snapshots/, skills/data/ all persist)
VOLUME /app/agent

EXPOSE 8420

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8420/healthz')"

# tini as PID 1, entry.py as the container adapter
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "vessal.ark.shell.container.entry"]
