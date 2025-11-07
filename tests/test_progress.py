import unittest

from webapp.app import app, operation_progress


class ProgressEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        self._original_progress = {
            'process': operation_progress.get('process', {}).copy(),
            'match': operation_progress.get('match', {}).copy(),
        }

    def tearDown(self):
        operation_progress['process'] = self._original_progress.get('process', {}).copy()
        operation_progress['match'] = self._original_progress.get('match', {}).copy()

    def test_progress_endpoint_returns_current_status(self):
        operation_progress['process'] = {
            'status': 'running',
            'processed': 10,
            'total': 50,
            'errors': 1,
            'message': 'Batch 1/5 complete.'
        }
        operation_progress['match'] = {
            'status': 'completed',
            'processed': 30,
            'total': 30,
            'errors': 0,
            'message': 'Matching complete.'
        }

        response = self.client.get('/api/progress')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertTrue(data['success'])
        self.assertEqual(data['process']['status'], 'running')
        self.assertEqual(data['process']['processed'], 10)
        self.assertEqual(data['match']['status'], 'completed')
        self.assertEqual(data['match']['total'], 30)

    def test_progress_endpoint_returns_defaults_when_unset(self):
        operation_progress['process'] = {}
        operation_progress['match'] = {}

        response = self.client.get('/api/progress')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertTrue(data['success'])
        self.assertEqual(data['process'], {})
        self.assertEqual(data['match'], {})


if __name__ == '__main__':
    unittest.main()
