# DocuLens demo script (about 12 minutes)

All files below are in this folder; see `SOURCES.md` for where each one came from.

## Before the demo

1. **Start the app** from the project root:

   ```bash
   ./start.sh
   ```

   Open http://127.0.0.1:5173. The first start downloads the embedding model (about 130 MB), so do it once beforehand.

2. **Check Groq** (prints the model and remaining rate limit, never the key):

   ```bash
   cd backend && ../.venv/bin/python -m app.llm.check
   ```

   The free tier has a daily token budget of roughly 10-15 analyses. Avoid heavy testing on the day of the demo. Already-analyzed documents open instantly from History, because results are cached.

3. **Optional: start with an empty History.** Stop the app (Ctrl+C), then from the project root:

   ```bash
   rm -f backend/data/doculens.db && find backend/data/files -type f -delete
   ```

## Walkthrough

### 1. Upload a real offer letter (2 min)

- On the home page, drop `offer_letters/bark_cfo_offer_letter_2026.pdf`.
- DocuLens shows what it detected: **Offer letter**, **United States**, parties **Barkbox, Inc** (employer) and **Anya** (candidate). Point out that the type comes from embeddings plus keywords, confirmed by the LLM.
- Under "I am reading this as the", choose **Candidate / Employee**. Leave **AI clause reasoning** on, then click **Run X-Ray**.
- While it runs, the progress tracker shows each stage: mapping, rules, AI reasoning, hidden risks, benchmarks and scoring.

### 2. Read the X-ray report (3 min)

- **Scorecard:** the grade, category subscores, radar chart and the top three items to negotiate.
- **Document viewer:** sentences are highlighted by severity, and the heat strip on the side helps you navigate.
- **Findings rail tabs:**
  - *Hidden:* the sign-on bonus must be repaid if you resign within 12 months. The rule engine and the AI found it independently, and the card shows both sources. The letter also relies on an Exhibit A that is not attached.
  - *Risks:* BARK may change your title, duties and pay going forward, and may change or remove benefits.
  - *Missing:* expected clauses the letter does not contain, such as a notice period.
- Click any finding: it scrolls to the exact sentence. Every AI quote is verified against the source text; fabricated quotes are dropped.

### 3. Act on it (2 min)

- **Ask the document:** "What happens to my sign-on bonus if I resign?" The answer cites clause numbers you can click.
- **PDF report:** download a shareable report.
- **Change perspective:** re-run as **Employer / HR**. The same clauses now appear as favorable.

### 4. Compare two real offers (1 min)

- Upload `offer_letters/fortrea_interim_ceo_offer_letter_2025.pdf` and run it as the candidate.
- Open **History**, tick BARK and Fortrea, then **Compare selected**. The comparison aligns the two letters clause by clause, with a verdict per clause type.

### 5. Other document types (2 min)

Pick one or two:

| File | What to point out |
| --- | --- |
| `terms_of_service/reddit_user_agreement.pdf` | Perpetual licence to your content, use of content for AI training, termination for any reason. The page contains both the US and the EU agreement, and each issue is reported once, citing both places. |
| `employment_agreements/aeries_india_employment_terms_2022.pdf` | Indian jurisdiction: the 24-month non-compete is benchmarked against the Indian market range (the **Market** tab), and the AI flags a waiver of statutory benefits. |
| `data_processing/atlassian_data_processing_addendum.pdf` | DPA from the customer's side: a 72-hour breach notice versus the 24-48 hour market range, and conflicting notice periods. |
| `ndas/oneNDA_mutual_nda_v2.1.docx` | A control: a balanced standard NDA. DocuLens should find little or nothing, which shows it does not flag everything. |

### 6. NLP Lab (2 min)

From any report, open **NLP Lab**. It shows the classic pipeline on the same document: tokenization, POS tags and lemmas, TF-IDF keywords, n-grams, readability, named-entity and value extraction, TextRank summary and obligation mining.

## Talking points

- **Hybrid design.** Local NLP (segmentation, embeddings, playbook rules, hidden-risk detectors and benchmarks) always runs. The LLM adds reasoning on top, but every AI finding must quote the document verbatim or it is dropped.
- **Perspective-aware.** Each rule says whom it hurts, so the same clause is a risk for the candidate and favorable for the employer.
- **Privacy.** Emails, phone numbers and ID numbers are redacted before any AI call. Strict mode also hides names and amounts.
- **Evaluation.** A gold set with 100% precision and recall on internal test documents, CUAD clause alignment (macro F1 68%), and ToS;DR agreement (29 of 33 points). See the README.
- **Resilience.** If Groq's free-tier limit is reached, DocuLens rotates to fallback models. If they are exhausted too, it finishes with local rules and the report says so, with an estimate of when to retry.

## If something goes wrong

- **The report shows "Groq rate limit reached":** the analysis completed with local rules. Show it anyway, and turn **AI clause reasoning** off for further runs, or re-run later.
- **"No LLM key configured":** check that `.env` in the project root has `GROQ_API_KEY` and `LLM_PROVIDER=groq`, then restart.
- **The UI cannot reach the API:** make sure `backend/run.py` is running on port 8000 (`./start.sh` starts both).
