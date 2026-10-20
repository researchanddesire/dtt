import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from publish_immutable_firmware import (
    Artifact,
    ControlPlaneHttpError,
    complete_release_artifacts,
    compatibility_rules,
    is_missing_required_provenance_role,
    parse_artifact,
    positive_int,
    read_version,
    validate_artifacts,
    validate_release_artifacts,
)


class PublisherTests(unittest.TestCase):
    def test_dtt_hardware_variants_are_explicit(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--hardware-variant", required=True, choices=("v1", "v2"))
        self.assertEqual(
            parser.parse_args(["--hardware-variant", "v1"]).hardware_variant,
            "v1",
        )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(
            SystemExit
        ):
            parser.parse_args(["--hardware-variant", "default"])

    def test_reads_numeric_semantic_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Version.h"
            path.write_text('#define VERSION "1.2.3"\n')
            self.assertEqual(read_version(path), "1.2.3")

    def test_rejects_missing_artifact(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_artifact("application:missing.bin:1:true")

    def test_parses_installable_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "firmware.bin"
            path.write_bytes(b"firmware")
            artifact = parse_artifact(f"application:{path}:2:true")
            self.assertTrue(artifact.installable)
            self.assertEqual(artifact.install_order, 2)
            self.assertEqual(artifact.sha256, "c3bf47ea1f4a4a605470313cacb3a44f4a461f68c6faeab07e737610cb5ac835")

    def test_adds_physical_flash_compatibility_rule(self):
        self.assertEqual(
            compatibility_rules(positive_int("16777216")),
            [{"minFlashSizeBytes": 16_777_216}],
        )
        self.assertEqual(compatibility_rules(None), [])
        self.assertEqual(
            compatibility_rules(positive_int("16777216"), "legacy-v1"),
            [
                {
                    "minFlashSizeBytes": 16_777_216,
                    "partitionLayout": "legacy-v1",
                }
            ],
        )

    def test_rejects_non_positive_flash_size(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")

    def test_accepts_filesystem_before_application(self):
        artifacts = [
            Artifact("filesystem", Path("filesystem.bin"), 1, True),
            Artifact("application", Path("firmware.bin"), 2, True),
            Artifact("partitions", Path("partitions.bin"), 0, False),
        ]
        self.assertEqual(
            [artifact.role for artifact in validate_artifacts(artifacts)],
            ["filesystem", "application"],
        )

    def test_rejects_duplicate_installable_roles(self):
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            validate_artifacts(
                [
                    Artifact("application", Path("first.bin"), 1, True),
                    Artifact("application", Path("second.bin"), 2, True),
                ]
            )
        with self.assertRaisesRegex(RuntimeError, "at most one"):
            validate_artifacts(
                [
                    Artifact("filesystem", Path("first-spiffs.bin"), 0, True),
                    Artifact("filesystem", Path("second-spiffs.bin"), 1, True),
                    Artifact("application", Path("firmware.bin"), 2, True),
                ]
            )

    def test_rejects_filesystem_after_application(self):
        with self.assertRaisesRegex(RuntimeError, "before application"):
            validate_artifacts(
                [
                    Artifact("application", Path("firmware.bin"), 1, True),
                    Artifact("filesystem", Path("filesystem.bin"), 2, True),
                ]
            )

    def test_rejects_out_of_range_install_order(self):
        with self.assertRaisesRegex(RuntimeError, "between 0 and 7"):
            validate_artifacts(
                [Artifact("application", Path("firmware.bin"), 8, True)]
            )

    def test_firmware_requires_one_non_installable_web_installer(self):
        application = Artifact("application", Path("firmware.bin"), 2, True)
        web_installer = Artifact(
            "web-installer", Path("web-installer.bin"), 4, False
        )
        validate_release_artifacts("firmware", [application, web_installer])
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            validate_release_artifacts("firmware", [application])

    def test_migration_forbids_web_installer(self):
        with self.assertRaisesRegex(RuntimeError, "must not include"):
            validate_release_artifacts(
                "migration",
                [
                    Artifact("application", Path("firmware.bin"), 2, True),
                    Artifact(
                        "web-installer", Path("web-installer.bin"), 4, False
                    ),
                ],
            )

    def test_release_includes_manifest_and_provenance(self):
        application = Artifact("application", Path("firmware.bin"), 2, True)
        manifest = Artifact("manifest", Path("manifest.json"), 5, False)
        provenance = Artifact("provenance", Path("provenance.json"), 7, False)
        self.assertEqual(
            [
                artifact.role
                for artifact in complete_release_artifacts(
                    [application], manifest, provenance
                )
            ],
            ["application", "manifest", "provenance"],
        )

    def test_outdated_production_schema_is_detected_without_fallback(self):
        old_schema = ControlPlaneHttpError(
            400,
            '{"issues":[{"code":"invalid_value","values":'
            '["application","manifest","release"],"path":'
            '["artifacts",6,"role"]}]}',
        )
        self.assertTrue(
            is_missing_required_provenance_role("main", old_schema)
        )
        self.assertFalse(
            is_missing_required_provenance_role("staging", old_schema)
        )
        self.assertFalse(
            is_missing_required_provenance_role(
                "main",
                ControlPlaneHttpError(
                    400,
                    '{"issues":[{"code":"invalid_value","values":'
                    '["application","provenance"],"path":'
                    '["artifacts",6,"role"]}]}',
                ),
            )
        )

if __name__ == "__main__":
    unittest.main()
