import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('sync_user_docs', Path(__file__).with_name('sync_user_docs.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UserDocsSyncTests(unittest.TestCase):
    def test_mirrors_nested_content_and_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary)/'source', Path(temporary)/'target'
            source.mkdir()
            (source/'index.mdx').write_text('# DTT')
            (source/'img').mkdir()
            (source/'img/screen.webp').write_bytes(b'\x00\xffimage')
            target.mkdir()
            (target/'old.md').write_text('stale')
            MODULE.sync(source, target)
            self.assertEqual(MODULE.files(source), MODULE.files(target))
            self.assertFalse((target/'old.md').exists())

    def test_check_detects_drift_without_editing(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary)/'source', Path(temporary)/'target'
            source.mkdir()
            target.mkdir()
            (source/'index.mdx').write_text('# DTT')
            (target/'index.mdx').write_text('edited copy')
            with self.assertRaises(ValueError):
                MODULE.sync(source, target, check=True)
            self.assertEqual((target/'index.mdx').read_text(), 'edited copy')

    def test_invalid_source_preserves_existing_docs(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary)/'source', Path(temporary)/'target'
            source.mkdir()
            target.mkdir()
            (target/'index.mdx').write_text('# DTT')
            with self.assertRaises(ValueError):
                MODULE.sync(source, target)
            self.assertEqual((target/'index.mdx').read_text(), '# DTT')
