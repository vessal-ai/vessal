# Vessal container Shell — Docker 容器就是蟹壳。
#
# 构建方式：vessal build [agent_dir]
# 运行方式：vessal run [name] --port 8420
#
# 构建上下文结构（由 vessal build 组装）：
#   vessal/     vessal 源码包
#   agent/      Agent 定义（SOUL.md · hull.toml · skills/）

FROM python:3.12-slim

# tini — PID 1 信号转发 + 僵尸进程回收
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

# 安装 vessal 运行时
COPY vessal/ /opt/vessal/
RUN pip install --no-cache-dir /opt/vessal/

# Agent 定义暂存到 /opt/agent-image/
# 运行时由 entry.py sync_image_to_volume() 同步到 /app/agent/（volume 挂载点）
COPY agent/ /opt/agent-image/

# 安装 Agent 依赖（skills 可能有额外依赖）
RUN if [ -f /opt/agent-image/requirements.txt ]; then \
        pip install --no-cache-dir -r /opt/agent-image/requirements.txt; \
    fi

WORKDIR /app/agent

# /app/agent 整体为 volume 挂载点（logs/、snapshots/、skills/data/ 均持久化）
VOLUME /app/agent

EXPOSE 8420

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8420/healthz')"

# tini 做 PID 1，entry.py 做容器适配器
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "vessal.ark.shell.container.entry"]
