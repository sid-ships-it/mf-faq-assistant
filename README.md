# Facts-Only MF Assistant (Groww context, PPFAS Mutual Fund)

A small RAG chatbot that answers **factual** questions about three mutual fund schemes, using only official AMC, SEBI and AMFI pages. Every answer carries one source link and a "Last updated from sources" date. It refuses advice, does not compute or compare returns, and blocks personal data.

**Product context:** Groww. Groww users comparing schemes, and Groww's support and content teams, field the same factual questions every day (expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, statements). This assistant answers them from primary sources instead of third-party blogs.

## Scope

- **AMC:** PPFAS Mutual Fund (Parag Parikh)
- **Schemes (3):**
  - Parag Parikh Large Cap Fund (large cap)
  - Parag Parikh Flexi Cap Fund (flexi cap)
  - Parag Parikh ELSS Tax Saver Fund (ELSS)
- **Corpus:** 24 public pages and documents from PPFAS AMC, AMFI (Mutual Funds Sahi Hai) and SEBI: scheme pages, KIMs, SIDs, the factsheet, the TER disclosure, statement pages, the tax reckoner and investor education pages.
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
2. Retrieve    -> TF-IDF search over 21 verified fact cards + ~1,500 chunks of the 24 sources
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
| `sources.csv` | The 24 source URLs |
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

| # | Publisher | Type | Scheme | Document | URL |
|---|---|---|---|---|---|
| 1 | PPFAS AMC | Scheme page | Parag Parikh Flexi Cap Fund | Parag Parikh Flexi Cap Fund - scheme page | https://amc.ppfas.com/schemes/parag-parikh-flexi-cap-fund/ |
| 2 | PPFAS AMC | Scheme page | Parag Parikh ELSS Tax Saver Fund | Parag Parikh ELSS Tax Saver Fund - scheme page | https://amc.ppfas.com/schemes/parag-parikh-elss-tax-saver-fund/ |
| 3 | PPFAS AMC | Scheme page | Parag Parikh Large Cap Fund | Parag Parikh Large Cap Fund - scheme page | https://amc.ppfas.com/schemes/parag-parikh-large-cap-fund/ |
| 4 | PPFAS AMC | KIM | Parag Parikh Flexi Cap Fund | Key Information Memorandum - Flexi Cap Fund | https://amc.ppfas.com/downloads/parag-parikh-flexi-cap-fund/KIM_PPFCF.pdf |
| 5 | PPFAS AMC | KIM | Parag Parikh ELSS Tax Saver Fund | Key Information Memorandum - ELSS Tax Saver Fund | https://amc.ppfas.com/downloads/parag-parikh-tax-saver-fund/kim-parag-parikh-tax-saver-fund.pdf |
| 6 | PPFAS AMC | KIM | Parag Parikh Large Cap Fund | Key Information Memorandum - Large Cap Fund | https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/kim-parag-parikh-large-cap-fund.pdf |
| 7 | PPFAS AMC | SID | Parag Parikh Flexi Cap Fund | Scheme Information Document - Flexi Cap Fund | https://amc.ppfas.com/downloads/parag-parikh-flexi-cap-fund/SID_PPFCF.pdf |
| 8 | PPFAS AMC | SID | Parag Parikh ELSS Tax Saver Fund | Scheme Information Document - ELSS Tax Saver Fund | https://amc.ppfas.com/downloads/parag-parikh-tax-saver-fund/sid-parag-parikh-tax-saver-fund.pdf |
| 9 | PPFAS AMC | SID | Parag Parikh Large Cap Fund | Scheme Information Document - Large Cap Fund | https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/sid-parag-parikh-large-cap-fund.pdf |
| 10 | PPFAS AMC | Factsheet | All schemes | PPFAS MF Factsheet - August 2026 | https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-August-2026.pdf |
| 11 | PPFAS AMC | Documents index | All schemes | KIM / SID / SAI downloads page | https://amc.ppfas.com/downloads/kim-sid-and-sai/ |
| 12 | PPFAS AMC | Fees and charges | All schemes | Total Expense Ratio (TER) disclosures | https://amc.ppfas.com/statutory-disclosures/total-expense-ratio-TER/ |
| 13 | PPFAS AMC | Statements and services | All schemes | PPFAS MF home (account statement and capital gains statement links) | https://amc.ppfas.com/ |
| 14 | PPFAS AMC | Statements and services | All schemes | PPFAS MF Investor Desk | https://amc.ppfas.com/investor-desk/ |
| 15 | PPFAS AMC | Statements and services | All schemes | Account statement via missed call | https://amc.ppfas.com/investor-desk/statement-via-missed-call/ |
| 16 | PPFAS AMC | Tax guide | All schemes | Tax Reckoner 2026-27 | https://amc.ppfas.com/schemes/Tax_Reckoner_2026-27.pdf |
| 17 | PPFAS AMC | Investor education | All schemes | Systematic Investment Plan explainer | https://amc.ppfas.com/knowledge-center/systematic-investment-plan/ |
| 18 | AMFI (Mutual Funds Sahi Hai) | Investor education | All schemes | ELSS funds explained | https://www.mutualfundssahihai.com/en/elss-fund-tax-saving-mutual-fund |
| 19 | AMFI (Mutual Funds Sahi Hai) | Investor education | All schemes | Costs when redeeming (exit load) | https://www.mutualfundssahihai.com/en/what-costs-does-one-incur-while-redeeming-mutual-fund-units |
| 20 | AMFI (Mutual Funds Sahi Hai) | Investor education | All schemes | SIP and how it works | https://www.mutualfundssahihai.com/en/sip-and-how-it-works |
| 21 | AMFI (Mutual Funds Sahi Hai) | Investor education | All schemes | Types of mutual funds | https://www.mutualfundssahihai.com/en/what-are-various-types-mutual-funds |
| 22 | AMFI (Mutual Funds Sahi Hai) | Investor education | All schemes | Mutual fund glossary | https://www.mutualfundssahihai.com/en/glossary |
| 23 | SEBI | Investor education | All schemes | SEBI investor page - mutual fund investments | https://investor.sebi.gov.in/securities-mf-investments.html |
| 24 | SEBI | Statements and services | All schemes | SEBI - Consolidated Account Statement (CAS) | https://investor.sebi.gov.in/consolidated_account_statement.html |

