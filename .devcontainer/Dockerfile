# Unified Development Container
# Contains: Node.js and Python
# Includes: Claude Code CLI + persistent auth

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install common build tools and dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    ca-certificates \
    software-properties-common \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# === Node.js (customize version as needed) ===
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# === Python (customize version as needed) ===
RUN add-apt-repository ppa:deadsnakes/ppa \
    && apt-get install -y \
        python3.13 \
        python3.13-venv \
        python3.13-dev \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1 \
    && python3 -m ensurepip --upgrade

# === Create development user ===
# Use UID 1000 to match typical host user (avoids permission issues with mounted volumes)
RUN useradd -m -u 1000 -s /bin/bash lifted \
    && mkdir -p /home/lifted/.local/bin \
    && mkdir -p /home/lifted/.claude \
    && touch /home/lifted/.bashrc \
    && touch /home/lifted/.bash_history \
    && chown -R lifted:lifted /home/lifted

# Switch to user for remaining setup
USER lifted
WORKDIR /workspaces/recyclable

# === Language tool setup (as user) ===
RUN python3 -m pip install --user --upgrade pip

# npm global prefix (must be set before npm install)
ENV npm_config_prefix=/home/lifted/.local
RUN npm install -g typescript-language-server typescript

# === Claude Code CLI (as non-root user) ===
RUN curl -fsSL https://claude.ai/install.sh | bash

# Verification
RUN echo "Node: $(node --version)" \
    && echo "npm: $(npm --version)" \
    && echo "Python: $(python3 --version)" \
    && echo "pip: $(pip --version)"

CMD ["/bin/bash"]
