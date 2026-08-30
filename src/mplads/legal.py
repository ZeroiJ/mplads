"""LG1 - Hardcoded legal-route lookup: fraud type -> statutes/action points.

LOCKED RULE (AGENT.md): the ML/rule pipeline NEVER outputs legal citations.
Legal consequences are applied ONLY here, from a static, auditable, hand-written
table. Nothing in this module is model-generated.

Mapping is deliberately conservative: fraud type -> relevant statutory area +
who to refer to. It surfaces candidate legal routes for an enforcement agency
to assess; it never declares someone guilty.

Fraud types (from classify.py):
  duplicate_claim, ghost_work, siphoned_funds, over_invoicing, statistical_anomaly
"""

from .classify import _FRAUD_TYPES

LEGAL_TABLE = {
    "duplicate_claim": {
        "statutes": ["Bharatiya Nyaya Sanhita (BNS) - cheating / dishonest misappropriation",
                     "Indian Penal Code-era analogues to misappropriation provisions"],
        "refer_to": "Controlling authority (scheme re-personnel) for verification before any referral",
        "note": "Outright duplicate claims of public funds for the same work are unlawful;"
                " verification of both claims is required before citing any provision.",
        "route": "internal - administrative recovery",
    },
    "ghost_work": {
        "statutes": ["BNS - criminal breach of trust",
                     "Prevention of Corruption Act, 1988 - disproportionate assets / misappropriation not captured in accounts"],
        "refer_to": "Enforcement agency only if records show funds drawn against non-existent work",
        "note": "Work sanctioned and funded but never executed - if funds are routed out without execution,"
                " it engages breach-of-trust analysis under the relevant criminal code.",
        "route": "enforcement - agency investigation",
    },
    "siphoned_funds": {
        "statutes": ["Prevention of Money Laundering Act (PMLA), 2002 - if proceeds routed through layered transactions",
                     "Prevention of Corruption Act, 1988 - misappropriation / abuse of public office"],
        "refer_to": "ED/FIU additionally if bank trails show layering",
        "note": "Funds sanctioned, not disbursed to physical work, and possibly rerouted:"
                " PMLA analysis attaches only when financial trails indicate layering.",
        "route": "enforcement - agency investigation",
    },
    "over_invoicing": {
        "statutes": ["BNS - cheating / forgery of records",
                     "Prevention of Corruption Act, 1988 - criminal misconduct if a public servant is involved"],
        "refer_to": "Audit trail (expenditure vs sanction) provided; confirm invoices against market rates before referral",
        "note": "Inflated billing or sanction overrun is a predicate for cheating /"
                " forgery-of-records analysis, not proof by itself.",
        "route": "internal - audit then enforcement",
    },
    "statistical_anomaly": {
        "statutes": [],
        "refer_to": "Operational review only - no legal route on its own",
        "note": "A statistical outlier is a screening flag, not a legal finding. No statute applies until"
                " corroborating evidence links it to a concrete fraud type.",
        "route": "internal - review only",
    },
}


def legal_route(fraud_type: str) -> dict:
    """Return the hardcoded legal-route dict for a fraud type (safe for any input)."""
    return LEGAL_TABLE.get(fraud_type, LEGAL_TABLE["statistical_anomaly"])


def verify_table() -> bool:
    """Sanity: every fraud type the classifier can emit has a legal entry."""
    missing = [t for t in _FRAUD_TYPES if t not in LEGAL_TABLE]
    if missing:
        raise RuntimeError(f"legal table missing entries for: {missing}")
    return True