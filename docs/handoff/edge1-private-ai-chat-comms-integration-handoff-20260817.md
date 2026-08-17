# Edge1 Private AI Chat / Communications Relay Integration Handoff

Date: 2026-08-17  
System: `edge1.ww.cx`  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Classification: sanitized engineering handoff

## Objective

Update the private AI Chat bot that runs on Edge1 so it can become a useful read-only intelligence layer over the accepted WW.CX Communications Relay and its durable project documentation.

The first implementation phase must preserve the current security boundary:

- no public exposure changes;
- no direct NNTP listener exposure;
- no upstream posting;
- no relay/database mutation;
- no credential access or credential-content indexing;
- no raw sealed-evidence ingestion into ordinary chat retrieval;
- no service restart, authentication-policy change, DNS/firewall/certificate change, or other privileged mutation merely to enable AI retrieval.

The desired result is a private chat assistant that can answer questions from authoritative WW.CX documentation and locally stored NNTP/relay data while showing provenance and remaining operationally read-only.

## Completed

The Communications Relay / selective Eternal September ingestion / private News Reader project is complete and archived.

Accepted relay state:

- IRC: `127.0.0.1:16667`;
- NNTP: `127.0.0.1:1119`;
- control/API/News Reader: `127.0.0.1:8100`;
- service: `edge1-comms-relay.service`;
- health: accepted `status=ok`, version `1.0.0`;
- network exposure disabled;
- control/API mutations blocked with HTTP 405;
- upstream posting, inbound feeds and formal peering disabled.

Accepted News Reader production checkout:

```text
branch: deploy/private-nntp-news-reader-v2-20260817
head: 974c7141e18deac92671f81fb1bd3c3ed02a6c68
result: NEWS_READER_V2_DEPLOYMENT=PASS
```

Accepted reader capabilities include group browsing, bounded search, exact source filters, pagination, article detail/provenance, raw stored headers, and threaded/flat views using stored reference ancestry.

The protected Communications Relay archive is sealed at:

```text
/var/lib/wwcx-deployment-evidence/comms-relay/archive-seal-20260817T023340Z
```

Archive package manifest SHA-256:

```text
e218e3939ef823d2b36f7a413fb78fad836879bbffd958824254c421008eb3b8
```

Repository seal/current-state reconciliation was completed through PRs #346 and #347.

## Current verified state

The Communications Relay itself does not need modification for the first AI integration phase.

The current repository contains the authoritative sanitized documentation required for retrieval:

- `docs/communications/README.md`;
- `docs/communications/edge1-comms-relay-architecture.md`;
- `docs/communications/edge1-comms-relay-ingestion.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp.md`;
- `docs/communications/edge1-comms-relay-upstream-nntp-validation.md`;
- `docs/communications/edge1-comms-relay-news-reader.md`;
- `docs/handoff/edge1-comms-relay-runbook.md`;
- dated Communications Relay acceptance records;
- `.agent/comms-relay.md`;
- `.agent/comms-relay-upstream-nntp.md`;
- `.agent/current-state.md`;
- `.agent/validation.md`;
- `docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`;
- `docs/archive/edge1-comms-relay-archive-seal-20260817.md`.

The private Edge1 AI Chat bot implementation, service name, repository/path, API, model backend, storage, authentication boundary and current permissions were **not identified in `edge1-management-interface` during this handoff preparation**. Do not invent these details. The next agent must discover them from Edge1 using read-only inspection before designing adapters or changing code.

## Material changes

No AI Chat runtime change has been made by this handoff.

The target design is:

```text
Private user
   |
   v
Edge1 AI Chat
   |
   +--> Sanitized WW.CX documentation retrieval / RAG
   |
   +--> Read-only Communications Relay adapter
           |
           +--> http://127.0.0.1:8100/api/comms/...
           +--> locally stored NNTP article summaries/details/provenance
           +--> relay/source/health state
```

### Capability 1 — authoritative documentation RAG

Index only appropriate sanitized documentation and durable `.agent` state.

The bot should be able to answer questions such as:

- What is the accepted production checkout?
- Why are there nine articles in an imported group when only eight came from Eternal September?
- What safety boundary applies before exposing NNTP publicly?
- What validation is required after restarting the relay?
- What is the archive status and manifest hash?

