# WW.CX Records Retention Schedule

**Status:** Baseline internal schedule
**Owner:** Christmas Island Worldwide
**Review cycle:** Annual and after material legal, operational, or organizational change

This schedule assigns default retention periods to records associated with Edge1, Big Bird, WW.CX, the Private Library, public documentation, and related infrastructure work. A legal hold, investigation, contract, law, or regulatory requirement overrides every period below.

## Retention rules

| Record class | Examples | Retention | Trigger | Final disposition |
|---|---|---:|---|---|
| Governing records | policies, standards, approvals, ownership records, major architecture decisions | Permanent | creation or supersession | preserve permanently |
| Project and architecture records | ADRs, project registers, completion records, major design documentation | Permanent | project closure or supersession | preserve permanently |
| Source code and release records | tagged releases, release notes, build manifests, dependency locks | Permanent for significant releases; 7 years for superseded working branches | release or branch closure | preserve release; review working material |
| Security and access records | access reviews, incident records, vulnerability remediation evidence | 7 years | incident closure or review date | secure destruction after review |
| Audit and operational logs | service audit logs, administrative event records, deployment evidence | 3 years unless incident-related | event date | secure destruction after review |
| Change and deployment records | pull requests, approvals, deployment plans, rollback evidence | 7 years | implementation or cancellation | secure destruction or permanent preservation when historically significant |
| Contracts and partnership records | agreements, statements of work, material correspondence | 7 years after expiry or termination | contract end | secure destruction after legal review |
| Financial and timekeeping records | time entries, invoices, payroll-supporting records, reconciliations | 7 years | fiscal-year close | secure destruction after review |
| Personnel and authorization records | role assignments, authorization statements, training acknowledgements | 7 years after separation or supersession | separation or supersession | secure destruction |
| Routine correspondence | non-substantive coordination and scheduling | 2 years | message date | destroy when no longer needed |
| Convenience copies and transitory material | duplicates, temporary exports, scratch files, regenerated artifacts | until purpose is complete, normally no more than 90 days | creation | destroy promptly |
| Archival packages and preservation evidence | manifests, checksums, transfer receipts, fixity reports, preservation-event logs | Permanent | package creation | preserve permanently |

## Holds and suspension of disposition

When litigation, audit, investigation, public-record request, security incident, contractual dispute, or other preservation duty is reasonably anticipated:

1. suspend deletion for the affected record classes;
2. document the scope, authority, start date, and custodian of the hold;
3. preserve relevant versions, metadata, and audit history;
4. release the hold only through documented authorization;
5. restart the retention clock only when the release specifies that it is appropriate.

## Disposition approval

No official record may be destroyed solely because its nominal retention period elapsed. The records custodian must confirm that:

- the retention trigger and period are correct;
- no hold or unresolved business need applies;
- required archival transfer has occurred;
- destruction is secure and proportionate to sensitivity;
- a disposition certificate records what was destroyed, when, by whom, under which authority, and by what method.

## Review note

This schedule is an internal governance baseline and must be reconciled with applicable jurisdictional, contractual, tax, employment, privacy, and litigation requirements before being treated as legal advice or a definitive statutory schedule.
