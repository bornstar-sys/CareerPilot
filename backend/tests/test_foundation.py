"""Smoke tests for the initial project structure."""

import unittest
from pathlib import Path

import careerpilot


class FoundationTests(unittest.TestCase):
    def test_package_loads_from_project_source(self) -> None:
        backend_directory = Path(__file__).resolve().parents[1]
        expected_file = (
            backend_directory
            / "src"
            / "careerpilot"
            / "__init__.py"
        )

        self.assertIsNotNone(careerpilot.__file__)
        self.assertEqual(
            Path(careerpilot.__file__).resolve(),
            expected_file.resolve(),
        )


if __name__ == "__main__":
    unittest.main()
