"""Deterministic verifiers. No execution of generated code; no model judging itself."""
import json
import math
from decimal import Decimal, InvalidOperation

OPS = {
    "mean": ("算术平均值", "sum(x) / n"),
    "delta": ("末值与首值之差", "x[-1] - x[0]"),
    "ratio": ("末值与首值之比", "x[-1] / x[0]"),
    "range": ("极差", "max(x) - min(x)"),
}


def reference(op, values):
    if op not in OPS or not isinstance(values, list) or len(values) < 2:
        raise ValueError("Unsupported operation or insufficient observations")
    try:
        nums = [Decimal(str(x)) for x in values]
    except InvalidOperation as exc:
        raise ValueError("Invalid numeric observation") from exc
    if not all(n.is_finite() for n in nums):
        raise ValueError("Non-finite observations")
    if op == "mean":
        result = sum(nums) / len(nums)
    elif op == "delta":
        result = nums[-1] - nums[0]
    elif op == "range":
        result = max(nums) - min(nums)
    else:
        if nums[0] == 0:
            raise ValueError("Division by zero")
        result = nums[-1] / nums[0]
    return float(result)


def numeric_reward(completion, ground_truth):
    """Strict final answer contract prevents matching an arbitrary number in prose."""
    try:
        obj = json.loads(completion) if isinstance(completion, str) else completion
        answer = obj["answer"]
        if isinstance(answer, bool) or not isinstance(answer, (int, float)):
            return 0.0
        unit = obj.get("unit")
        expected = ground_truth["answer"]
        valid = math.isfinite(answer) and math.isfinite(expected)
        valid = valid and unit == ground_truth["unit"]
        return float(valid and math.isclose(answer, expected, rel_tol=1e-6, abs_tol=1e-8))
    except (TypeError, KeyError, ValueError):
        return 0.0


def grpo_reward(completions, ground_truth, **kwargs):
    """TRL custom reward function; extra dataset columns are passed by the trainer."""
    result = []
    for completion, truth in zip(completions, ground_truth):
        if isinstance(completion, list):
            completion = completion[-1].get("content", "") if completion else ""
        if isinstance(truth, str):
            truth = json.loads(truth)
        result.append(numeric_reward(completion, truth))
    return result
