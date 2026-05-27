---
name: dm-mcp-creator
description: 创建并注册项目专用的达梦 DM 数据库 MCP 服务。适用于用户希望 Codex 通过 MCP 连接达梦数据库、为不同项目创建 dm-product-icc 这类独立 profile、处理不同 schema 和密码环境变量、生成本地 stdio MCP 服务、或添加带安全限制的读写 SQL 工具（禁止 DDL、限制 UPDATE/DELETE 影响行数）等场景。
---

# 达梦 MCP 创建器

## 作用

使用这个技能，把用户提供的达梦数据库连接信息，转换成一个本地 stdio MCP 服务。Codex 后续可以通过这些工具访问数据库：

- `health_check`：测试连接
- `list_tables`：列出表
- `describe_table`：查看表字段
- `query_sql`：执行只读查询
- `execute_sql`：执行受保护的写 SQL

使用内置模板 `assets/dm-db-mcp-template/` 开始。默认流程必须先进入“检查模式”：读取项目配置、现有 MCP 注册项和模板状态，只输出创建计划与待确认信息。只有用户在看到计划后明确回复“确认创建”“执行注册”“可以写入”等等价授权，才能复制模板、写入 secrets、执行 `codex mcp add` 和做健康检查。

## 执行模式

### 默认检查模式

用户仅提到本技能、询问如何创建 MCP、或给出不完整连接信息时，只允许执行检查模式。检查模式可以读取本地项目配置、检查 JDBC jar 是否存在、检查 `.codex-mcp/` 是否存在、运行 `codex mcp list/get`，但不得产生任何文件或全局配置变更。

检查模式输出必须包含：

- 将要使用的 MCP 名称。
- 目标项目路径和模板目标目录。
- host、port、schema、用户名、JDBC jar 路径。
- 密码环境变量名和建议的 secrets 文件路径，但不得展示密码明文。
- 写操作策略：是否可写、允许的 SQL 类型、禁止 DDL、最大影响行数。
- 明确询问用户是否确认创建。

### 确认创建模式

只有用户在检查计划之后明确授权，才允许执行写入动作。允许的写入动作包括：

- 创建 `<project>/.codex-mcp/` 并复制模板。
- 设置 `run.sh` 可执行权限。
- 创建或修改 `~/.codex/secrets/<profile>.env`。
- 执行 `codex mcp add` 注册 MCP。
- 运行 stdio 健康检查。

如果用户只说“看看”“检查一下”“用这个技能”“有没有要改的地方”，必须停留在检查模式，不得自动创建或注册 MCP。

## 需要用户提供的信息

创建项目 profile 前，先收集这些字段：

```text
MCP 名称：dm-<默认生成项目名>
profile/项目标识：
达梦 JDBC 驱动 jar 绝对路径：/Users/pengshuaifeng/.m2/repository/com/dm/dm8-jdbc/1.8.0/dm8-jdbc-1.8.0.jar
host：8.138.127.55
port：18801
schema：
用户名：
密码环境变量名：建议给当前项目用独立环境变量
是否可写：true/false
允许写操作：INSERT, UPDATE, DELETE
是否禁止 DDL：true
单次最大影响行数：1000
目标项目路径：默认当前项目
```

不要让用户把数据库密码明文发到聊天里。每个项目使用独立密码环境变量，例如 `PRODUCT_ICC_DM_PASSWORD`。

如果项目配置文件里已经存在密码字段，只能说明“检测到配置文件存在密码字段，可在确认后迁移为环境变量”，不得把密码值输出到聊天，也不得在未确认时自动写入 `~/.codex/secrets/`。

## 密码处理

优先从 `~/.codex/secrets/*.env` 加载密钥。每个项目用不同变量名，避免互相覆盖。创建或修改 secrets 文件属于写入动作，必须等用户确认创建后才能执行：

```bash
mkdir -p ~/.codex/secrets
chmod 700 ~/.codex/secrets
```

密钥文件示例。示例中只能使用占位值，不要在回复中出现真实密码：

