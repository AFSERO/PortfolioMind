# Stage 1: Install official Codex CLI in Node environment
FROM node:20-bookworm-slim AS node-base
RUN npm install -g @openai/codex@latest

# Stage 2: Python 3.12 runtime with minimal Node & Codex CLI
FROM python:3.12-slim

WORKDIR /app

# Install minimal OS utilities required for Codex CLI, network requests, and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Node runtime and global npm modules (including codex CLI) from node-base
COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules

# Create canonical executable symlinks in PATH
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex

# Install dependencies into system Python before source is mounted
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source so image is self-contained (used by CI / production builds)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
