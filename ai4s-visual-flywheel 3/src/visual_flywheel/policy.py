"""Deterministic, conservative evidence gate for upstream vision observations.

Input confidence is a ranking score, never a probability of correctness. Actual
media decoding, inference, license audit and human reference review are upstream.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from . import ENGINE_VERSION


def fingerprint(policy: dict, taxonomy: dict) -> str:
    raw = json.dumps({"engine_version": ENGINE_VERSION, "policy": policy, "taxonomy": taxonomy}, sort_keys=True,
                     separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def cohort_key(label: str, modality: str) -> str:
    return f"{label}|{modality}"


def finite_number(value) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def valid_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_sha256(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value.lower()))


def validate_configuration(policy, taxonomy) -> dict:
    """Reject malformed trusted configuration before any acceptance decision."""
    if not isinstance(policy, dict) or not isinstance(taxonomy, dict):
        raise ValueError("policy and taxonomy must be JSON objects")
    for key in ("minimum_independent_families", "minimum_audit_n", "minimum_tune_n"):
        if type(policy.get(key)) is not int or policy[key] < 1:
            raise ValueError(f"policy.{key} must be a positive integer")
    for key in ("candidate_score_floor", "contradiction_score", "whole_video_minimum_coverage"):
        if not finite_number(policy.get(key)) or not 0 <= policy[key] <= 1:
            raise ValueError(f"policy.{key} must be a finite number in [0,1]")
    if not finite_number(policy.get("target_precision")) or not 0 < policy["target_precision"] <= 1:
        raise ValueError("policy.target_precision must be in (0,1]")
    if not finite_number(policy.get("familywise_alpha")) or not 0 < policy["familywise_alpha"] < 1:
        raise ValueError("policy.familywise_alpha must be in (0,1)")
    if not valid_text(policy.get("pipeline_version")):
        raise ValueError("policy.pipeline_version must be a nonempty string")
    labels = taxonomy.get("labels")
    if not isinstance(labels, list) or not labels:
        raise ValueError("taxonomy.labels must be a nonempty array")
    nodes = {}
    for node in labels:
        if not isinstance(node, dict) or not valid_text(node.get("id")):
            raise ValueError("Each taxonomy label must have a nonempty string id")
        if node["id"] in nodes:
            raise ValueError(f"Duplicate taxonomy label: {node['id']}")
        modalities = node.get("modalities", node.get("scope"))
        if (not isinstance(modalities, list) or not modalities
                or any(x not in ("image", "video") for x in modalities)
                or type(node.get("requires_temporal", False)) is not bool):
            raise ValueError(f"Invalid modalities/temporal declaration: {node['id']}")
        for field in ("required_checks", "excludes"):
            values = node.get(field, [])
            if not isinstance(values, list) or any(not valid_text(x) for x in values):
                raise ValueError(f"Invalid {field}: {node['id']}")
        nodes[node["id"]] = node
    for label, node in nodes.items():
        parent = node.get("parent")
        if parent is not None and (not valid_text(parent) or parent not in nodes):
            raise ValueError(f"Unknown parent for label: {label}")
        if any(other not in nodes for other in node.get("excludes", [])):
            raise ValueError(f"Unknown exclusion for label: {label}")
    for label in nodes:
        seen, cursor = set(), label
        while cursor is not None:
            if cursor in seen:
                raise ValueError(f"Cyclic taxonomy hierarchy: {label}")
            seen.add(cursor)
            cursor = nodes[cursor].get("parent")
    return nodes


def valid_box(box) -> bool:
    return (isinstance(box, list) and len(box) == 4 and all(finite_number(x) for x in box)
            and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)


def valid_interval(interval, duration) -> bool:
    return (isinstance(interval, list) and len(interval) == 2
            and all(finite_number(x) for x in interval)
            and finite_number(duration) and 0 <= interval[0] < interval[1] <= duration)


def evidence_ok(evidence, modality: str, duration, temporal: bool, required_checks=()) -> bool:
    if not isinstance(evidence, dict) or evidence.get("channel") != "visual":
        return False
    if not valid_text(evidence.get("ref")):
        return False
    checks = evidence.get("checks", {})
    if not isinstance(checks, dict):
        return False
    for check in required_checks:
        attestation = checks.get(check, {})
        if (not isinstance(attestation, dict) or attestation.get("passed") is not True
                or not isinstance(attestation.get("ref"), str) or not attestation["ref"].strip()):
            return False
    if modality == "image":
        return valid_box(evidence.get("bbox")) and not temporal
    if not valid_interval(evidence.get("interval"), duration):
        return False
    if evidence.get("bbox") is not None and not valid_box(evidence["bbox"]):
        return False
    observed_segments = evidence.get("observed_segments", [])
    if (not isinstance(observed_segments, list)
            or any(not valid_interval(segment, duration) for segment in observed_segments)):
        return False
    if temporal:
        times = evidence.get("observed_times", [])
        if (not isinstance(times, list) or len(times) < 2
                or not all(finite_number(t) for t in times)
                or times != sorted(set(times))
                or not all(evidence["interval"][0] <= t <= evidence["interval"][1] for t in times)
                or evidence.get("time_order_verified") is not True):
            return False
        # Preserve temporal relations when the observer asserts one.
        relations = evidence.get("relations", [])
        if not isinstance(relations, list):
            return False
        for relation in relations:
            if not isinstance(relation, dict):
                return False
            a, b = relation.get("before"), relation.get("after")
            if (not valid_interval(a, duration) or not valid_interval(b, duration)
                    or a[1] > b[0]
                    or a[0] < evidence["interval"][0]
                    or b[1] > evidence["interval"][1]):
                return False
    return True


def interval_coverage(intervals: list, duration: float) -> float:
    if not intervals or not finite_number(duration) or duration <= 0:
        return 0.0
    merged, total = sorted(intervals), 0.0
    start, end = merged[0]
    for a, b in merged[1:]:
        if a <= end:
            end = max(end, b)
        else:
            total += end - start
            start, end = a, b
    return min(1.0, (total + end - start) / duration)


def _certificate_threshold(calibration, label, modality, cohort, policy, taxonomy):
    if not isinstance(calibration, dict):
        return None
    if (calibration.get("policy_fingerprint") != fingerprint(policy, taxonomy)
            or calibration.get("cohort") != cohort
            or calibration.get("synthetic") is True
            or calibration.get("reference_provenance_verified") is not True):
        return None
    label_certificates = calibration.get("labels")
    if not isinstance(label_certificates, dict):
        return None
    item = label_certificates.get(cohort_key(label, modality), {})
    if not isinstance(item, dict) or item.get("certified") is not True:
        return None
    # Reject inconsistent certificate statistics. Authenticity and reviewer
    # identity still require a trusted local artifact producer.
    from .calibration import precision_lower_bound
    n, successes, alpha = item.get("audit_n"), item.get("audit_correct"), item.get("alpha")
    expected_alpha = policy["familywise_alpha"] / max(1, len(label_certificates))
    if (type(n) is not int or type(successes) is not int or not 0 <= successes <= n
            or n < policy["minimum_audit_n"] or not finite_number(item.get("lower_bound"))
            or not finite_number(alpha) or abs(alpha - expected_alpha) > 1e-12
            or calibration.get("method") != "one_sided_clopper_pearson_bonferroni"):
        return None
    actual_lower = precision_lower_bound(successes, n, alpha)
    if (abs(actual_lower - item["lower_bound"]) > 1e-10
            or actual_lower < policy["target_precision"]):
        return None
    threshold = item.get("threshold")
    return threshold if finite_number(threshold) and 0 <= threshold <= 1 else None


def classify(record: dict, policy: dict, taxonomy: dict, calibration: dict | None = None) -> dict:
    """Classify existing observations; never infer labels from media metadata alone."""
    nodes = validate_configuration(policy, taxonomy)
    if not isinstance(record, dict):
        return {"asset_id": None, "unit_id": None, "modality": None, "synthetic": False,
                "labels": [], "policy_fingerprint": fingerprint(policy, taxonomy),
                "warnings": ["record_must_be_object"], "reference_reviews": [],
                "source": {}, "cohort": None, "split": None, "duration_seconds": None,
                "status": "human_review"}
    result = {"asset_id": record.get("asset_id"), "unit_id": record.get("unit_id"), "modality": record.get("modality"),
              "synthetic": record.get("synthetic", False), "labels": [],
              "policy_fingerprint": fingerprint(policy, taxonomy), "warnings": [],
              "reference_reviews": record.get("reference_reviews", []),
              "source": record.get("source", {}), "cohort": record.get("cohort"),
              "split": record.get("split"), "duration_seconds": record.get("duration_seconds")}
    source = record.get("source", {})
    if not isinstance(source, dict):
        return {**result, "source": {}, "status": "quarantine", "warnings": ["invalid_source"]}
    rights = source.get("rights", {})
    if (not isinstance(rights, dict) or rights.get("status") != "cleared" or rights.get("training_allowed") is not True
            or rights.get("redistribution_allowed") is not True
            or not valid_text(rights.get("license_id")) or not valid_text(rights.get("audit_ref"))):
        return {**result, "status": "quarantine", "warnings": ["rights_not_cleared"]}
    if (record.get("modality") not in ("image", "video") or not valid_text(source.get("url"))
            or not valid_text(record.get("asset_id")) or not valid_text(record.get("unit_id"))
            or record.get("split") not in ("train", "validation", "test", "tune", "audit")
            or not valid_text(source.get("source_group")) or not valid_text(record.get("cohort"))
            or not valid_sha256(source.get("sha256"))
            or type(record.get("synthetic", False)) is not bool):
        return {**result, "status": "human_review", "warnings": ["invalid_or_missing_provenance"]}
    if (record["modality"] == "video"
            and (record.get("claim_scope", "segment") not in ("segment", "whole_asset")
                 or not finite_number(record.get("duration_seconds")) or record["duration_seconds"] <= 0)):
        return {**result, "status": "human_review", "warnings": ["invalid_video_scope_or_duration"]}
    quality = record.get("quality", {})
    if (not isinstance(quality, dict) or quality.get("usable") is not True
            or not valid_text(quality.get("audit_ref"))):
        return {**result, "status": "human_review", "warnings": ["missing_or_failed_quality_gate"]}
    observations = record.get("observations", [])
    reviews = record.get("reference_reviews", [])
    if (not isinstance(observations, list) or any(not isinstance(x, dict) for x in observations)
            or not isinstance(reviews, list) or any(not isinstance(x, dict) for x in reviews)):
        return {**result, "status": "human_review", "warnings": ["invalid_observation_or_reference_schema"]}
    if any(not valid_text(x.get("label")) for x in observations):
        return {**result, "status": "human_review", "warnings": ["invalid_observation_label"]}
    by_label = defaultdict(list)
    for observation in observations:
        by_label[observation.get("label", "")].append(observation)
    modality, duration = record["modality"], record.get("duration_seconds")
    for label, observations in sorted(by_label.items()):
        decision = {"id": label, "status": "human_review", "score": None,
                    "families": [], "evidence": [], "reasons": []}
        node = nodes.get(label)
        if node is None:
            decision["reasons"].append("unknown_label")
            result["labels"].append(decision)
            continue
        if modality not in node.get("modalities", node.get("scope", [])):
            decision["reasons"].append("modality_mismatch")
            result["labels"].append(decision)
            continue
        families = defaultdict(list)
        contradictions = []
        for observation in observations:
            score, family = observation.get("score"), observation.get("dependency_family")
            evidence = observation.get("evidence")
            if (not finite_number(score) or not 0 <= score <= 1 or not valid_text(family)
                    or not valid_text(observation.get("observer_id"))
                    or observation.get("unit_id") != record["unit_id"]
                    or not evidence_ok(evidence, modality, duration, node.get("requires_temporal", False),
                                       node.get("required_checks", [])
                                       if observation.get("verdict") == "support" else [])):
                decision["reasons"].append("invalid_or_ungrounded_observation")
                continue
            if observation.get("verdict") == "contradict" and score >= policy["contradiction_score"]:
                contradictions.append(family)
            elif observation.get("verdict") == "support":
                families[family].append(observation)
        decision["families"] = sorted(families)
        # Family minimum prevents best-of-N confidence cherry-picking inside a family.
        family_scores = sorted((min(o["score"] for o in votes) for votes in families.values()), reverse=True)
        decision["evidence"] = [o["evidence"] for votes in families.values() for o in votes]
        if contradictions:
            decision["reasons"].append("grounded_contradiction")
        if len(families) < policy["minimum_independent_families"]:
            decision["reasons"].append("insufficient_independent_support")
        if len(family_scores) >= policy["minimum_independent_families"]:
            decision["score"] = family_scores[policy["minimum_independent_families"] - 1]
            if decision["score"] < policy["candidate_score_floor"]:
                decision["reasons"].append("score_below_candidate_floor")
        if modality == "video" and record.get("claim_scope", "segment") == "whole_asset":
            # A claim interval or two isolated frames do not prove continuous inspection.
            coverage = interval_coverage([segment for e in decision["evidence"]
                                          for segment in e.get("observed_segments", [])], duration)
            decision["visual_coverage"] = coverage
            if coverage < policy["whole_video_minimum_coverage"]:
                decision["reasons"].append("insufficient_whole_video_coverage")
        # An invalid observation is retained for audit but is not itself fatal if
        # sufficient other valid independent evidence exists.
        fatal = set(decision["reasons"]) - {"invalid_or_ungrounded_observation"}
        if not fatal:
            threshold = _certificate_threshold(calibration, label, modality, record["cohort"], policy, taxonomy)
            if threshold is None:
                decision["status"] = "provisional"
                decision["reasons"].append("missing_matching_precision_certificate")
            elif decision["score"] < threshold:
                decision["reasons"].append("score_below_calibrated_threshold")
            else:
                decision["status"] = "accepted"
        result["labels"].append(decision)
    # No inheritance: a child needs direct supporting observations of its own.
    indexed = {x["id"]: x for x in result["labels"]}
    for label, decision in indexed.items():
        node = nodes.get(label, {})
        for other in node.get("excludes", []):
            if (other in indexed and decision["status"] in ("accepted", "provisional")
                    and indexed[other]["status"] in ("accepted", "provisional")):
                for conflict in (decision, indexed[other]):
                    conflict["status"] = "human_review"
                    if "taxonomy_conflict" not in conflict["reasons"]:
                        conflict["reasons"].append("taxonomy_conflict")
    if not result["labels"]:
        result["status"] = "abstain"
        result["warnings"].append("no_supported_candidates")
    elif any(x["status"] == "human_review" for x in result["labels"]):
        result["status"] = "human_review"
    elif any(x["status"] == "provisional" for x in result["labels"]):
        result["status"] = "provisional"
    else:
        result["status"] = "accepted"
    return result


def classify_batch(records, policy, taxonomy, calibration=None):
    records = list(records)
    groups = defaultdict(set)
    hashes = defaultdict(set)
    for record in records:
        if not isinstance(record, dict):
            continue
        source = record.get("source", {})
        if not isinstance(source, dict) or not valid_text(record.get("split")):
            continue
        if valid_text(source.get("source_group")):
            groups[source["source_group"]].add(record["split"])
        if valid_sha256(source.get("sha256")):
            hashes[source["sha256"].lower()].add(record["split"])
    decisions = []
    for record in records:
        result = classify(record, policy, taxonomy, calibration)
        source = record.get("source", {}) if isinstance(record, dict) else {}
        source = source if isinstance(source, dict) else {}
        group = source.get("source_group")
        digest = source.get("sha256")
        if ((valid_text(group) and len(groups.get(group, [])) > 1)
                or (valid_sha256(digest) and len(hashes.get(digest.lower(), [])) > 1)):
            result["status"] = "quarantine"
            result["warnings"].append("cross_split_source_or_exact_duplicate_leakage")
        decisions.append(result)
    return decisions
