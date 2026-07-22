#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$BASE_DIR/build/classes"
DM_JDBC_JAR="${DM_JDBC_JAR:-}"
DM_MCP_SECRET_FILE="${DM_MCP_SECRET_FILE:-}"

# 每个 MCP Profile 只能加载自己的密钥文件，避免公共 secrets 目录中的连接参数互相覆盖。
# 主机、端口、Schema、用户和 SQL 策略由 Codex 注册环境提供，密钥文件只负责导出密码变量。
if [ -n "$DM_MCP_SECRET_FILE" ]; then
  if [ ! -r "$DM_MCP_SECRET_FILE" ]; then
    echo "DM_MCP_SECRET_FILE is not readable: $DM_MCP_SECRET_FILE" >&2
    exit 1
  fi
  source "$DM_MCP_SECRET_FILE"
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
