#!/bin/bash

# Ensure ~/.claude/settings.json exists on the host before Docker bind-mounts it.
# If the file doesn't exist, Docker creates it as a directory instead, breaking Claude Code.
SETTINGS_FILE="$HOME/.claude/settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
  mkdir -p "$(dirname "$SETTINGS_FILE")"
  echo '{}' > "$SETTINGS_FILE"
  echo "Created empty $SETTINGS_FILE -- configure your Claude Code settings here."
fi

# Create empty bashrc if it doesn't exist (so Docker doesn't create it as a directory)
BASHRC_FILE="$HOME/.container-bashrc"
if [ ! -f "$BASHRC_FILE" ]; then
  touch "$BASHRC_FILE"
  echo "Created $BASHRC_FILE"
fi

# === Install project-specific dependencies ===

# Backend (Python worker)
if [ -f /workspaces/recyclable/backend/requirements.txt ]; then
  cd /workspaces/recyclable/backend && pip3 install --user -r requirements.txt
fi

# Frontend (Next.js)
if [ -f /workspaces/recyclable/frontend/package.json ]; then
  cd /workspaces/recyclable/frontend && npm install
fi
