import unittest

from core.review_model import apply_review_changes, build_review_model, get_review_node
from schemas.models import DocType


class ReviewModelUnitTests(unittest.TestCase):
    def test_build_review_model_for_srs_items(self) -> None:
        extracted_data = {
            "doc_type": "srs",
            "title": "订单系统 SRS",
            "summary": "核心需求",
            "items": [
                {"id": "REQ-1", "title": "登录", "description": "支持账号密码登录", "priority": "high"},
                {"id": "REQ-2", "title": "支付", "description": "支持下单支付", "priority": "medium"},
            ],
        }

        review_model = build_review_model(DocType.SRS, extracted_data)

        self.assertEqual(review_model["meta_fields"][0]["field_key"], "title")
        self.assertEqual(review_model["groups"][0]["group_key"], "items")
        self.assertEqual(review_model["groups"][0]["items"][0]["node_id"], "items:id:req-1")

    def test_build_review_model_for_issue_steps(self) -> None:
        extracted_data = {
            "doc_type": "issue",
            "title": "支付失败",
            "steps": ["打开支付页", "点击确认支付"],
            "status": "open",
        }

        review_model = build_review_model(DocType.ISSUE, extracted_data)

        self.assertEqual(len(review_model["groups"]), 1)
        self.assertEqual(review_model["groups"][0]["group_key"], "steps")
        self.assertEqual(review_model["groups"][0]["items"][1]["fields"][0]["field_key"], "content")

    def test_apply_review_changes_updates_meta_and_item_only(self) -> None:
        extracted_data = {
            "doc_type": "srs",
            "title": "旧标题",
            "items": [
                {"id": "REQ-1", "title": "登录", "description": "旧描述", "priority": "high"},
                {"id": "REQ-2", "title": "支付", "description": "不应变化", "priority": "medium"},
            ],
        }

        updated = apply_review_changes(
            DocType.SRS,
            extracted_data,
            [
                {"node_id": "meta:title", "field_key": "title", "value": "新标题"},
                {"node_id": "items:id:req-1", "field_key": "description", "value": "新描述"},
            ],
        )

        self.assertEqual(updated["title"], "新标题")
        self.assertEqual(updated["items"][0]["description"], "新描述")
        self.assertEqual(updated["items"][1]["description"], "不应变化")

    def test_get_review_node_for_item(self) -> None:
        extracted_data = {
            "doc_type": "api",
            "items": [
                {"method": "GET", "path": "/orders", "summary": "订单列表"},
            ],
        }

        node = get_review_node(DocType.API, extracted_data, "items:endpoint:get-orders")

        self.assertEqual(node["node_type"], "item")
        self.assertEqual(node["fields"][0]["field_key"], "method")


if __name__ == "__main__":
    unittest.main()
