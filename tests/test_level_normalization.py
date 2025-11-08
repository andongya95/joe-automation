import unittest

from processor import llm_parser


class LevelNormalizationTests(unittest.TestCase):

    def test_pre_doc_title_normalizes_to_pre_doc(self):
        raw_levels = ["Predoctoral Research Assistant", "Research Assistant (Pre-Doc)"]
        normalized = llm_parser.normalize_level_labels(raw_levels, job_title="Predoctoral Research Fellow")
        self.assertEqual(normalized, ["Pre-doc"])

    def test_post_doc_title_normalizes_to_postdoc(self):
        raw_levels = ["Postdoctoral Fellow", "Post-Doc"]
        normalized = llm_parser.normalize_level_labels(raw_levels, job_title="Postdoctoral Scholar in Economics")
        self.assertEqual(normalized, ["Postdoc"])

    def test_professor_levels_preserve_order_and_deduplicate(self):
        raw_levels = ["Assistant", "Associate", "Assistant Professor"]
        normalized = llm_parser.normalize_level_labels(raw_levels, job_title="Assistant or Associate Professor of Economics")
        self.assertEqual(normalized, ["Assistant", "Associate"])

    def test_unknown_levels_fall_back_to_other(self):
        raw_levels = ["Visiting Fellow"]
        normalized = llm_parser.normalize_level_labels(raw_levels, job_title="Visiting Fellow in Public Policy")
        self.assertEqual(normalized, ["Other"])


if __name__ == "__main__":
    unittest.main()


