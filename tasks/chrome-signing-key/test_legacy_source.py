import re
import unittest
from pathlib import Path


class LegacySourceRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        playbook = (Path(__file__).resolve().parents[2] / "browser/chrome.yml").read_text()
        task = playbook.split("- name: Remove duplicate legacy Chrome sources", 1)[1]
        pattern = re.search(r"^\s+regexp: '([^']+)'$", task, re.MULTILINE).group(1)
        # Ansible's replace module uses MULTILINE, without DOTALL.
        cls.pattern = re.compile(pattern, re.MULTILINE)

    def test_non_equivalent_components_are_preserved(self):
        for component in ("main contrib", "main-extra"):
            with self.subTest(component=component):
                source = f"deb https://dl.google.com/linux/chrome/deb/ stable {component}\n"
                self.assertEqual(self.pattern.sub("", source), source)

    def test_equivalent_lines_are_removed(self):
        for source in (
            "deb https://dl.google.com/linux/chrome/deb/ stable main\n",
            "  deb [arch=amd64] http://dl.google.com/linux/chrome/deb stable main  # legacy\n",
            "deb https://dl.google.com/linux/chrome/deb/ stable main",
        ):
            with self.subTest(source=source):
                self.assertEqual(self.pattern.sub("", source), "")


if __name__ == "__main__":
    unittest.main()
