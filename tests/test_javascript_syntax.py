from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is optional; JavaScript syntax checks skipped")
class JavaScriptSyntaxTests(unittest.TestCase):
    def test_all_frontend_modules_parse_as_es_modules(self) -> None:
        javascript_files = sorted((ROOT / "web" / "js").rglob("*.js"))
        self.assertTrue(javascript_files, "expected frontend JavaScript modules")

        for path in javascript_files:
            with self.subTest(path=path.relative_to(ROOT)):
                completed = subprocess.run(
                    [NODE, "--input-type=module", "--check"],
                    cwd=ROOT,
                    input=path.read_text(encoding="utf-8"),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=(completed.stderr or completed.stdout).strip(),
                )


if __name__ == "__main__":
    unittest.main()
