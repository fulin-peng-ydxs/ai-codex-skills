import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "sync_codex_config.py"
)
SPEC = importlib.util.spec_from_file_location("sync_codex_config", SCRIPT_PATH)
assert SPEC and SPEC.loader
SYNC_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SYNC_MODULE
SPEC.loader.exec_module(SYNC_MODULE)


class DiscoverSkillsTest(unittest.TestCase):
    def test_codex_only_skills_excluded_from_sync_and_cleanup(self):
        for identity in ["automation-management", "config-codex-sync"]:
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, target = root / "source", root / "target"
                for base in [source, target]:
                    base.mkdir()
                    for name in [identity, "portable", "alias"]:
                        folder = base / name
                        folder.mkdir()
                        skill_name = identity if name == "alias" else name
                        (folder / "SKILL.md").write_text(f"---\nname: '{skill_name}'\ndescription: Codex workflow\n---\n")
                    (base / f"{identity}.md").write_text(f"---\nname: {identity}\ndescription: test\n---\n")
                (target / identity / "old.txt").write_text("keep")
                included, excluded = SYNC_MODULE.discover_skills(source)
                self.assertEqual(["portable"], [p.name for p in included])
                self.assertEqual({identity, f"{identity}.md", "alias"}, {p.name for p in excluded})
                self.assertEqual([], SYNC_MODULE.plan_deletions(source, target))

    def test_excludes_all_mcp_skill_types(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            skills_root = Path(temporary_directory)
            included_names = ("database-client", "regular-skill")
            excluded_names = (
                "config-project-mcp-sync",
                "dm-mcp-creator",
                "mcp-audit",
                "mcp-generator",
                "mcp-monitor",
                "mcp-security",
                "ordinary-mcp-client",
                "synchronize_mcp_profile",
            )

            for name in included_names + excluded_names:
                skill_directory = skills_root / name
                skill_directory.mkdir()
                (skill_directory / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: test\n---\n",
                    encoding="utf-8",
                )

            skills, excluded_skills = SYNC_MODULE.discover_skills(skills_root)

            self.assertEqual([skill.name for skill in skills], list(included_names))
            self.assertEqual(
                [skill.name for skill in excluded_skills],
                list(excluded_names),
            )

    def test_excludes_skill_identified_as_mcp_in_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            skills_root = Path(temporary_directory)
            skill_directory = skills_root / "protocol-tool"
            skill_directory.mkdir()
            (skill_directory / "SKILL.md").write_text(
                "---\n"
                "name: protocol-tool\n"
                "description: Audit and monitor MCP servers\n"
                "---\n",
                encoding="utf-8",
            )

            skills, excluded_skills = SYNC_MODULE.discover_skills(skills_root)

            self.assertEqual(skills, [])
            self.assertEqual(excluded_skills, [skill_directory])

    def test_excludes_single_file_mcp_sync_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            skills_root = Path(temporary_directory)
            skill_file = skills_root / "mcp-sync.md"
            skill_file.write_text(
                "---\nname: mcp-sync\ndescription: test\n---\n",
                encoding="utf-8",
            )

            skills, excluded_skills = SYNC_MODULE.discover_skills(skills_root)

            self.assertEqual(skills, [])
            self.assertEqual(excluded_skills, [skill_file])



class DeleteSyncTest(unittest.TestCase):
    def test_preview_default_delete_and_protected_entries(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            def skill(base, name):
                path = base / 'skills' / name
                path.mkdir(parents=True)
                (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: test\n---\n')
                return path
            keep = skill(source, 'keep')
            (source / 'AGENTS.md').write_text('rules')
            target_keep = skill(target, 'keep')
            (target_keep / 'obsolete.txt').write_text('old')
            old = skill(target, 'retired')
            protected = skill(target, 'protected')
            (protected / '.git').mkdir()
            (protected / '.git' / 'config').write_text('preserve')
            mcp = skill(target, 'setup-mcp')
            (target / 'skills' / 'README.md').write_text('index')
            outside = root / 'outside'; outside.mkdir()
            (outside / 'data').write_text('preserve')
            (target_keep / 'link').symlink_to(outside, target_is_directory=True)
            command = [sys.executable, str(SCRIPT_PATH), '--target', 'claude', '--codex-root', str(source), '--claude-root', str(target)]
            def run(*args):
                result = subprocess.run(command + list(args), capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                return result.stdout
            (keep / 'obsolete.txt').write_text('old')
            run()
            (keep / 'obsolete.txt').unlink()
            preview = run('--delete', '--dry-run')
            self.assertNotIn(str(old / 'SKILL.md'), preview)
            self.assertIn(str(target_keep / 'obsolete.txt'), preview)
            self.assertTrue(old.exists())
            self.assertTrue((target / 'CLAUDE.md').exists())
            run()
            self.assertTrue(old.exists())
            run('--delete')
            self.assertTrue((old / 'SKILL.md').exists())
            self.assertTrue((protected / 'SKILL.md').exists())
            self.assertFalse((target_keep / 'obsolete.txt').exists())
            self.assertTrue((mcp / 'SKILL.md').exists())
            self.assertTrue((protected / '.git' / 'config').exists())
            self.assertTrue((outside / 'data').exists())
            self.assertTrue((target_keep / 'link').is_symlink())
            self.assertTrue((target / 'skills' / 'README.md').exists())
            self.assertEqual([], SYNC_MODULE.plan_deletions(source / 'skills', target / 'skills'))

    def test_empty_source_and_conflict_do_not_delete(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; target = root / 'target'
            (source / 'skills').mkdir(parents=True)
            (source / 'AGENTS.md').write_text('rules')
            old = target / 'skills' / 'old'; old.mkdir(parents=True)
            (old / 'SKILL.md').write_text('---\nname: old\ndescription: test\n---\n')
            command = [sys.executable, str(SCRIPT_PATH), '--target', 'claude', '--codex-root', str(source), '--claude-root', str(target), '--delete']
            self.assertNotEqual(0, subprocess.run(command, capture_output=True).returncode)
            keep = source / 'skills' / 'keep'; keep.mkdir()
            (keep / 'SKILL.md').write_text('---\nname: keep\ndescription: test\n---\n')
            (target / 'skills' / 'keep').write_text('conflict')
            self.assertNotEqual(0, subprocess.run(command, capture_output=True).returncode)
            self.assertTrue((old / 'SKILL.md').exists())
            self.assertFalse((target / 'CLAUDE.md').exists())

    def test_single_file_and_source_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'; target = root / 'target'
            source.mkdir(); target.mkdir()
            def entry(base, name, description='test'):
                path = base / name
                path.write_text(f'---\nname: sample\ndescription: {description}\n---\n')
                return path
            stale = entry(target, 'old.md')
            entry(target, 'mcp.md', 'MCP tool')
            entry(target, 'excluded.md')
            entry(source, 'excluded.md', 'MCP tool')
            entry(target, 'kept.md'); entry(source, 'kept.md')
            (target / 'notes.txt').write_text('unmanaged')
            self.assertEqual([], SYNC_MODULE.plan_deletions(source, target))
            self.assertTrue(stale.exists())

    def test_reject_nested_and_symlink_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'source'
            (source / 'skills').mkdir(parents=True)
            (source / 'AGENTS.md').write_text('rules')
            for target in [root, source / 'child', source]:
                with self.assertRaises(SYNC_MODULE.SyncError):
                    SYNC_MODULE.validate_paths(source, [('Claude', target)])
            target = root / 'target'; target.mkdir()
            (target / 'skills').symlink_to(source / 'skills', target_is_directory=True)
            with self.assertRaises(SYNC_MODULE.SyncError):
                SYNC_MODULE.validate_paths(source, [('Claude', target)])


class ManagedRetirementTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.target = self.root / 'source', self.root / 'target'
        (self.source / 'skills').mkdir(parents=True)
        (self.source / 'AGENTS.md').write_text('rules')
        self.skill(self.source, 'keep')

    def skill(self, root, name):
        path = root / 'skills' / name
        path.mkdir(parents=True, exist_ok=True)
        (path / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: test\n---\n')
        return path

    def run_sync(self, *args, code=0, source=None):
        import subprocess
        result = subprocess.run([sys.executable, str(SCRIPT_PATH), '--target', 'claude', '--codex-root', str(source or self.source), '--claude-root', str(self.target), *args], capture_output=True, text=True)
        self.assertEqual(code, result.returncode, result.stdout + result.stderr)
        return result.stdout

    def state(self):
        import json
        return json.loads((self.target / SYNC_MODULE.STATE_FILE).read_text())

    def test_lifecycle_preview_incremental_retirement_and_idempotence(self):
        import shutil
        old = self.skill(self.source, 'old')
        independent = self.skill(self.target, 'independent')
        self.run_sync('--dry-run')
        self.assertFalse((self.target / SYNC_MODULE.STATE_FILE).exists())
        self.run_sync()
        self.assertIn('old', self.state()['managed'])
        self.assertNotIn('independent', self.state()['managed'])
        shutil.rmtree(old)
        self.run_sync()  # Missing-source ownership must survive incremental runs.
        self.assertIn('old', self.state()['managed'])
        self.run_sync('--delete', '--dry-run')
        self.assertTrue((self.target / 'skills/old').exists())
        self.run_sync('--delete')
        self.assertFalse((self.target / 'skills/old').exists())
        self.assertTrue(independent.exists())
        self.assertNotIn('old', self.state()['managed'])
        self.run_sync('--delete')

    def test_modified_and_added_files_block_whole_skill_retirement(self):
        import shutil
        old = self.skill(self.source, 'old')
        self.run_sync()
        baseline = self.state()['managed']['old']
        shutil.rmtree(old)
        target = self.target / 'skills/old'
        (target / 'SKILL.md').write_text('customized')
        self.run_sync('--delete', code=2)
        self.assertEqual(baseline, self.state()['managed']['old'])
        self.assertEqual('customized', (target / 'SKILL.md').read_text())
        (target / 'SKILL.md').write_text('---\nname: old\ndescription: test\n---\n')
        (target / 'extra').write_text('user data')
        self.run_sync('--delete', code=2)
        self.assertTrue((target / 'extra').exists())

    def test_modified_removed_file_keeps_baseline_for_retry(self):
        src = self.source / 'skills/keep/file'
        src.write_text('baseline')
        self.run_sync()
        src.unlink()
        dst = self.target / 'skills/keep/file'
        dst.write_text('user edit')
        self.run_sync('--delete', code=2)
        self.assertEqual('user edit', dst.read_text())
        dst.write_text('baseline')
        self.run_sync('--delete')
        self.assertFalse(dst.exists())

    def test_partial_adapter_does_not_retire_unselected_skill(self):
        import shutil
        self.skill(self.source, 'other')
        self.run_sync()
        adapter = self.root / 'adapter'
        (adapter / 'skills').mkdir(parents=True)
        shutil.copytree(self.source / 'skills/keep', adapter / 'skills/keep')
        shutil.copy2(self.source / 'AGENTS.md', adapter / 'AGENTS.md')
        self.run_sync('--origin-root', str(self.source), '--delete', source=adapter, code=1)
        self.run_sync('--origin-root', str(self.source), '--partial', '--delete', source=adapter)
        self.assertTrue((self.target / 'skills/other').exists())
        self.assertIn('other', self.state()['managed'])

    def test_state_identity_corruption_and_path_traversal_fail_closed(self):
        import json
        self.run_sync()
        path = self.target / SYNC_MODULE.STATE_FILE
        original = self.state()
        path.write_text('{bad json')
        self.run_sync('--delete', code=1)
        original['managed']['../outside'] = {'.': 'dir'}
        path.write_text(json.dumps(original))
        self.run_sync('--delete', code=1)
        del original['managed']['../outside']
        original['origin'] = '/different-source'
        path.write_text(json.dumps(original))
        self.run_sync('--delete', code=1)

    def test_explicit_retirement_requires_matching_snapshot(self):
        dest = self.skill(self.target, 'retired')
        snapshot = SYNC_MODULE.tree_snapshot(dest)
        registry = {'retired': {'baselines': [{'snapshot': snapshot}]}}
        state = {'managed': {}}
        plan, conflicts, retired, _ = SYNC_MODULE.managed_deletions(self.source / 'skills', self.target / 'skills', state, registry, False)
        self.assertFalse(conflicts)
        self.assertIn(dest, plan)
        self.assertEqual({'retired'}, retired)
        (dest / 'extra').write_text('keep')
        plan, conflicts, _, _ = SYNC_MODULE.managed_deletions(self.source / 'skills', self.target / 'skills', state, registry, False)
        self.assertFalse(plan)
        self.assertTrue(conflicts)

    def test_filtered_origin_entry_is_not_mistaken_for_retirement(self):
        origin = self.root / 'origin'
        self.skill(origin, 'previously-portable')
        dest = self.skill(self.target, 'previously-portable')
        state = {'managed': {'previously-portable': SYNC_MODULE.tree_snapshot(dest)}}
        # The adapted source omits the now-excluded entry; the canonical source still has it.
        plan, conflicts, retired, _ = SYNC_MODULE.managed_deletions(self.source / 'skills', self.target / 'skills', state, {}, False, origin / 'skills')
        self.assertFalse(plan)
        self.assertFalse(conflicts)
        self.assertFalse(retired)

    def test_excluded_skill_is_never_retired(self):
        for name in ['setup-mcp', 'automation-management', 'config-codex-sync']:
            dest = self.skill(self.target, name)
            state = {'managed': {name: SYNC_MODULE.tree_snapshot(dest)}}
            plan, conflicts, retired, _ = SYNC_MODULE.managed_deletions(self.source / 'skills', self.target / 'skills', state, {}, False)
            self.assertFalse(plan)
            self.assertFalse(conflicts)
            self.assertNotIn(name, retired)

if __name__ == "__main__":
    unittest.main()
