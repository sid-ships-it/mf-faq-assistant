"""Facts-only MF assistant: guardrails + retrieval + answer generation.

Pipeline for every question:
1. Guardrails: block PII, refuse advice/opinion, redirect performance questions.
2. Retrieve: TF-IDF over (a) verified fact cards and (b) chunks of the 24
   official source documents. Fact cards get a score boost because they were
   checked by hand against the source.
3. Generate: if a Gemini API key is set, the LLM writes a <=3 sentence answer
   using ONLY the retrieved context and cites one URL from it. With no key,
   the best-matching fact card (or source sentences) is returned directly.
"""
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).parent
DATA = ROOT / "data"
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

SCHEMES = {
    "Parag Parikh Flexi Cap Fund": ["flexi", "flexicap", "ppfcf"],
    "Parag Parikh ELSS Tax Saver Fund": ["elss", "tax saver", "taxsaver", "tax saving", "80c"],
    "Parag Parikh Large Cap Fund": ["large cap", "largecap", "large-cap", "bluechip"],
}
FACT_WORDS = {
    "expense ratio": ["expense ratio", "ter", "expense", "fees", "charges", "cost of fund"],
    "exit load": ["exit load", "exit", "redemption charge", "load"],
    "minimum sip": ["minimum sip", "min sip", "sip amount", "minimum investment", "minimum amount", "minimum", "lumpsum", "lump sum"],
    "lock-in": ["lock-in", "lock in", "lockin", "locked"],
    "riskometer": ["riskometer", "risk-o-meter", "risk level", "how risky", "risk"],
    "benchmark": ["benchmark", "index"],
    "capital gains statement": ["capital gain", "capital gains", "capital-gains", "capital-gain", "tax statement", "cg statement"],
    "account statement": ["account statement", "statement", "cas", "missed call"],
    "elss tax benefit": ["80c", "tax benefit", "tax deduction", "save tax"],
}

EDU_LINK = "https://www.mutualfundssahihai.com/en/what-is-a-mutual-fund"
FACTSHEET_LINK = "https://amc.ppfas.com/downloads/factsheet/"
SEBI_LINK = "https://investor.sebi.gov.in/securities-mf-investments.html"

DISCLAIMER = "Facts-only. No investment advice."

# --- Guardrails ------------------------------------------------------------
PII_PATTERNS = {
    "PAN": r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b",
    "Aadhaar": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    "phone number": r"(?<!\d)(\+?91[\s-]?)?[6-9]\d{9}(?!\d)",
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "OTP": r"\botp\b",
    "account number": r"\b(account|folio|a/c)\s*(no\.?|number|#)?\s*[:\-]?\s*\d{6,}\b",
}
ADVICE_PATTERNS = [
    r"\bshould i\b", r"\bis\b.*\b(good|safe|worth|right for me)\b", r"\bshall i\b", r"\bwhich (one|fund|scheme) (is|should)\b", r"\bis it (good|safe|worth)\b",
    r"\bbest\b", r"\brecommend", r"\bsuggest", r"\badvi[cs]e\b", r"\bbuy\b", r"\bsell\b", r"\bhold\b",
    r"\bswitch to\b", r"\bbetter\b", r"\bworth (it|investing)\b", r"\bgood (fund|investment|time)\b",
    r"\bportfolio\b", r"\ballocat", r"\bhow much should\b", r"\bwhere (should|to) invest\b",
]
PERFORMANCE_PATTERNS = [
    r"\breturns?\b", r"\bcagr\b", r"\bperform", r"\bnav\b", r"\bgrowth rate\b", r"\bhow much (will|would|can) i (get|earn|make)\b",
    r"\bbeat(s|en)? the (index|benchmark|market)\b",
]


@dataclass
class Answer:
    text: str
    url: str
    updated: str
    kind: str  # answer | refusal | pii | performance | unknown
    contexts: list = field(default_factory=list)


def check_guardrails(q: str):
    low = q.lower()
    for label, pat in PII_PATTERNS.items():
        if re.search(pat, q, re.I):
            return Answer(
                f"For your safety I can't accept personal details like a {label}. Please remove it and ask your question again. "
                "I only answer general facts about mutual fund schemes.",
                SEBI_LINK, "", "pii")
    if any(re.search(p, low) for p in ADVICE_PATTERNS):
        return Answer(
            "I can only share facts about mutual fund schemes, so I can't say whether you should buy, sell or choose a fund. "
            "For decisions based on your goals, please consult a SEBI-registered investment adviser. "
            "You can learn how to evaluate schemes on AMFI's investor education site.",
            EDU_LINK, "", "refusal")
    if any(re.search(p, low) for p in PERFORMANCE_PATTERNS):
        return Answer(
            "I don't calculate or compare returns. The latest official performance figures for PPFAS schemes are in the monthly factsheet. "
            "Past performance is not an indicator of future results.",
            FACTSHEET_LINK, "", "performance")
    return None


