"""Bridge-level tests."""

from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from pykmextract.bridge.pyheor import _import_pyheor


class BridgeTests(unittest.TestCase):
    def test_import_pyheor_is_cached(self):
        fake_module = types.SimpleNamespace(__name__="pyheor")
        _import_pyheor.cache_clear()

        with patch("pykmextract.bridge.pyheor.importlib.import_module", return_value=fake_module) as mock_import:
            first = _import_pyheor()
            second = _import_pyheor()

        self.assertIs(first, fake_module)
        self.assertIs(second, fake_module)
        self.assertEqual(mock_import.call_count, 1)
        _import_pyheor.cache_clear()


if __name__ == "__main__":
    unittest.main()
