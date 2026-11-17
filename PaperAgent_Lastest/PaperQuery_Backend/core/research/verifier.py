"""Research Verifier：检查任务是否满足成功条件。"""
from __future__ import annotations

from collections import Counter

from core.research.schemas import StepResult, TaskPlan


class Verifier:
    def verify(
        self, plan: TaskPlan, step_results: list[StepResult], artifacts: list[dict]
    ) -> tuple[bool, dict]:
        """对照计划检查步骤记录和要求交付的产物类型。"""
        planned = Counter(step.step_id for step in plan.steps)
        received = Counter(result.step_id for result in step_results)
        all_success = all(r.status == "SUCCESS" for r in step_results)
        complete = bool(planned) and max(planned.values()) == 1 and planned == received
        artifact_types = {item.get("type") for item in artifacts}
        missing_artifacts = sorted(set(plan.expected_artifacts) - artifact_types)
        checks = {
            "all_steps_success": all_success,
            "steps_match_plan": complete,
            "missing_artifacts": missing_artifacts,
            "completed_steps": sum(1 for r in step_results if r.status == "SUCCESS"),
            "total_steps": len(plan.steps),
        }
        return complete and all_success and not missing_artifacts, checks
