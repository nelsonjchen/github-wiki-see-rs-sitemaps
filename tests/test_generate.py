"""Offline regression checks for the scheduled sitemap generator."""

import contextlib
import datetime
import functools
import gzip
import http.server
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from diskcache import Cache
from smart_open import open as smart_open

REPOSITORY = Path(__file__).resolve().parents[1]
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@contextlib.contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache_directory = tempfile.TemporaryDirectory()
        cls.cache = Cache(cls.cache_directory.name)
        # Import with an isolated cache so tests never read/write production data.
        spec = importlib.util.spec_from_file_location(
            "sitemap_generator_under_test", REPOSITORY / "generator/generate.py"
        )
        cls.generate = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.generate
        with mock.patch("diskcache.Cache", return_value=cls.cache):
            spec.loader.exec_module(cls.generate)

    @classmethod
    def tearDownClass(cls):
        cls.cache.close()
        cls.cache_directory.cleanup()
        del sys.modules[cls.generate.__name__]

    def setUp(self):
        self.cache.clear()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.archive_time = self.generate.HourBackDate(2026, 11, 1, 3)
        self.page_url = "https://github.com/example/project/wiki/Install"

    def write_archive(self):
        def event(created_at, pages):
            return {
                "type": "GollumEvent",
                "created_at": created_at,
                "payload": {"pages": [{"html_url": url} for url in pages]},
            }

        events = [
            {"type": "PushEvent"},
            event("2026-11-01T03:10:00Z", [self.page_url]),
            event("2026-11-01T03:20:00Z", [self.page_url]),
            event("2026-11-01T03:05:00Z", [self.page_url]),
            event("2026-11-01T03:30:00Z", [
                f"https://github.com/example/project/wiki/{page}"
                for page in ("Home", "_Sidebar", "_Footer", "_Header")
            ]),
        ]
        archive = self.root / "events.json.gz"
        with gzip.open(archive, "wt", encoding="utf-8") as stream:
            for event_data in events:
                stream.write(json.dumps(event_data) + "\n")
        return archive

    def test_archive_filters_pages_and_keeps_latest_timestamp(self):
        archive = self.write_archive()
        with mock.patch.object(
            self.generate, "smart_open",
            side_effect=lambda url, *args, **kwargs: smart_open(str(archive), *args, **kwargs),
        ) as reader:
            result = self.generate._process_archive_time(self.archive_time)
        reader.assert_called_once_with(
            "https://data.gharchive.org/2026-11-01-3.json.gz", "r", encoding="utf-8"
        )
        self.assertEqual(result, {self.page_url: datetime.datetime(2026, 11, 1, 3, 20)})

    def test_cached_archive_is_not_downloaded_twice(self):
        archive = self.write_archive()
        with mock.patch.object(
            self.generate, "smart_open",
            side_effect=lambda url, *args, **kwargs: smart_open(str(archive), *args, **kwargs),
        ) as reader:
            first = self.generate._process_archive_time(self.archive_time)
            second = self.generate._process_archive_time(self.archive_time)
        self.assertEqual(first, second)
        self.assertEqual(reader.call_count, 1)
        self.assertTrue(first)

    def test_http_transport_streams_and_decompresses_archive(self):
        self.write_archive()
        handler = functools.partial(QuietHandler, directory=self.root)
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/events.json.gz"
                with mock.patch.object(
                    self.generate, "smart_open",
                    side_effect=lambda original_url, *args, **kwargs: smart_open(url, *args, **kwargs),
                ):
                    result = self.generate._process_archive_time(self.archive_time)
                self.assertEqual(result, {self.page_url: datetime.datetime(2026, 11, 1, 3, 20)})
            finally:
                server.shutdown()
                thread.join()

    def test_download_failure_returns_no_entries(self):
        with mock.patch.object(self.generate, "smart_open", side_effect=OSError("offline")):
            self.assertEqual(self.generate._process_archive_time(self.archive_time), {})

    def test_sitemap_uses_latest_timestamp_across_hours_and_escapes_urls(self):
        (self.root / "generator").mkdir()
        (self.root / "dist").mkdir()
        other_url = "https://github.com/example/project/wiki/A&B"
        pool = mock.Mock()
        pool.imap_unordered.return_value = iter([
            {self.page_url: datetime.datetime(2026, 11, 1, 4, 0)},
            {self.page_url: datetime.datetime(2026, 11, 1, 3, 20),
             other_url: datetime.datetime(2026, 11, 1, 3, 30)},
        ])
        with working_directory(self.root / "generator"), mock.patch.object(
            self.generate, "Pool", return_value=pool
        ):
            self.generate.generate_last_week_from_gha(hours_back=2)
        sitemap = ET.parse(self.root / "dist/generated_sitemap.xml")
        entries = {
            node.findtext("s:loc", namespaces=NS): node.findtext("s:lastmod", namespaces=NS)
            for node in sitemap.findall("s:url", NS)
        }
        self.assertEqual(entries, {
            "https://github-wiki-see.page/m/example/project/wiki/Install": "2026-11-01T04:00:00+00:00",
            "https://github-wiki-see.page/m/example/project/wiki/A&B": "2026-11-01T03:30:00+00:00",
        })
        arguments = list(pool.imap_unordered.call_args.args[1])
        self.assertEqual(len(arguments), 2)

    def test_manual_sitemaps_copy_without_modification(self):
        (self.root / "generator").mkdir()
        (self.root / "dist").mkdir()
        (self.root / "base").mkdir()
        (self.root / "seed_sitemaps").mkdir()
        (self.root / "base_sitemap.xml").write_text("<urlset/>")
        (self.root / "base/sitemap_index.xml").write_text("<sitemapindex/>")
        seed_bytes = gzip.compress(b"<urlset/>")
        (self.root / "seed_sitemaps/seed.xml.gz").write_bytes(seed_bytes)
        with working_directory(self.root / "generator"):
            self.generate.copy_manual_sitemaps()
        self.assertEqual((self.root / "dist/base_sitemap.xml").read_text(), "<urlset/>")
        self.assertEqual((self.root / "dist/sitemap_index.xml").read_text(), "<sitemapindex/>")
        self.assertEqual((self.root / "dist/seed_sitemaps/seed.xml.gz").read_bytes(), seed_bytes)


if __name__ == "__main__":
    unittest.main()