Answers should cite repository path and, where feasible, section/heading or commit provenance.

Normal RAG should **exclude**:

- `/etc/wwcx/credentials/eternal-september.json`;
- credential values, private keys, tokens or cookies;
- raw `/var/lib/wwcx-comms/comms.sqlite3` as a general document corpus;
- raw protected evidence under `/var/lib/wwcx-deployment-evidence/...`;
- password hashes, authentication transcripts or private account material.

The sanitized archive seal/closeout documents may be indexed because they contain no credential contents.

### Capability 2 — read-only Communications Relay tool

Prefer the existing loopback HTTP control/News Reader API rather than giving the bot direct SQLite access.

The adapter should support bounded operations such as:

- list newsgroups;
- list configured/readable ingestion sources;
- list/search articles for one group;
- fetch one article detail;
- filter by exact `source_name`;
- paginate using bounded `limit`/`offset`;
- retrieve thread/reference metadata;
- retrieve relay health/source status.

Do not add a write-capable endpoint merely for the bot.

### Capability 3 — NNTP/thread intelligence

Add AI-level functions on top of the read-only article API:

- summarize one article;
- summarize one thread using real reference ancestry;
- identify unresolved questions in a thread;
- compare two threads or two source groups;
- explain unfamiliar technical terms in context;
- produce a concise `what matters here` briefing;
- report which statements came from which group/article/source.

Provenance should retain at least:

- local group;
- local article ID;
- Message-ID when available;
- `source_name`;
- upstream group/server/message/article metadata when present;
- relevant thread ancestry.

Do not use subject-line similarity as a substitute for reference-based thread provenance when real references exist.

### Capability 4 — operations explainer

The bot may read and explain current operational state, for example:

- service health;
- configured source status/cursors;
- listener posture from an approved read-only status adapter;
- audit summaries that are already safe to expose internally;
- why `Type=simple` systemd active state does not prove application readiness;
- why provenance-aware article counts differ from raw group totals.

The first phase should **diagnose/explain only**. It should not restart services, apply configs, alter accounts, change listeners, modify firewall/DNS/certificates, rotate credentials, post articles or originate production traffic.

### Capability 5 — provenance-first answers

Every answer generated from relay/news data should be able to expose a compact source trail.

Preferred response metadata model:

```json
{
  "sources": [
    {
      "kind": "relay_article",
      "group": "usenet.comp.lang.python",
      "article_id": 123,
      "message_id": "<...>",
      "source_name": "eternal.comp.lang.python"
    },
    {
      "kind": "repo_document",
      "path": "docs/communications/edge1-comms-relay-news-reader.md",
      "section": "..."
    }
  ]
}
```

Exact schema can follow the bot's existing framework after discovery.

## Commits and pull requests

Communications Relay milestones relevant to this integration:

- PR #341 — integrate exact validated News Reader blobs;
- PR #342 — durable Communications Relay state;
- PR #344 — comprehensive documentation/archive preparation;
- PR #345 — documentation closeout merge point;
- PR #346 — final protected archive seal;
- PR #347 — repository-wide sealed-state reconciliation.

This handoff is intentionally independent of the accepted live News Reader checkout. Do not move production to remote `main` merely to begin AI Chat discovery.

## Validation evidence

The underlying Communications Relay/News Reader has already passed:

- production readiness validation;
- controlled ingestion regression;
- upstream NNTP TLS validation;
- config-control metadata validation;
- News Reader threaded pagination/source-filter validation;
- JavaScript syntax validation;
- loopback listener validation;
- HTTP 405 mutation enforcement;
- exact source filtering;
- provenance/accounting checks;
- archive inventory idempotence;
- archive seal `ARCHIVE_SEAL_GATE=PASS`.

The AI integration requires its own new tests. Minimum first-phase acceptance:

1. bot/service implementation identity is documented from live inspection;
2. documentation retrieval returns only allowlisted sanitized roots;
3. retrieval excludes credential/raw protected-evidence paths;
4. relay adapter can query health/groups/articles over loopback only;
5. adapter has no POST/PUT/PATCH/DELETE capability;
6. bounded search and pagination are enforced;
7. thread summary output preserves article/source provenance;
8. prompt-injection-like text inside article bodies cannot grant tool permissions or cause tool writes;
9. failure of the relay/API degrades the bot gracefully without retries that mutate state;
10. existing relay service, listeners, config and database remain unchanged;
11. targeted tests and repository CI pass;
12. any live activation is separately inspected and accepted.

