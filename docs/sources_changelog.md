# Sources changelog (playbook version 2026.10.29)

Every market standard and benchmark range shown in DocuLens now links to at least one trusted source in
[`backend/app/playbooks/sources.yaml`](../backend/app/playbooks/sources.yaml). Allowed sources, in order of preference:

1. **Official** - statutes, regulators and courts (EUR-Lex, EDPB, legislation.gov.uk, GOV.UK, ICO, California
   Legislative Information, the FTC, India Code, MeitY, the Ministry of Labour, RBI, CERT-In, the Supreme Court of India).
2. **Professional** - recognised professional and standards bodies (ISO, AICPA, SHRM, the American Bar Association,
   the American Arbitration Association, Cornell LII).
3. **Law firm** - published guidance from established firms (Norton Rose Fulbright, Mayer Brown, Littler, Khaitan & Co,
   Nishith Desai Associates, DLA Piper, JSA, Seyfarth Shaw and others).
4. **News** - major business news, used only for market-practice numbers (The Economic Times, The Times of India).

Where a source disagreed with the previous value, the value was changed to match the source. Where no allowed source
could be found, the claim or range was removed. All playbook versions were raised, so cached analyses are recomputed.

## Values corrected to match a source

| Playbook | Item | Before | After | Source |
| --- | --- | --- | --- | --- |
| Offer letter | Service / training bond | "Lump-sum penalties unrelated to actual cost are typically struck down" | Minimum-service bonds operating during employment are valid if reasonable; only reasonable compensation up to the stated amount is recoverable | Supreme Court of India, *Vijaya Bank v Narnaware* (2025); Indian Contract Act s.74 |
| Offer letter, Employment | Notice period, India | typical 60 days | typical 90 days (range 30-90 unchanged) | The Times of India; The Economic Times |
| Offer letter, Employment | Non-compete, UK | up to 6 months, typical 3 | up to 12 months, typical 6 | Mayer Brown; Littler |
| Offer letter | Non-solicit, India | up to 12 months (all jurisdictions) | up to 24 months | Khaitan & Co |
| Offer letter | Non-solicit, UK | up to 12 months, typical 12 | up to 12 months, typical 6 | Littler |
| NDA | Indemnification | "Most NDAs contain no indemnity" | Remedies usually include an injunction and indemnification for losses caused by a breach | Moritt Hock & Hamroff |
| NDA | Definition | Oral disclosures confirmed in writing within 30 days | Marked, or reasonably understood to be confidential | Moritt Hock & Hamroff; American Bar Association |
| MSA / SaaS | Liability cap | "Super-cap (2-3x) for data breach" stated as standard | A separate data-liability cap appears in only about 1 in 5 contracts; confidentiality usually uncapped | Norton Rose Fulbright global benchmark |
| MSA / SaaS | IP indemnity | "Indemnities sit outside the general cap" | Vendor IP-infringement indemnity is uncapped in 78% of technology contracts | Norton Rose Fulbright global benchmark |
| Generic contract | Indemnity | "Mutual, fault-based and capped" | Limited to losses the indemnifying party causes; contract should say whether indemnities sit inside the cap | Norton Rose Fulbright global benchmark |
| Generic contract | Payment | Late interest "1-1.5% per month" | Statutory late interest (EU reference rate + 8 points; UK 8% above base); India 45-day limit for micro and small suppliers | EU Directive 2011/7/EU; UK Late Payment Act 1998; MSMED Act s.15 |
| Generic contract, MSA | Termination cure period | "15-30 day" / "30-day" cure period | Written notice and a reasonable opportunity to cure | Faegre Drinker |
| Privacy policy | Rights response time | "within 30 days" | One month (EU and UK), 45 days (CCPA) | GDPR Arts. 12-22; ICO; California AG |
| Terms of service | Warranty disclaimers | Statutory guarantees cannot be excluded in "the EU, UK, Australia or India" | UK (CRA 2015 s.31), EU, and Indian consumer complaints for deficient service (Australia removed: no source collected) | Consumer Rights Act 2015; Directive 93/13/EEC; Consumer Protection Act 2019 |
| DPA | Breach notice, India | Separate India range of up to 24 hours, typical 6 (CERT-In) | Removed - CERT-In's 6 hours is the deadline for reporting to CERT-In, not processor-to-controller notice; now stated in the text instead | CERT-In Directions 2022; DPDP Rules 2025 |

## Ranges now shown only where a source covers the jurisdiction

Before, each benchmark had one default range used for every country. Now a range is shown only for the
jurisdictions a source covers; for other jurisdictions the clause is still analysed, but no market slider is shown.

| Benchmark | Jurisdictions with a sourced range |
| --- | --- |
| Probation length | India (L&E Global, JSA), US (SHRM) |
| Resignation / notice period | India (Economic Times, Times of India), US (SHRM) |
| Non-compete duration | India (s.27, Khaitan), UK (Mayer Brown, Littler), US (Seyfarth, ABA) |
| Non-solicit duration | India (Khaitan), UK (Littler) |
| SaaS liability cap | All (Norton Rose Fulbright) |
| SaaS payment terms | All (EU Late Payment Directive) |
| SaaS / DPA breach notice | All (GDPR, EDPB, Fox Rothschild) |
| NDA confidentiality duration | All (Moritt Hock & Hamroff) |

## Test expectations updated to match the sources

| Gold file | Change | Reason |
| --- | --- | --- |
| `hr_offer_letter.yaml` (US) | The 24-month non-solicit is now an acceptable finding, not a required one, and its "above market" benchmark expectation was removed | Several US states presume non-solicits of 18-24 months reasonable (Seyfarth 50-state guide), so there is no sourced US non-solicit range |
| `saas_msa.yaml` | Uptime and non-renewal-window benchmark expectations removed | Those benchmarks were removed (no trusted source for a numeric range) |

## Removed because no allowed source was found

| Playbook | Item removed |
| --- | --- |
| MSA / SaaS | Uptime benchmark (99.5-99.99%) - the SLA standard now describes measurement, maintenance windows and remedies instead |
| MSA / SaaS | Non-renewal notice window benchmark (0-60 days) |
| MSA / SaaS | "Renewal price increases capped at CPI or 5-7%" |
| MSA / SaaS | Warranty market standard ("conformity-to-documentation warranty") |
| DPA | Deletion-after-termination benchmark (0-90 days) and "30-90 days" in the text |
| DPA | "Annual penetration tests", "quarterly access reviews", "5-10 days" for data-subject requests |
| Privacy policy | "Deletion within 30-90 days of account closure" |
| Terms of service | "30-day arbitration opt-out window", "data export window of 30 days or more", "greater of 12 months' fees" liability floor |
| Offer letter | Transfer and relocation market standard |
| Employment | "Side work allowed if non-competing and disclosed" |
