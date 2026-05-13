FROM ubuntu:24.04

# SkillsBench train variant: Logistics PDDL planning environment.
# Parallels the val task's dependency stack so PDDLReader / PlanValidator /
# pyperplan behave identically across train and val.

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pin the same planning stack used by the validation task so plans parse
# identically between train and val.
RUN pip3 install --break-system-packages \
    requests==2.32.3 \
    bibtexparser==1.4.2 \
    pyyaml==6.0.3 \
    numpy==2.4.1 \
    pyperplan==2.1 \
    unified_planning==1.3.0 \
    up-pyperplan==1.1.0

COPY problem.json /app/problem.json
COPY logistics /app/logistics
