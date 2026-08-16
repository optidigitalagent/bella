from __future__ import annotations

import hashlib
import importlib.util
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


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

EXPECTED_ROBOTS = (
    "User-agent: *\n"
    "Allow: /\n"
    "\n"
    "Sitemap: https://belladentclinik.kr.ua/sitemap.xml\n"
).encode("utf-8")
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
EXPECTED_SITEMAP_LOCS = [
    "https://belladentclinik.kr.ua/",
    "https://belladentclinik.kr.ua/price.html",
]
SITE_ROOT = "https://belladentclinik.kr.ua/"
LOGO_URL = f"{SITE_ROOT}images/bella-dent-mark.png.png"
INSTAGRAM_URL = "https://www.instagram.com/bella.dent.clinic"
FACEBOOK_URL = "https://www.facebook.com/share/1JF7VKAp6X/?mibextid=wwXIfr"
MAP_URL = "https://maps.app.goo.gl/4f5ZoSzFxpXF6iEY8"
MAP_EMBED_URL = (
    "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2643.5!2d33.4757767!3d48.0183088"
    "!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x40dae1c011d7f895:"
    "0x5bf876226c7311c0!2z0YPQuy4g0JLQsNGC0YPRgtC40L3QsCwgNDMvM9CQ!5e0!3m2!1sru!2sua!4v1234567890"
)


def normalized_text(parts: list[str] | str) -> str:
    text = parts if isinstance(parts, str) else " ".join(parts)
    return " ".join(text.split())


class TechnicalSeoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonicals: list[str] = []
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.links: list[dict[str, str | None]] = []
        self.metas: list[dict[str, str | None]] = []
        self.anchors: list[dict[str, object]] = []
        self.iframes: list[dict[str, str | None]] = []
        self.img_alts: list[str] = []
        self.json_ld_texts: list[str] = []
        self.titles: list[str] = []
        self.body_text: list[str] = []
        self._anchor_stack: list[dict[str, object]] = []
        self._json_ld_parts: list[str] | None = None
        self._title_parts: list[str] | None = None
        self._in_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag == "link":
            self.links.append(attributes)
            if "canonical" in (attributes.get("rel") or "").casefold().split():
                self.canonicals.append(attributes.get("href") or "")
        elif tag == "meta":
            self.metas.append(attributes)
        elif tag == "a":
            anchor: dict[str, object] = {"attributes": attributes, "text": []}
            self.anchors.append(anchor)
            self._anchor_stack.append(anchor)
            if attributes.get("href") is not None:
                self.hrefs.append(attributes["href"] or "")
        elif tag == "iframe":
            self.iframes.append(attributes)
        elif tag == "img":
            self.img_alts.append(attributes.get("alt") or "")
        elif tag == "script" and attributes.get("type") == "application/ld+json":
            self._json_ld_parts = []
        elif tag == "title":
            self._title_parts = []
        elif tag == "body":
            self._in_body = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor_stack:
            self._anchor_stack.pop()
        elif tag == "script" and self._json_ld_parts is not None:
            self.json_ld_texts.append("".join(self._json_ld_parts))
            self._json_ld_parts = None
        elif tag == "title" and self._title_parts is not None:
            self.titles.append(normalized_text(self._title_parts))
            self._title_parts = None
        elif tag == "body":
            self._in_body = False

    def handle_data(self, data: str) -> None:
        if self._anchor_stack:
            text = self._anchor_stack[-1]["text"]
            if isinstance(text, list):
                text.append(data)
        if self._json_ld_parts is not None:
            self._json_ld_parts.append(data)
        if self._title_parts is not None:
            self._title_parts.append(data)
        if self._in_body:
            self.body_text.append(data)