# --- Retrieval ---------------------------------------------------------------
class Retriever:
    def __init__(self):
        self.facts = json.loads((DATA / "facts.json").read_text())
        self.chunks = [json.loads(l) for l in open(DATA / "chunks.jsonl")]
        self.docs = []
        for f in self.facts:
            self.docs.append({"text": f"{f['scheme']} {f['fact']} {f['answer']}", "url": f["url"],
                              "title": f"{f['scheme']} - {f['fact']}", "scheme": f["scheme"],
                              "fact": f["fact"], "as_of": f["as_of"], "is_fact": True, "answer": f["answer"]})
        for c in self.chunks:
            self.docs.append({"text": c["text"], "url": c["url"], "title": c["title"], "scheme": c["scheme"],
                              "fact": None, "as_of": c["fetched"], "is_fact": False})
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self.matrix = self.vec.fit_transform(d["text"] for d in self.docs)

    @staticmethod
    def _has(low: str, key: str) -> bool:
        return re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", low) is not None

    @classmethod
    def detect_scheme(cls, q: str):
        low = q.lower()
        return [s for s, keys in SCHEMES.items() if any(cls._has(low, k) for k in keys)]

    @classmethod
    def detect_fact(cls, q: str):
        low = q.lower()
        # check the most specific facts first
        for fact in ["capital gains statement", "elss tax benefit", "account statement", "expense ratio",
                     "exit load", "lock-in", "minimum sip", "riskometer", "benchmark"]:
            if any(cls._has(low, k) for k in FACT_WORDS[fact]):
                return fact
        return None

    def search(self, q: str, k: int = 5):
        schemes, fact = self.detect_scheme(q), self.detect_fact(q)
        sims = cosine_similarity(self.vec.transform([q]), self.matrix).ravel()
        scored = []
        for i, d in enumerate(self.docs):
            s = sims[i]
            if d["is_fact"]:
                s += 0.15
                if fact and d["fact"] == fact:
                    s += 0.5
                if d["scheme"] in schemes or (d["scheme"] == "All schemes" and not schemes):
                    s += 0.3
            elif schemes and d["scheme"] in schemes:
                s += 0.05
            scored.append((s, i))
        scored.sort(reverse=True)
        return [dict(self.docs[i], score=float(s)) for s, i in scored[:k]], schemes, fact


# --- Generation ---------------------------------------------------------------
SYSTEM_PROMPT = """You are a facts-only FAQ assistant for PPFAS Mutual Fund schemes (Parag Parikh Flexi Cap Fund, Parag Parikh ELSS Tax Saver Fund, Parag Parikh Large Cap Fund).

Rules:
- Answer ONLY from the CONTEXT below. If the context does not contain the fact, reply exactly: NOT_FOUND
- Identify the exact fact asked (expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, statements) and answer only that.
- At most 3 short sentences. Plain language. Include numbers exactly as written in the context.
- Never give advice, opinions, recommendations, predictions, or return figures.
- Do not include any URL in your answer text; the app adds the citation.
- On the last line write: SOURCE: <the number of the context block you used>
"""


def _llm():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return None
    from google import genai
    return genai.Client(api_key=key)


def generate(q: str, hits: list):
    client = _llm()
    if client is None:
        return None
    ctx = "\n\n".join(f"[{i + 1}] ({h['title']}; as of {h['as_of']})\n{h['text'][:1500]}" for i, h in enumerate(hits))
    prompt = f"{SYSTEM_PROMPT}\nCONTEXT:\n{ctx}\n\nQUESTION: {q}"
    try:
        resp = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        out = (resp.text or "").strip()
    except Exception:
        return None
    if not out or out.startswith("NOT_FOUND"):
        return ("NOT_FOUND", None)
    m = re.search(r"SOURCE:\s*\[?(\d+)", out)
    idx = int(m.group(1)) - 1 if m else 0
    body = re.sub(r"\n?SOURCE:.*$", "", out, flags=re.S).strip()
    body = re.sub(r"https?://\S+", "", body).strip()
    return (body, hits[min(max(idx, 0), len(hits) - 1)])


def _limit_sentences(text: str, n: int = 3) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


class Assistant:
    def __init__(self):
        self.retriever = Retriever()

    def ask(self, q: str) -> Answer:
        q = (q or "").strip()
        if not q:
            return Answer("Please type a question about a PPFAS scheme.", EDU_LINK, "", "unknown")
        blocked = check_guardrails(q)
        if blocked:
            return blocked
        hits, schemes, fact = self.retriever.search(q)
        general_facts = ("capital gains statement", "account statement", "elss tax benefit")

        # A scheme-specific fact with no scheme named: ask, don't guess.
        if fact and not schemes and fact not in general_facts:
            return Answer(
                "Which scheme do you mean? I cover Parag Parikh Flexi Cap Fund, ELSS Tax Saver Fund and Large Cap Fund. "
                f"For example: 'What is the {fact} of Parag Parikh Flexi Cap Fund?'",
                "https://amc.ppfas.com/downloads/kim-sid-and-sai/", "", "clarify", hits)

        gen = generate(q, hits)
        if gen and gen[0] != "NOT_FOUND":
            body, src = gen
            return Answer(_limit_sentences(body), src["url"], src["as_of"], "answer", hits)

        # No LLM (or LLM found nothing): use a verified fact card that matches the fact asked.
        if fact:
            cards = [f for f in self.retriever.facts if f["fact"] == fact
                     and (f["scheme"] in schemes or f["scheme"] == "All schemes")]
            if len(cards) > 1:
                # several schemes named: one sentence each, same fact (no ranking or opinion)
                text = " ".join(re.split(r"(?<=[.!?])\s+", c["answer"])[0] for c in cards[:3])
                return Answer(text, cards[0]["url"], cards[0]["as_of"], "answer", hits)
            if cards:
                c = cards[0]
                return Answer(_limit_sentences(c["answer"]), c["url"], c["as_of"], "answer", hits)
        return Answer(
            "I couldn't find that in my verified facts. I cover expense ratio, exit load, minimum SIP, lock-in, riskometer, "
            "benchmark and statements for three PPFAS schemes. The scheme documents linked here have full details.",
            "https://amc.ppfas.com/downloads/kim-sid-and-sai/", "", "unknown", hits)
