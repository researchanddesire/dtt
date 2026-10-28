import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_workflow import branch_configuration, main, tag_action

PUBLISH_WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "publish_firmware.yml"
VERSION_ALLOCATOR = Path(__file__).with_name("allocate_version.sh")
FIRMWARE_ROOT = Path(__file__).resolve().parents[2] / "software"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_branch_configuration_maps_tracks_and_projects(self):
        self.assertEqual(
            branch_configuration("main")["PIO_ENV_V1"], "production-v1"
        )
        self.assertEqual(
            branch_configuration("main")["PIO_ENV_V2"], "production-v2"
        )
        self.assertEqual(
            branch_configuration("staging")["PIO_ENV_V1"], "staging-v1"
        )
        self.assertEqual(
            branch_configuration("staging")["PIO_ENV_V2"], "staging-v2"
        )
        self.assertEqual(
            branch_configuration("main")["PIO_ENV_MIGRATION"],
            "migration-production",
        )
        self.assertEqual(
            branch_configuration("staging")["PIO_ENV_MIGRATION"],
            "migration-staging",
        )
        self.assertNotEqual(
            branch_configuration("main")["STORAGE_PROJECT_REF"],
            branch_configuration("staging")["STORAGE_PROJECT_REF"],
        )
        self.assertEqual(
            branch_configuration("main")["FIRMWARE_CONTROL_PLANE_BASE_URL"],
            "https://dashboard.researchanddesire.com",
        )
        self.assertEqual(
            branch_configuration("staging")["FIRMWARE_CONTROL_PLANE_BASE_URL"],
            "https://staging.researchanddesire.com",
        )
        with self.assertRaises(ValueError):
            branch_configuration("feature")

    def test_tag_action_is_idempotent_and_fails_on_collision(self):
        sha = "a" * 40
        self.assertEqual(tag_action("", sha), "create")
        self.assertEqual(tag_action(sha, sha), "exists")
        with self.assertRaisesRegex(ValueError, "different commit"):
            tag_action("b" * 40, sha)

    def test_configure_writes_github_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "env"
            with patch.dict("os.environ", {"GITHUB_ENV": str(env_file)}), patch(
                "sys.argv", ["release_workflow.py", "configure", "--branch", "staging"]
            ):
                self.assertEqual(main(), 0)
            self.assertIn("TRACK=staging", env_file.read_text())

    @unittest.skipUnless(PUBLISH_WORKFLOW.exists(), "publish workflow is not installed")
    def test_publish_configures_control_plane_before_version_allocation(self):
        workflow = PUBLISH_WORKFLOW.read_text()
        self.assertLess(
            workflow.index("- name: Select track and build environment"),
            workflow.index("- name: Allocate and commit next version"),
        )
        self.assertIn("run: bash .github/scripts/allocate_version.sh", workflow)
        allocator = VERSION_ALLOCATOR.read_text()
        self.assertIn('if [[ "$GITHUB_REF_NAME" != main ]]', allocator)
        self.assertIn(
            '"https://dashboard.researchanddesire.com/api/internal/firmware/v1/versions/next"',
            allocator,
        )

    def test_insecure_lab_transport_is_isolated_from_release_environments(self):
        configuration = (FIRMWARE_ROOT / "platformio.ini").read_text().splitlines()
        sections_with_lab_transport = set()
        section = ""
        for line in configuration:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                section = stripped
            if "DTT_MIGRATION_LAB_INSECURE_HTTP" in stripped:
                sections_with_lab_transport.add(section)
        self.assertEqual(
            sections_with_lab_transport,
            {"[lab_ota_application]", "[env:migration-lab]"},
        )


if __name__ == "__main__":
    unittest.main()
