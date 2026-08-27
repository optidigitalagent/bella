from __future__ import annotations

import base64
import hashlib
from html import unescape
import importlib.util
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.parse import quote, urlsplit
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
    "https://belladentclinik.kr.ua/implantatsiia-zubiv.html",
    "https://belladentclinik.kr.ua/khirurhichna-stomatolohiia.html",
]
SITE_ROOT = "https://belladentclinik.kr.ua/"
LOGO_URL = f"{SITE_ROOT}images/bella-dent-mark.png.png"
HOMEPAGE_TITLE = "Стоматологія у Кривому Розі — Bella Dent Clinic"
HOMEPAGE_DESCRIPTION = (
    "Bella Dent Clinic — стоматологія у Кривому Розі. Лікування, хірургія, "
    "протезування, ортодонтія, імплантація, прайс і запис на консультацію."
)
HOMEPAGE_HERO_LOCAL_INTENT = (
    "Стоматологія у Кривому Розі — послуги, лікарі, прайс і запис на консультацію."
)
HOMEPAGE_SERVICES_HEADING = "Стоматологічні послуги у Кривому Розі"
IMPLANTATION_PAGE = "implantatsiia-zubiv.html"
IMPLANTATION_TITLE = "Імплантація зубів у Кривому Розі — Bella Dent Clinic"
IMPLANTATION_CANONICAL = f"{SITE_ROOT}{IMPLANTATION_PAGE}"
IMPLANTATION_DESCRIPTION = (
    "Імплантація зубів у Bella Dent Clinic у Кривому Розі: опублікований прайс, "
    "лікар, контакти та запис на консультацію."
)
EXPECTED_IMPLANTATION_PRICES = [
    ("Імпланти: Alfa Bio Ізраїль", "400 у.о."),
    ("Імпланти: Neobiotech / Identall", "400 у.о."),
    ("Імпланти: MEGAGEN (Anyridge) Корея", "450 у.о."),
    ("Імплантат MEGAGEN AnyOne (Корея)", "400 у.о."),
    ("Виготовлення шаблону на імплантацію", "55–100 у.о."),
    ("Встановлення формувача ясен", "900 грн"),
    ("Закритий синусліфтинг (без урахування кісткового матеріалу) гребневий", "7000 грн"),
    ("Закритий синусліфтинг (без урахування кісткового матеріалу) з остеотомами", "12000 грн"),
    ("Відкритий синусліфтинг (без урахування кісткового матеріалу)", "45000 грн"),
    ("Розщеплення гребеню альвеолярного відростку", "5000 грн"),
    ("Виготовлення індивідуального абатменту", "4000 грн"),
    ("Виготовлення цирконієвого індивідуального абатменту", "4500 грн"),
    ("Металокерамічна коронка на імплант", "5500 грн"),
    ("Коронка з діоксиду цирконію на імплантат", "8000 грн"),
    ("Виготовлення цільновідлитої коронки на імплантат", "4000 грн"),
    ("Фіксація коронки склоіономерним цементом на імплантат", "500 грн"),
    ("Мультюніт", "4000 грн"),
    ("Горизонтальна аугментація кістковим блоком по Кюрі", "8000 грн"),
    ("Горизонтальна аугментація", "10000 грн"),
    ("Встановлення кісткового гвинта", "600 грн"),
    ("Встановлення кісткового блоку 15202", "6000 грн"),
    ("Встановлення кісткового блоку 15302", "9000 грн"),
    ("Встановлення кісткового блоку 7.5202", "4000 грн"),
    ("Встановлення кісткового блоку 7.5302", "5000 грн"),
    ("Встановлення мембрани (ксеноімплантат) 20*30", "2000 грн"),
    ("Встановлення мембрани (ксеноімплантат) 30*40", "3000 грн"),
    ("Мембрана APRF", "2000 грн"),
    ("Редукція кісткової тканини", "2000 грн"),
    ("Імплант Сервіс", "3000 грн"),
]
SURGICAL_PAGE = 'khirurhichna-stomatolohiia.html'
SURGICAL_TITLE = 'Хірургічна стоматологія у Кривому Розі — Bella Dent Clinic'
SURGICAL_CANONICAL = f"{SITE_ROOT}{SURGICAL_PAGE}"
SURGICAL_DESCRIPTION = 'Хірургічна стоматологія у Bella Dent Clinic у Кривому Розі: опубліковані послуги й ціни, лікар, контакти та запис на консультацію.'
EXPECTED_SURGICAL_PRICES = [
    ('Премедикація', '500 грн'),
    ('Видалення уламку зуба', '200 грн'),
    ('Видалення рухомого зуба при парадонтозі / парадонтиті', '400 грн'),
    ('Видалення 1 кореневого зуба', '500 грн'),
    ('Видалення 2 кореневого зуба', '1000 грн'),
    ('Видалення 3 кореневого зуба', '1500 грн'),
    ('Видалення екзостозів (обл. 1 зуба)', '800 грн'),
    ('Видалення зуба мудрості (типове)', '1500 грн'),
    ('Видалення зуба атипове', '2500 грн'),
    ('Гемісекція зуба (без врахув. кістк.-пластичн. матеріалу)', '1500 грн'),
    ('Видалення ретинованого зуба (без врахув. кістк.-пластичн. матеріалу)', '4200 грн'),
    ('Видалення понадкомплектного зуба', '3000 грн'),
    ('Резекція верхівки кореня при періодонтиті', '4500 грн'),
    ('Реімплантація', '4500 грн'),
    ('Цистектомія з резекцією верхівки кореня (без врахув. кістк.-пластичн. матеріалу)', '4500 грн'),
    ('Цистектомія через лунку (без врахув. кістк.-пластичн. матеріалу)', '2200 грн'),
    ('Мембранна тканина', '1500 грн'),
    ('Встановлення титанового піну', '500 грн'),
    ('Ксено кістка Bio Bone (0,25 м3, 1 вел. ложка)', '1500 грн'),
    ('Алокістка Probones (0,25м3, 1 вел. ложка)', '1500 грн'),
    ('Заповнення кісткового дефекту "КОЛЛАПАН" 1шт.', '500 грн'),
    ('Заповнення кісткового дефекту "КОЛЛАПОЛ" 1шт.', '500 грн'),
    ('Видалення доброякісної пухлини', '3000 грн'),
    ('Виправлення вивиху СНЩС', '2000 грн'),
    ('Репозиція зуба при неповному вивиху', '2000 грн'),
    ('Гінгівектомія (обл. 1 зуба)', '1000 грн'),
    ('Розтин абсцесу з наступним дренуванням', '900 грн'),
    ('Розтин пародонтального абсцесу', '800 грн'),
    ('Гострий перекороніт (висічення капюшона)', '1200 грн'),
    ('Кюретаж пародонтального карману в обл. 1-го зуба', '1000 грн'),
    ('Медична обробка слизової оболонки при стоматиті', '500 грн'),
    ('Надання допомоги при альвеоліті (кюрет., мед. обр)', '800 грн'),
    ('Лоскутна операція (без врахув. кістк.-пластичн. матеріалу)', '4200 грн'),
    ('Накладення швів', '150 грн'),
    ('Зняття швів', '150 грн'),
    ('Пункція', '300 грн'),
    ('Промивання лунки', '100 грн'),
    ('Пластика вуздечки язика', '2000 грн'),
    ('Пластика верхньої губи (за Лімбергом)', '3000 грн'),
    ('Пластика передодні порожнини рота', '3000 грн'),
    ('Висічення гіпертрофічно зміненої слизової оболонки (обл. 1 зуба)', '1000 грн'),
    ('Секвестректомія', '2500 грн'),
    ('Синтетичний кістковий композит (1гр)', '2000 грн'),
    ('Промивка гайморової пазухи через лунку вид. зуба', '500 грн'),
    ('Заповнення кісткового дефекта колагеновою губкою Резорба', '1500 грн'),
]
INSTAGRAM_URL = "https://www.instagram.com/bella.dent.clinic"
FACEBOOK_URL = "https://www.facebook.com/share/1JF7VKAp6X/?mibextid=wwXIfr"
MAP_URL = "https://maps.app.goo.gl/4f5ZoSzFxpXF6iEY8"
MAP_EMBED_URL = (
    "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2643.5!2d33.4757767!3d48.0183088"
    "!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x40dae1c011d7f895:"
    "0x5bf876226c7311c0!2z0YPQuy4g0JLQsNGC0YPRgtC40L3QsCwgNDMvM9CQ!5e0!3m2!1sru!2sua!4v1234567890"
)
GALLERY_IMAGES = [
    ("images/1779104568309443.jpg", 3024, 4032),
    ("images/1779104635629528.jpg", 3024, 4032),
    ("images/1779104606802140.jpg", 3024, 4032),
    ("images/1779104570737709.jpg", 3024, 4032),
    ("images/1779104566334594.jpg", 3024, 4032),
    ("images/1779104583967888.jpg", 3024, 4032),
    ("images/1779104673660235.jpg", 3024, 4032),
    ("images/1779104670644090.jpg", 3024, 4032),
    ("images/1779104592293313.jpg", 3024, 4032),
    ("images/1779104572279425.jpg", 4284, 5712),
    ("images/177910463479041.jpg", 4284, 5712),
    ("images/1779104593232172.jpg", 3024, 4032),
    ("images/1779104585368255.jpg", 4284, 5712),
    ("images/1779104591598850.jpg", 4284, 5712),
    ("images/1779104606802140.jpg", 3024, 4032),
    ("images/1779104588550840.jpg", 3024, 4032),
]
CASE_IMAGES = [
    ("cases/case-1.jpg", 1203, 380),
    ("cases/case-2.jpg", 1203, 380),
    ("cases/case-3.jpg", 1203, 380),
    ("cases/case-4.jpg", 971, 380),
    ("cases/case-5.jpg", 569, 380),
    ("cases/case-6.jpg", 691, 380),
    ("cases/case-7.jpg", 570, 380),
    ("cases/case-8.jpg", 570, 380),
    ("cases/case-9.jpg", 570, 380),
]
DOCTOR_IMAGE_DIMENSIONS = {
    "doctors/oliynyk1.png": (1086, 1448),
    "doctors/rybin2.png": (1086, 1448),
    "doctors/sokolova.png": (1086, 1448),
    "doctors/sidykh.png": (1086, 1448),
    "doctors/levchenko.png": (1086, 1448),
}
CERTIFICATE_IMAGE_DIMENSIONS = {
    "./certificates/cert-1.png": (1310, 950),
    "./certificates/cert-2.png": (1217, 861),
    **{f"./certificates/cert-{number}.png": (1233, 873) for number in range(3, 15)},
    "./certificates/cert-15.png": (1074, 873),
}


