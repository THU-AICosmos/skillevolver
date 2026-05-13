FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python, pip, and PDF tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /root

# Copy the blank patient intake form (Greenfield Medical Center MIF-200)
COPY intake-blank.pdf /root/intake-blank.pdf

# Install Python dependencies for PDF form filling
RUN pip3 install --break-system-packages \
    pypdf==5.1.0 \
    fillpdf==0.7.3 \
    pdfrw==0.4 \
    PyPDF2==3.0.1 \
    reportlab==4.2.5 \
    cryptography==43.0.3

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
# Portable agents format (Goose, Amp)
COPY skills /root/.agents/skills
# Gemini
COPY skills /root/.gemini/skills
