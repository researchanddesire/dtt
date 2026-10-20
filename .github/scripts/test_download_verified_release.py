import unittest

from download_verified_release import legacy_version_document


class LegacyVersionDocumentTests(unittest.TestCase):
    def test_includes_fields_required_by_deployed_dtt_updaters(self):
        document = legacy_version_document("2.0.68", "a" * 40, "release-id")

        self.assertEqual(
            document,
            {
                "version": "2.0.68",
                "major": 2,
                "minor": 0,
                "patch": 68,
                "buildSha": "a" * 40,
                "releaseId": "release-id",
            },
        )

    def test_rejects_non_numeric_semantic_version(self):
        for version in ("2.0", "v2.0.68", "2.0.68-beta"):
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                legacy_version_document(version, "a" * 40, "release-id")


if __name__ == "__main__":
    unittest.main()
