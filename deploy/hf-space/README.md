---
title: DocuLens API
emoji: 📄
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: API for DocuLens, a contract and terms risk analyzer
---

# DocuLens API

Backend for [DocuLens](https://github.com/agr-arsh-15/doculens), which analyses contracts, offer letters,
terms of service and privacy policies for risky, hidden and missing clauses, with every market standard linked
to a trusted source.

This Space only serves the API used by the web app; it has no user interface of its own. The code is synced
automatically from the `backend/` folder of the GitHub repository. Secrets (database, Supabase and Groq keys)
are stored as Space secrets and are never part of the code.