```bash
export PRODUCT_ICC_DM_PASSWORD='<password-placeholder>'
```

设置权限：

```bash
chmod 600 ~/.codex/secrets/product-icc.env
```

模板里的 `run.sh` 会自己加载 `~/.codex/secrets/*.env`，所以不依赖 Codex 主进程是否继承了终端环境变量。

## 创建 MCP 服务

以下命令只能在“确认创建模式”中执行。把模板复制到目标项目：

```bash
mkdir -p <project>/.codex-mcp
cp -R <skill>/assets/dm-db-mcp-template <project>/.codex-mcp/dm-db-mcp
chmod +x <project>/.codex-mcp/dm-db-mcp/run.sh
```

一般不要把连接信息写死到 Java 源码里。优先在注册 MCP 时用 `--env` 传入项目参数，这样同一套模板可以复用于多个项目：

```bash
codex mcp add dm-product-icc \
  --env DM_JDBC_JAR=/path/to/dm8-jdbc.jar \
  --env DM_MCP_HOST=8.138.127.55 \
  --env DM_MCP_PORT=18801 \
  --env DM_MCP_SCHEMA=PRODUCT_ICC \
  --env DM_MCP_USER=PRODUCT_ICC \
  --env DM_MCP_PASSWORD_ENV=PRODUCT_ICC_DM_PASSWORD \
  --env DM_MCP_WRITABLE=true \
  --env DM_MCP_MAX_AFFECTED_ROWS=1000 \
  -- <project>/.codex-mcp/dm-db-mcp/run.sh
```

注册另一个项目时，换一个 MCP 名称和密码环境变量：

```bash
codex mcp add dm-aiot-admin \
  --env DM_JDBC_JAR=/path/to/dm8-jdbc.jar \
  --env DM_MCP_SCHEMA=AIOT_ADMIN \
  --env DM_MCP_PASSWORD_ENV=AIOT_ADMIN_DM_PASSWORD \
  -- <project>/.codex-mcp/dm-db-mcp/run.sh
```

## 验证

完成创建后，先直接验证 stdio 服务能否启动并连接数据库。直接调用 `run.sh` 时需要显式传入与 `codex mcp add --env` 相同的非敏感环境变量；密码仍应由 `~/.codex/secrets/*.env` 加载：

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"health_check","arguments":{}}}' \
  | <project>/.codex-mcp/dm-db-mcp/run.sh
```

期望结果：

```text
ok: connected to <host>:<port>/<schema>
```

再检查 Codex 是否注册成功：

```bash
codex mcp list
codex mcp get <mcp-name>
```

如果当前 Codex 对话看不到新添加的 MCP 服务，提醒用户重启 Codex。只重启终端通常不够。

## 禁止自动化行为

- 禁止因为用户只输入技能名就自动复制模板、注册 MCP 或写 secrets。
- 禁止未确认时从项目配置提取密码并写入 `~/.codex/secrets/`。
- 禁止在聊天中展示数据库密码、完整敏感连接串或 secrets 文件内容。
- 禁止把数据库密码写入 `codex mcp add --env`，只能传入密码环境变量名。
- 禁止直接执行真实写 SQL；必须先 dry-run 或查询预览影响范围。

## 安全规则

除非用户明确要求改变策略并接受风险，否则保留这些保护：

- `query_sql` 只允许 `SELECT` 或 `WITH`。
- `execute_sql` 只允许 `INSERT`、`UPDATE`、`DELETE`。
- 拒绝 DDL 和权限类语句：`CREATE`、`ALTER`、`DROP`、`TRUNCATE`、`GRANT`、`REVOKE`、`MERGE`、`CALL`、`EXEC`、`COMMENT`。
- `UPDATE` 和 `DELETE` 必须带 `WHERE`。
- 如果影响行数超过 `DM_MCP_MAX_AFFECTED_ROWS`，必须回滚。
- 真正写数据前，先 dry-run 或先用查询 SQL 预览影响范围。
