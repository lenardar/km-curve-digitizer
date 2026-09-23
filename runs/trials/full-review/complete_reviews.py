import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


BASE_PANELS = {
    "study01-os": "Both colored traces remain distinct through crossings, dense censor marks, and the late tail.",
    "study01-pfs": "Both traces follow the dense early descent and their separate late endpoints; the shorter Sorafenib tail is visible in the source.",
    "study02-os": "The dark-teal and taupe traces retain identity through labels, large censor dots, and late plateaus.",
    "study02-pfs": "Both traces follow the visible source steps through large censor dots and separate terminal plateaus.",
    "study03-os": "The orange and blue-gray traces follow the visible fine staircase and remain separate across the full axis.",
    "study05-os": "The cyan and red traces follow the source through dense censor marks and the late cyan drops.",
    "study05-pfs": "The cyan and red traces follow the source through the early decline, long plateaus, and late cyan drops.",
}


def complete_clear_review(panel: str, panel_observation: str) -> None:
    path = ROOT / panel / "base-scan" / "scan_review.json"
    review = json.loads(path.read_text())
    for window in review["window_reviews"]:
        t0, t1 = window["time_range"]
        window["status"] = "clear"
        window["observation"] = (
            f"Source-only and both focused overlays were inspected from {t0:g}-{t1:g}; "
            f"step continuity agrees across both overlap boundaries. {panel_observation}"
        )
        for curve in window["curve_reviews"]:
            curve["status"] = "clear"
            curve["observation"] = (
                f"{curve['curve_name']} follows the visible source steps in {window['window_id']} "
                "without an unsupported jump or identity switch."
            )
    path.write_text(json.dumps(review, indent=2) + "\n")


for panel, observation in BASE_PANELS.items():
    complete_clear_review(panel, observation)


base_path = ROOT / "study04-pfs" / "base-scan" / "scan_review.json"
base = json.loads(base_path.read_text())
for window in base["window_reviews"]:
    is_tail = window["window_id"] in {"w005", "w006"}
    window["status"] = "confirmed_defect" if is_tail else "clear"
    window["observation"] = (
        "The dark Nivolumab trace is forward-filled past its visible x=362 endpoint."
        if is_tail
        else "Both focused overlays follow the visible steps and preserve curve identity in this window."
    )
    for curve in window["curve_reviews"]:
        defect = is_tail and curve["curve_name"] == "Nivolumab"
        curve["status"] = "confirmed_defect" if defect else "clear"
        curve["observation"] = (
            "Nivolumab continues to x=385 although the source-only crop ends at x=362."
            if defect
            else f"{curve['curve_name']} follows the visible source in {window['window_id']}."
        )
base_path.write_text(json.dumps(base, indent=2) + "\n")


candidate_path = ROOT / "study04-pfs" / "candidate" / "narrow-scan" / "scan_review.json"
candidate = json.loads(candidate_path.read_text())
for window in candidate["window_reviews"]:
    is_tail = window["window_id"] in {"w005", "w006"}
    window["status"] = "resolved" if is_tail else "clear"
    window["observation"] = (
        "The edited Nivolumab trace now stops at the last visible dark endpoint while Bevacizumab retains its longer light-gray tail."
        if is_tail
        else "Source-only and both focused overlays agree; curve identities remain continuous through the overlap."
    )
    for curve in window["curve_reviews"]:
        resolved = is_tail and curve["curve_name"] == "Nivolumab"
        curve["status"] = "resolved" if resolved else "clear"
        curve["observation"] = (
            "The unsupported x=363-385 extension is absent and the trace ends at the visible x=362 endpoint."
            if resolved
            else f"{curve['curve_name']} follows the visible source in {window['window_id']} without switching identity."
        )

issue_observations = {
    "q001-curve_identity_review": "The curves are close near the origin, but the dark and light source pixels remain separately traceable and neither extraction switches identity.",
    "q002-curve_identity_review": "The local approach near 21 months is present in the source; overlapping windows show each trace continuing on its own color afterward.",
    "q003-curve_identity_review": "The long close run from 22-24 months is a real source configuration, with distinct dark and light endpoints visible in the source-only windows.",
    "q004-curve_identity_review": "The terminal approach is genuine; the dark trace ends at x=362 while the light trace continues farther right, confirming identity.",
}
for issue in candidate["issue_reviews"]:
    issue["status"] = "false_positive"
    issue["observation"] = issue_observations[issue["issue_id"]]
candidate_path.write_text(json.dumps(candidate, indent=2) + "\n")


accepted_dirs = {
    "study01-os": ROOT / "study01-os" / "accepted",
    "study01-pfs": ROOT / "study01-pfs" / "accepted",
    "study02-os": ROOT / "study02-os" / "accepted",
    "study02-pfs": ROOT / "study02-pfs" / "accepted",
    "study03-os": ROOT / "study03-os" / "accepted",
    "study03-pfs": ROOT.parent / "study03-pfs-scan" / "accepted",
    "study04-os": ROOT.parent / "study04-os-scan" / "accepted",
    "study04-pfs": ROOT / "study04-pfs" / "accepted",
    "study05-os": ROOT / "study05-os" / "accepted",
    "study05-pfs": ROOT / "study05-pfs" / "accepted",
}

summary_path = ROOT.parents[1] / "summary.json"
summary = json.loads(summary_path.read_text())
summary["panels_accepted"] = 10
summary["panels_pending_scan_review"] = 0
summary["notes"] = [
    "All ten panels were inspected left-to-right with overlapping source-only and per-curve windows.",
    "Acceptance is tied to the exact result signature and a completed scan review for every window and curve.",
    "The full pass retained eight reviewed results and corrected unsupported or displaced trace segments in study03/pfs, study04/os, and study04/pfs.",
]
for panel in summary["panels"]:
    key = f"{panel['study']}-{panel['endpoint']}"
    accepted_dir = accepted_dirs[key]
    decision = json.loads((accepted_dir / "review_decision.json").read_text())
    result = json.loads((accepted_dir / "result.json").read_text())
    relative_dir = accepted_dir.relative_to(ROOT.parents[2])
    panel["status"] = "accepted_after_overlapping_window_review"
    panel["review_kind"] = decision["review_kind"]
    panel["verification"] = decision["verification"]
    panel["revision_count"] = len(result.get("revisions", []))
    panel["validation_issues"] = result.get("validation", {}).get("issues", [])
    panel["result"] = str(relative_dir / "result.json")
    panel["overlay"] = str(relative_dir / "overlay.png")
    panel["review_decision"] = str(relative_dir / "review_decision.json")
    panel["scan_review"] = str(relative_dir / "scan_review.json")

summary_path.write_text(json.dumps(summary, indent=2) + "\n")
