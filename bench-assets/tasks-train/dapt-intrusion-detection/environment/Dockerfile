FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    wget \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for network analysis
RUN pip3 install --break-system-packages \
    scapy==2.5.0 \
    pandas==2.2.2 \
    numpy==1.26.4

WORKDIR /root

# Copy data files
# Data source note: packets.pcap for the TRAIN variant is a synthetic cloud-tenant
# web-audit capture generated for exploration; it is NOT the DAPT2020 capture used
# for validation.
COPY packets.pcap /root/packets.pcap
COPY network_analysis_template.csv /root/network_analysis.csv

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
