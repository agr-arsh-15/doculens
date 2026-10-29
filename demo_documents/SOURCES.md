# Demo documents: sources

Every file in this folder is a real, publicly available document, retrieved on 11 October 2026.
None of them were written for DocuLens and none are bundled into the app; upload them through the UI.

How they were captured:

- **SEC EDGAR exhibits** were downloaded as filed (HTML) and printed to PDF with headless Chromium. The text is unchanged.
- **Web policies** were printed to PDF from the live page with headless Chromium. Only the page's main content was kept, without site navigation and cookie banners.
- **oneNDA** is the publisher's own DOCX file, unmodified.

| File | Document | Source | Licence / status |
| --- | --- | --- | --- |
| `offer_letters/bark_cfo_offer_letter_2026.pdf` | BARK, Inc. offer letter to its Chief Financial Officer (July 2026), Exhibit 10.2 to Form 10-Q | [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1819574/000162828026054441/offerletter-anyahamill.htm) | Public SEC filing |
| `offer_letters/fortrea_interim_ceo_offer_letter_2025.pdf` | Fortrea Holdings offer letter to its interim CEO (May 2025), Exhibit 10.2 to Form 10-Q | [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1965040/000196504025000050/ftre-petermneupertofferlet.htm) | Public SEC filing |
| `employment_agreements/zoomcar_india_employment_agreement_2025.pdf` | Zoomcar India Pvt Ltd employment agreement with its General Counsel (Bengaluru, January 2025), Exhibit 99.1 to Form 8-K | [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1854275/000121390025002316/ea022719901ex99-1_zoomcar.htm) | Public SEC filing |
| `employment_agreements/aeries_india_employment_terms_2022.pdf` | Aeries Technology (ATG Business Solutions Pvt Ltd, India) letter revising an executive's employment terms, with CTC, notice and garden leave (June 2022), Exhibit 10.25 | [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1853044/000119312523207752/d479906dex1025.htm) | Public SEC filing |
| `employment_agreements/wella_executive_employment_agreement_2026.pdf` | Wella executive employment agreement (Switzerland, April 2026), Exhibit 10.25 to Form S-1 | [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/2125056/000162828026059572/exhibit1025-sx1.htm) | Public SEC filing |
| `ndas/hillevax_xoma_mutual_nda_2024.pdf` | HilleVax / XOMA mutual nondisclosure agreement (December 2024), Exhibit (d)(2) to Schedule TO | [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1888012/000119312525182241/d13490dex99d2.htm) | Public SEC filing |
| `ndas/oneNDA_mutual_nda_v2.1.docx` | oneNDA standard mutual NDA, version 2.1 (Word) | [oneNDA](https://www.onenda.org/download) ([file](https://storage.googleapis.com/lawinsider-public/assets/standards/onenda/oneNDA_v2.1.docx)) | CC BY 4.0 |
| `saas_contracts/gravity_bridgenet_saas_agreement.pdf` | Gravity Supply Chain Solutions SaaS agreement for PO-management software, Exhibit 10.14 | [SEC EDGAR](https://www.sec.gov/Archives/edgar/data/2084806/000149315226012919/ex10-14.htm) | Public SEC filing |
| `terms_of_service/spotify_terms_of_use.pdf` | Spotify Terms of Use (US, last updated 4 Sep 2026) | [spotify.com](https://www.spotify.com/us/legal/end-user-agreement/) | Public web page, © Spotify; used for non-commercial academic analysis |
| `terms_of_service/reddit_user_agreement.pdf` | Reddit User Agreement (effective 1 Jul 2026) | [redditinc.com](https://redditinc.com/policies/user-agreement) | Public web page, © Reddit; used for non-commercial academic analysis |
| `privacy_policies/dropbox_privacy_policy.pdf` | Dropbox Privacy Policy (effective 30 May 2025) | [dropbox.com](https://www.dropbox.com/privacy) | Public web page, © Dropbox; used for non-commercial academic analysis |
| `privacy_policies/zoom_privacy_statement.pdf` | Zoom Privacy Statement | [zoom.com](https://www.zoom.com/en/trust/privacy/privacy-statement/) | Public web page, © Zoom; used for non-commercial academic analysis |
| `data_processing/atlassian_data_processing_addendum.pdf` | Atlassian Data Processing Addendum (effective 17 Aug 2026), a vendor DPA with EU SCCs | [atlassian.com](https://www.atlassian.com/legal/data-processing-addendum) | Public web page, © Atlassian; used for non-commercial academic analysis |

SEC filings sometimes redact details with `[***]`. Those gaps are in the originals.

## Results (29 October 2026, playbook version 2026.10.29)

Local mode (rules + neural embeddings, no AI), default perspective (candidate/employee, user, receiving party or customer). Times are on a MacBook Air. Market benchmarks appear only where a trusted source gives a range for the detected jurisdiction (see `docs/sources_changelog.md`).

| File | Detected as | Clauses | Findings | Score | Time | Top issues |
| --- | --- | --- | --- | --- | --- | --- |
| `offer_letters/bark_cfo_offer_letter_2026.pdf` | Offer letter, US | 17 | 2 | 82 B | 1.9 s | Sign-on bonus repayment if you resign within 12 months; Exhibit A referenced but not attached |
| `offer_letters/fortrea_interim_ceo_offer_letter_2025.pdf` | Offer letter, US | 16 | 3 | 86 A | 1.2 s | No notice period; benefits and tax withholding at the company's sole discretion |
| `employment_agreements/zoomcar_india_employment_agreement_2025.pdf` | Employment agreement, India | 108 | 6 | 68 C | 6.5 s | IP assignment beyond employment duties; binding terms at a web link |
| `employment_agreements/aeries_india_employment_terms_2022.pdf` | Employment agreement, India | 146 | 8 | 60 C | 10.0 s | Repayment on exit; 24-month non-compete and 180-day notice (both outside the sourced Indian ranges) |
| `employment_agreements/wella_executive_employment_agreement_2026.pdf` | Employment agreement, global | 163 | 7 | 66 C | 12.2 s | Broad post-employment non-compete; policies "as amended from time to time" |
| `ndas/hillevax_xoma_mutual_nda_2024.pdf` | NDA, US | 16 | 2 | 88 A | 1.0 s | 6-year confidentiality term (above the 2-5 year range) |
| `ndas/oneNDA_mutual_nda_v2.1.docx` | NDA | 10 | 0 | 100 A | 0.6 s | None: a balanced standard template |
| `saas_contracts/gravity_bridgenet_saas_agreement.pdf` | SaaS / MSA, Singapore | 272 | 2 | 89 A | 15.2 s | Terms that change via documents "amended from time to time" |
| `terms_of_service/spotify_terms_of_use.pdf` | Terms of service, US | 88 | 13 | 46 D | 6.0 s | Perpetual licence to your content; termination at any time; mandatory arbitration and class-action waiver |
| `terms_of_service/reddit_user_agreement.pdf` | Terms of service, US | 53 | 11 | 52 D | 3.5 s | Perpetual licence to your content (US and EU versions reported once); termination for any reason; content used for AI training |
| `privacy_policies/dropbox_privacy_policy.pdf` | Privacy policy, US | 29 | 3 | 83 B | 2.1 s | Third-party trackers; sensitive data |
| `privacy_policies/zoom_privacy_statement.pdf` | Privacy policy, US | 75 | 3 | 83 B | 4.7 s | Third-party trackers; sensitive data; binding terms at a web link |
| `data_processing/atlassian_data_processing_addendum.pdf` | DPA / compliance, EU | 138 | 4 | 73 B | 6.8 s | 72-hour breach notice (sourced range up to 48 h); conflicting 30- vs 60-day notice periods |

Compared with the 12 October run, Wella (63 to 66) and Gravity (84 to 89) score higher because notice, non-compete, uptime and renewal ranges without a source for Switzerland or Singapore no longer apply.

Hybrid mode (Groq `openai/gpt-oss-120b` with `gpt-oss-20b` fallback) adds AI-reviewed findings with verified quotes, an AI summary and redlines. Short documents (offer letters, NDAs, Dropbox) take 10-40 seconds. Long agreements and policies take about 1-2 minutes and send only their highest-priority clauses to the AI, because the free tier allows about 8,000 tokens per minute per model. Hybrid scores are lower than local ones because the AI finds more issues. For example, BARK drops to about 55 (C) once the AI flags the unilateral right to change pay and duties.
