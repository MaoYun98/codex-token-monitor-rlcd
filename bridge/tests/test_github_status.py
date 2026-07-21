import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import github_status


class GithubStatusTests(unittest.TestCase):
    def setUp(self):
        github_status._cache.update(value=None, ts=0.0)

    def test_disabled_without_token_or_repositories(self):
        with patch.object(github_status, "TOKEN", None), patch.object(github_status, "REPOSITORIES", []):
            self.assertIsNone(github_status.fetch_github_status())

    def test_counts_review_requests_and_latest_failing_workflows(self):
        def fake_get(path: str):
            if path == "/user":
                return {"login": "octocat"}
            if path.startswith("/search/issues"):
                return {"total_count": 3}
            if path == "/repos/acme/dashboard":
                return {"default_branch": "main"}
            if path.startswith("/repos/acme/dashboard/actions/runs"):
                return {"workflow_runs": [
                    {"workflow_id": 1, "conclusion": "failure"},
                    {"workflow_id": 1, "conclusion": "success"},
                    {"workflow_id": 2, "conclusion": "success"},
                ]}
            raise AssertionError(path)

        with patch.object(github_status, "TOKEN", "test-token"), \
                patch.object(github_status, "REPOSITORIES", ["acme/dashboard"]), \
                patch.object(github_status, "_get", side_effect=fake_get):
            value = github_status.fetch_github_status()
        self.assertTrue(value.valid)
        self.assertEqual(value.review_requests, 3)
        self.assertEqual(value.failing_workflows, 1)


if __name__ == "__main__":
    unittest.main()
