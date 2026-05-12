FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python, pip, and utilities
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /root

COPY 13f-2025-q4.zip /root/13f-2025-q4.zip
COPY 13f-2026-q1.zip /root/13f-2026-q1.zip
RUN mkdir /root/2025-q4
RUN mkdir /root/2026-q1

RUN unzip /root/13f-2025-q4.zip -d /root/2025-q4
RUN unzip /root/13f-2026-q1.zip -d /root/2026-q1

# Copy skills to agent-specific locations
# Claude Code
COPY skills /root/.claude/skills
# Codex
COPY skills /root/.codex/skills
# OpenCode
COPY skills /root/.opencode/skill
# Goose
COPY skills /root/.goose/skills
# Factory
COPY skills /root/.factory/skills
# Goose/Amp (portable agents format)
COPY skills /root/.agents/skills
# Gemini
COPY skills /root/.gemini/skills

RUN pip3 install --break-system-packages pandas==2.3.3 rapidfuzz==3.14.3
