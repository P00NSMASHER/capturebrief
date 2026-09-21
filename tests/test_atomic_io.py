from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capturebrief_core.atomic_io import atomic_write_bytes, atomic_write_text, ensure_exact_bytes


class AtomicIoTests(unittest.TestCase):
    def test_atomic_write_text_replaces_complete_file(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"value.json"
            target.write_text("old")
            atomic_write_text(target,"new\n")
            self.assertEqual(target.read_text(),"new\n")
            self.assertEqual(list(Path(d).glob(".value.json.*.tmp")),[])

    def test_failed_atomic_write_preserves_existing_target(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"artifact.bin"
            target.write_bytes(b"existing")
            with patch("capturebrief_core.atomic_io._write_all",side_effect=OSError("simulated failure")):
                with self.assertRaises(OSError):
                    atomic_write_bytes(target,b"replacement")
            self.assertEqual(target.read_bytes(),b"existing")
            self.assertEqual(list(Path(d).glob(".artifact.bin.*.tmp")),[])

    def test_ensure_exact_bytes_is_idempotent_and_rejects_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"artifact.bin"
            first=ensure_exact_bytes(target,b"abc")
            second=ensure_exact_bytes(target,b"abc")
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(second["sha256"],hashlib.sha256(b"abc").hexdigest())
            with self.assertRaises(ValueError):
                ensure_exact_bytes(target,b"different")
            self.assertEqual(target.read_bytes(),b"abc")

    def test_concurrent_same_content_publication_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"artifact.bin"
            def race(_src,dst):
                Path(dst).write_bytes(b"abc")
                raise FileExistsError("other writer won")
            with patch("capturebrief_core.atomic_io.os.link",side_effect=race):
                result=ensure_exact_bytes(target,b"abc")
            self.assertFalse(result["created"])
            self.assertEqual(target.read_bytes(),b"abc")

    def test_concurrent_different_content_publication_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"artifact.bin"
            def race(_src,dst):
                Path(dst).write_bytes(b"other")
                raise FileExistsError("other writer won")
            with patch("capturebrief_core.atomic_io.os.link",side_effect=race):
                with self.assertRaises(ValueError):
                    ensure_exact_bytes(target,b"abc")
            self.assertEqual(target.read_bytes(),b"other")

    def test_symlink_existing_artifact_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            actual=root/"actual.bin"; actual.write_bytes(b"abc")
            link=root/"link.bin"
            try:
                link.symlink_to(actual)
            except (OSError,NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValueError):
                ensure_exact_bytes(link,b"abc")


if __name__=="__main__":
    unittest.main()
