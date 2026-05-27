#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$BASE_DIR/build/classes"
DM_JDBC_JAR="${DM_JDBC_JAR:-}"

SECRETS_DIR="$HOME/.codex/secrets"
if [ -d "$SECRETS_DIR" ]; then
  for env_file in "$SECRETS_DIR"/*.env; do
    [ -r "$env_file" ] && source "$env_file"
  done
fi

if [ ! -f "$DM_JDBC_JAR" ]; then
  echo "DM_JDBC_JAR is not set or the file does not exist: $DM_JDBC_JAR" >&2
  exit 1
fi

if [ ! -f "$BUILD_DIR/com/gzzn/mcp/dmdb/DmDbMcpServer.class" ] || [ "$BASE_DIR/src/main/java/com/gzzn/mcp/dmdb/DmDbMcpServer.java" -nt "$BUILD_DIR/com/gzzn/mcp/dmdb/DmDbMcpServer.class" ]; then
  mkdir -p "$BUILD_DIR"
  javac -encoding UTF-8 -cp "$DM_JDBC_JAR" -d "$BUILD_DIR" "$BASE_DIR/src/main/java/com/gzzn/mcp/dmdb/DmDbMcpServer.java"
fi

exec java -cp "$BUILD_DIR:$DM_JDBC_JAR" com.gzzn.mcp.dmdb.DmDbMcpServer
