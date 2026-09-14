FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# BearCode 持久化路径全部基于 cwd / HOME：
# WORKDIR 即 AGENT_HOME（启动时 chdir 到这里），HOME 同设，运行时目录挂 named volume
ENV HOME=/app/agent-home \
    AGENT_HOME=/app/agent-home \
    PORT=8003

COPY bear ./bear
COPY app ./app
# 预置领域 skills：agent-home/.bear/skills/<name>/SKILL.md
COPY agent-home ./agent-home

EXPOSE 8003

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
