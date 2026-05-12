FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    libreoffice \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install python packages with pinned versions
RUN pip3 install --break-system-packages \
    openpyxl==3.1.5 \
    pandas==2.2.3 \
    pdfplumber==0.11.4 \
    tabula-py==2.9.3 \
    PyPDF2==3.0.1 \
    reportlab==4.1.0 \
    python-docx==1.1.2 \
    python-pptx==1.0.2 \
    pytest

# Copy the pre-generated data files into the unsorted folder
RUN mkdir -p /root/documents/unsorted
COPY data/ /root/documents/unsorted/

# Copy skills to ALL agent paths
COPY skills /root/.claude/skills
COPY skills /root/.codex/skills
COPY skills /root/.opencode/skill
COPY skills /root/.goose/skills
COPY skills /root/.factory/skills
COPY skills /root/.agents/skills
COPY skills /root/.gemini/skills
