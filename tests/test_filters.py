import unittest
from unittest import mock

from webapp.app import app


class PositionTrackFilterTests(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config["TESTING"] = True

    @mock.patch("webapp.app.get_all_jobs")
    def test_position_track_filter_returns_only_matching_jobs(self, mock_get_all_jobs):
        mock_get_all_jobs.return_value = [
            {"job_id": "1", "position_track": "junior tenure-track"},
            {"job_id": "2", "position_track": "senior tenure-track"},
            {"job_id": "3", "position_track": "junior tenure-track"},
        ]

        response = self.client.get("/api/jobs?position_track=Junior Tenure-Track")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertTrue(payload["success"])
        returned_ids = {job["job_id"] for job in payload["jobs"]}
        self.assertEqual(returned_ids, {"1", "3"})

        mock_get_all_jobs.assert_called_once()

    @mock.patch("webapp.app.get_all_jobs")
    def test_position_tracks_endpoint_returns_unique_sorted_list(self, mock_get_all_jobs):
        mock_get_all_jobs.return_value = [
            {"position_track": "junior tenure-track"},
            {"position_track": "teaching"},
            {"position_track": "Junior Tenure-Track"},
            {"position_track": None},
            {},
        ]

        response = self.client.get("/api/position-tracks")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["tracks"], ["junior tenure-track", "teaching"])


if __name__ == "__main__":
    unittest.main()


