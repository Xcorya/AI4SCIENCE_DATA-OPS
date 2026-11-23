"""Training candidate export and deterministic reference-grounded reward.

No hidden reasoning traces are requested. RL references require external human
review or an executable oracle; a second VLM's approval is not such a reference.
"""
from __future__ import annotations

from .policy import finite_number, valid_box, valid_interval, valid_text


def _iou_box(a, b):
    if not valid_box(a) or not valid_box(b):
        return 0.0
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union if union else 0.0


def _iou_time(a, b):
    if (not isinstance(a, list) or len(a) != 2 or not isinstance(b, list) or len(b) != 2
            or not all(finite_number(x) for x in a + b)
            or a[0] < 0 or a[0] >= a[1] or b[0] < 0 or b[0] >= b[1]):
        return 0.0
    overlap = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return overlap / union if union else 0.0


def reward(response: dict, reference: dict) -> dict:
    """Exact-label gate followed by IoU grounding; wrong labels receive zero."""
    if (not isinstance(reference, dict) or not isinstance(reference.get("label"), str)
            or not reference["label"].strip()):
        return {"reward": 0.0, "label_correct": False, "grounding_iou": 0.0,
                "error": "invalid_reference"}
    has_box, has_time = "bbox" in reference, "interval" in reference
    if (has_box == has_time
            or (has_box and not valid_box(reference["bbox"]))
            or (has_time and not valid_interval(reference["interval"], reference.get("duration_seconds")))):
        return {"reward": 0.0, "label_correct": False, "grounding_iou": 0.0,
                "error": "invalid_grounding_reference"}
    if not isinstance(response, dict) or response.get("label") != reference["label"]:
        return {"reward": 0.0, "label_correct": False, "grounding_iou": 0.0}
    expected_keys = {"label", "bbox" if has_box else "interval"}
    if (set(response) != expected_keys
            or (has_box and not valid_box(response.get("bbox")))
            or (has_time and not valid_interval(response.get("interval"), reference["duration_seconds"]))):
        return {"reward": 0.0, "label_correct": True, "grounding_iou": 0.0,
                "error": "invalid_response_schema_or_grounding"}
    if has_box:
        iou = _iou_box(response.get("bbox"), reference["bbox"])
    else:
        iou = _iou_time(response.get("interval"), reference["interval"])
    return {"reward": 1.0 if iou >= 0.5 else 0.0, "label_correct": True,
            "grounding_iou": iou}


def export_training(decisions: list[dict], taxonomy: dict) -> tuple[list, list]:
    sft, rl = [], []
    for item in decisions:
        if (item["status"] in ("quarantine", "abstain") or item.get("synthetic") is True
                or item.get("split") != "train"):
            continue
        accepted = [label for label in item["labels"] if label["status"] == "accepted"]
        if not accepted:
            continue
        sft.append({"asset_id": item["asset_id"], "unit_id": item["unit_id"], "media": item["source"]["url"],
                    "supervision": "calibrated_pseudo_labels_partial_not_exhaustive",
                    "label_ids": [label["id"] for label in accepted],
                    "evidence": {label["id"]: label["evidence"] for label in accepted},
                    "policy_fingerprint": item["policy_fingerprint"], "source": item["source"],
                    "cohort": item["cohort"]})
        accepted_ids = {label["id"] for label in accepted}
        for review in item.get("reference_reviews", []):
            if (not isinstance(review, dict) or not valid_text(review.get("label"))
                    or review["label"] not in accepted_ids or review.get("status") != "verified"
                    or review.get("unit_id") != item["unit_id"]
                    or review.get("method") not in ("human", "executable_oracle")
                    or not valid_text(review.get("reviewer_id")) or not valid_text(review.get("reference_id"))
                    or not isinstance(review.get("question"), str) or not review["question"].strip()):
                continue
            reference = {"label": review["label"]}
            if item["modality"] == "image" and valid_box(review.get("bbox")):
                reference["bbox"] = review["bbox"]
            elif (item["modality"] == "video"
                  and valid_interval(review.get("interval"), item.get("duration_seconds"))
                  and (review.get("duration_seconds") is None
                       or review["duration_seconds"] == item["duration_seconds"])):
                reference["interval"] = review["interval"]
                reference["duration_seconds"] = item["duration_seconds"]
            else:
                continue
            rl.append({"task_id": f"{item['asset_id']}:{item['unit_id']}:{review['label']}",
                       "task_type": "visual_label_grounding", "media": item["source"]["url"],
                       "prompt": review["question"] + " Return JSON with label and normalized bbox (image) or interval in seconds (video).",
                       "candidate_label_ids": [n["id"] for n in taxonomy["labels"]
                                               if item["modality"] in n.get("modalities", [])],
                       "reference": reference, "reward_function": "visual_flywheel.training.reward",
                       "reference_id": review["reference_id"], "reference_method": review["method"],
                       "reviewer_id": review["reviewer_id"], "policy_fingerprint": item["policy_fingerprint"],
                       "source": item["source"], "unit_id": item["unit_id"], "cohort": item["cohort"]})
    return sft, rl
