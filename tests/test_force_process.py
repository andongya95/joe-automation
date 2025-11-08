import unittest
from unittest import mock

import main


class ForceProcessTests(unittest.TestCase):

    @mock.patch("main._process_job_batch")
    @mock.patch("main._needs_llm_processing", return_value=False)
    @mock.patch("main.get_all_jobs")
    def test_force_process_runs_even_when_jobs_marked_complete(self, mock_get_all_jobs, mock_needs_llm, mock_batch):
        mock_get_all_jobs.return_value = [
            {"job_id": "1", "title": "Job One"},
            {"job_id": "2", "title": "Job Two"},
        ]
        mock_batch.return_value = 2

        processed = main.process_jobs_incrementally(force=True)

        self.assertEqual(processed, mock_batch.return_value)
        # ensure we invoked batch processing despite _needs_llm_processing returning False
        mock_batch.assert_called()
        mock_needs_llm.assert_not_called()

    @mock.patch("main.update_job")
    @mock.patch("main.get_job")
    @mock.patch("main.evaluate_position_track_batch", return_value={})
    @mock.patch("main.classify_position_batch")
    @mock.patch("main.extract_job_details_batch")
    @mock.patch("main.parse_deadlines_batch", return_value={})
    @mock.patch("main.get_all_jobs")
    def test_force_process_overwrites_existing_level(
        self,
        mock_get_all_jobs,
        mock_parse_deadlines,
        mock_extract_details,
        mock_classify,
        mock_evaluate_track,
        mock_get_job,
        mock_update_job,
    ):
        job = {
            "job_id": "1",
            "title": "Assistant Professor of Economics",
            "description": "Teach and research.",
        }
        mock_get_all_jobs.return_value = [job]
        mock_get_job.return_value = {"job_id": "1", "level": "Assistant/Associate"}
        mock_extract_details.return_value = {
            "1": {
                "level": "Assistant",
                "requirements": "PhD in economics.",
            }
        }
        mock_classify.return_value = {
            "1": {
                "level": "Assistant",
                "type": "Tenure-track",
                "field_focus": "Economics",
            }
        }

        main.process_jobs_incrementally(force=True)

        mock_update_job.assert_called()
        args, kwargs = mock_update_job.call_args
        self.assertEqual(args[0], "1")
        update_payload = args[1]
        self.assertEqual(update_payload.get("level"), "Assistant")
        self.assertIn("requirements", update_payload)


if __name__ == "__main__":
    unittest.main()


