import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "sync_project_mcp.py"


class SyncProjectMcpTest(unittest.TestCase):
    def run_sync(self, project: Path, config: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--project",
                str(project),
                "--config",
                str(config),
                "--no-validate",
                *extra_args,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_registers_command_and_stdio_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            run_sh = project / "mcp" / "run.sh"
            run_sh.parent.mkdir()
            run_sh.write_text("#!/bin/sh\n", encoding="utf-8")
            (project / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "database": {
                                "command": "./mcp/run.sh",
                                "args": ["--mode", "readonly"],
                                "env": {"DB_HOST": "127.0.0.1", "DB_PORT": 5236},
                                "env_vars": ["DB_PASSWORD"],
                                "cwd": "./mcp",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = root / "config.toml"
            config.write_text('model = "gpt-test"\n', encoding="utf-8")

            result = self.run_sync(project, config)

            self.assertEqual(result.returncode, 0, result.stderr)
            registered = tomllib.loads(config.read_text(encoding="utf-8"))["mcp_servers"]["database"]
            self.assertEqual(registered["command"], str(run_sh.resolve()))
            self.assertEqual(registered["args"], ["--mode", "readonly"])
            self.assertEqual(registered["env"], {"DB_HOST": "127.0.0.1", "DB_PORT": "5236"})
            self.assertEqual(registered["env_vars"], ["DB_PASSWORD"])
            self.assertEqual(registered["cwd"], str(run_sh.parent.resolve()))
            self.assertNotIn("127.0.0.1", result.stdout)

    def test_updates_parameters_and_preserves_codex_options_and_unrelated_servers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            run_sh = project / "run.sh"
            run_sh.write_text("#!/bin/sh\n", encoding="utf-8")
            (project / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "database": {
                                "command": str(run_sh),
                                "env": {"DB_SCHEMA": "AIOT"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = root / "config.toml"
            config.write_text(
                (
                    "[mcp_servers.database]\n"
                    f'command = "{run_sh}"\n'
                    'args = ["--stale"]\n'
                    "enabled = false\n"
                    "\n"
                    "[mcp_servers.database.env]\n"
                    'DB_SCHEMA = "OLD"\n'
                    "\n"
                    "[mcp_servers.unrelated]\n"
                    'command = "npx"\n'
                    'args = ["server"]\n'
                ),
                encoding="utf-8",
            )

            result = self.run_sync(project, config)

            self.assertEqual(result.returncode, 0, result.stderr)
            parsed = tomllib.loads(config.read_text(encoding="utf-8"))["mcp_servers"]
            self.assertEqual(parsed["database"]["env"], {"DB_SCHEMA": "AIOT"})
            self.assertNotIn("args", parsed["database"])
            self.assertFalse(parsed["database"]["enabled"])
            self.assertEqual(parsed["unrelated"]["args"], ["server"])
            self.assertEqual(len(list(root.glob("config.toml.bak-sync-project-mcp-*"))), 1)

    def test_dry_run_does_not_write_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "project"
            project.mkdir()
            (project / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "database": {
                                "command": "npx",
                                "args": ["server-package"],
                                "env": {"TOKEN": "secret"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = root / "config.toml"
            original = 'model = "gpt-test"\n'
            config.write_text(original, encoding="utf-8")

            result = self.run_sync(project, config, "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(config.read_text(encoding="utf-8"), original)
            self.assertNotIn("secret", result.stdout)

    def test_shared_launcher_preserves_all_candidates_and_unrelated_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            servers = {name: {"command": "npx", "args": [f"package-{name}"]}
                       for name in ("alpha", "beta", "my_db", "my-db")}
            (project / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))
            config = root / "config.toml"
            config.write_text('[mcp_servers.unrelated]\ncommand = "npx"\nargs = ["preserve"]\n')
            for _ in range(2):
                result = self.run_sync(project, config)
                self.assertEqual(0, result.returncode, result.stderr)
                registered = tomllib.loads(config.read_text())["mcp_servers"]
                self.assertEqual(set(servers) | {"unrelated"}, set(registered))
                self.assertEqual(["preserve"], registered["unrelated"]["args"])
                for name, settings in servers.items():
                    self.assertEqual(settings, registered[name])
                    self.assertIn(f"- {name}: npx [", result.stdout)
                self.assertNotIn("- unrelated:", result.stdout)
            self.assertIn("没有需要注册或更新", result.stdout)

    def test_name_collision_is_stable_and_preserves_http_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / ".mcp.json").write_text(json.dumps({"mcpServers": {
                "database": {"command": "npx", "args": ["new"]},
                "project-database": {"command": "npx", "args": ["separate"]},
            }}))
            config = root / "config.toml"
            config.write_text('[mcp_servers.database]\nurl = "https://example.invalid/mcp"\n')
            for _ in range(2):
                result = self.run_sync(project, config)
                self.assertEqual(0, result.returncode, result.stderr)
                servers = tomllib.loads(config.read_text())["mcp_servers"]
                self.assertEqual(3, len(servers))
                self.assertEqual("https://example.invalid/mcp", servers["database"]["url"])
                self.assertEqual(["new"], servers["project-database-2"]["args"])
                self.assertEqual(["separate"], servers["project-database"]["args"])

    def test_json_declaration_overrides_only_duplicate_run_script_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / ".codex-mcp/db/run.sh"
            script.parent.mkdir(parents=True)
            script.write_text("#!/bin/sh\n")
            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {
                "db": {"command": str(script), "args": ["configured"]},
                "db-readonly": {"command": str(script), "args": ["readonly"]},
            }}))
            config = root / "config.toml"
            config.write_text("")
            result = self.run_sync(root, config)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({"db", "db-readonly"}, set(tomllib.loads(config.read_text())["mcp_servers"]))

    def test_actual_cli_diagnostics_never_echo_remote_secrets(self):
        secret = "FAKE_AUDIT_SECRET_ONLY"
        for mode in ("initialize", "tools/list", "stderr", "malformed", "bad-cwd"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                server = root / "server.py"
                server.write_text(
                    "import sys, json, os, time\n"
                    "mode = sys.argv[1]\n"
                    "for line in sys.stdin:\n"
                    " req = json.loads(line)\n"
                    " if mode == 'stderr':\n"
                    "  sys.stderr.write(os.environ['TOKEN'] * 20000); sys.stderr.flush(); sys.exit(7)\n"
                    " if mode == 'malformed':\n"
                    "  print(os.environ['TOKEN'], flush=True); time.sleep(2); break\n"
                    " response = {'jsonrpc':'2.0','id':req['id'],'result':{}}\n"
                    " if req['method'] == mode:\n"
                    "  response = {'error':{'code':-32001,'message':os.environ['TOKEN'],'data':os.environ['TOKEN']}}\n"
                    " print(json.dumps(response), flush=True)\n"
                )
                settings = {"command": sys.executable, "args": [str(server), mode], "env": {"TOKEN": secret}}
                if mode == "bad-cwd":
                    settings["cwd"] = str(root / "missing")
                (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"sample": settings}}))
                config = root / "config.toml"
                config.write_text("")
                result = subprocess.run([sys.executable, str(SCRIPT), "--project", str(root),
                                         "--config", str(config), "--timeout", "0.5"],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertNotIn(secret, result.stdout + result.stderr)
                self.assertIn("sample: 失败", result.stdout)
                if mode in ("initialize", "tools/list"):
                    self.assertIn(f"{mode}：服务返回错误（错误码=-32001）", result.stdout)

    def test_handshake_validates_each_service_sharing_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / "server.py"
            server.write_text(
                "import sys,json\n"
                "for line in sys.stdin:\n"
                " req=json.loads(line)\n"
                " print(json.dumps({'id':req['id'],'result':{'tools':[{}]*int(sys.argv[1])}}),flush=True)\n"
            )
            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {
                name: {"command": sys.executable, "args": [str(server), str(count)]}
                for name, count in (("one", 1), ("two", 2))
            }}))
            config = root / "config.toml"
            config.write_text("")
            result = subprocess.run([sys.executable, str(SCRIPT), "--project", str(root),
                                     "--config", str(config)], capture_output=True, text=True, timeout=5)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("one: 通过 (1 个工具)", result.stdout)
            self.assertIn("two: 通过 (2 个工具)", result.stdout)

    def test_generated_prefix_and_numeric_names_never_share_a_registration(self):
        for existing_args in (None, "first-service", "unowned-service"):
            with self.subTest(existing_args=existing_args), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project = root / "project"
                project.mkdir()
                (project / ".mcp.json").write_text(json.dumps({"mcpServers": {
                    name: {"command": "npx", "args": [arg]}
                    for name, arg in (("db", "first-service"), ("db-2", "second-service"))
                }}))
                config = root / "config.toml"
                original = ''.join(f'[mcp_servers.{name}]\ncommand="python3"\nargs=["preserve"]\n'
                                   for name in ("db", "db-2", "project-db"))
                if existing_args:
                    original += f'[mcp_servers.project-db-2]\ncommand="npx"\nargs=["{existing_args}"]\n'
                config.write_text(original)
                result = self.run_sync(project, config)
                if existing_args == "unowned-service":
                    self.assertEqual(2, result.returncode)
                    self.assertIn("归属不唯一", result.stderr)
                    self.assertEqual(original, config.read_text())
                    self.assertFalse(list(root.glob("*.bak-*")))
                    continue
                for iteration in range(2):
                    self.assertEqual(0, result.returncode, result.stderr)
                    servers = tomllib.loads(config.read_text())["mcp_servers"]
                    active = {name: item for name, item in servers.items() if item["command"] == "npx"}
                    self.assertEqual(2, len(active))
                    self.assertEqual({"first-service", "second-service"}, {item["args"][0] for item in active.values()})
                    for name in active:
                        self.assertEqual(1, result.stdout.count(f"- {name}: npx ["))
                    if iteration == 0:
                        before = config.read_bytes()
                        result = self.run_sync(project, config)
                        self.assertEqual(before, config.read_bytes())

    def test_legacy_normalized_names_are_reused_without_duplicate_registration(self):
        for legacy_name in ("my-db", "my-project-my-db", "my-project-my-db-10"):
            with self.subTest(legacy_name=legacy_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project = root / "my_project"
                project.mkdir()
                declaration = {"command": "npx", "args": ["updated-package"]}
                (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"my_db": declaration}}))
                config = root / "config.toml"
                config.write_text(f'[mcp_servers.{legacy_name}]\ncommand="npx"\nargs=["old-package"]\nenabled=false\n')
                for _ in range(2):
                    result = self.run_sync(project, config)
                    self.assertEqual(0, result.returncode, result.stderr)
                    servers = tomllib.loads(config.read_text())["mcp_servers"]
                    self.assertEqual({legacy_name}, set(servers))
                    self.assertEqual(["updated-package"], servers[legacy_name]["args"])
                    self.assertFalse(servers[legacy_name]["enabled"])

    def test_ambiguous_legacy_alias_fails_before_backup_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {
                name: {"command": "npx", "args": ["same-package"]} for name in ("my_db", "my-db")
            }}))
            config = root / "config.toml"
            original = '[mcp_servers.my-db]\ncommand="npx"\nargs=["same-package"]\n'
            config.write_text(original)
            result = self.run_sync(root, config)
            self.assertEqual(2, result.returncode)
            self.assertIn("历史注册名称归属冲突", result.stderr)
            self.assertEqual(original, config.read_text())
            self.assertFalse(list(root.glob("*.bak-*")))

    def test_closed_stdin_cleanup_preserves_failure_and_continues_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            closed = root / "closed.py"
            closed.write_text(
                "import sys,os,time,json\n"
                "req=json.loads(sys.stdin.readline())\n"
                "os.close(0)\n"
                "print(json.dumps({'id':req['id'],'result':{}}),flush=True)\n"
                "time.sleep(20)\n"
            )
            healthy = root / "healthy.py"
            healthy.write_text(
                "import sys,json\n"
                "for line in sys.stdin:\n"
                " req=json.loads(line)\n"
                " print(json.dumps({'id':req['id'],'result':{'tools':[]}}),flush=True)\n"
            )
            (root / ".mcp.json").write_text(json.dumps({"mcpServers": {
                "a-closed": {"command": sys.executable, "args": [str(closed)]},
                "z-healthy": {"command": sys.executable, "args": [str(healthy)]},
            }}))
            config = root / "config.toml"
            config.write_text("")
            result = subprocess.run([sys.executable, str(SCRIPT), "--project", str(root),
                                     "--config", str(config), "--timeout", "0.5"],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("a-closed: 失败 (tools/list：", result.stdout)
            self.assertIn("z-healthy: 通过 (0 个工具)", result.stdout)


if __name__ == "__main__":
    unittest.main()
