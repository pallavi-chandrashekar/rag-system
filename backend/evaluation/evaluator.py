"""Lightweight RAG evaluation harness.

Computes offline quality metrics over a set of labelled cases without requiring
any third-party eval service. The metric functions are pure and unit-testable;
``Evaluator.run`` drives them against any ``search_fn`` (the live API, a stub,
or a mock) so the same harness works in CI and against a deployed stack.

Metrics (Step 11):
* citation_rate          -- answers that carry >= 1 source.
* avg_source_count       -- mean citations per answered query.
* unknown_answer_accuracy-- correct abstention on out-of-scope queries.
* relevance              -- expected keyword coverage in the answer.
* groundedness           -- proxy: answer terms supported by cited sources.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall((text or "").lower()))


@dataclass
class EvalCase:
    query: str
    # Keywords expected in a correct grounded answer.
    expected_keywords: List[str] = field(default_factory=list)
    # True when the system *should* abstain ("I don't know...").
    expect_unknown: bool = False


def relevance_score(answer: str, expected_keywords: List[str]) -> float:
    """Fraction of expected keywords present in the answer."""
    if not expected_keywords:
        return 1.0
    a = (answer or "").lower()
    hits = sum(1 for k in expected_keywords if k.lower() in a)
    return hits / len(expected_keywords)


def groundedness_score(answer: str, sources: List[Dict]) -> float:
    """Proxy groundedness: share of answer content terms found in sources.

    A high score means the answer's vocabulary is supported by the retrieved
    context (a cheap stand-in for an LLM/NLI groundedness judge).
    """
    answer_terms = _tokens(answer)
    if not answer_terms:
        return 0.0
    source_terms = set()
    for s in sources:
        source_terms |= _tokens(s.get("text_snippet") or s.get("content", ""))
    if not source_terms:
        return 0.0
    supported = answer_terms & source_terms
    return len(supported) / len(answer_terms)


def is_unknown(answer: str, unknown_text: str = "I don't know") -> bool:
    return unknown_text.lower() in (answer or "").lower()


class Evaluator:
    def __init__(self, unknown_text: str = "I don't know based on the available documents."):
        self.unknown_text = unknown_text

    def run(self, cases: List[EvalCase], search_fn: Callable[[str], Dict]) -> Dict:
        """Run all cases. ``search_fn(query)`` must return a response dict with
        ``answer`` and ``sources`` keys (matching the API contract)."""
        per_case = []
        for case in cases:
            resp = search_fn(case.query)
            answer = resp.get("answer", "")
            sources = resp.get("sources", []) or []
            abstained = is_unknown(answer, self.unknown_text)

            if case.expect_unknown:
                unknown_correct = abstained
                relevance = 1.0 if abstained else 0.0
                grounded = 1.0 if abstained else 0.0
            else:
                unknown_correct = not abstained
                relevance = relevance_score(answer, case.expected_keywords)
                grounded = groundedness_score(answer, sources)

            per_case.append(
                {
                    "query": case.query,
                    "answered": not abstained,
                    "source_count": len(sources),
                    "has_citations": len(sources) > 0,
                    "unknown_correct": unknown_correct,
                    "relevance": round(relevance, 3),
                    "groundedness": round(grounded, 3),
                }
            )

        answered = [c for c in per_case if c["answered"]]
        n = len(per_case) or 1
        n_answered = len(answered) or 1
        summary = {
            "cases": len(per_case),
            "citation_rate": round(sum(c["has_citations"] for c in answered) / n_answered, 3),
            "avg_source_count": round(sum(c["source_count"] for c in answered) / n_answered, 3),
            "unknown_answer_accuracy": round(sum(c["unknown_correct"] for c in per_case) / n, 3),
            "avg_relevance": round(sum(c["relevance"] for c in per_case) / n, 3),
            "avg_groundedness": round(sum(c["groundedness"] for c in per_case) / n, 3),
        }
        return {"summary": summary, "cases": per_case}


# A small default suite aligned with the bundled sample documents.
DEFAULT_CASES = [
    EvalCase("What is the remote work policy?", ["remote", "work"]),
    EvalCase("How many vacation days do employees get?", ["vacation"]),
    EvalCase("What are the steps to handle a Sev-1 incident?", ["incident", "sev"]),
    EvalCase("How do I reset my password?", ["password"]),
    EvalCase("What is the airspeed velocity of an unladen swallow?", expect_unknown=True),
]


if __name__ == "__main__":  # pragma: no cover - live smoke run
    import os
    import requests

    base = os.getenv("RAG_BASE_URL", "http://localhost:8000")
    tenant = os.getenv("RAG_EVAL_TENANT", "demo-corp")

    def live_search(query: str) -> Dict:
        r = requests.post(
            f"{base}/api/v1/search",
            json={"text": query, "tenant_id": tenant, "chat_history": []},
            timeout=60,
        )
        return r.json()

    report = Evaluator().run(DEFAULT_CASES, live_search)
    import json

    print(json.dumps(report, indent=2))