def parse_repository_html(relative_path: str) -> TechnicalSeoHTMLParser:
    parser = TechnicalSeoHTMLParser()
    parser.feed((REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8", errors="strict"))
    parser.close()
    return parser


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


class RepositoryTechnicalSeoContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_path = REPOSITORY_ROOT / "pages-public-manifest.txt"
        cls.manifest_entries, _ = BUILDER.read_manifest(cls.manifest_path)
        cls.temporary_directory = tempfile.TemporaryDirectory(
            prefix=".pages-contract-",
            dir=REPOSITORY_ROOT,
        )
        cls.output = Path(cls.temporary_directory.name) / "_site"
        cls.build_report = BUILDER.build_artifact(
            REPOSITORY_ROOT,
            cls.manifest_path,
            cls.output,
        )
        cls.verify_report = VERIFIER.verify_artifact(
            REPOSITORY_ROOT,
            cls.manifest_path,
            cls.output,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_page_identity_metadata_is_exact_and_description_free(self) -> None:
        page_contracts = {
            "index.html": {
                "title": "Bella Dent Clinic — Центр сучасної стоматології",
                "canonical": SITE_ROOT,
            },
            "price.html": {
                "title": "Прайс клініки — Bella Dent Clinic",
                "canonical": f"{SITE_ROOT}price.html",
            },
        }
        common_properties = {
            "og:type": "website",
            "og:locale": "uk_UA",
            "og:site_name": "Bella Dent Clinic",
            "og:image": LOGO_URL,
            "og:image:alt": "Bella Dent Clinic",
        }
        common_names = {
            "twitter:card": "summary",
            "twitter:image": LOGO_URL,
            "twitter:image:alt": "Bella Dent Clinic",
        }

        for relative_path, contract in page_contracts.items():
            with self.subTest(relative_path=relative_path):
                parsed = parse_repository_html(relative_path)
                self.assertEqual(parsed.titles, [contract["title"]])
                self.assertEqual(parsed.canonicals, [contract["canonical"]])

                favicons = [
                    link
                    for link in parsed.links
                    if "icon" in (link.get("rel") or "").casefold().split()
                ]
                self.assertEqual(
                    favicons,
                    [{"rel": "icon", "type": "image/png", "href": LOGO_URL}],
                )

                expected_properties = {
                    **common_properties,
                    "og:title": contract["title"],
                    "og:url": contract["canonical"],
                }
                expected_names = {
                    **common_names,
                    "twitter:title": contract["title"],
                }
                for attribute, expected in (
                    ("property", expected_properties),
                    ("name", expected_names),
                ):
                    for key, value in expected.items():
                        matches = [
                            meta.get("content")
                            for meta in parsed.metas
                            if meta.get(attribute) == key
                        ]
                        self.assertEqual(matches, [value], f"{relative_path}: {key}")

                self.assertFalse(
                    any(
                        (meta.get("name") or "").casefold() == "description"
                        or meta.get("property") == "og:description"
                        or meta.get("name") == "twitter:description"
                        for meta in parsed.metas
                    )
                )

    def test_homepage_json_ld_is_exact_visible_fact_entity(self) -> None:
        index = parse_repository_html("index.html")
        price = parse_repository_html("price.html")
        self.assertEqual(len(index.json_ld_texts), 1)
        self.assertEqual(price.json_ld_texts, [])

        entity = json.loads(index.json_ld_texts[0])
        expected = {
            "@context": "https://schema.org",
            "@type": "Dentist",
            "@id": f"{SITE_ROOT}#dentist",
            "name": "Bella Dent Clinic",
            "url": SITE_ROOT,
            "logo": LOGO_URL,
            "image": LOGO_URL,
            "telephone": "+380964303719",
            "email": "klinikanika@gmail.com",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "вул. Федора Караманиць, 43/3А",
                "addressLocality": "Кривий Ріг",
                "addressRegion": "Дніпропетровська область",
                "postalCode": "50000",
                "addressCountry": "UA",
            },
            "geo": {
                "@type": "GeoCoordinates",
                "latitude": 48.01832,
                "longitude": 33.4757793,
            },
            "openingHoursSpecification": [
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                    "opens": "09:00",
                    "closes": "18:00",
                },
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": "Saturday",
                    "opens": "09:00",
                    "closes": "14:00",
                },
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": "Sunday",
                    "opens": "09:00",
                    "closes": "16:00",
                },
            ],
            "sameAs": [INSTAGRAM_URL],
        }
        self.assertEqual(entity, expected)

    def test_json_ld_excludes_unapproved_entity_and_medical_properties(self) -> None:
        entity = json.loads(parse_repository_html("index.html").json_ld_texts[0])
        disallowed = {
            "alternateName",
            "aggregateRating",
            "review",
            "employee",
            "founder",
            "medicalSpecialty",
            "award",
            "isAcceptingNewPatients",
            "priceRange",
            "hasMap",
            "makesOffer",
            "hasOfferCatalog",
        }

        def property_names(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | set().union(*(property_names(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(property_names(item) for item in value))
            return set()

        self.assertTrue(disallowed.isdisjoint(property_names(entity)))
        serialized = json.dumps(entity, ensure_ascii=False).casefold()
        for forbidden in ("facebook.com", "t.me", "telegram", "ніка дент", "nika dent"):
            self.assertNotIn(forbidden, serialized)

    def test_homepage_contact_links_hours_and_map_are_exact(self) -> None:
        parsed = parse_repository_html("index.html")

        def anchors_for(href: str) -> list[dict[str, object]]:
            return [
                anchor
                for anchor in parsed.anchors
                if isinstance(anchor["attributes"], dict)
                and anchor["attributes"].get("href") == href
            ]

        phone = anchors_for("tel:+380964303719")
        self.assertEqual(len(phone), 1)
        self.assertEqual(normalized_text(phone[0]["text"]), "096 430 37 19")
        self.assertEqual(phone[0]["attributes"].get("class"), "contact-value-link")

        email = anchors_for("mailto:klinikanika@gmail.com")
        self.assertEqual(len(email), 1)
        self.assertEqual(normalized_text(email[0]["text"]), "klinikanika@gmail.com")
        self.assertEqual(email[0]["attributes"].get("class"), "contact-value-link")

        address = anchors_for(MAP_URL)
        self.assertEqual(len(address), 1)
        expected_address = (
            "м. Кривий Ріг, Покровський район, зуп. Військового Тилу, "
            "вул. Федора Караманиць, 43/3А, 50000"
        )
        address_text = normalized_text(address[0]["text"])
        self.assertEqual(address_text, expected_address)
        self.assertNotIn("Федора Карамани,", address_text)
        self.assertNotIn("Ватутіна", address_text)
        self.assertEqual(address[0]["attributes"].get("class"), "contact-value-link")
        self.assertEqual(address[0]["attributes"].get("target"), "_blank")
        self.assertEqual(address[0]["attributes"].get("rel"), "noopener")
        self.assertEqual(
            address[0]["attributes"].get("aria-label"),
            "Відкрити Bella Dent Clinic у Google Maps",
        )

        visible_body = normalized_text(parsed.body_text)
        self.assertIn(
            "Пн – Пт: 09:00 – 18:00 Сб: 09:00 – 14:00 Нд:09:00 – 16:00",
            visible_body,
        )

        map_iframes = [iframe for iframe in parsed.iframes if iframe.get("src") == MAP_EMBED_URL]
        self.assertEqual(len(map_iframes), 1)
        self.assertEqual(map_iframes[0].get("class"), "map-iframe")
        self.assertEqual(map_iframes[0].get("title"), "Bella Dent Clinic на Google Maps")
        self.assertEqual(map_iframes[0].get("loading"), "lazy")
        self.assertEqual(map_iframes[0].get("allowfullscreen"), "")
        self.assertEqual(map_iframes[0].get("referrerpolicy"), "no-referrer-when-downgrade")

        facebook = anchors_for(FACEBOOK_URL)
        self.assertEqual(len(facebook), 1)
        self.assertEqual(facebook[0]["attributes"].get("aria-label"), "Facebook")
        self.assertEqual(facebook[0]["attributes"].get("target"), "_blank")
        self.assertEqual(facebook[0]["attributes"].get("rel"), "noopener")

    def test_public_content_scope_boundaries_remain_locked(self) -> None:
        index_path = REPOSITORY_ROOT / "index.html"
        price_path = REPOSITORY_ROOT / "price.html"
        manifest_path = REPOSITORY_ROOT / "pages-public-manifest.txt"
        index = parse_repository_html("index.html")

        self.assertEqual(index.img_alts.count("Клініка Ніка Дент"), 16)
        for path in (index_path, price_path):
            source = path.read_text(encoding="utf-8", errors="strict")
            self.assertNotIn("t.me/", source.casefold())
            self.assertNotIn("telegram.me/", source.casefold())

        price_source = price_path.read_text(encoding="utf-8", errors="strict")
        self.assertEqual(price_source.count('background-image:url("images/фото для прайса.jpg")'), 1)
        self.assertNotIn("images/фото для прайса.jpg", self.manifest_entries)

        price_raw = price_path.read_bytes()
        self.assertIn(b"<body", price_raw)
        price_body = b"<body" + price_raw.split(b"<body", 1)[1]
        self.assertEqual(
            hashlib.sha256(price_body).hexdigest(),
            "988dba59828f14d8aba085ab62ab19fbd4507245e72713811b115e86f2c00489",
        )
        self.assertEqual(
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "0888f7c65e3e6cb1db0780f0f165c057c56dd5a9e49757d9b465a0b55df2609d",
        )

    def test_contact_value_link_css_is_narrowly_scoped(self) -> None:
        source = (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8", errors="strict")
        expected = """  .contact-value-link {
    color: inherit;
    text-decoration: none;
    transition: color .25s ease;
  }
  .contact-value-link:hover,
  .contact-value-link:focus-visible {
    color: var(--gold);
  }
  .contact-value-link:focus-visible {
    outline: 2px solid var(--gold);
    outline-offset: 3px;
  }"""
        self.assertEqual(source.count(expected), 1)

    def test_manifest_and_candidate_artifact_have_exact_public_inventory(self) -> None:
        expected_new_files = {"robots.txt", "sitemap.xml"}
        expected_protected_files = {".nojekyll", "CNAME"}
        forbidden_prefixes = (".github/", ".seo/", "docs/", "scripts/", "server/", "tests/")

        self.assertEqual(len(self.manifest_entries), 56)
        self.assertEqual(len(set(self.manifest_entries)), 56)
        self.assertTrue(expected_new_files.issubset(self.manifest_entries))
        self.assertTrue(expected_protected_files.issubset(self.manifest_entries))
        self.assertNotIn("pages-public-manifest.txt", self.manifest_entries)
        self.assertNotIn("bella-dent-clinic-fixed.html", self.manifest_entries)
        self.assertFalse(
            any(entry.startswith(forbidden_prefixes) for entry in self.manifest_entries)
        )
        self.assertEqual(self.build_report["file_count"], 56)
        self.assertEqual(self.verify_report["file_count"], 56)
        self.assertEqual(self.verify_report["status"], "verified")

        artifact_files = {
            path.relative_to(self.output).as_posix()
            for path in self.output.rglob("*")
            if path.is_file()
        }
        self.assertEqual(artifact_files, set(self.manifest_entries))
        for relative_path in expected_new_files | expected_protected_files:
            self.assertEqual(
                (self.output / relative_path).read_bytes(),
                (REPOSITORY_ROOT / relative_path).read_bytes(),
            )

    def test_robots_policy_is_exact_utf8_lf_text(self) -> None:
        raw = (REPOSITORY_ROOT / "robots.txt").read_bytes()
        self.assertEqual(raw, EXPECTED_ROBOTS)
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", raw)
        text = raw.decode("utf-8", errors="strict")
        directives = [line for line in text.splitlines() if line.startswith("Sitemap:")]
        self.assertEqual(directives, ["Sitemap: https://belladentclinik.kr.ua/sitemap.xml"])
        self.assertNotRegex(text, r"(?im)^\s*Disallow\s*:")
        for private_path in (".seo", ".github", "server/", "tests/", "scripts/"):
            self.assertNotIn(private_path, text)

    def test_sitemap_has_exact_ordered_canonical_inventory(self) -> None:
        raw = (REPOSITORY_ROOT / "sitemap.xml").read_bytes()
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n'))
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", raw)

        root = ET.fromstring(raw)
        url_tag = f"{{{SITEMAP_NAMESPACE}}}url"
        loc_tag = f"{{{SITEMAP_NAMESPACE}}}loc"
        self.assertEqual(root.tag, f"{{{SITEMAP_NAMESPACE}}}urlset")
        urls = list(root)
        self.assertEqual([element.tag for element in urls], [url_tag, url_tag])
        for element in urls:
            self.assertEqual([child.tag for child in element], [loc_tag])
        locs = [element[0].text for element in urls]
        self.assertEqual(locs, EXPECTED_SITEMAP_LOCS)
        self.assertEqual(len(locs), len(set(locs)))
        prohibited = {"lastmod", "changefreq", "priority"}
        self.assertFalse(
            any(element.tag.rsplit("}", 1)[-1] in prohibited for element in root.iter())
        )

    def test_html_canonicals_are_unique_absolute_and_preferred(self) -> None:
        expected = {
            "index.html": "https://belladentclinik.kr.ua/",
            "price.html": "https://belladentclinik.kr.ua/price.html",
        }
        for relative_path, canonical in expected.items():
            with self.subTest(relative_path=relative_path):
                parsed = parse_repository_html(relative_path)
                self.assertEqual(parsed.canonicals, [canonical])
                url = urlsplit(canonical)
                self.assertEqual(url.scheme, "https")
                self.assertEqual(url.netloc, "belladentclinik.kr.ua")
                self.assertNotIn(url.path, {"/index.html", "/price"})

    def test_price_home_links_use_root_and_valid_home_fragments(self) -> None:
        price = parse_repository_html("price.html")
        home = parse_repository_html("index.html")

        internal_index_targets = []
        for href in price.hrefs:
            url = urlsplit(href)
            if not url.scheme and not url.netloc and url.path.casefold().endswith("index.html"):
                internal_index_targets.append(href)
        self.assertEqual(internal_index_targets, [])
        self.assertEqual(price.hrefs.count("/"), 5)
        self.assertEqual(price.hrefs.count("/#contacts"), 4)
        self.assertEqual(price.hrefs.count("/#services"), 1)
        self.assertEqual(price.hrefs.count("/#doctors"), 1)

        normalized_fragments = {
            urlsplit(href).fragment
            for href in price.hrefs
            if href.startswith("/#")
        }
        self.assertTrue(normalized_fragments)
        self.assertTrue(normalized_fragments.issubset(home.ids))


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
