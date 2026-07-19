import unittest

from server.edge1_operator_runtime import execution_id


class TestEdge1OperatorRuntime(unittest.TestCase):
    def test_execution_id_is_generated(self):
        value = execution_id()
        self.assertEqual(len(value), 16)


if __name__ == "__main__":
    unittest.main()
