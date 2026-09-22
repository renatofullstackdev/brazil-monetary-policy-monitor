import unittest

from monetary_policy_dashboard import DataKind


class DataKindTest(unittest.TestCase):
    def test_expected_categories_are_stable(self) -> None:
        self.assertEqual(
            {item.value for item in DataKind},
            {"observed", "survey", "estimated", "derived", "simulated"},
        )

    def test_enum_serializes_as_string(self) -> None:
        self.assertEqual(str(DataKind.OBSERVED), "observed")


if __name__ == "__main__":
    unittest.main()
