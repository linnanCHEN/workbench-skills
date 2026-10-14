from __future__ import annotations

import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).parents[1]


class ContextEfficiencyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.reference_text = (
            SKILL_ROOT / "references" / "context-efficiency.md"
        ).read_text(encoding="utf-8")
        cls.trigger_evals = json.loads(
            (SKILL_ROOT / "evals" / "trigger-evals.json").read_text(encoding="utf-8")
        )

    def test_long_thread_recommendation_is_non_blocking(self) -> None:
        self.assertIn("这是成本与速度建议，不是数据完整性门禁", self.skill_text)
        self.assertIn("用户要求继续当前对话时直接执行", self.skill_text)

    def test_skill_does_not_create_thread_without_explicit_request(self) -> None:
        self.assertIn("不得擅自创建、迁移或分叉线程", self.skill_text)
        self.assertIn("没有用户明确要求时也不得擅自创建线程", self.reference_text)

    def test_batching_preserves_completeness(self) -> None:
        self.assertIn("并行工具批次", self.skill_text)
        self.assertIn("不得减少 ASIN、忽略续页", self.reference_text)

    def test_token_usage_is_not_estimated(self) -> None:
        self.assertIn("TOKEN_USAGE=NOT_AVAILABLE", self.skill_text)
        self.assertIn("不得为了得到这个数字额外扫描整段 rollout", self.reference_text)

    def test_efficiency_regression_cases_exist(self) -> None:
        by_id = {item["id"]: item for item in self.trigger_evals}
        self.assertTrue({"TR-009", "TR-010", "TR-011"}.issubset(by_id))
        self.assertTrue(by_id["TR-009"]["should_trigger"])
        self.assertTrue(by_id["TR-010"]["should_trigger"])
        self.assertTrue(by_id["TR-011"]["should_trigger"])


if __name__ == "__main__":
    unittest.main()
