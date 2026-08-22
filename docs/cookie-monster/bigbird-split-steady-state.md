# Big Bird -> Cookie Monster responsibility split

## Big Bird steady-state responsibility

Big Bird remains the human/operations orchestration plane for bounded tools and live infrastructure views. Keep these domains with Big Bird/Edge1 operations rather than turning Cookie Monster into a second operations platform:

- Edge1 status and infrastructure control surfaces;
- telephony and numbering operations;
- messaging and Mail Room operational workflows;
- security/authentication boundaries;
- time authority and network/service health;
- bounded draft/orchestration actions;
- human-facing routing to specialist subsystems.

## Cookie Monster responsibility

Move or build data-heavy research/ingestion work here:

- archive intake and content hashing;
- document/media metadata extraction;
- OCR/document enrichment handoff;
- web capture handoff;
- exact duplicate grouping;
- provenance and derivation chains;
- research-source normalization;
- bibliographic/external archive connectors;
- knowledge synthesis and human review queues;
- reproducible dataset-oriented batch work delegated to Fengus.

## Fengus responsibility

Fengus is execution muscle, not authority. It receives bounded data-only work items, has no archive credentials, no arbitrary path/URL/command fields, no network in the hardened worker unit, and no direct authority to approve or publish knowledge.

## Retirement rule

A Big Bird ingestion/research component can be retired only after:

1. its consumers are identified;
2. Cookie Monster replacement behavior is source-tested;
3. provenance/history is preserved;
4. operational UI exists for the replacement;
5. rollback is documented;
6. live acceptance proves no missing consumer;
7. the old component is archived/disabled rather than destructively deleted on first cutover.

Do not retire communications, telephony, messaging, security or infrastructure services merely because they produce data; their operational control remains a Big Bird/Edge1 responsibility.
