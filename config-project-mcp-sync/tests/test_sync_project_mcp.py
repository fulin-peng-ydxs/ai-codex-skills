import json
import subprocess
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


if __name__ == "__main__":
    unittest.main()
