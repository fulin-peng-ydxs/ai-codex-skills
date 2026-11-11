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

    def system_dependency(self, name='skill-creator'):
        dependent = self.source / 'skills/keep/SKILL.md'
        dependent.write_text(dependent.read_text() + f'\n[provider](../.system/{name}/SKILL.md#initialize)\n')
        provider = self.skill(self.source, '.system/' + name)
        entry = provider / 'SKILL.md'
        entry.write_text(entry.read_text().replace(f'name: .system/{name}', f'name: {name}') + '\nDefault: `$CODEX_HOME/skills`, or `~/.codex/skills` when `CODEX_HOME` is unset.\n'
                         'scripts/init_skill.py example --path "${CODEX_HOME:-$HOME/.codex}/skills"\n')
        (provider / 'scripts').mkdir()
        (provider / 'scripts/init_skill.py').write_text('print("initializer")\n')
        return provider

    def test_system_dependency_adapted_for_supported_selectors_without_source_changes(self):
        provider = self.system_dependency()
        dependent_source = self.source / 'skills/keep/SKILL.md'
        dependent_source.write_text(dependent_source.read_text() +
                                    '\npython3 <skills-root>/.system/skill-creator/scripts/init_skill.py\n')
        source_before = SYNC_MODULE.tree_snapshot(self.source)
        self.target = self.root / 'claude target'
        preview = self.run_sync('--dry-run')
        self.assertIn('skill-creator', preview)
        self.assertFalse(self.target.exists())
        for selector in ['claude', 'all']:
            self.run_sync('--target', selector)
            dependent = self.target / 'skills/keep/SKILL.md'
            self.assertIn(str(provider / 'SKILL.md') + '#initialize', dependent.read_text())
            self.assertFalse((self.target / 'skills/skill-creator').exists())
            self.assertFalse((self.target / 'skills/.system').exists())
            import shlex
            import subprocess
            command = dependent.read_text().splitlines()[-1]
            result = subprocess.run(shlex.split(command), cwd=self.target, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual('initializer', result.stdout.strip())
        self.assertEqual(source_before, SYNC_MODULE.tree_snapshot(self.source))
        self.assertNotIn('skill-creator', self.state()['managed'])
        self.assertIn('更新 0、未变化 1', self.run_sync('--dry-run'))

    def test_default_sync_is_single_target_and_unknown_selectors_fail_before_writes(self):
        """The CLI default and compatibility alias must share one destination."""
        import subprocess
        command = [sys.executable, str(SCRIPT_PATH), '--codex-root', str(self.source),
                   '--claude-root', str(self.target)]
        rejected = subprocess.run(command + ['--target', 'unsupported'], capture_output=True, text=True)
        self.assertEqual(2, rejected.returncode)
        self.assertFalse(self.target.exists())
        completed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertTrue((self.target / 'CLAUDE.md').is_file())
        self.assertEqual({self.source, self.target}, set(self.root.iterdir()))

    def test_missing_system_dependency_fails_before_writing_any_target(self):
        import shutil
        provider = self.system_dependency()
        shutil.rmtree(provider)
        for options in [('--dry-run',), ()]:
            self.run_sync(*options, code=1)
            self.assertFalse(self.target.exists())

    def test_other_system_dependencies_are_external_and_never_copied(self):
        provider = self.system_dependency('another-provider')
        self.run_sync()
        self.assertIn(str(provider / 'SKILL.md'), (self.target / 'skills/keep/SKILL.md').read_text())
        self.assertEqual({'keep'}, set(self.state()['managed']))
        self.assertEqual({'keep'}, {p.name for p in (self.target / 'skills').iterdir()})

    def test_external_dependency_does_not_touch_same_named_target(self):
        self.system_dependency()
        (self.target / 'skills').mkdir(parents=True)
        (self.target / 'skills/skill-creator').write_text('preserve')
        self.run_sync('--target', 'all')
        self.assertTrue((self.target / 'skills/keep').exists())
        self.assertNotIn('skill-creator', self.state()['managed'])
        self.assertEqual('preserve', (self.target / 'skills/skill-creator').read_text())

    def test_partial_staging_resolves_system_dependency_from_origin(self):
        import shutil
        self.system_dependency()
        self.skill(self.source, 'unselected')
        adapter = self.root / 'adapter'
        shutil.copytree(self.source / 'skills/keep', adapter / 'skills/keep')
        shutil.copy2(self.source / 'AGENTS.md', adapter / 'AGENTS.md')
        self.run_sync('--origin-root', str(self.source), '--partial', source=adapter)
        self.assertIn(str(self.source / 'skills/.system/skill-creator/SKILL.md'),
                      (self.target / 'skills/keep/SKILL.md').read_text())
        self.assertFalse((self.target / 'skills/skill-creator').exists())
        self.assertFalse((self.target / 'skills/unselected').exists())
        self.assertFalse((self.target / 'CLAUDE.md').exists())

    def test_dependency_retirement_uses_existing_management_baseline(self):
        import json
        # A copy managed by an older version remains governed by its baseline;
        # switching to external references alone does not authorize deletion.
        self.system_dependency()
        self.run_sync()
        old = self.skill(self.target, 'skill-creator')
        state = self.state()
        state['managed']['skill-creator'] = SYNC_MODULE.tree_snapshot(old)
        (self.target / SYNC_MODULE.STATE_FILE).write_text(json.dumps(state))
        self.run_sync()
        self.assertIn('skill-creator', self.state()['managed'])
        self.run_sync('--delete')
        self.assertFalse((self.target / 'skills/skill-creator').exists())

    def test_unreferenced_system_skills_remain_excluded(self):
        self.skill(self.source, '.system/skill-creator')
        self.skill(self.source, '.system/unrelated')
        self.run_sync()
        self.assertFalse((self.target / 'skills/skill-creator').exists())
        self.assertFalse((self.target / 'skills/unrelated').exists())

    def test_external_provider_content_is_not_rewritten(self):
        provider = self.system_dependency()
        entry = provider / 'SKILL.md'
        entry.write_text(entry.read_text() + '\nNew command: $CODEX_HOME/new-runtime\n')
        baseline = SYNC_MODULE.tree_snapshot(provider)
        self.run_sync()
        self.assertEqual(baseline, SYNC_MODULE.tree_snapshot(provider))
        self.assertFalse((self.target / 'skills/skill-creator').exists())

    def test_dependency_cannot_escape_provider_or_replace_another_source(self):
        self.system_dependency()
        dependent = self.source / 'skills/keep/SKILL.md'
        (self.source / 'outside.md').write_text('outside')
        dependent.write_text('---\nname: keep\ndescription: test\n---\n[escape](../.system/skill-creator/../../../outside.md)\n')
        self.run_sync(code=1)
        self.assertFalse(self.target.exists())
        dependent.write_text('---\nname: keep\ndescription: test\n---\n[provider](../.system/skill-creator/SKILL.md)\n')
        self.skill(self.source, 'skill-creator')
        self.run_sync()
        self.assertTrue((self.target / 'skills/skill-creator/SKILL.md').exists())
        self.assertIn(str(self.source / 'skills/.system/skill-creator/SKILL.md'),
                      (self.target / 'skills/keep/SKILL.md').read_text())

    def test_partial_skills_needs_no_agents_and_preserves_target_document(self):
        self.target.mkdir()
        document = self.target / 'CLAUDE.md'
        document.write_text('target customization')
        (self.source / 'AGENTS.md').unlink()
        for options in [('--dry-run',), ()]:
            output = self.run_sync('--partial', *options)
            self.assertIn('CLAUDE.md 未纳入同步', output)
            self.assertEqual('target customization', document.read_text())

    def test_explicit_skills_scope_preserves_document_and_all_scope_updates_it(self):
        self.target.mkdir()
        document = self.target / 'CLAUDE.md'
        document.write_text('target customization')
        self.run_sync('--scope', 'skills')
        self.assertEqual('target customization', document.read_text())
        self.run_sync('--partial', '--scope', 'all')
        self.assertEqual('rules', document.read_text())

    def test_document_scope_needs_no_skills_and_does_not_touch_inventory(self):
        import shutil
        self.run_sync()
        baseline = SYNC_MODULE.tree_snapshot(self.target / 'skills')
        inventory = (self.target / SYNC_MODULE.STATE_FILE).read_bytes()
        shutil.rmtree(self.source / 'skills')
        (self.source / 'AGENTS.md').write_text('updated rules')
        self.run_sync('--scope', 'document', '--dry-run')
        self.assertEqual('rules', (self.target / 'CLAUDE.md').read_text())
        self.run_sync('--scope', 'document')
        self.assertEqual('updated rules', (self.target / 'CLAUDE.md').read_text())
        self.assertEqual(inventory, (self.target / SYNC_MODULE.STATE_FILE).read_bytes())
        self.assertEqual(baseline, SYNC_MODULE.tree_snapshot(self.target / 'skills'))
        self.run_sync('--scope', 'document', '--delete', code=1)

    def test_ordinary_links_and_commands_use_target_absolute_paths_with_spaces(self):
        import shlex
        import subprocess
        self.target = self.root / 'claude target'
        sibling = self.skill(self.source, 'sibling')
        (sibling / 'run.py').write_text('print("target script")\n')
        entry = self.source / 'skills/keep/SKILL.md'
        entry.write_text(entry.read_text() + '\n[other](../sibling/SKILL.md#title)\n'
                         '\npython3 <skills-root>/sibling/run.py\n')
        self.run_sync()
        output = (self.target / 'skills/keep/SKILL.md').read_text()
        self.assertIn(f'](<{self.target.resolve()}/skills/sibling/SKILL.md#title>)', output)
        result = subprocess.run(shlex.split(output.splitlines()[-1]), cwd=self.target,
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('target script', result.stdout.strip())
        self.assertIn('<skills-root>', entry.read_text())

    def test_missing_ordinary_dependency_blocks_before_target_writes(self):
        entry = self.source / 'skills/keep/SKILL.md'
        entry.write_text(entry.read_text() + '\n[missing](../absent/SKILL.md)\n')
        self.run_sync(code=1)
        self.assertFalse(self.target.exists())

    def test_system_command_without_markdown_link_is_checked(self):
        provider = self.system_dependency()
        entry = self.source / 'skills/keep/SKILL.md'
        entry.write_text('---\nname: keep\ndescription: test\n---\n'
                         'python3 <skills-root>/.system/skill-creator/scripts/missing.py\n')
        self.run_sync(code=1)
        self.assertFalse(self.target.exists())
        entry.write_text(entry.read_text().replace('missing.py', 'init_skill.py'))
        self.run_sync()
        self.assertIn(str(provider / 'scripts/init_skill.py'),
                      (self.target / 'skills/keep/SKILL.md').read_text())

    def test_deletion_of_referenced_dependency_fails_before_any_target_write(self):
        import shutil
        provider = self.skill(self.source, 'provider')
        entry = self.source / 'skills/keep/SKILL.md'
        original = entry.read_text()
        entry.write_text(original + '\n[provider](../provider/SKILL.md)\n')
        self.run_sync()
        baseline = SYNC_MODULE.tree_snapshot(self.target)
        shutil.rmtree(provider)
        (self.source / 'AGENTS.md').write_text('must not be written on failure')
        for options in [('--dry-run',), ()]:
            self.run_sync('--delete', *options, code=1)
            self.assertEqual(baseline, SYNC_MODULE.tree_snapshot(self.target))
        entry.write_text(original)
        self.run_sync('--delete')
        self.assertFalse((self.target / 'skills/provider').exists())

    def test_retained_unselected_dependency_is_valid_for_partial_sync(self):
        import shutil
        self.skill(self.source, 'provider')
        entry = self.source / 'skills/keep/SKILL.md'
        entry.write_text(entry.read_text() + '\n[provider](../provider/SKILL.md)\n')
        self.run_sync()
        adapter = self.root / 'adapter'
        shutil.copytree(self.source / 'skills/keep', adapter / 'skills/keep')
        self.run_sync('--partial', '--delete', '--origin-root', str(self.source), source=adapter)
        self.assertTrue((self.target / 'skills/provider/SKILL.md').is_file())
        self.assertIn(str(self.target.resolve() / 'skills/provider/SKILL.md'),
                      (self.target / 'skills/keep/SKILL.md').read_text())

    def test_literal_markdown_and_template_examples_remain_byte_identical(self):
        examples = (
            '```markdown\n[usage](docs/usage.md)\n```\n'
            '~~~text verbatim\npython3 <skills-root>/missing/example.py\n~~~\n'
            '````document-template\n```bash\npython3 <skills-root>/missing/example.py\n```\n'
            '[usage](docs/template.md)\n````\n'
            'Inline: `[usage](docs/inline.md)`\n'
            'Double: `` `[usage](docs/with-backticks.md)` ``\n'
            'Multiline: ``[usage](docs/multiline.md)\nmore literal text``\n'
        )
        entry = self.source / 'skills/keep/SKILL.md'
        entry.write_text(entry.read_text() + '\n' + examples)
        source_before = entry.read_bytes()
        self.run_sync()
        self.assertEqual(source_before, (self.target / 'skills/keep/SKILL.md').read_bytes())
        self.assertEqual(source_before, entry.read_bytes())

    def test_live_links_and_shell_commands_are_converted_beside_examples(self):
        provider = self.system_dependency()
        entry = self.source / 'skills/keep/SKILL.md'
        example = '```markdown\n[example](docs/not-a-dependency.md)\n```\n'
        entry.write_text(entry.read_text() + '\n' + example +
                         '\n```bash\npython3 <skills-root>/.system/skill-creator/scripts/init_skill.py\n```\n')
        self.run_sync()
        text = (self.target / 'skills/keep/SKILL.md').read_text()
        self.assertIn(example, text)
        self.assertIn(str(provider.resolve() / 'SKILL.md'), text)
        self.assertIn(str(provider.resolve() / 'scripts/init_skill.py'), text)
        self.assertNotIn('<skills-root>', text)

    def test_missing_live_shell_dependency_still_blocks_before_writes(self):
        entry = self.source / 'skills/keep/SKILL.md'
        entry.write_text(entry.read_text() + '\n```bash\npython3 <skills-root>/missing/tool.py\n```\n')
        self.run_sync(code=1)
        self.assertFalse(self.target.exists())

    def test_missing_live_leaf_link_is_not_mistaken_for_an_example(self):
        resource = self.source / 'skills/keep/helper.md'
        resource.write_text('# Helper\n')
        entry = self.source / 'skills/keep/SKILL.md'
        entry.write_text(entry.read_text() + '\n[helper](helper.md)\n')
        self.run_sync()
        baseline = SYNC_MODULE.tree_snapshot(self.target)
        resource.unlink()
        for options in [('--dry-run',), ()]:
            self.run_sync('--delete', *options, code=1)
            self.assertEqual(baseline, SYNC_MODULE.tree_snapshot(self.target))

if __name__ == "__main__":
    unittest.main()