def normalized_text(parts: list[str] | str) -> str:
    text = parts if isinstance(parts, str) else " ".join(parts)
    return " ".join(text.split())


def canonicalize_newlines_to_lf(content: bytes) -> bytes:
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


class TechnicalSeoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonicals: list[str] = []
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.id_values: list[str] = []
        self.links: list[dict[str, str | None]] = []
        self.metas: list[dict[str, str | None]] = []
        self.anchors: list[dict[str, object]] = []
        self.iframes: list[dict[str, str | None]] = []
        self.images: list[dict[str, object]] = []
        self.img_alts: list[str] = []
        self.json_ld_texts: list[str] = []
        self.titles: list[str] = []
        self.h1_texts: list[str] = []
        self.h2_texts: list[str] = []
        self.table_rows: list[list[str]] = []
        self.table_captions: list[str] = []
        self.th_scopes: list[str | None] = []
        self.body_text: list[str] = []
        self._anchor_stack: list[dict[str, object]] = []
        self._json_ld_parts: list[str] | None = None
        self._title_parts: list[str] | None = None
        self._text_captures: list[tuple[str, list[str]]] = []
        self._current_row: list[str] | None = None
        self._in_body = False
        self._noscript_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "noscript":
            self._noscript_depth += 1
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
            self.id_values.append(element_id)
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
            self.images.append(
                {"attributes": attributes, "noscript": self._noscript_depth > 0}
            )
            self.img_alts.append(attributes.get("alt") or "")
        elif tag == "script" and attributes.get("type") == "application/ld+json":
            self._json_ld_parts = []
        elif tag == "title":
            self._title_parts = []
        elif tag in {"h1", "h2", "caption", "th", "td"}:
            self._text_captures.append((tag, []))
            if tag == "th":
                self.th_scopes.append(attributes.get("scope"))
        elif tag == "tr":
            self._current_row = []
        elif tag == "body":
            self._in_body = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "noscript":
            self._noscript_depth -= 1
        elif tag == "a" and self._anchor_stack:
            self._anchor_stack.pop()
        elif tag == "script" and self._json_ld_parts is not None:
            self.json_ld_texts.append("".join(self._json_ld_parts))
            self._json_ld_parts = None
        elif tag == "title" and self._title_parts is not None:
            self.titles.append(normalized_text(self._title_parts))
            self._title_parts = None
        elif tag in {"h1", "h2", "caption", "th", "td"} and self._text_captures:
            capture_tag, parts = self._text_captures.pop()
            if capture_tag != tag:
                raise AssertionError(f"unexpected HTML capture close: {capture_tag} / {tag}")
            text = normalized_text(parts)
            if tag == "h1":
                self.h1_texts.append(text)
            elif tag == "h2":
                self.h2_texts.append(text)
            elif tag == "caption":
                self.table_captions.append(text)
            elif self._current_row is not None:
                self._current_row.append(text)
        elif tag == "tr" and self._current_row is not None:
            self.table_rows.append(self._current_row)
            self._current_row = None
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
        for _, parts in self._text_captures:
            parts.append(data)
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

    def test_page_identity_metadata_and_description_contracts_are_exact(self) -> None:
        page_contracts = {
            "index.html": {
                "title": HOMEPAGE_TITLE,
                "canonical": SITE_ROOT,
                "description": HOMEPAGE_DESCRIPTION,
            },
            "price.html": {
                "title": "Прайс клініки — Bella Dent Clinic",
                "canonical": f"{SITE_ROOT}price.html",
                "description": None,
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

                descriptions = [
                    meta.get("content")
                    for meta in parsed.metas
                    if (meta.get("name") or "").casefold() == "description"
                ]
                expected_descriptions = (
                    [contract["description"]] if contract["description"] else []
                )
                self.assertEqual(descriptions, expected_descriptions)
                self.assertFalse(
                    any(
                        meta.get("property") == "og:description"
                        or meta.get("name") == "twitter:description"
                        for meta in parsed.metas
                    )
                )

    def test_homepage_local_intent_copy_is_exact_visible_and_not_stuffed(self) -> None:
        source = (REPOSITORY_ROOT / "index.html").read_text(
            encoding="utf-8",
            errors="strict",
        )
        parsed = parse_repository_html("index.html")
        visible = normalized_text(parsed.body_text)

        self.assertEqual(parsed.h1_texts, ["BELLA DENT CLINIC"])
        self.assertEqual(
            source.count(f'<p class="hero-subtitle">{HOMEPAGE_HERO_LOCAL_INTENT}</p>'),
            1,
        )
        self.assertEqual(visible.count(HOMEPAGE_HERO_LOCAL_INTENT), 1)
        self.assertEqual(
            source.count(f'<h2 class="section-heading">{HOMEPAGE_SERVICES_HEADING}</h2>'),
            1,
        )
        self.assertEqual(parsed.h2_texts.count(HOMEPAGE_SERVICES_HEADING), 1)
        self.assertNotIn("Комплексна турбота про вашу усмішку", visible)

        core_phrase = "стоматологія у кривому розі"
        self.assertEqual(visible.casefold().count(core_phrase), 1)
        for russian_copy in (
            "стоматология",
            "стоматологическая клиника",
            "стоматолог в кривом роге",
            "кривой рог",
        ):
            self.assertNotIn(russian_copy, visible.casefold())
        for hidden_seo_marker in (
            "bot-only",
            "ai-only",
            "hidden-ai",
            "seo-only",
            "seo-hidden",
            "keyword-list",
        ):
            self.assertNotIn(hidden_seo_marker, source.casefold())

    def test_homepage_service_card_order_and_destinations_are_exact(self) -> None:
        price_source = (REPOSITORY_ROOT / "prices.js").read_text(
            encoding="utf-8",
            errors="strict",
        )
        home_source = (REPOSITORY_ROOT / "index.html").read_text(
            encoding="utf-8",
            errors="strict",
        )
        categories = re.findall(
            r"(?m)^    title: '([^']+)',\n    slug: '([^']+)',",
            price_source,
        )
        self.assertEqual(
            categories,
            [
                ("Терапевтична стоматологія", "terapiia"),
                ("Хірургічна стоматологія", "khirurhiia"),
                ("Ортопедія", "ortopediia"),
                ("Ортодонтія", "ortodontiia"),
                ("Імплантологія", "implantolohiia"),
            ],
        )
        expected_destinations = [
            "price.html#terapiia",
            "khirurhichna-stomatolohiia.html",
            "price.html#ortopediia",
            "price.html#ortodontiia",
            "implantatsiia-zubiv.html",
        ]
        actual_destinations = [
            "khirurhichna-stomatolohiia.html"
            if slug == "khirurhiia"
            else "implantatsiia-zubiv.html"
            if slug == "implantolohiia"
            else f"price.html#{slug}"
            for _, slug in categories
        ]
        self.assertEqual(actual_destinations, expected_destinations)
        self.assertEqual(
            home_source.count(
                "a.href = cat.slug === 'khirurhiia' ? 'khirurhichna-stomatolohiia.html' : cat.slug === 'implantolohiia' ? 'implantatsiia-zubiv.html' : 'price.html#' + cat.slug;"
            ),
            1,
        )
        self.assertEqual(
            home_source.count('<div class="services-grid" id="price-categories-grid"></div>'),
            1,
        )


    def test_surgical_page_head_contract_is_exact(self) -> None:
        source = (REPOSITORY_ROOT / SURGICAL_PAGE).read_text(encoding="utf-8", errors="strict")
        parsed = parse_repository_html(SURGICAL_PAGE)
        self.assertTrue(source.startswith('<!DOCTYPE html>\n<html lang="uk">\n'))
        self.assertEqual(parsed.titles, [SURGICAL_TITLE])
        self.assertEqual(parsed.canonicals, [SURGICAL_CANONICAL])
        self.assertEqual(parsed.json_ld_texts, [])
        expected_properties = {
            "og:type": "website",
            "og:locale": "uk_UA",
            "og:site_name": "Bella Dent Clinic",
            "og:title": SURGICAL_TITLE,
            "og:description": SURGICAL_DESCRIPTION,
            "og:url": SURGICAL_CANONICAL,
            "og:image": LOGO_URL,
            "og:image:alt": "Bella Dent Clinic",
        }
        expected_names = {
            "description": SURGICAL_DESCRIPTION,
            "twitter:card": "summary",
            "twitter:title": SURGICAL_TITLE,
            "twitter:description": SURGICAL_DESCRIPTION,
            "twitter:image": LOGO_URL,
            "twitter:image:alt": "Bella Dent Clinic",
        }
        for attribute, expected in (("property", expected_properties), ("name", expected_names)):
            for key, value in expected.items():
                matches = [meta.get("content") for meta in parsed.metas if meta.get(attribute) == key]
                self.assertEqual(matches, [value], key)
        self.assertFalse(any(
            "noindex" in (meta.get("content") or "").casefold()
            for meta in parsed.metas
            if (meta.get("name") or "").casefold() in {"robots", "googlebot"}
        ))

    def test_surgical_page_visible_answer_contract_is_exact(self) -> None:
        parsed = parse_repository_html(SURGICAL_PAGE)
        visible = normalized_text(parsed.body_text)
        self.assertEqual(parsed.h1_texts, ["Хірургічна стоматологія у Кривому Розі"])
        self.assertEqual(
            parsed.h2_texts,
            [
                "Де надаються послуги?",
                "Хто вказаний у списку лікарів?",
                "Які послуги та ціни опубліковані?",
                "Де переглянути імплантацію?",
                "Ціни на хірургічні стоматологічні послуги",
                "Як записатися на консультацію?",
                "Контакти Bella Dent Clinic",
            ],
        )
        required = [
            "У Bella Dent Clinic у Кривому Розі опубліковано напрям «Хірургічна стоматологія».",
            "Інформацію та ціни підтверджено за поточними публічними даними Bella Dent Clinic станом на 27 серпня 2026 року.",
            "Bella Dent Clinic знаходиться у Кривому Розі за адресою: вул. Федора Караманиць, 43/3А, Покровський район, 50000.",
            "Олійник Ігор Євгенійович — Головний лікар клініки, хірург-стоматолог, імплантолог, ортопед.",
            "Нижче наведено 45 позицій розділу «Хірургічна стоматологія»",
            "Пн–Пт 09:00–18:00 Сб 09:00–14:00 Нд 09:00–16:00",
        ]
        for value in required:
            self.assertIn(value, visible)
        self.assertNotIn("Ватутіна", visible)
        self.assertEqual(len(parsed.id_values), len(set(parsed.id_values)))

    def test_surgical_price_table_and_fallback_are_exact(self) -> None:
        parsed = parse_repository_html(SURGICAL_PAGE)
        self.assertEqual(
            parsed.table_captions,
            ["Опубліковані позиції розділу «Хірургічна стоматологія»"],
        )
        self.assertEqual(parsed.th_scopes, ["col", "col", "col"])
        self.assertEqual(parsed.table_rows[0], ["№", "Назва", "Ціна"])
        expected = [
            [str(index), name, price]
            for index, (name, price) in enumerate(EXPECTED_SURGICAL_PRICES, 1)
        ]
        self.assertEqual(parsed.table_rows[1:], expected)
        self.assertEqual(len(parsed.table_rows) - 1, 45)
        prices = (REPOSITORY_ROOT / "prices.js").read_text(encoding="utf-8", errors="strict")
        start = prices.index("title: 'Хірургічна стоматологія'")
        end = prices.index("title: 'Ортопедія'", start)
        block = prices[start:end]
        fallback = [
            (name.replace("\\'", "'"), price)
            for name, price in re.findall(
                r"\{ name: '((?:\\'|[^'])+)', price: '([^']+)' \}",
                block,
            )
        ]
        self.assertEqual(fallback, EXPECTED_SURGICAL_PRICES)

    def test_surgical_internal_links_and_fragments_are_resolvable(self) -> None:
        home_source = (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8", errors="strict")
        self.assertEqual(home_source.count("a.href = cat.slug === 'khirurhiia' ? 'khirurhichna-stomatolohiia.html' : cat.slug === 'implantolohiia' ? 'implantatsiia-zubiv.html' : 'price.html#' + cat.slug;"), 1)
        self.assertEqual(home_source.count("var cardCta = cat.slug === 'khirurhiia' ? 'Детальніше про хірургію' : cat.slug === 'implantolohiia' ? 'Детальніше про імплантацію' : 'Відкрити прайс';"), 1)
        price = parse_repository_html("price.html")
        self.assertEqual(price.hrefs.count("/khirurhichna-stomatolohiia.html"), 1)
        implantation = parse_repository_html(IMPLANTATION_PAGE)
        self.assertEqual(implantation.hrefs.count("/khirurhichna-stomatolohiia.html"), 1)
        pages = {
            "/": parse_repository_html("index.html"),
            "/price.html": price,
            "/implantatsiia-zubiv.html": implantation,
            "/khirurhichna-stomatolohiia.html": parse_repository_html(SURGICAL_PAGE),
        }
        surgical = pages["/khirurhichna-stomatolohiia.html"]
        for href in surgical.hrefs:
            url = urlsplit(href)
            if url.scheme or url.netloc or href.startswith(("tel:", "mailto:")):
                continue
            target_path = url.path or "/khirurhichna-stomatolohiia.html"
            if not target_path.startswith("/"):
                target_path = "/" + target_path
            self.assertIn(target_path, pages, href)
            if not url.fragment:
                continue
            if target_path == "/price.html" and url.fragment == "khirurhiia":
                self.assertIn("slug: 'khirurhiia'", (REPOSITORY_ROOT / "prices.js").read_text(encoding="utf-8"))
            else:
                self.assertIn(url.fragment, pages[target_path].ids, href)

    def test_surgical_page_restricted_content_and_crawler_guards(self) -> None:
        source = (REPOSITORY_ROOT / SURGICAL_PAGE).read_text(encoding="utf-8", errors="strict")
        visible = normalized_text(parse_repository_html(SURGICAL_PAGE).body_text).casefold()
        for forbidden in (
            "гарантія", "гарантований", "100%", "безболіс", "назавжди",
            "підходить усім", "протипоказ", "ризик", "відновлен",
            "успішність", "років досвіду", "ліцензован", "перевірено лікарем",
            "терміновий прийом", "лікуємо дітей", "обов’язкова кт",
        ):
            self.assertNotIn(forbidden, visible)
        for marker in ("bot-only", "ai-only", "hidden-ai", "oai-searchbot", "gptbot"):
            self.assertNotIn(marker, source.casefold())
        self.assertNotRegex(source.casefold(), r"<meta[^>]+(?:noindex|nofollow)")

    def test_implantation_page_head_contract_is_exact(self) -> None:
        source = (REPOSITORY_ROOT / IMPLANTATION_PAGE).read_text(encoding="utf-8", errors="strict")
        parsed = parse_repository_html(IMPLANTATION_PAGE)
        self.assertTrue(source.startswith('<!DOCTYPE html>\n<html lang="uk">\n'))
        self.assertEqual(parsed.titles, [IMPLANTATION_TITLE])
        self.assertEqual(parsed.canonicals, [IMPLANTATION_CANONICAL])
        self.assertEqual(parsed.json_ld_texts, [])

        favicons = [
            link
            for link in parsed.links
            if "icon" in (link.get("rel") or "").casefold().split()
        ]
        self.assertEqual(favicons, [{"rel": "icon", "type": "image/png", "href": LOGO_URL}])

        expected_properties = {
            "og:type": "website",
            "og:locale": "uk_UA",
            "og:site_name": "Bella Dent Clinic",
            "og:title": IMPLANTATION_TITLE,
            "og:description": IMPLANTATION_DESCRIPTION,
            "og:url": IMPLANTATION_CANONICAL,
            "og:image": LOGO_URL,
            "og:image:alt": "Bella Dent Clinic",
        }
        expected_names = {
            "description": IMPLANTATION_DESCRIPTION,
            "twitter:card": "summary",
            "twitter:title": IMPLANTATION_TITLE,
            "twitter:description": IMPLANTATION_DESCRIPTION,
            "twitter:image": LOGO_URL,
            "twitter:image:alt": "Bella Dent Clinic",
        }
        for attribute, expected in (("property", expected_properties), ("name", expected_names)):
            for key, value in expected.items():
                matches = [
                    meta.get("content")
                    for meta in parsed.metas
                    if meta.get(attribute) == key
                ]
                self.assertEqual(matches, [value], key)

        robots_values = [
            meta.get("content", "")
            for meta in parsed.metas
            if (meta.get("name") or "").casefold() in {"robots", "googlebot"}
        ]
        self.assertFalse(any("noindex" in value.casefold() or "nofollow" in value.casefold() for value in robots_values))

    def test_implantation_page_visible_answer_contract_is_exact(self) -> None:
        parsed = parse_repository_html(IMPLANTATION_PAGE)
        visible = normalized_text(parsed.body_text)
        self.assertEqual(parsed.h1_texts, ["Імплантація зубів у Кривому Розі"])
        self.assertEqual(
            parsed.h2_texts,
            [
                "Де надається послуга?",
                "Хто вказаний у поточному списку лікарів?",
                "Які ціни опубліковані?",
                "Як записатися на консультацію?",
                "Контакти Bella Dent Clinic",
            ],
        )
        required_copy = [
            "У Bella Dent Clinic у Кривому Розі опубліковано напрям «Імплантологія». На цій сторінці зібрані позиції з публічного прайсу, контактні дані та способи запису на консультацію.",
            "Інформацію та ціни звірено з публічними джерелами Bella Dent Clinic станом на 18 серпня 2026 року.",
            "Перед записом уточніть поточну вартість і доступність послуги у клініці.",
            "Bella Dent Clinic знаходиться у Кривому Розі за адресою: вул. Федора Караманиць, 43/3А, Покровський район, 50000.",
            "У поточному списку лікарів Bella Dent Clinic опубліковано: Олійник Ігор Євгенійович — Головний лікар клініки, хірург-стоматолог, імплантолог, ортопед.",
            "Нижче наведено 29 позицій розділу «Імплантологія» з публічного прайсу Bella Dent Clinic, звірених 18 серпня 2026 року.",
            "Поточний прайс може оновлюватися. Перед записом уточніть актуальну вартість у клініці.",
            "Скористайтеся формою консультації на головній сторінці або зателефонуйте за номером 096 430 37 19.",
            "Україна, Дніпропетровська область, 50000, м. Кривий Ріг, Покровський район, вул. Федора Караманиць, 43/3А",
            "Пн–Пт 09:00–18:00 Сб 09:00–14:00 Нд 09:00–16:00",
            "Сторінка містить інформацію з публічного прайсу та контактів Bella Dent Clinic. Для уточнення послуги, її доступності та поточної вартості зверніться до клініки.",
        ]
        for expected in required_copy:
            self.assertIn(expected, visible)
        self.assertNotIn("Ватутіна", visible)
        self.assertEqual(len(parsed.id_values), len(set(parsed.id_values)))

        def anchors_for(href: str) -> list[dict[str, object]]:
            return [
                anchor
                for anchor in parsed.anchors
                if isinstance(anchor["attributes"], dict)
                and anchor["attributes"].get("href") == href
            ]

        self.assertTrue(anchors_for("/#contacts"))
        self.assertTrue(anchors_for("tel:+380964303719"))
        self.assertTrue(anchors_for("mailto:klinikanika@gmail.com"))
        self.assertTrue(anchors_for("/price.html#implantolohiia"))
        maps = anchors_for(MAP_URL)
        self.assertGreaterEqual(len(maps), 2)
        for anchor in maps:
            self.assertEqual(anchor["attributes"].get("target"), "_blank")
            self.assertEqual(anchor["attributes"].get("rel"), "noopener")

    def test_implantation_price_table_and_fallback_are_exact(self) -> None:
        parsed = parse_repository_html(IMPLANTATION_PAGE)
        self.assertEqual(parsed.table_captions, ["Опубліковані позиції розділу «Імплантологія»"])
        self.assertEqual(parsed.th_scopes, ["col", "col", "col"])
        self.assertEqual(parsed.table_rows[0], ["№", "Назва", "Ціна"])
        expected_rows = [
            [str(index), name, price]
            for index, (name, price) in enumerate(EXPECTED_IMPLANTATION_PRICES, 1)
        ]
        self.assertEqual(parsed.table_rows[1:], expected_rows)
        self.assertEqual(len(parsed.table_rows) - 1, 29)

        price_source = (REPOSITORY_ROOT / "prices.js").read_text(encoding="utf-8", errors="strict")
        start = price_source.index("title: 'Імплантологія'")
        end = price_source.index("\n  }\n];", start)
        implantation_block = price_source[start:end]
        fallback_rows = re.findall(
            r"\{ name: '([^']+)', price: '([^']+)' \}",
            implantation_block,
        )
        self.assertEqual(fallback_rows, EXPECTED_IMPLANTATION_PRICES)
        for obsolete in (
            "Імпланти: Neobiotech, Identall",
            "Встановлення кісткового блоку 7,5202",
            "Встановлення кісткового блоку 7,5302",
        ):
            self.assertNotIn(obsolete, price_source)

    def test_implantation_internal_links_and_fragments_are_resolvable(self) -> None:
        home_source = (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8", errors="strict")
        self.assertEqual(
            home_source.count(
                "a.href = cat.slug === 'khirurhiia' ? 'khirurhichna-stomatolohiia.html' : cat.slug === 'implantolohiia' ? 'implantatsiia-zubiv.html' : 'price.html#' + cat.slug;"
            ),
            1,
        )
        self.assertEqual(
            home_source.count(
                "var cardCta = cat.slug === 'khirurhiia' ? 'Детальніше про хірургію' : cat.slug === 'implantolohiia' ? 'Детальніше про імплантацію' : 'Відкрити прайс';"
            ),
            1,
        )

        price = parse_repository_html("price.html")
        price_links = [
            anchor
            for anchor in price.anchors
            if isinstance(anchor["attributes"], dict)
            and anchor["attributes"].get("href") == "/implantatsiia-zubiv.html"
        ]
        self.assertEqual(len(price_links), 1)
        self.assertEqual(normalized_text(price_links[0]["text"]), "Імплантація зубів")

        pages = {
            "/": parse_repository_html("index.html"),
            "/price.html": price,
            "/implantatsiia-zubiv.html": parse_repository_html(IMPLANTATION_PAGE),
            "/khirurhichna-stomatolohiia.html": parse_repository_html(SURGICAL_PAGE),
        }
        implantation = pages["/implantatsiia-zubiv.html"]
        for href in implantation.hrefs:
            url = urlsplit(href)
            if url.scheme or url.netloc or href.startswith(("tel:", "mailto:")):
                continue
            target_path = url.path
            if not target_path:
                target_path = "/implantatsiia-zubiv.html"
            elif not target_path.startswith("/"):
                target_path = "/" + target_path
            self.assertIn(target_path, pages, href)
            if not url.fragment:
                continue
            if target_path == "/price.html" and url.fragment == "implantolohiia":
                self.assertIn("slug: 'implantolohiia'", (REPOSITORY_ROOT / "prices.js").read_text(encoding="utf-8"))
            else:
                self.assertIn(url.fragment, pages[target_path].ids, href)

    def test_implantation_page_restricted_content_and_crawler_guards(self) -> None:
        source = (REPOSITORY_ROOT / IMPLANTATION_PAGE).read_text(encoding="utf-8", errors="strict")
        folded = source.casefold()
        visible_folded = normalized_text(parse_repository_html(IMPLANTATION_PAGE).body_text).casefold()
        for forbidden in (
            "гарантія",
            "гарантований",
            "100%",
            "безболіс",
            "назавжди",
            "підходить усім",
            "протипоказ",
            "ризик",
            "відновлен",
            "успішність",
            "років досвіду",
            "сертифікат",
            "ліцензован",
        ):
            self.assertNotIn(forbidden, visible_folded)
        for bot_only_marker in ("bot-only", "ai-only", "hidden-ai", "oai-searchbot", "gptbot"):
            self.assertNotIn(bot_only_marker, folded)
        self.assertNotRegex(folded, r"<meta[^>]+(?:noindex|nofollow)")
        robots = (REPOSITORY_ROOT / "robots.txt").read_text(encoding="utf-8", errors="strict")
        self.assertIn("User-agent: *\nAllow: /", robots)
        self.assertNotRegex(robots, r"(?im)^\s*Disallow\s*:")

    def test_homepage_json_ld_is_exact_visible_fact_entity(self) -> None:
        index = parse_repository_html("index.html")
        price = parse_repository_html("price.html")
        implantation = parse_repository_html(IMPLANTATION_PAGE)
        surgical = parse_repository_html(SURGICAL_PAGE)
        self.assertEqual(len(index.json_ld_texts), 1)
        self.assertEqual(price.json_ld_texts, [])
        self.assertEqual(implantation.json_ld_texts, [])
        self.assertEqual(surgical.json_ld_texts, [])

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

        self.assertEqual(index.img_alts.count("Клініка Ніка Дент"), 32)
        for path in (index_path, price_path):
            source = path.read_text(encoding="utf-8", errors="strict")
            self.assertNotIn("t.me/", source.casefold())
            self.assertNotIn("telegram.me/", source.casefold())

        price_raw = price_path.read_bytes()
        self.assertIn(b"<body", price_raw)
        price_body = b"<body" + price_raw.split(b"<body", 1)[1]
        canonical_price_body = canonicalize_newlines_to_lf(price_body)
        approved_price_body_hash = "ec497c6363316582dc89931c6fff850ddea19f0a4eb7eaf05ae17e3af1a51cd6"
        self.assertEqual(
            hashlib.sha256(canonical_price_body).hexdigest(),
            approved_price_body_hash,
        )
        synthetic_crlf_price_body = canonical_price_body.replace(b"\n", b"\r\n")
        self.assertEqual(
            hashlib.sha256(canonicalize_newlines_to_lf(synthetic_crlf_price_body)).hexdigest(),
            approved_price_body_hash,
        )
        mutated_price_body = canonical_price_body.replace(b"<body", b"<body data-mutation", 1)
        self.assertNotEqual(
            hashlib.sha256(canonicalize_newlines_to_lf(mutated_price_body)).hexdigest(),
            approved_price_body_hash,
        )
        self.assertEqual(
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "80387b7ab0b143750e6dd6fa3b092a0272f8301a78c566e8c02ebb44de2aef9a",
        )

    def test_homepage_static_image_delivery_contract_is_exact(self) -> None:
        page = parse_repository_html("index.html")
        source = (REPOSITORY_ROOT / "index.html").read_text(
            encoding="utf-8",
            errors="strict",
        )

        normal_images = [
            image for image in page.images if not bool(image["noscript"])
        ]
        fallback_images = [
            image for image in page.images if bool(image["noscript"])
        ]

        logo_images = [
            image["attributes"]
            for image in normal_images
            if image["attributes"].get("src") == "images/bella-dent-mark.png.png"
        ]
        self.assertEqual(len(logo_images), 2)
        self.assertEqual(
            [image.get("class") for image in logo_images],
            ["brand-mark", "footer-brand-mark"],
        )
        for image in logo_images:
            self.assertEqual(image.get("alt"), "Bella Dent Clinic")
            self.assertEqual((image.get("width"), image.get("height")), ("1074", "873"))
            self.assertNotEqual(image.get("loading"), "lazy")
            self.assertIsNone(image.get("data-src"))

        gallery = [
            image["attributes"]
            for image in normal_images
            if "about-slide" in (image["attributes"].get("class") or "").split()
        ]
        expected_gallery_paths = [path for path, _, _ in GALLERY_IMAGES]
        self.assertEqual(len(gallery), 16)
        self.assertEqual([image.get("data-src") for image in gallery], expected_gallery_paths)
        self.assertTrue(all(image.get("src") is None for image in gallery))
        self.assertEqual([image.get("alt") for image in gallery], ["Клініка Ніка Дент"] * 16)
        self.assertEqual(
            [(int(image["width"]), int(image["height"])) for image in gallery],
            [(width, height) for _, width, height in GALLERY_IMAGES],
        )
        self.assertTrue(all(image.get("loading") == "lazy" for image in gallery))
        self.assertTrue(all(image.get("decoding") == "async" for image in gallery))
        self.assertEqual(len(set(expected_gallery_paths)), 15)
        self.assertEqual(expected_gallery_paths.count("images/1779104606802140.jpg"), 2)

        fallback_gallery = [
            image["attributes"]
            for image in fallback_images
            if "about-slide" in (image["attributes"].get("class") or "").split()
        ]
        self.assertEqual(len(fallback_gallery), 16)
        self.assertEqual([image.get("src") for image in fallback_gallery], expected_gallery_paths)
        self.assertEqual([image.get("alt") for image in fallback_gallery], ["Клініка Ніка Дент"] * 16)
        self.assertEqual(
            [(int(image["width"]), int(image["height"])) for image in fallback_gallery],
            [(width, height) for _, width, height in GALLERY_IMAGES],
        )
        self.assertTrue(all(image.get("data-src") is None for image in fallback_gallery))

        cases = [
            image["attributes"]
            for image in normal_images
            if (image["attributes"].get("src") or "").startswith("cases/case-")
        ]
        self.assertEqual(len(cases), 9)
        self.assertEqual([image.get("src") for image in cases], [path for path, _, _ in CASE_IMAGES])
        self.assertEqual([image.get("alt") for image in cases], [f"Кейс {number}" for number in range(1, 10)])
        self.assertEqual(
            [(int(image["width"]), int(image["height"])) for image in cases],
            [(width, height) for _, width, height in CASE_IMAGES],
        )
        self.assertTrue(all(image.get("loading") == "lazy" for image in cases))
        self.assertTrue(all(image.get("decoding") == "async" for image in cases))

        self.assertEqual(source.count("image.src = image.dataset.src;"), 1)
        self.assertIn("new IntersectionObserver", source)
        self.assertIn("document.addEventListener('DOMContentLoaded', observeGallery, { once: true });", source)
        self.assertIn("{ rootMargin: '500px 0px' }", source)
        self.assertIn("function loadSlide(index)", source)
        self.assertIn("function loadAdjacent(index)", source)
        self.assertNotIn("slides.forEach(function(image) { image.src", source)

    def test_dynamic_doctor_and_certificate_dimensions_are_exact(self) -> None:
        source = (REPOSITORY_ROOT / "index.html").read_text(
            encoding="utf-8",
            errors="strict",
        )
        doctor_block = source[
            source.index("var DOCTOR_PHOTO_DIMENSIONS") : source.index("var PLACEHOLDER_SVG")
        ]
        doctor_dimensions = {
            path: (int(width), int(height))
            for path, width, height in re.findall(
                r"'(doctors/[^']+)': \[(\d+), (\d+)\]",
                doctor_block,
            )
        }
        self.assertEqual(doctor_dimensions, DOCTOR_IMAGE_DIMENSIONS)
        render_block = source[source.index("function renderDoctors") : source.index("})();", source.index("function renderDoctors"))]
        self.assertIn("img.loading = 'lazy';", render_block)
        self.assertIn("img.decoding = 'async';", render_block)
        self.assertIn("img.width = dimensions[0];", render_block)
        self.assertIn("img.height = dimensions[1];", render_block)
        self.assertIn("img.onerror = function () { photoDiv.innerHTML = PLACEHOLDER_SVG; };", render_block)
        self.assertIn("nameDiv.textContent = d.name;", render_block)
        self.assertIn("roleDiv.textContent = d.role;", render_block)

        certificate_block = source[
            source.index("var CERTIFICATE_DIMENSIONS") : source.index("var track", source.index("var CERTIFICATE_DIMENSIONS"))
        ]
        certificate_dimensions = {
            path: (int(width), int(height))
            for path, width, height in re.findall(
                r"'(\./certificates/[^']+)': \[(\d+), (\d+)\]",
                certificate_block,
            )
        }
        self.assertEqual(certificate_dimensions, CERTIFICATE_IMAGE_DIMENSIONS)
        make_slide_block = source[source.index("function makeSlide") : source.index("function rebuildSizes")]
        self.assertIn("img.setAttribute('loading', 'lazy');", make_slide_block)
        self.assertIn("img.setAttribute('decoding', 'async');", make_slide_block)
        self.assertIn("img.setAttribute('width', String(dimensions[0]));", make_slide_block)
        self.assertIn("img.setAttribute('height', String(dimensions[1]));", make_slide_block)
        self.assertLess(make_slide_block.index("img.setAttribute('width'"), make_slide_block.index("img.src = src;"))

    def test_homepage_performance_pr_preserves_assets_and_repository_boundary(self) -> None:
        image_extensions = {".avif", ".gif", ".jpg", ".jpeg", ".png", ".svg", ".webp"}
        image_paths = sorted(
            path
            for path in self.manifest_entries
            if Path(path).suffix.casefold() in image_extensions
        )
        image_records = [
            f"{path}\0{hashlib.sha256((REPOSITORY_ROOT / path).read_bytes()).hexdigest()}"
            for path in image_paths
        ]
        self.assertEqual(len(image_paths), 45)
        self.assertEqual(sum((REPOSITORY_ROOT / path).stat().st_size for path in image_paths), 65_170_885)
        self.assertEqual(
            hashlib.sha256("\n".join(image_records).encode("utf-8")).hexdigest(),
            "d875fc137cb3c6bc776caae6a3641d81710a80291f449927fd4516d642e43bd1",
        )

        tracked_output = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", errors="strict")
        tracked_paths = [path for path in tracked_output.split("\0") if path]
        allowed_paths = {
            "implantatsiia-zubiv.html",
            "index.html",
            "khirurhichna-stomatolohiia.html",
            "pages-public-manifest.txt",
            "price.html",
            "sitemap.xml",
            "tests/test_pages_artifact_isolation.py",
        }
        protected_records = []
        for path in tracked_paths:
            if path in allowed_paths:
                continue
            object_id = subprocess.run(
                ["git", "hash-object", f"--path={path}", path],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
            protected_records.append(f"{path}\0{object_id}")
        self.assertEqual(len(protected_records), 171)
        self.assertEqual(
            hashlib.sha256("\n".join(protected_records).encode("utf-8")).hexdigest(),
            "caf4ec1dd2bb079ed52e5671626715f944ca2f65b30672b33d95ad555d683122",
        )

        self.assertNotIn("llms.txt", self.manifest_entries)
        self.assertFalse(any(path.startswith(".seo/") for path in self.manifest_entries))

    def test_price_hero_stale_reference_is_absent_from_public_code(self) -> None:
        stale_filename = "фото для прайса.jpg"
        stale_path = f"images/{stale_filename}"
        encoded_filename = quote(stale_filename, safe="").casefold()
        encoded_path = quote(stale_path, safe="/").casefold()

        self.assertNotIn(stale_path, self.manifest_entries)
        self.assertEqual(len(self.manifest_entries), 58)
        for relative_path in self.manifest_entries:
            if Path(relative_path).suffix.casefold() not in {".css", ".html", ".js"}:
                continue
            source = (REPOSITORY_ROOT / relative_path).read_text(
                encoding="utf-8",
                errors="strict",
            )
            with self.subTest(relative_path=relative_path):
                self.assertNotIn(stale_filename, source)
                self.assertNotIn(stale_path, source)
                self.assertNotIn(encoded_filename, source.casefold())
                self.assertNotIn(encoded_path, source.casefold())

        artifact_price = self.output / "price.html"
        self.assertNotIn(
            stale_path,
            VERIFIER._references_for("price.html", artifact_price),
        )
        artifact_source = artifact_price.read_text(encoding="utf-8", errors="strict")
        self.assertNotIn(stale_path, artifact_source)
        self.assertNotIn(encoded_path, artifact_source.casefold())

    def test_price_catalog_and_public_diff_boundary_are_exact(self) -> None:
        price_source = (REPOSITORY_ROOT / "price.html").read_text(
            encoding="utf-8",
            errors="strict",
        )
        expected_price_hero_rule = (
            ".price-hero{padding:160px 0 90px;position:relative;"
            "background-size:cover;background-position:center;"
            "background-repeat:no-repeat;"
            "border-bottom:1px solid rgba(196,154,85,.15);}"
        )
        self.assertEqual(price_source.count(expected_price_hero_rule), 1)
        self.assertEqual(price_source.count(".price-hero::before{"), 1)

        prices_path = REPOSITORY_ROOT / "prices.js"
        prices_source = prices_path.read_text(encoding="utf-8", errors="strict")
        prices_raw = prices_path.read_bytes()
        prices_lf = canonicalize_newlines_to_lf(prices_raw)
        expected_prices_lf_sha256 = (
            "b62efce80b6ef43a3ebe67085b1679c1b24c68ff65fd79fb50cbf15ec50402c5"
        )
        self.assertEqual(
            hashlib.sha256(prices_lf).hexdigest(),
            expected_prices_lf_sha256,
        )
        synthetic_crlf = prices_lf.replace(b"\n", b"\r\n")
        self.assertEqual(
            hashlib.sha256(canonicalize_newlines_to_lf(synthetic_crlf)).hexdigest(),
            expected_prices_lf_sha256,
        )
        self.assertEqual(len(re.findall(r"(?m)^\s*title:", prices_source)), 5)
        self.assertEqual(
            len(re.findall(r"\{ name: '.*?', price: '.*?' \}", prices_source)),
            180,
        )

        price = parse_repository_html("price.html")
        self.assertEqual(price.titles, ["Прайс клініки — Bella Dent Clinic"])
        self.assertEqual(price.canonicals, [f"{SITE_ROOT}price.html"])
        self.assertEqual(price.json_ld_texts, [])
        self.assertEqual(price.hrefs.count("/implantatsiia-zubiv.html"), 1)
        self.assertEqual(price.hrefs.count("/khirurhichna-stomatolohiia.html"), 1)

        public_records = []
        for relative_path in self.manifest_entries:
            if relative_path in {"index.html", "price.html"}:
                continue
            object_id = subprocess.run(
                ["git", "hash-object", f"--path={relative_path}", relative_path],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
            public_records.append(f"{relative_path}\0{object_id}")
        public_aggregate = hashlib.sha256("\n".join(public_records).encode("utf-8")).hexdigest()
        self.assertEqual(len(public_records), 56)
        self.assertEqual(
            public_aggregate,
            "12d0a469213f35dcbeaf42e94f9680a12f63bcce281c647f5368228c3a78928c",
        )
        candidate_price_object = subprocess.run(
            ["git", "hash-object", "--path=price.html", "price.html"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        self.assertEqual(candidate_price_object, "427ed9a7fb745abb066c1e47b64e2e87fe991810")
        self.assertNotEqual(
            candidate_price_object,
            "52db00f3a4b7e893ed477bd97c91084f8a590cba",
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
        expected_new_files = {"robots.txt", "sitemap.xml", IMPLANTATION_PAGE, SURGICAL_PAGE}
        expected_protected_files = {".nojekyll", "CNAME"}
        forbidden_prefixes = (".github/", ".seo/", "docs/", "scripts/", "server/", "tests/")

        self.assertEqual(len(self.manifest_entries), 58)
        self.assertEqual(len(set(self.manifest_entries)), 58)
        self.assertTrue(expected_new_files.issubset(self.manifest_entries))
        self.assertTrue(expected_protected_files.issubset(self.manifest_entries))
        self.assertNotIn("pages-public-manifest.txt", self.manifest_entries)
        self.assertNotIn("bella-dent-clinic-fixed.html", self.manifest_entries)
        self.assertFalse(
            any(entry.startswith(forbidden_prefixes) for entry in self.manifest_entries)
        )
        self.assertEqual(self.build_report["file_count"], 58)
        self.assertEqual(self.verify_report["file_count"], 58)
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
        self.assertEqual([element.tag for element in urls], [url_tag] * len(EXPECTED_SITEMAP_LOCS))
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
            IMPLANTATION_PAGE: IMPLANTATION_CANONICAL,
            SURGICAL_PAGE: SURGICAL_CANONICAL,
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
        self.assertEqual(price.hrefs.count("/implantatsiia-zubiv.html"), 1)
        self.assertEqual(price.hrefs.count("/khirurhichna-stomatolohiia.html"), 1)

        normalized_fragments = {
            urlsplit(href).fragment
            for href in price.hrefs
            if href.startswith("/#")
        }
        self.assertTrue(normalized_fragments)
        self.assertTrue(normalized_fragments.issubset(home.ids))


class RepositoryDoctorDomSecurityTests(unittest.TestCase):
    MALICIOUS_NAME = '<img src=x onerror="window.__bellaInjected=1">Dr Test'
    MALICIOUS_ROLE = '<svg onload="window.__bellaInjected=2"></svg><script>window.__bellaInjected=3</script>'
    ADDITIONAL_TEXT = '<b>Implantologist</b> & "quoted"'

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (REPOSITORY_ROOT / "index.html").read_text(encoding="utf-8", errors="strict")
        marker = "/* ── Секція «Наші лікарі»"
        marker_offset = cls.source.index(marker)
        script_start = cls.source.rfind("<script>", 0, marker_offset)
        script_end = cls.source.index("</script>", marker_offset)
        cls.doctor_script = cls.source[script_start + len("<script>") : script_end]

        style_start = cls.source.index("<style>")
        style_end = cls.source.index("</style>", style_start) + len("</style>")
        cls.styles = cls.source[style_start:style_end]

        candidates = [
            os.environ.get("BELLA_CHROME_PATH"),
            shutil.which("google-chrome"),
            shutil.which("google-chrome-stable"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ]
        cls.chrome = next(
            (str(candidate) for candidate in candidates if candidate and Path(candidate).is_file()),
            None,
        )
        if cls.chrome is None:
            raise AssertionError("system Chrome is required for doctor DOM security regression tests")

    @classmethod
    def _validate_test_owned_chrome_launch(
        cls,
        temp_root: Path,
        profile_path: Path,
        launch_command: list[str],
    ) -> None:
        system_temp = Path(tempfile.gettempdir()).resolve()
        resolved_root = temp_root.resolve()
        resolved_profile = profile_path.resolve()
        if (
            resolved_root.parent != system_temp
            or not resolved_root.name.startswith("bella-doctor-browser-")
            or resolved_profile != resolved_root / "chrome-profile"
        ):
            raise AssertionError(
                f"refusing to launch Chrome outside the exact test-owned profile boundary: {profile_path}"
            )

        installed_chrome = Path(cls.chrome).resolve(strict=True)
        launched_chrome = Path(launch_command[0]).resolve(strict=True)
        if not installed_chrome.is_file() or launched_chrome != installed_chrome:
            raise AssertionError(
                f"refusing to launch an unexpected Chrome executable: {launch_command[0]}"
            )

        expected_profile_argument = f"--user-data-dir={resolved_profile}"
        if launch_command.count(expected_profile_argument) != 1:
            raise AssertionError(
                f"Chrome launch does not own the exact test profile {resolved_profile}: {launch_command}"
            )

    @classmethod
    def _terminate_windows_test_owned_chrome(
        cls,
        process: subprocess.Popen[bytes],
        temp_root: Path,
        profile_path: Path,
        launch_command: list[str],
    ) -> None:
        cls._validate_test_owned_chrome_launch(temp_root, profile_path, launch_command)
        if list(process.args) != launch_command or process.pid <= 0:
            raise AssertionError(
                f"refusing to terminate Chrome without the exact retained Popen ownership: "
                f"PID {process.pid}; args {process.args}"
            )
        if process.poll() is not None:
            return

        taskkill = subprocess.Popen(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            taskkill.wait(timeout=10)
        except subprocess.TimeoutExpired:
            taskkill.kill()
            try:
                taskkill.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        if process.poll() is None:
            process.kill()

    @staticmethod
    def _read_windows_process_command_line(process_handle: int) -> str:
        import ctypes
        from ctypes import wintypes

        class ProcessBasicInformation(ctypes.Structure):
            _fields_ = [
                ("Reserved1", ctypes.c_void_p),
                ("PebBaseAddress", ctypes.c_void_p),
                ("Reserved2_0", ctypes.c_void_p),
                ("Reserved2_1", ctypes.c_void_p),
                ("UniqueProcessId", ctypes.c_void_p),
                ("InheritedFromUniqueProcessId", ctypes.c_void_p),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        kernel32.ReadProcessMemory.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.LPVOID,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        kernel32.ReadProcessMemory.restype = wintypes.BOOL

        def read_memory(address: int, size: int) -> bytes:
            buffer = (ctypes.c_ubyte * size)()
            read = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(
                process_handle,
                address,
                buffer,
                size,
                ctypes.byref(read),
            ):
                raise OSError(ctypes.get_last_error())
            return bytes(buffer[: read.value])

        basic = ProcessBasicInformation()
        returned = wintypes.ULONG()
        status = ntdll.NtQueryInformationProcess(
            process_handle,
            0,
            ctypes.byref(basic),
            ctypes.sizeof(basic),
            ctypes.byref(returned),
        )
        if status != 0:
            raise OSError(f"NtQueryInformationProcess status {status:#x}")
        pointer_size = ctypes.sizeof(ctypes.c_void_p)
        parameters_offset = 0x20 if pointer_size == 8 else 0x10
        command_line_offset = 0x70 if pointer_size == 8 else 0x40
        pointer_bytes = read_memory(basic.PebBaseAddress + parameters_offset, pointer_size)
        parameters = int.from_bytes(pointer_bytes, "little")
        unicode_string = read_memory(
            parameters + command_line_offset,
            16 if pointer_size == 8 else 8,
        )
        length = int.from_bytes(unicode_string[0:2], "little")
        buffer_offset = 8 if pointer_size == 8 else 4
        buffer_address = int.from_bytes(
            unicode_string[buffer_offset : buffer_offset + pointer_size],
            "little",
        )
        return read_memory(buffer_address, length).decode("utf-16-le", errors="replace")

    @classmethod
    def _windows_test_owned_profile_processes(
        cls,
        profile_path: Path,
        *,
        include_terminated: bool = False,
    ) -> list[dict[str, object]]:
        import ctypes
        from ctypes import wintypes

        system_temp = Path(tempfile.gettempdir()).resolve()
        resolved_profile = profile_path.resolve()
        test_root = resolved_profile.parent
        if (
            test_root.parent != system_temp
            or not test_root.name.startswith("bella-doctor-browser-")
            or resolved_profile != test_root / "chrome-profile"
        ):
            raise AssertionError(f"refusing to inspect a non-test Chrome profile: {profile_path}")

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi")
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        psapi.EnumProcesses.argtypes = [
            ctypes.POINTER(wintypes.DWORD),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        psapi.EnumProcesses.restype = wintypes.BOOL

        pids = (wintypes.DWORD * 32768)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(needed)):
            raise AssertionError(f"could not inspect Windows process IDs: {ctypes.get_last_error()}")

        profile_arguments = (
            f"--user-data-dir={resolved_profile}".casefold(),
            f'--user-data-dir="{resolved_profile}"'.casefold(),
        )
        matches: list[dict[str, object]] = []
        for pid in pids[: needed.value // ctypes.sizeof(wintypes.DWORD)]:
            process_handle = kernel32.OpenProcess(0x0400 | 0x0010 | 0x0001, False, pid)
            if not process_handle:
                continue
            retain_handle = False
            try:
                image = ctypes.create_unicode_buffer(32768)
                image_length = wintypes.DWORD(len(image))
                if not kernel32.QueryFullProcessImageNameW(
                    process_handle,
                    0,
                    image,
                    ctypes.byref(image_length),
                ):
                    continue
                if Path(image.value).name.casefold() != "chrome.exe":
                    continue
                try:
                    command_line = cls._read_windows_process_command_line(process_handle)
                except OSError:
                    continue
                folded_command_line = command_line.casefold()
                if not any(argument in folded_command_line for argument in profile_arguments):
                    continue
                if "bella-doctor-browser-" not in folded_command_line:
                    raise AssertionError(
                        f"refusing a Chrome process without the exact test marker: PID {pid}"
                    )
                if not Path(image.value).samefile(Path(cls.chrome)):
                    raise AssertionError(
                        f"refusing an unexpected Chrome executable for test profile {profile_path}: "
                        f"PID {pid}; executable {image.value}"
                    )
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code)):
                    continue
                is_active = exit_code.value == 259  # STILL_ACTIVE
                if not include_terminated and not is_active:
                    continue
                matches.append(
                    {
                        "ProcessId": int(pid),
                        "ProcessHandle": int(process_handle),
                        "ExecutablePath": image.value,
                        "CommandLine": command_line,
                        "Active": is_active,
                    }
                )
                retain_handle = True
            finally:
                if not retain_handle:
                    kernel32.CloseHandle(process_handle)
        return matches

    @classmethod
    def _terminate_windows_test_owned_profile_residue(cls, profile_path: Path) -> None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        deadline = time.monotonic() + 45
        quiet_since: float | None = None
        observed_pids: set[int] = set()
        kill_errors: set[str] = set()
        while True:
            matches = cls._windows_test_owned_profile_processes(profile_path)
            if not matches:
                if quiet_since is None:
                    quiet_since = time.monotonic()
                elif time.monotonic() - quiet_since >= 0.5:
                    return
                if time.monotonic() >= deadline:
                    return
                time.sleep(0.1)
                continue

            quiet_since = None
            process_ids = sorted(int(match["ProcessId"]) for match in matches)
            observed_pids.update(process_ids)
            for match in matches:
                process_id = int(match["ProcessId"])
                process_handle = int(match["ProcessHandle"])
                try:
                    if not kernel32.TerminateProcess(process_handle, 1):
                        kill_errors.add(
                            f"PID {process_id}: TerminateProcess error {ctypes.get_last_error()}"
                        )
                finally:
                    kernel32.CloseHandle(process_handle)
            if time.monotonic() >= deadline:
                remaining = cls._windows_test_owned_profile_processes(profile_path)
                if not remaining:
                    return
                remaining_pids = [int(match["ProcessId"]) for match in remaining]
                for match in remaining:
                    kernel32.CloseHandle(int(match["ProcessHandle"]))
                raise AssertionError(
                    f"test-owned Chrome residue did not exit for {profile_path}; "
                    f"observed PIDs {sorted(observed_pids)}; "
                    f"remaining PIDs {remaining_pids}; "
                    f"termination errors {sorted(kill_errors)}"
                )
            time.sleep(0.1)

    @classmethod
    def _wait_for_windows_test_owned_profile_objects(cls, profile_path: Path) -> None:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        deadline = time.monotonic() + 60
        quiet_since: float | None = None
        observed_pids: set[int] = set()
        while True:
            matches = cls._windows_test_owned_profile_processes(
                profile_path,
                include_terminated=True,
            )
            process_ids = sorted(int(match["ProcessId"]) for match in matches)
            observed_pids.update(process_ids)
            for match in matches:
                kernel32.CloseHandle(int(match["ProcessHandle"]))
            if not matches:
                if quiet_since is None:
                    quiet_since = time.monotonic()
                elif time.monotonic() - quiet_since >= 0.5:
                    return
                time.sleep(0.1)
                continue
            quiet_since = None
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"test-owned Chrome process objects did not disappear for {profile_path}; "
                    f"observed PIDs {sorted(observed_pids)}; remaining PIDs {process_ids}"
                )
            time.sleep(0.1)

    @classmethod
    def browser_result(
        cls,
        doctors: list[dict[str, object]] | None = None,
        *,
        ready: bool = True,
        reject: bool = False,
    ) -> dict[str, object]:
        fixture_json = json.dumps(doctors or [], ensure_ascii=True, separators=(",", ":"))
        fixture_base64 = base64.b64encode(fixture_json.encode("ascii")).decode("ascii")
        if reject:
            load_expression = "Promise.reject(new Error('deterministic Sheet failure'))"
        else:
            load_expression = f"Promise.resolve(JSON.parse(atob('{fixture_base64}')))"

        instrumentation = """
<script>
window.__bellaErrors = [];
window.addEventListener('error', function (event) {
  window.__bellaErrors.push(String(event.message || event.error || 'error'));
});
window.addEventListener('unhandledrejection', function (event) {
  window.__bellaErrors.push(String(event.reason || 'unhandled rejection'));
});
</script>
"""
        sheets_stub = f"""
<script>
window.SheetsLoader = {{
  ready: {str(ready).lower()},
  loadDoctorsData: function () {{ return {load_expression}; }}
}};
</script>
"""
        result_probe = """
<pre id="results"></pre>
<script>
setTimeout(function () {
  var grid = document.getElementById('doctors-grid');
  var gridRect = grid.getBoundingClientRect();
  var cards = Array.from(grid.querySelectorAll('.doctor-card')).map(function (card) {
    var image = card.querySelector('.doctor-photo img');
    return {
      className: card.className,
      name: card.querySelector('.doctor-name').textContent,
      role: card.querySelector('.doctor-role').textContent,
      photo: image ? image.getAttribute('src') : null,
      alt: image ? image.getAttribute('alt') : null,
      loading: image ? image.getAttribute('loading') : null,
      decoding: image ? image.getAttribute('decoding') : null,
      width: image ? image.getAttribute('width') : null,
      height: image ? image.getAttribute('height') : null,
      plusCount: card.querySelectorAll('.doctor-plus').length
    };
  });
  var layoutContained = Array.from(grid.querySelectorAll('.doctor-card')).every(function (card) {
    var rect = card.getBoundingClientRect();
    return rect.left >= gridRect.left - 0.5 && rect.right <= gridRect.right + 0.5;
  });
  document.getElementById('results').textContent = JSON.stringify({
    cards: cards,
    injectedOwnProperty: Object.prototype.hasOwnProperty.call(window, '__bellaInjected'),
    injectedValue: window.__bellaInjected === undefined ? null : window.__bellaInjected,
    injectedImageCount: grid.querySelectorAll('img[src="x"]').length,
    injectedSvgCount: grid.querySelectorAll('svg[onload]').length,
    injectedScriptCount: grid.querySelectorAll('script').length,
    errors: window.__bellaErrors,
    layoutContained: layoutContained,
    horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
  });
}, 250);
</script>
"""
        harness = "".join(
            (
                "<!doctype html><html><head><meta charset=\"utf-8\">",
                f'<base href="{REPOSITORY_ROOT.as_uri()}/">',
                cls.styles,
                "</head><body><section id=\"doctors\"><div class=\"container\">",
                '<div class="doctors-grid" id="doctors-grid"></div>',
                "</div></section>",
                instrumentation,
                sheets_stub,
                "<script>",
                cls.doctor_script,
                "</script>",
                result_probe,
                "</body></html>",
            )
        )

        temp_root = Path(tempfile.mkdtemp(prefix="bella-doctor-browser-"))
        harness_path = temp_root / "doctor-harness.html"
        profile_path = temp_root / "chrome-profile"
        process: subprocess.Popen[bytes] | None = None
        stdout_chunks: list[bytes] = []
        result_ready = threading.Event()
        reader_done = threading.Event()
        result_value: list[dict[str, object]] = []
        result_parse_error: list[BaseException] = []
        reader_error: list[BaseException] = []
        reader: threading.Thread | None = None
        result_timed_out = False
        launch_command = [
            str(Path(cls.chrome).resolve(strict=True)),
            "--headless=new",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-gpu",
            "--no-first-run",
            "--no-sandbox",
            "--allow-file-access-from-files",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=1000",
            "--window-size=390,844",
            f"--user-data-dir={profile_path.resolve()}",
            "--dump-dom",
            harness_path.as_uri(),
        ]
        try:
            harness_path.write_text(harness, encoding="utf-8", newline="\n")
            cls._validate_test_owned_chrome_launch(temp_root, profile_path, launch_command)
            process = subprocess.Popen(
                launch_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=os.name != "nt",
            )

            if process.stdout is None:
                raise AssertionError("Chrome DOM harness stdout pipe was not created")

            def read_browser_stdout() -> None:
                try:
                    while True:
                        chunk = process.stdout.read1(4096)
                        if not chunk:
                            break
                        stdout_chunks.append(chunk)
                        stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                        match = re.search(r'<pre id="results">(.*?)</pre>', stdout, flags=re.DOTALL)
                        if match is None or not match.group(1):
                            continue
                        try:
                            parsed = json.loads(unescape(match.group(1)))
                        except (json.JSONDecodeError, TypeError) as exc:
                            result_parse_error.append(exc)
                        else:
                            if not isinstance(parsed, dict):
                                result_parse_error.append(
                                    TypeError(f"Chrome DOM harness published {type(parsed).__name__}, not an object")
                                )
                            else:
                                result_value.append(parsed)
                        result_ready.set()
                        break
                except BaseException as exc:
                    reader_error.append(exc)
                    result_ready.set()
                finally:
                    reader_done.set()

            reader = threading.Thread(
                target=read_browser_stdout,
                name=f"bella-doctor-browser-stdout-{process.pid}",
                daemon=True,
            )
            reader.start()
            result_timed_out = not result_ready.wait(timeout=90)
        finally:
            process_cleanup_error: AssertionError | None = None
            stdout_closed = False
            if (
                process is not None
                and process.stdout is not None
                and not result_timed_out
            ):
                if reader is not None:
                    reader_done.wait(timeout=2)
                    reader.join(timeout=0)
                if reader is None or not reader.is_alive():
                    process.stdout.close()
                    stdout_closed = True
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
            if process is not None:
                try:
                    if os.name == "nt":
                        cls._terminate_windows_test_owned_chrome(
                            process,
                            temp_root,
                            profile_path,
                            launch_command,
                        )
                    else:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                except AssertionError as exc:
                    process_cleanup_error = exc
            if process is not None:
                if process.poll() is None:
                    process.kill()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()

            if reader is not None:
                reader_done.wait(timeout=15)
                reader.join(timeout=0)
            if process is not None and process.stdout is not None and not stdout_closed:
                process.stdout.close()
            if reader is not None:
                reader_done.wait(timeout=5)
                reader.join(timeout=0)
                if reader.is_alive() and process_cleanup_error is None:
                    process_cleanup_error = AssertionError(
                        f"Chrome stdout reader did not exit for {profile_path}"
                    )

            if os.name == "nt":
                try:
                    cls._terminate_windows_test_owned_profile_residue(profile_path)
                except AssertionError as exc:
                    process_cleanup_error = exc

            cleanup_error: OSError | None = None
            for attempt in range(600):
                try:
                    if temp_root.exists():
                        shutil.rmtree(temp_root)
                    cleanup_error = None
                    break
                except OSError as exc:
                    cleanup_error = exc
                    time.sleep(0.1)
            if cleanup_error is not None:
                raise AssertionError(
                    f"Chrome did not release temporary profile {profile_path}; "
                    f"exact parent PID {None if process is None else process.pid}; "
                    f"parent return code {None if process is None else process.poll()}; "
                    f"last error: {cleanup_error}"
                ) from cleanup_error
            if os.name == "nt":
                cls._wait_for_windows_test_owned_profile_objects(profile_path)
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process_cleanup_error = AssertionError(
                        f"Chrome parent PID {process.pid} did not exit for {profile_path}"
                    )
            if process_cleanup_error is not None:
                raise process_cleanup_error

        if reader_error:
            raise AssertionError(
                f"Chrome DOM harness stdout reader failed for {profile_path}: {reader_error[0]}"
            ) from reader_error[0]
        if result_timed_out:
            raise AssertionError(
                f"Chrome DOM harness result timed out for temporary profile {profile_path}; "
                f"captured {sum(len(chunk) for chunk in stdout_chunks)} stdout bytes"
            )
        if result_parse_error:
            raise AssertionError(
                f"Chrome DOM harness published invalid results for {profile_path}: {result_parse_error[0]}"
            ) from result_parse_error[0]
        if not result_value:
            returncode = None if process is None else process.returncode
            raise AssertionError(
                f"Chrome DOM harness did not publish results for {profile_path}; Chrome returned {returncode}"
            )
        return result_value[0]

    def test_sheet_fed_text_uses_safe_dom_construction_only(self) -> None:
        render_block = self.doctor_script[self.doctor_script.index("function renderDoctors") :]
        self.assertIn("grid.replaceChildren();", render_block)
        self.assertEqual(render_block.count("nameDiv.textContent = d.name;"), 1)
        self.assertEqual(render_block.count("roleDiv.textContent = d.role;"), 1)
        self.assertNotIn("infoDiv.innerHTML", render_block)
        self.assertNotIn("insertAdjacentHTML", render_block)
        self.assertNotIn("outerHTML", render_block)
        self.assertNotIn("document.write", render_block)

        inner_html_assignments = re.findall(
            r"(\w+)\.innerHTML\s*=\s*([^;]+);",
            render_block,
        )
        self.assertEqual(
            inner_html_assignments,
            [("photoDiv", "PLACEHOLDER_SVG"), ("photoDiv", "PLACEHOLDER_SVG")],
        )
        self.assertTrue(all("d." not in value for _, value in inner_html_assignments))

        placeholder_block = self.doctor_script[
            self.doctor_script.index("var PLACEHOLDER_SVG") : self.doctor_script.index("function renderDoctors")
        ]
        self.assertNotIn("d.", placeholder_block)
        self.assertNotIn("${", placeholder_block)

    def test_normal_sheet_fixture_is_editable_and_preserves_card_contract(self) -> None:
        doctors = [
            {
                "name": "Редагований лікар",
                "role": "Лікар-стоматолог",
                "photo": "doctors/oliynyk1.png",
                "isNurse": False,
            },
            {
                "name": "Редагована асистентка",
                "role": "Медична сестра",
                "photo": "doctors/sokolova.png",
                "isNurse": True,
            },
        ]
        first = self.browser_result(doctors)
        changed = [dict(doctor) for doctor in doctors]
        changed[0]["name"] = "Ім’я змінено лише у Google Sheet fixture"
        second = self.browser_result(changed)

        self.assertEqual(len(first["cards"]), 2)
        self.assertEqual(
            [card["className"] for card in first["cards"]],
            ["doctor-card", "doctor-card doctor-card--nurse"],
        )
        self.assertEqual(
            [card["name"] for card in first["cards"]],
            [doctor["name"] for doctor in doctors],
        )
        self.assertEqual(
            [card["role"] for card in first["cards"]],
            [doctor["role"] for doctor in doctors],
        )
        self.assertEqual(
            [card["photo"] for card in first["cards"]],
            [doctor["photo"] for doctor in doctors],
        )
        self.assertEqual(
            [card["alt"] for card in first["cards"]],
            [doctor["name"] for doctor in doctors],
        )
        self.assertEqual([card["loading"] for card in first["cards"]], ["lazy", "lazy"])
        self.assertEqual([card["decoding"] for card in first["cards"]], ["async", "async"])
        self.assertEqual([card["width"] for card in first["cards"]], ["1086", "1086"])
        self.assertEqual([card["height"] for card in first["cards"]], ["1448", "1448"])
        self.assertEqual([card["plusCount"] for card in first["cards"]], [1, 0])
        self.assertEqual(first["cards"][1:], second["cards"][1:])
        self.assertEqual(second["cards"][0]["name"], changed[0]["name"])
        self.assertNotEqual(first["cards"][0]["name"], second["cards"][0]["name"])
        self.assertNotIn(changed[0]["name"], self.source)
        self.assertTrue(first["layoutContained"])
        self.assertFalse(first["horizontalOverflow"])
        self.assertEqual(first["errors"], [])

    def test_sheet_unavailable_and_failed_load_preserve_static_fallback(self) -> None:
        expected_names = [
            "Олійник Ігор Євгенійович",
            "Рибін Олександр Володимирович",
            "Соколова Анастасія Сергіївна",
            "Сідих Катерина Іванівна",
            "Левченко Ірина Михайлівна",
        ]
        expected_classes = [
            "doctor-card",
            "doctor-card",
            "doctor-card doctor-card--nurse",
            "doctor-card doctor-card--nurse",
            "doctor-card doctor-card--nurse",
        ]
        unavailable = self.browser_result(ready=False)
        failed = self.browser_result(reject=True)
        for result in (unavailable, failed):
            self.assertEqual([card["name"] for card in result["cards"]], expected_names)
            self.assertEqual([card["className"] for card in result["cards"]], expected_classes)
            self.assertEqual([card["plusCount"] for card in result["cards"]], [1, 1, 0, 0, 0])
            self.assertEqual([card["alt"] for card in result["cards"]], expected_names)
            self.assertTrue(all(card["photo"] for card in result["cards"]))
            self.assertTrue(all(card["loading"] == "lazy" for card in result["cards"]))
            self.assertTrue(all(card["decoding"] == "async" for card in result["cards"]))
            self.assertTrue(all(card["width"] == "1086" for card in result["cards"]))
            self.assertTrue(all(card["height"] == "1448" for card in result["cards"]))
            self.assertTrue(result["layoutContained"])
            self.assertFalse(result["horizontalOverflow"])
            self.assertEqual(result["errors"], [])

    def test_adversarial_sheet_markup_is_literal_and_never_executes(self) -> None:
        fixture = [
            {
                "name": self.MALICIOUS_NAME,
                "role": self.MALICIOUS_ROLE,
                "photo": "",
                "isNurse": False,
            },
            {
                "name": "Additional text fixture",
                "role": self.ADDITIONAL_TEXT,
                "photo": "",
                "isNurse": False,
            },
        ]
        result = self.browser_result(fixture)
        self.assertEqual(len(result["cards"]), 2)
        self.assertEqual(result["cards"][0]["name"], self.MALICIOUS_NAME)
        self.assertEqual(result["cards"][0]["role"], self.MALICIOUS_ROLE)
        self.assertEqual(result["cards"][1]["role"], self.ADDITIONAL_TEXT)
        self.assertFalse(result["injectedOwnProperty"])
        self.assertIsNone(result["injectedValue"])
        self.assertEqual(result["injectedImageCount"], 0)
        self.assertEqual(result["injectedSvgCount"], 0)
        self.assertEqual(result["injectedScriptCount"], 0)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["layoutContained"])
        self.assertFalse(result["horizontalOverflow"])


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
