"""Tune thresholds, then certify on disjoint, independently adjudicated audit groups.

Certificates are trusted local artifacts, not cryptographic attestations. Callers
must validate the reviewer provenance. The mathematical bound assumes exchangeable
independent source groups and an unchanged downstream cohort.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from .policy import cohort_key, finite_number, fingerprint, valid_sha256, valid_text, validate_configuration


def _binomial_upper_tail(n: int, k: int, p: float) -> float:
    if k <= 0:
        return 1.0
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    logs = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p) for i in range(k, n + 1)]
    peak = max(logs)
    return min(1.0, math.exp(peak) * sum(math.exp(x - peak) for x in logs))


def precision_lower_bound(successes: int, n: int, alpha: float) -> float:
    """Exact one-sided Clopper–Pearson lower confidence bound."""
    if (type(successes) is not int or type(n) is not int or not finite_number(alpha)
            or not (0 <= successes <= n and n >= 0 and 0 < alpha < 1)):
        raise ValueError("Invalid binomial counts or alpha")
    if successes == 0:
        return 0.0
    if successes == n:
        return alpha ** (1 / n)
    lo, hi = 0.0, 1.0
    for _ in range(65):
        mid = (lo + hi) / 2
        if _binomial_upper_tail(n, successes, mid) < alpha:
            lo = mid
        else:
            hi = mid
    return lo


def calibrate(rows: list[dict], policy: dict, taxonomy: dict,
              reference_provenance_verified: bool = False) -> dict:
    nodes = validate_configuration(policy, taxonomy)
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Calibration input must be a nonempty array of JSON objects")
    expected = fingerprint(policy, taxonomy)
    cohort = rows[0].get("cohort")
    if not valid_text(cohort):
        raise ValueError("A named calibration cohort is required")
    groups, hashes, per_label_groups, per_label_hashes = defaultdict(set), defaultdict(set), set(), set()
    batches = defaultdict(lambda: {"tune": [], "audit": []})
    for row in rows:
        label, modality, split = row.get("label"), row.get("modality"), row.get("split")
        score = row.get("score")
        if (not valid_text(label) or label not in nodes or modality not in ("image", "video")
                or split not in ("tune", "audit") or type(row.get("correct")) is not bool
                or not finite_number(score) or not 0 <= score <= 1
                or row.get("cohort") != cohort or row.get("policy_fingerprint") != expected
                or row.get("hard_gate_eligible") is not True
                or not valid_text(row.get("source_group")) or not valid_sha256(row.get("content_sha256"))
                or not valid_text(row.get("reference_id"))
                or type(row.get("synthetic", False)) is not bool):
            raise ValueError("Invalid calibration row or policy/cohort mismatch")
        groups[row["source_group"]].add(split)
        digest = row["content_sha256"].lower()
        hashes[digest].add(split)
        key = cohort_key(label, modality)
        independent_unit = (key, row["source_group"])
        if independent_unit in per_label_groups:
            raise ValueError("Repeated source group within label; count independent groups only")
        per_label_groups.add(independent_unit)
        content_unit = (key, digest)
        if content_unit in per_label_hashes:
            raise ValueError("Repeated exact content within label; duplicated content is not independent")
        per_label_hashes.add(content_unit)
        batches[key][split].append(row)
    if any(len(splits) > 1 for splits in list(groups.values()) + list(hashes.values())):
        raise ValueError("Tune/audit source-group or content leakage")
    alpha = policy["familywise_alpha"] / len(batches)
    labels = {}
    synthetic = any(row.get("synthetic") is True for row in rows)
    for key, partition in sorted(batches.items()):
        tune, audit = partition["tune"], partition["audit"]
        threshold = None
        # Choose once on tuning data. Audit data must never select the threshold.
        for candidate in sorted({r["score"] for r in tune if r["score"] >= policy["candidate_score_floor"]}):
            selected = [r for r in tune if r["score"] >= candidate]
            if (len(selected) >= policy["minimum_tune_n"]
                    and sum(r["correct"] for r in selected) / len(selected) >= policy["target_precision"]):
                threshold = candidate
                break
        selected_audit = [r for r in audit if threshold is not None and r["score"] >= threshold]
        n, successes = len(selected_audit), sum(r["correct"] for r in selected_audit)
        lower = precision_lower_bound(successes, n, alpha)
        certified = (threshold is not None and n >= policy["minimum_audit_n"]
                     and lower >= policy["target_precision"] and not synthetic
                     and reference_provenance_verified is True)
        labels[key] = {"threshold": threshold, "audit_n": n, "audit_correct": successes,
                       "lower_bound": lower, "alpha": alpha, "certified": certified,
                       "tune_n": len(tune), "audit_total_n": len(audit)}
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"format_version": "1", "policy_fingerprint": expected, "cohort": cohort,
            "method": "one_sided_clopper_pearson_bonferroni",
            "reference_provenance_verified": reference_provenance_verified is True,
            "synthetic": synthetic, "input_manifest_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "labels": labels,
            "assumptions": ["independent_source_groups", "correct_external_gold",
                            "exchangeable_unchanged_cohort", "fixed_policy_and_thresholds",
                            "local_artifact_provenance_is_trusted"]}
