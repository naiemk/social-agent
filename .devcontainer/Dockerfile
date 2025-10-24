FROM mcr.microsoft.com/devcontainers/typescript-node:1-22-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-full \
    python3-yaml \
    curl \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

USER node

# install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
# Ensure the installed binary is on the `PATH`
RUN /home/node/.local/bin/uv python install python3.11
RUN cd /home/node && /home/node/.local/bin/uv python pin python3.11

# Install Node package managers
RUN npm install -g yarn \
    && npm install -g hardhat bun \
    && curl -fsSL https://bun.sh/install | bash

# Set up custom prompt
RUN echo 'alias nh="npx hardhat"' >> /home/node/.bashrc
RUN echo 'alias nhc="clear && npx hardhat compile"' >> /home/node/.bashrc
RUN echo 'alias nht="clear && npx hardhat test"' >> /home/node/.bashrc
RUN echo 'alias urp="clear && uv run python"' >> /home/node/.bashrc
RUN echo 'alias c="clear"' >> /home/node/.bashrc

# Set working directory
WORKDIR /workspace

# Switch to node user
