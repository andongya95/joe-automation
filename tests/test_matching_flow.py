import unittest
from unittest import mock

from matcher import fit_calculator
from database import job_db


class MatchingFlowTests(unittest.TestCase):

    def setUp(self):
        self.portfolio = {'combined_text': 'Research summary about public economics and econometrics.'}
        self.job = {
            'job_id': 'JOB-123',
            'title': 'Assistant Professor of Economics',
            'institution': 'Example University',
            'description': 'Research-focused position in public economics.',
            'requirements': 'PhD in economics; teaching experience preferred.',
            'position_track': 'junior tenure-track',
            'fit_score': 75.0,
            'difficulty_score': 40.0,
            'difficulty_reasoning': 'Existing reasoning',
            'fit_portfolio_hash': 'abc123',
            'fit_updated_at': '2025-11-01T12:00:00',
            'last_updated': '2025-11-01T12:00:00',
        }

    def test_needs_fit_recompute_skips_when_scores_present(self):
        portfolio_hash = 'abc123'
        self.assertFalse(job_db.needs_fit_recompute(self.job, portfolio_hash))

    def test_joint_llm_called_per_job(self):
        jobs = [dict(self.job, fit_score=None, difficulty_score=None)]

        with mock.patch('matcher.fit_calculator.evaluate_fit_and_difficulty') as joint_mock:
            joint_mock.return_value = {
                'fit_score': 82.5,
                'fit_reasoning': 'LLM reasoning',
                'fit_alignment': {'research': 'Strong', 'teaching': 'Moderate', 'other': 'N/A'},
                'difficulty_score': 35.0,
                'difficulty_reasoning': 'LLM difficulty reasoning',
            }

            scored_jobs = fit_calculator.calculate_fit_scores_with_difficulty(
                jobs,
                self.portfolio,
                force=False,
            )

        self.assertEqual(joint_mock.call_count, 1)
        self.assertEqual(scored_jobs[0]['fit_score'], 82.5)
        self.assertEqual(scored_jobs[0]['difficulty_score'], 35.0)


if __name__ == '__main__':
    unittest.main()

