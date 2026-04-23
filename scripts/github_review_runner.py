"""
github_review_runner.py

Bridges GitHub Actions with the PRCodeReviewFlow.
- Reads the PR diff from a file
- Runs the CrewAI flow
- Posts the review as a PR comment
- Approves or requests changes via the GitHub API
"""

import argparse
import os
import sys
import re
import json
import requests

# ── Make sure the project src is importable ──────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from code_review_flow.main import PRCodeReviewFlow


# ── GitHub API helpers ────────────────────────────────────────────────────────

def gh_headers() -> dict:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise EnvironmentError("GH_TOKEN / GITHUB_TOKEN is not set.")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def post_pr_comment(repo: str, pr_number: int, body: str) -> None:
    """Post a comment on the PR."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=gh_headers(), json={"body": body})
    resp.raise_for_status()
    print(f"✅ Comment posted (id={resp.json()['id']})")


def submit_pr_review(repo: str, pr_number: int, event: str, body: str) -> None:
    """
    Submit a formal GitHub review.
    event must be one of: APPROVE | REQUEST_CHANGES | COMMENT
    """
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    resp = requests.post(
        url,
        headers=gh_headers(),
        json={"event": event, "body": body},
    )
    resp.raise_for_status()
    print(f"✅ Review submitted: {event}")


# ── Decision parsing ──────────────────────────────────────────────────────────

def parse_decision(final_answer: str) -> str:
    """
    Extract APPROVE / REQUEST CHANGES / ESCALATE from the LLM's free-text answer.
    Returns a normalised string: 'APPROVE', 'REQUEST_CHANGES', or 'ESCALATE'.
    """
    upper = final_answer.upper()
    if "APPROVE" in upper and "REQUEST" not in upper:
        return "APPROVE"
    if "REQUEST CHANGES" in upper or "REQUEST_CHANGES" in upper:
        return "REQUEST_CHANGES"
    if "ESCALATE" in upper:
        return "ESCALATE"
    # Fallback: be conservative
    return "REQUEST_CHANGES"


def extract_confidence(final_answer: str) -> int | None:
    """Pull the first integer that follows 'Confidence' in the answer."""
    match = re.search(r"confidence\s*[:\-]?\s*(\d+)", final_answer, re.IGNORECASE)
    return int(match.group(1)) if match else None


# ── Comment formatting ────────────────────────────────────────────────────────

DECISION_EMOJI = {
    "APPROVE": "✅",
    "REQUEST_CHANGES": "🔴",
    "ESCALATE": "⚠️",
}

DECISION_LABEL = {
    "APPROVE": "APPROVED",
    "REQUEST_CHANGES": "CHANGES REQUESTED",
    "ESCALATE": "NEEDS HUMAN REVIEW",
}


def format_comment(
    decision: str,
    confidence: int | None,
    final_answer: str,
    review_result: dict,
    crew_used: bool,
) -> str:
    emoji = DECISION_EMOJI.get(decision, "🤖")
    label = DECISION_LABEL.get(decision, decision)
    conf_str = f"**Confidence:** {confidence}/100  \n" if confidence is not None else ""
    review_type = "Multi-Agent Crew Review" if crew_used else "Quick LLM Review"

    comment = f"""## {emoji} AI Code Review — {label}

{conf_str}**Review type:** {review_type}

---

### 📋 Final Decision

{final_answer}

---

### 🔍 Detailed Analysis

<details>
<summary>Click to expand raw review data</summary>

```json
{json.dumps(review_result, indent=2, default=str)}
```

</details>

---
*Automated review by [PRCodeReviewFlow](https://github.com/{os.environ.get("REPO", "your-org/your-repo")}) · powered by CrewAI + Groq*
"""
    return comment


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run AI code review on a GitHub PR diff")
    parser.add_argument("--diff-file", required=True, help="Path to the PR diff file")
    parser.add_argument("--pr-number", required=True, type=int, help="PR number")
    parser.add_argument("--repo", required=True, help="GitHub repo in owner/name format")
    args = parser.parse_args()

    diff_file = args.diff_file
    pr_number = args.pr_number
    repo = args.repo

    # ── Validate diff file ────────────────────────────────────────────────────
    if not os.path.exists(diff_file):
        print(f"❌ Diff file not found: {diff_file}")
        sys.exit(1)

    with open(diff_file) as f:
        diff_content = f.read().strip()

    if not diff_content:
        print("⚠️  Empty diff — nothing to review. Skipping.")
        sys.exit(0)

    print(f"📄 Diff loaded: {len(diff_content)} chars, PR #{pr_number} in {repo}")

    # ── Run the CrewAI flow ───────────────────────────────────────────────────
    print("🚀 Starting PRCodeReviewFlow…")

    flow = PRCodeReviewFlow(tracing=False)
    flow.state.pr_file_path = diff_file   # point at the temp diff file

    # Manually step through the flow (mirrors how app.py calls it)
    flow.read_pr_file()

    decision_route = flow.analyze_changes(None)
    print(f"📊 Complexity decision: {decision_route}")

    if decision_route == "ERROR":
        error_body = f"## ⚠️ AI Code Review — Error\n\n{flow.state.final_answer}"
        post_pr_comment(repo, pr_number, error_body)
        sys.exit(1)

    if decision_route == "SIMPLE":
        flow.simple_review()
    else:
        flow.full_crew_review()

    flow.make_final_decision()
    flow.return_final_answer()

    final_answer = flow.state.final_answer
    review_result = flow.state.review_result
    crew_used = flow.state.crew_needed

    print(f"\n📝 Final Answer:\n{final_answer}\n")

    # ── Parse the LLM decision ────────────────────────────────────────────────
    gh_event = parse_decision(final_answer)
    confidence = extract_confidence(final_answer)

    print(f"🎯 GitHub review event: {gh_event} (confidence={confidence})")

    # ── Build and post the comment + formal review ────────────────────────────
    comment_body = format_comment(
        decision=gh_event,
        confidence=confidence,
        final_answer=final_answer,
        review_result=review_result,
        crew_used=crew_used,
    )

    # Map flow decision to GitHub review event
    # ESCALATE → leave a comment only (no formal approval/rejection)
    if gh_event == "APPROVE":
        submit_pr_review(repo, pr_number, "APPROVE", comment_body)
    elif gh_event == "REQUEST_CHANGES":
        submit_pr_review(repo, pr_number, "REQUEST_CHANGES", comment_body)
    else:
        # ESCALATE — just post a plain comment, don't block or approve
        post_pr_comment(repo, pr_number, comment_body)

    print("✨ Done!")


if __name__ == "__main__":
    main()