## Sample Q&A
Generated by running `python make_samples.py` against the assistant. Types: answer = factual reply, refusal = advice question declined, performance = returns question redirected to the factsheet, pii = personal details blocked, clarify = scheme not named.

**1. What is the expense ratio of Parag Parikh Flexi Cap Fund?**

> The Total Expense Ratio (TER) of Parag Parikh Flexi Cap Fund is 1.30% for the Regular Plan and 0.69% for the Direct Plan, as disclosed for 30 Sep 2026. TER can change daily, so check the AMC's TER page for the current figure.
>
> Source: https://amc.ppfas.com/statutory-disclosures/total-expense-ratio-TER/
>
> Last updated from sources: 30 Sep 2026

_Type: answer_

**2. What is the exit load of the Flexi Cap Fund?**

> For each purchase, 10% of the units can be redeemed without exit load. Units above that limit carry a 2% exit load if redeemed within 365 days and 1% if redeemed after 365 days but within 730 days. There is no exit load after 730 days.
>
> Source: https://amc.ppfas.com/schemes/parag-parikh-flexi-cap-fund/
>
> Last updated from sources: 02 Oct 2026

_Type: answer_

**3. What is the minimum SIP for Parag Parikh Large Cap Fund?**

> The minimum monthly SIP in Parag Parikh Large Cap Fund is Rs 1,000 and the minimum quarterly SIP is Rs 3,000. The minimum lump-sum purchase is Rs 1,000.
>
> Source: https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/kim-parag-parikh-large-cap-fund.pdf
>
> Last updated from sources: 10 Dec 2025 (KIM date)

_Type: answer_

**4. What is the lock-in period of the ELSS Tax Saver Fund?**

> Parag Parikh ELSS Tax Saver Fund has a statutory lock-in of 3 years (as stated in its Key Information Memorandum). The scheme also offers a tax benefit under Section 80C.
>
> Source: https://amc.ppfas.com/downloads/parag-parikh-tax-saver-fund/kim-parag-parikh-tax-saver-fund.pdf
>
> Last updated from sources: 27 Nov 2025 (KIM date)

_Type: answer_

**5. What is the riskometer rating and benchmark of the Large Cap Fund?**

> Parag Parikh Large Cap Fund is rated Very High risk on the riskometer. Its benchmark, the Nifty 100 TRI, is also rated Very High risk.
>
> Source: https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/kim-parag-parikh-large-cap-fund.pdf
>
> Last updated from sources: 10 Dec 2025 (KIM date)

_Type: answer_

**6. How do I download my capital gains statement?**

> On the PPFAS Mutual Fund website, use the 'Capital Gains Statement' link on the home page. It takes you to the request page of CAMS, the fund's registrar, where you can request the statement.
>
> Source: https://amc.ppfas.com/
>
> Last updated from sources: 02 Oct 2026

_Type: answer_

**7. Should I buy Parag Parikh Flexi Cap Fund now?**

> I can only share facts about mutual fund schemes, so I can't say whether you should buy, sell or choose a fund. For decisions based on your goals, please consult a SEBI-registered investment adviser. You can learn how to evaluate schemes on AMFI's investor education site.
>
> Source: https://www.mutualfundssahihai.com/en/what-is-a-mutual-fund

_Type: refusal_

**8. What were the 5-year returns of the ELSS fund?**

> I don't calculate or compare returns. The latest official performance figures for PPFAS schemes are in the monthly factsheet. Past performance is not an indicator of future results.
>
> Source: https://amc.ppfas.com/downloads/factsheet/

_Type: performance_

**9. My PAN is ABCDE1234F, can you check my folio?**

> For your safety I can't accept personal details like a PAN. Please remove it and ask your question again. I only answer general facts about mutual fund schemes.
>
> Source: https://investor.sebi.gov.in/securities-mf-investments.html

_Type: pii_

**10. What is the expense ratio?**

> Which scheme do you mean? I cover Parag Parikh Flexi Cap Fund, ELSS Tax Saver Fund and Large Cap Fund. For example: 'What is the expense ratio of Parag Parikh Flexi Cap Fund?'
>
> Source: https://amc.ppfas.com/downloads/kim-sid-and-sai/

_Type: clarify_