## Blockers requiring approval

Stop for explicit approval before any design or deployment that requires:

- credential/token creation, disclosure or rotation;
- AI-provider secret changes;
- authentication/authorization policy changes;
- public network exposure;
- DNS, firewall or certificate changes;
- service restart if not already explicitly included in the approved implementation step;
- write access to Communications Relay/SQLite;
- article posting/deletion/moderation through the AI bot;
- ingestion of raw sealed evidence into normal RAG;
- access to unrelated private data stores;
- destructive cleanup or archive modification.

## Remaining safe work

### Phase 0 — discover the existing private AI Chat bot

Use authenticated read-only Edge1 inspection to identify:

- systemd service/process/container name;
- listening address/port and exposure posture;
- source repository and checkout/path;
- implementation language/framework;
- model/provider/backend, without displaying secrets;
- configuration locations, recording paths/keys but not secret values;
- data/chat/history storage location;
- authentication boundary;
- existing RAG/vector/search components;
- existing tool/plugin/function-calling framework;
- logging/audit behavior;
- current user identity/role model;
- deployment/restart/runbook and rollback mechanism.

Do not assume the bot is in `edge1-management-interface`; current repository search did not identify it.

### Phase 1 — design the minimum read-only adapter

After Phase 0, choose the smallest integration compatible with the bot's existing architecture.

Preferred order:

1. bot-side HTTP client/tool -> existing relay control API;
2. bot-side repository-document retriever -> allowlisted sanitized paths;
3. provenance wrapper shared by document and relay retrieval;
4. thread/article summarization prompts with untrusted-content isolation;
5. tests and local/offline fixtures;
6. guarded live read-only validation.

Avoid direct database coupling unless the existing bot architecture makes the HTTP API impossible; if direct DB access is ever considered, document why and preserve strict read-only permissions.

### Phase 2 — user-facing capabilities

Initial commands/intents may include:

- `Summarize the newest Python Usenet discussions.`
- `Show only Eternal September articles in news.admin.peering.`
- `Summarize this NNTP thread and show the source trail.`
- `What changed in the relay since yesterday?`
- `Why is the relay healthy but the reader not ready yet?`
- `What documentation governs this subsystem?`
- `What is safe to change next?`

### Phase 3 — possible later guarded action proposals

After a successful read-only phase, the bot may eventually prepare proposed diagnostics, candidate diffs or operator commands. It must not gain autonomous production mutation merely because it can formulate those commands.

Keep the control model:

**AI diagnoses and proposes; guarded operator tooling executes.**

## Exact continuation command or next action

Start a new engineering chat with this handoff and ask the agent to inspect the existing private AI Chat bot on Edge1 before changing anything.

Suggested first attended Edge1 read-only discovery block:

```bash
cd /opt/edge1-management-interface
printf '%s\n' '=== host ==='
hostname -f

printf '%s\n' '=== candidate services ==='
systemctl list-units --type=service --all --no-pager \
  | grep -Ei 'ai|chat|agent|assistant|llm|ollama|big.?bird' || true

printf '%s\n' '=== candidate listening processes ==='
sudo ss -ltnp \
  | grep -Ei 'python|node|gunicorn|uvicorn|ollama|llama|chat|agent' || true

printf '%s\n' '=== candidate processes ==='
ps -eo pid,user,comm,args \
  | grep -Ei 'ai|chat|agent|assistant|llm|ollama|llama|big.?bird' \
  | grep -v grep || true

printf '%s\n' '=== likely local project directories ==='
find /opt /srv /var/www /home/wwadmin \
  -maxdepth 3 -type d \
  \( -iname '*chat*' -o -iname '*agent*' -o -iname '*assistant*' -o -iname '*llm*' -o -iname '*big*bird*' \) \
  -print 2>/dev/null | sort -u
```

Do **not** print environment variables, credential files, token values, private keys or unredacted application configuration during discovery.

Once the implementation/service is identified, inspect its repository/state and build the smallest read-only Communications Relay + documentation retrieval integration from there.
