from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, module_name: str):
    path = REPOSITORY_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_script("build-pages-artifact.py", "test_pages_builder")
VERIFIER = load_script("verify-pages-artifact.py", "test_pages_verifier")


class ArtifactFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.manifest = self.root / "pages-public-manifest.txt"
        self.output = self.root / "_site"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_file(self, relative_path: str, content: bytes | str = b"content") -> Path:
        path = self.root.joinpath(*relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)
        return path

    def write_manifest(self, entries: list[str]) -> None:
        self.manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")

    def build(self):
        return BUILDER.build_artifact(self.root, self.manifest, self.output)

    def verify(self):
        try:
            return VERIFIER.verify_artifact(self.root, self.manifest, self.output)
        except VERIFIER.ArtifactError as exc:
            raise BUILDER.ArtifactError(str(exc)) from exc


class ValidArtifactTests(ArtifactFixture):
    def test_valid_sorted_explicit_manifest_builds_and_verifies(self) -> None:
        self.write_file("assets/bg.png", b"png")
        self.write_file("index.html", '<link rel="stylesheet" href="style.css"><img src="assets/bg.png">')
        self.write_file("style.css", "body { background: url('assets/bg.png'); }")
        self.write_manifest(["assets/bg.png", "index.html", "style.css"])

        build_report = self.build()
        verify_report = self.verify()

        self.assertEqual(build_report["file_count"], 3)
        self.assertEqual(verify_report["status"], "verified")
        self.assertEqual(
            [item["path"] for item in build_report["files"]],
            ["assets/bg.png", "index.html", "style.css"],
        )

    def test_nested_files_and_spaces_preserve_relative_paths(self) -> None:
        self.write_file("assets/clinic photo.jpg", b"jpeg")
        self.write_file("index.html", '<img src="assets/clinic photo.jpg">')
        self.write_manifest(["assets/clinic photo.jpg", "index.html"])
        self.build()
        self.verify()
        self.assertEqual((self.output / "assets" / "clinic photo.jpg").read_bytes(), b"jpeg")

    def test_nojekyll_is_allowed_only_as_explicit_exception(self) -> None:
        self.write_file(".nojekyll", b"")
        self.write_file("index.html", "<h1>Home</h1>")
        self.write_manifest([".nojekyll", "index.html"])
        self.build()
        self.verify()
        self.assertTrue((self.output / ".nojekyll").is_file())

        self.write_file(".hidden", b"hidden")
        self.write_manifest([".hidden", "index.html"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_external_data_contact_and_fragment_links_are_ignored(self) -> None:
        self.write_file(
            "index.html",
            """<a href="#local">Local</a><a href="mailto:a@example.test">Mail</a>
            <a href="tel:+380000000000">Phone</a><a href="https://example.test/x.html">External</a>
            <img src="data:image/png;base64,AA=="><script>const x = 'https://cdn.test/app.js';</script>""",
        )
        self.write_manifest(["index.html"])
        self.build()
        self.verify()

    def test_query_fragments_srcset_and_css_urls_are_normalized(self) -> None:
        self.write_file("assets/a.png", b"a")
        self.write_file("assets/b.png", b"b")
        self.write_file("index.html", '<img srcset="assets/a.png?x=1 1x, assets/b.png#v 2x"><link href="style.css?v=2" rel="stylesheet">')
        self.write_file("style.css", '@import "theme.css?v=1"; .x{background:url("assets/a.png#x")}')
        self.write_file("theme.css", ".theme { color: black; }")
        self.write_manifest(["assets/a.png", "assets/b.png", "index.html", "style.css", "theme.css"])
        self.build()
        self.verify()

    def test_runtime_static_references_in_inline_javascript_are_verified(self) -> None:
        self.write_file("certificates/cert-1.png", b"cert")
        self.write_file("doctors/doctor.png", b"doctor")
        self.write_file(
            "index.html",
            "<script>const cert='./certificates/cert-1.png'; const doctor=`doctors/doctor.png`;</script>",
        )
        self.write_manifest(["certificates/cert-1.png", "doctors/doctor.png", "index.html"])
        self.build()
        self.verify()

    def test_unallowlisted_legacy_html_remains_in_source_only(self) -> None:
        obsolete = self.write_file("legacy-backup.html", '<img src="missing.png">')
        self.write_file("index.html", "<h1>Home</h1>")
        self.write_manifest(["index.html"])
        self.build()
        self.verify()
        self.assertTrue(obsolete.is_file())
        self.assertFalse((self.output / "legacy-backup.html").exists())


class ManifestRejectionTests(ArtifactFixture):
    def assert_manifest_rejected(self, entry: str, create: bool = True) -> None:
        if create and not entry.endswith("/") and "*" not in entry and "?" not in entry:
            try:
                self.write_file(entry, b"x")
            except (OSError, ValueError):
                pass
        self.write_manifest([entry])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_absolute_path_rejected(self) -> None:
        self.assert_manifest_rejected("/index.html", create=False)

    def test_windows_absolute_path_rejected(self) -> None:
        self.assert_manifest_rejected("C:/index.html", create=False)

    def test_parent_traversal_rejected(self) -> None:
        self.assert_manifest_rejected("../index.html", create=False)

    def test_backslash_path_rejected(self) -> None:
        self.assert_manifest_rejected(r"assets\image.png", create=False)

    def test_glob_and_wildcard_rejected(self) -> None:
        for entry in ("assets/*.png", "file?.js", "assets/[ab].png"):
            with self.subTest(entry=entry):
                self.assert_manifest_rejected(entry, create=False)

    def test_duplicate_rejected(self) -> None:
        self.write_file("index.html", "home")
        self.write_manifest(["index.html", "index.html"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_unsorted_entries_rejected(self) -> None:
        self.write_file("a.txt")
        self.write_file("b.txt")
        self.write_manifest(["b.txt", "a.txt"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_directory_entry_rejected(self) -> None:
        (self.root / "assets").mkdir()
        self.write_manifest(["assets"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_missing_file_rejected(self) -> None:
        self.write_manifest(["missing.txt"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_empty_effective_manifest_rejected(self) -> None:
        self.manifest.write_text("# comments only\n\n", encoding="utf-8")
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_forbidden_internal_paths_rejected_case_insensitively(self) -> None:
        for entry in (
            ".seo/state.yml",
            "server/app.js",
            "docs/note.txt",
            ".github/workflows/x.yml",
            "README.md",
            "package.json",
            "site.js.map",
        ):
            with self.subTest(entry=entry):
                self.assert_manifest_rejected(entry, create=False)

    def test_manifest_self_inclusion_rejected(self) -> None:
        self.write_manifest(["pages-public-manifest.txt"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_utf8_bom_rejected(self) -> None:
        self.write_file("index.html", "home")
        self.manifest.write_bytes(b"\xef\xbb\xbfindex.html\n")
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()


class FilesystemIsolationTests(ArtifactFixture):
    def create_basic_artifact(self) -> None:
        self.write_file("index.html", "<h1>Home</h1>")
        self.write_manifest(["index.html"])
        self.build()

    def test_symlink_file_rejected(self) -> None:
        target = self.write_file("target.txt", "target")
        link = self.root / "link.txt"
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        self.write_manifest(["link.txt"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_symlink_parent_directory_rejected(self) -> None:
        real = self.root / "real"
        real.mkdir()
        (real / "file.txt").write_text("x", encoding="utf-8")
        link = self.root / "linked"
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks unavailable: {exc}")
        self.write_manifest(["linked/file.txt"])
        with self.assertRaises(BUILDER.ArtifactError):
            self.build()

    def test_extra_artifact_file_rejected(self) -> None:
        self.create_basic_artifact()
        (self.output / "extra.txt").write_text("extra", encoding="utf-8")
        with self.assertRaises(BUILDER.ArtifactError):
            self.verify()

    def test_missing_artifact_file_rejected(self) -> None:
        self.create_basic_artifact()
        (self.output / "index.html").unlink()
        with self.assertRaises(BUILDER.ArtifactError):
            self.verify()

    def test_modified_artifact_content_rejected(self) -> None:
        self.create_basic_artifact()
        (self.output / "index.html").write_text("changed", encoding="utf-8")
        with self.assertRaises(BUILDER.ArtifactError):
            self.verify()

    def test_hard_link_in_artifact_rejected(self) -> None:
        self.create_basic_artifact()
        artifact = self.output / "index.html"
        artifact.unlink()
        try:
            os.link(self.root / "index.html", artifact)
        except OSError as exc:
            self.skipTest(f"hard links unavailable: {exc}")
        with self.assertRaises(BUILDER.ArtifactError):
            self.verify()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixtures are not supported")
    def test_special_file_in_artifact_rejected(self) -> None:
        self.create_basic_artifact()
        fifo = self.output / "fifo"
        try:
            os.mkfifo(fifo)
        except OSError as exc:
            self.skipTest(f"FIFO unavailable: {exc}")
        with self.assertRaises(BUILDER.ArtifactError):
            self.verify()

    def test_source_root_and_outside_output_are_rejected(self) -> None:
        self.write_file("index.html", "home")
        self.write_manifest(["index.html"])
        with self.assertRaises(BUILDER.ArtifactError):
            BUILDER.build_artifact(self.root, self.manifest, self.root)
        with self.assertRaises(BUILDER.ArtifactError):
            BUILDER.build_artifact(self.root, self.manifest, self.root.parent / "outside")


class DependencyFailureTests(ArtifactFixture):
    def assert_dependency_rejected(self, html: str, extra_files: dict[str, str] | None = None) -> None:
        self.write_file("index.html", html)
        entries = ["index.html"]
        for relative_path, content in (extra_files or {}).items():
            self.write_file(relative_path, content)
            entries.append(relative_path)
        self.write_manifest(sorted(entries))
        self.build()
        with self.assertRaises(BUILDER.ArtifactError):
            self.verify()

    def test_missing_image_rejected(self) -> None:
        self.assert_dependency_rejected('<img src="missing.png">')

    def test_missing_stylesheet_rejected(self) -> None:
        self.assert_dependency_rejected('<link rel="stylesheet" href="missing.css">')

    def test_missing_script_rejected(self) -> None:
        self.assert_dependency_rejected('<script src="missing.js"></script>')

    def test_missing_linked_html_rejected(self) -> None:
        self.assert_dependency_rejected('<a href="missing.html">Missing</a>')

    def test_css_import_and_url_missing_rejected(self) -> None:
        for css in ('@import "missing.css";', 'body{background:url("missing.png")}'):
            with self.subTest(css=css):
                self.assert_dependency_rejected('<link rel="stylesheet" href="style.css">', {"style.css": css})

    def test_javascript_static_file_reference_missing_rejected(self) -> None:
        self.assert_dependency_rejected('<script src="app.js"></script>', {"app.js": "const icon = 'missing.svg';"})

    def test_javascript_static_file_reference_with_spaces_missing_rejected(self) -> None:
        self.assert_dependency_rejected(
            '<script src="app.js"></script>',
            {"app.js": "const photo = 'images/clinic photo.jpg';"},
        )

    def test_probable_private_key_content_rejected(self) -> None:
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        self.write_file("index.html", marker + "\nnot-a-real-key")
        self.write_manifest(["index.html"])
        self.build()
        with self.assertRaises(BUILDER.ArtifactError):
            self.verify()


class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        cls.event_block = cls.workflow.split("permissions:", 1)[0]
        cls.build_block, cls.deploy_block = cls.workflow.split("\n  deploy:", 1)

    def test_only_pull_request_and_workflow_dispatch_triggers_exist(self) -> None:
        self.assertRegex(self.event_block, r"(?m)^  pull_request:$")
        self.assertRegex(self.event_block, r"(?m)^  workflow_dispatch:$")
        for event in ("push", "pull_request_target", "workflow_run", "schedule", "release", "deployment", "repository_dispatch"):
            self.assertNotRegex(self.event_block, rf"(?m)^  {re.escape(event)}:")

    def test_build_job_has_read_only_permissions(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.workflow)
        self.assertNotIn("pages: write", self.build_block)
        self.assertNotIn("id-token: write", self.build_block)
        self.assertNotIn("actions/deploy-pages", self.build_block)

    def test_manual_deploy_guard_is_complete(self) -> None:
        for required in (
            "github.event_name == 'workflow_dispatch'",
            "inputs.deploy == true",
            "inputs.confirmation == 'DEPLOY_BELLA_PRODUCTION'",
            "inputs.expected_sha == github.sha",
            "github.repository == 'optidigitalagent/bella'",
            "github.ref == 'refs/heads/main'",
        ):
            self.assertIn(required, self.deploy_block)

    def test_workflow_dispatch_inputs_are_fail_closed(self) -> None:
        self.assertRegex(self.event_block, r"(?s)deploy:.*?required: true.*?default: false.*?type: boolean")
        self.assertRegex(self.event_block, r"(?s)confirmation:.*?required: true.*?default: ''")
        self.assertRegex(self.event_block, r"(?s)expected_sha:.*?required: true.*?default: ''")

    def test_actions_are_approved_and_immutably_pinned(self) -> None:
        expected = {
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0",
            "actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128 # v5.0.0",
        }
        uses = re.findall(r"(?m)^\s*uses:\s*(\S+@\S+\s+#\s+v\d+\.\d+\.\d+)\s*$", self.workflow)
        self.assertEqual(set(uses), expected)
        self.assertEqual(len(uses), 3)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40} # v\d+\.\d+\.\d+$")

    def test_checkout_and_artifact_upload_are_hardened(self) -> None:
        self.assertIn("ref: ${{ github.sha }}", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("fetch-depth: 1", self.workflow)
        self.assertIn("path: _site", self.workflow)
        self.assertNotRegex(self.workflow, r"(?m)^\s*path:\s*\.\s*$")
        self.assertIn("retention-days: 1", self.workflow)
        self.assertIn("include-hidden-files: true", self.workflow)

    def test_deploy_job_uses_environment_and_minimal_write_permissions(self) -> None:
        self.assertIn("name: github-pages", self.deploy_block)
        self.assertIn("contents: read", self.deploy_block)
        self.assertIn("pages: write", self.deploy_block)
        self.assertIn("id-token: write", self.deploy_block)


if __name__ == "__main__":
    unittest.main()
