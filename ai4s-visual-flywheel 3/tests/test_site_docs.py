import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("site_docs", ROOT / "scripts" / "build_site_docs.py")
site_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_docs)


class DocumentationRendererTests(unittest.TestCase):
    def test_inline_code_inside_link_expands_without_control_tokens(self):
        result = site_docs.inline("[`标签规范`](taxonomy.md)", ROOT / "docs" / "whitepaper.md")
        self.assertNotIn("\x00", result)
        self.assertEqual(result, '<a href="taxonomy.html"><code>标签规范</code></a>')

    def test_multiple_code_and_link_tokens_preserve_their_order(self):
        result = site_docs.inline("`A` [说明](whitepaper.md) [`B`](taxonomy.md)", ROOT / "docs" / "whitepaper.md")
        self.assertNotIn("\x00", result)
        self.assertIn('<code>A</code>', result)
        self.assertIn('<a href="whitepaper.html">说明</a>', result)
        self.assertIn('<a href="taxonomy.html"><code>B</code></a>', result)


if __name__ == "__main__":
    unittest.main()
