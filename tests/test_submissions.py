import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("check_hooks", Path(__file__).resolve().parents[1] / "scripts/check_hooks.py")
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)


class SubmissionBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "sample"
        self.folder.mkdir()
        self.row = dict(schemaVersion=1, name="sample", topology="SharedV4", source="Sample.sol", contract="Sample", license="MIT")
        self.save()
        (self.folder / "Sample.sol").write_text("// SPDX-License-Identifier: MIT\ncontract Sample {}\n")
        (self.folder / "review.md").write_text("Risks disclosed by contributor.\n")
        self.integration = dict(
            schemaVersion=1, kind="submission", authorId="0x1111111111111111111111111111111111111111",
            maximumDeveloperFeeBps=0, terms="No developer allocation requested.",
            bounds=dict(minimumTickSpacing=1, maximumTickSpacing=32767, maximumPositions=32,
                        maximumOracleCardinality=4096, feeModeFlags=3),
        )
        self.save_integration()

    def save_integration(self):
        (self.folder / "integration.json").write_text(json.dumps(self.integration))

    def save(self):
        (self.folder / "hook.json").write_text(json.dumps(self.row))

    def test_escape_source_rejected(self):
        self.row["source"] = "../../Sample.sol"
        self.save()
        with self.assertRaisesRegex(ValueError, "local Solidity"):
            checks.submissions(self.root)

    def test_symlink_source_rejected(self):
        source = self.folder / "Sample.sol"
        source.unlink()
        source.symlink_to(self.folder / "review.md")
        with self.assertRaisesRegex(ValueError, "regular files"):
            checks.submissions(self.root)

    def test_duplicate_fields_rejected(self):
        manifest = self.folder / "hook.json"
        manifest.write_text(manifest.read_text().replace('"schemaVersion": 1', '"schemaVersion": 1, "schemaVersion": 2'))
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            checks.submissions(self.root)

    def test_unknown_topology_rejected(self):
        self.row["topology"] = "ArbitraryV4"
        self.save()
        with self.assertRaisesRegex(ValueError, "Unsupported topology"):
            checks.submissions(self.root)

    def test_missing_review_rejected(self):
        (self.folder / "review.md").unlink()
        with self.assertRaisesRegex(ValueError, "review.md"):
            checks.submissions(self.root)

    def test_license_mismatch_rejected(self):
        self.row["license"] = "Apache-2.0"
        self.save()
        with self.assertRaisesRegex(ValueError, "SPDX"):
            checks.submissions(self.root)

    def test_empty_catalogue_rejected(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesRegex(ValueError, "Empty hook catalogue"):
                checks.submissions(Path(empty))

    def test_missing_integration_rejected(self):
        (self.folder / "integration.json").unlink()
        with self.assertRaisesRegex(ValueError, "integration.json"):
            checks.submissions(self.root)

    def test_invalid_author_identity_rejected(self):
        for author in (None, "0x" + "0" * 40, "0x1234", True):
            with self.subTest(author=author):
                self.integration["authorId"] = author
                self.save_integration()
                with self.assertRaisesRegex(ValueError, "authorId"):
                    checks.submissions(self.root)

    def test_reference_kind_cannot_bypass_author_input(self):
        self.integration.update(kind="reference", authorId=None)
        self.save_integration()
        with self.assertRaisesRegex(ValueError, "canonical example"):
            checks.submissions(self.root)

    def test_invalid_developer_ceilings_rejected(self):
        for ceiling in (-1, 10000, True, 1.5, "500"):
            with self.subTest(ceiling=ceiling):
                self.integration["maximumDeveloperFeeBps"] = ceiling
                self.save_integration()
                with self.assertRaisesRegex(ValueError, "maximumDeveloperFeeBps"):
                    checks.submissions(self.root)

    def test_invalid_registry_bounds_rejected(self):
        cases = (("minimumTickSpacing", 0), ("maximumTickSpacing", 32768),
                 ("maximumPositions", 33), ("maximumOracleCardinality", 1),
                 ("maximumOracleCardinality", 4097), ("feeModeFlags", 0),
                 ("feeModeFlags", 4), ("maximumPositions", True))
        for name, value in cases:
            with self.subTest(name=name, value=value):
                original = self.integration["bounds"][name]
                self.integration["bounds"][name] = value
                self.save_integration()
                with self.assertRaisesRegex(ValueError, "bounds"):
                    checks.submissions(self.root)
                self.integration["bounds"][name] = original

    def test_reversed_tick_spacing_rejected(self):
        self.integration["bounds"].update(minimumTickSpacing=60, maximumTickSpacing=10)
        self.save_integration()
        with self.assertRaisesRegex(ValueError, "Reversed"):
            checks.submissions(self.root)

    def test_missing_or_extra_bound_member_rejected(self):
        del self.integration["bounds"]["minimumTickSpacing"]
        self.save_integration()
        with self.assertRaisesRegex(ValueError, "five-member"):
            checks.submissions(self.root)
        self.integration["bounds"].update(minimumTickSpacing=1, maximumHookFeePips=100)
        self.save_integration()
        with self.assertRaisesRegex(ValueError, "five-member"):
            checks.submissions(self.root)

    def test_empty_author_terms_rejected(self):
        self.integration["terms"] = " \n "
        self.save_integration()
        with self.assertRaisesRegex(ValueError, "terms"):
            checks.submissions(self.root)

    def test_duplicate_integration_field_rejected(self):
        path = self.folder / "integration.json"
        path.write_text(path.read_text().replace('"kind": "submission"', '"kind": "reference", "kind": "submission"'))
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            checks.submissions(self.root)


if __name__ == "__main__":
    unittest.main()
