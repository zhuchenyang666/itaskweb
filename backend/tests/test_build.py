import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('build_all', Path(__file__).resolve().parents[2] / 'build_all.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class BuildTests(unittest.TestCase):
    def test_clean_only_generated_outputs_preserves_source_data(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
            root = Path(folder)
            for relative in ('release/iTime', 'build/package', 'frontend/dist', 'backend/data', 'backend/resources', 'build/other'):
                target = root / relative
                target.mkdir(parents=True)
                (target / 'sentinel').write_text('keep')
            with patch.object(builder, 'ROOT', root):
                builder.clean_outputs()
            for relative in ('build/package','frontend/dist'):
                self.assertFalse((root / relative).exists())
            for relative in ('release/iTime','backend/data','backend/resources','build/other'):
                self.assertTrue((root / relative / 'sentinel').is_file())

    def test_reject_directory_link_before_deleting_anything(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as folder:
            root = Path(folder)
            (root / 'release').mkdir()
            with patch.object(builder, 'ROOT', root), patch.object(Path, 'is_junction', return_value=True):
                with self.assertRaises(ValueError):
                    builder.clean_outputs()
            self.assertTrue((root / 'release').is_dir())

if __name__ == '__main__':
    unittest.main()
