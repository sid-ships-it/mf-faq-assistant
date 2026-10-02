"""Assemble README.md from the template below plus sources.csv and sample_qa.md."""
import csv
from pathlib import Path

ROOT = Path(__file__).parent
rows = list(csv.DictReader(open(ROOT / "sources.csv")))
table = ["| # | Publisher | Type | Scheme | Document | URL |", "|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    table.append(f"| {i} | {r['publisher']} | {r['source_type']} | {r['scheme']} | {r['title']} | {r['url']} |")
samples = (ROOT / "sample_qa.md").read_text().split("\n", 2)[2]

README = f"""# Facts-Only MF Assistant (Groww context, PPFAS Mutual Fund)

A small RAG chatbot that answers **factual** questions about three mutual fund schemes, using only official AMC, SEBI and AMFI pages. Every answer carries one source link and a "Last updated from sources" date. It refuses advice, does not compute or compare returns, and blocks personal data.

**Product context:** Groww. Groww users comparing schemes, and Groww's support and content teams, field the same factual questions every day (expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, statements). This assistant answers them from primary sources instead of third-party blogs.

## Scope

- **AMC:** PPFAS Mutual Fund (Parag Parikh)
- **Schemes (3):**
  - Parag Parikh Large Cap Fund (large cap)
  - Parag Parikh Flexi Cap Fund (flexi cap)
  - Parag Parikh ELSS Tax Saver Fund (ELSS)
- **Corpus:** {len(rows)} public pages and documents from PPFAS AMC, AMFI (Mutual Funds Sahi Hai) and SEBI: scheme pages, KIMs, SIDs, the factsheet, the TER disclosure, statement pages, the tax reckoner and investor education pages.
- **Facts covered:** expense ratio (TER), exit load, minimum SIP and lump sum, lock-in, riskometer, benchmark, account statement, capital gains statement, ELSS Section 80C benefit.

## How it works

```
question
   |
   v
1. Guardrails  -> PII (PAN, Aadhaar, phone, email, OTP, account no.)  -> blocked, not stored
               -> advice ("should I buy", "best", "is it good")      -> polite refusal + AMFI education link
               -> performance ("returns", "CAGR", "NAV")             -> link to official factsheet
   |
   v
2. Retrieve    -> TF-IDF search over 21 verified fact cards + ~1,500 chunks of the {len(rows)} sources
                  (fact cards were checked by hand against the source document and are boosted)
   |
   v
3. Answer      -> Gemini writes <=3 sentences from the retrieved context only, picks one source
                  (if no API key is set, the matching verified fact card is returned as-is)
   |
   v
answer + one source link + "Last updated from sources: <date>"
```

If a scheme-specific question doesn't name a scheme ("What is the expense ratio?"), the assistant asks which scheme instead of guessing.

## Files

| File | What it is |
|---|---|
| `app.py` | Streamlit UI: welcome line, 3 example questions, facts-only note, chat |
| `assistant.py` | Guardrails, retrieval and answer generation |
| `ingest.py` | Downloads every URL in `sources.csv`, extracts text, builds `data/chunks.jsonl` |
| `data/facts.json` | 21 verified fact cards, each with its source URL and as-of date |
| `sources.csv` | The {len(rows)} source URLs |
| `sample_qa.md` | 10 sample questions with the assistant's answers |
| `make_samples.py` | Regenerates `sample_qa.md` |

## Setup

```bash
git clone <this repo>
cd mf_faq_assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# optional: rebuild the corpus from the live sources (data/ is already committed)
python ingest.py

# optional: enable LLM answers (free key from https://aistudio.google.com)
export GEMINI_API_KEY="your-key"

streamlit run app.py
```

**Streamlit Community Cloud:** deploy `app.py` from this repo and add `GEMINI_API_KEY = "your-key"` under the app's Settings > Secrets. Without a key the app still works, using the verified fact cards.

## Known limits

- **Three schemes only.** Questions about other PPFAS schemes or other AMCs get "couldn't find that".
- **Point-in-time figures.** TER is taken from the AMC's disclosure for 30 Sep 2026 and changes often; exit load, minimum SIP, riskometer and benchmark come from the KIMs dated Nov/Dec 2025. Re-run `ingest.py` and update `data/facts.json` to refresh.
- **Keyword retrieval.** TF-IDF is fine for a corpus this small but can miss heavily paraphrased questions. Embeddings would be the next step.
- **PDF tables.** Factsheet tables extract as jumbled text, which is why figures like TER come from verified fact cards rather than raw chunks.
- **Rule-based guardrails.** Advice and PII detection use patterns, so unusual phrasing can slip past. The LLM prompt is a second line of defence.
- **Capital gains statement** requests are handled by CAMS, the registrar. The assistant points to the PPFAS link that opens the CAMS page and does not process requests.
- **No personal data is stored.** Chat history lives only in the browser session; messages containing PII are hidden and never logged.

## Disclaimer (shown in the UI)

> **Facts-only. No investment advice.** This assistant shares factual information from official public documents only. It does not provide investment advice, recommendations or return comparisons. Mutual fund investments are subject to market risks; read all scheme-related documents carefully. Figures can change, so always confirm on the linked official page.

## Sources

{chr(10).join(table)}

## Sample Q&A
{samples}
"""
(ROOT / "README.md").write_text(README)
print("README.md written,", len(README.splitlines()), "lines")
