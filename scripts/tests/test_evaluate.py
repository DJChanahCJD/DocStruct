import unittest

from scripts.evaluate import evaluate_slot, match_objects


class EvaluateTests(unittest.TestCase):
    """Tests for typed-schema evaluation matching behavior."""

    def test_endpoints_match_by_method_and_path(self) -> None:
        """Ensure endpoint names can differ when HTTP method and path match."""
        preds = [
            {"name": "11.1 注册 Webhook", "http_method": "post", "path": "/webhooks"},
        ]
        gts = [
            {"name": "注册Webhook", "http_method": "post", "path": "/webhooks"},
        ]

        tp, fp, fn, pairs = match_objects(preds, gts, "http_method", slot="endpoints")

        self.assertEqual((tp, fp, fn), (1, 0, 0))
        self.assertEqual(pairs[0]["similarity"], 1.0)

    def test_test_steps_match_by_action_text(self) -> None:
        """Ensure test steps use action text when synthetic names differ."""
        preds = [
            {"name": "TS-001", "action": "确认收货地址"},
        ]
        gts = [
            {"name": "创建订单（TC-ORDER-001） 步骤 2", "action": "确认收货地址"},
        ]

        tp, fp, fn, _ = match_objects(preds, gts, "", slot="test_steps")

        self.assertEqual((tp, fp, fn), (1, 0, 0))

    def test_modules_ignore_spacing_differences(self) -> None:
        """Ensure Chinese/English spacing differences do not break name matching."""
        preds = [{"name": "Web 前端"}]
        gts = [{"name": "Web前端"}]

        tp, fp, fn, _ = match_objects(preds, gts, "", slot="modules")

        self.assertEqual((tp, fp, fn), (1, 0, 0))

    def test_ignored_slot_does_not_count_predictions_as_fp(self) -> None:
        """Ensure explicitly unannotated slots are excluded from metrics."""
        pred = {"schemas": [{"name": "CreateRequest"}]}
        gt = {"ignored_slots": ["schemas"], "schemas": []}

        result = evaluate_slot(pred, gt, "schemas")

        self.assertTrue(result["ignored"])
        self.assertEqual(result["pred_count"], 1)
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (0, 0, 0))

    def test_unmatched_examples_are_reported(self) -> None:
        """Ensure slot diagnostics expose representative FP and FN labels."""
        pred = {"entities": [{"name": "Device", "entity_type": "data"}]}
        gt = {"entities": [{"name": "研究者", "entity_type": "actor"}]}

        result = evaluate_slot(pred, gt, "entities")

        self.assertEqual(result["false_positive_examples"], ["Device"])
        self.assertEqual(result["false_negative_examples"], ["研究者"])


if __name__ == "__main__":
    unittest.main()
