import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = {"w": "http://wixtoolset.org/schemas/v4/wxs"}


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tree = ET.parse(ROOT / "installer" / "Package.wxs")

    def test_package_identity(self):
        pkg = self.tree.getroot().find("w:Package", NS)
        self.assertIsNotNone(pkg)
        self.assertRegex(pkg.get("UpgradeCode"), r"^[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}$")
        self.assertEqual(pkg.get("Version"), "$(Version)")  # injectée par le workflow

    def test_every_component_is_in_the_feature(self):
        comps = {c.get("Id") for c in self.tree.iter("{%s}Component" % NS["w"])}
        refs = {r.get("Id") for r in self.tree.iter("{%s}ComponentRef" % NS["w"])}
        self.assertEqual(comps, refs)

    def test_installs_both_exes_built_by_workflow(self):
        sources = {f.get("Source") for f in self.tree.iter("{%s}File" % NS["w"])}
        wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
        for src in sources:
            exe = src.split("\\")[-1]
            self.assertIn(exe, wf, f"{exe} n'est pas produit par le workflow")

    def test_workflow_passes_the_variables_the_package_uses(self):
        wxs = (ROOT / "installer" / "Package.wxs").read_text(encoding="utf-8")
        wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
        for var in set(re.findall(r"\$\((\w+)\)", wxs.split("-->", 1)[1])):
            self.assertIn(f"-d {var}=", wf)


if __name__ == "__main__":
    unittest.main()
