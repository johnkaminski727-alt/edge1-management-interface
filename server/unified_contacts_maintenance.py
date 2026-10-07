#!/usr/bin/env python3
"""Read-only Contacts maintenance/review model.

The maintenance state database is intentionally separate from canonical
Unified Contacts. This module joins display metadata for operator review but
never mutates either database.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class UnifiedContactsMaintenance:
    def __init__(
        self,
        maintenance_database: str | Path = "/var/lib/edge1-contacts-maintenance/maintenance.sqlite",
        contacts_database: str | Path = "/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite",
    ) -> None:
        self.maintenance_database = Path(maintenance_database)
        self.contacts_database = Path(contacts_database)

    def _open(self, path: Path) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    def _entity_names(self, ids: set[int]) -> dict[int, str]:
        if not ids:
            return {}
        con = self._open(self.contacts_database)
        try:
            placeholders = ",".join("?" for _ in ids)
            rows = con.execute(
                f"SELECT id,COALESCE(display_name,canonical_name) AS name "
                f"FROM contact_entities WHERE id IN ({placeholders})",
                tuple(sorted(ids)),
            ).fetchall()
            return {int(row["id"]): row["name"] for row in rows}
        finally:
            con.close()

    def summary(self) -> dict:
        con = self._open(self.maintenance_database)
        try:
            scalar = lambda sql: int(con.execute(sql).fetchone()[0])
            latest = con.execute(
                "SELECT id,started_at,finished_at,status,summary_json "
                "FROM maintenance_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return {
                "open_findings": scalar("SELECT COUNT(*) FROM maintenance_findings WHERE status='open'"),
                "pending_candidates": scalar("SELECT COUNT(*) FROM candidate_changes WHERE status='pending'"),
                "pending_enrichment": scalar("SELECT COUNT(*) FROM enrichment_queue WHERE status='pending'"),
                "pending_identity_resolution": scalar("SELECT COUNT(*) FROM identity_resolution_queue WHERE status='pending'"),
                "pending_discoveries": scalar("SELECT COUNT(*) FROM contact_discovery_queue WHERE status='pending'"),
                "review_required_findings": scalar("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND action_level='REVIEW_REQUIRED'"),
                "duplicate_risks": scalar("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND finding_type='duplicate_entity'"),
                "shared_contact_risks": scalar("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND finding_type='shared_contact_point'"),
                "missing_sources": scalar("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND finding_type='source_missing'"),
                "validation_issues": scalar("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND finding_type='validation_issue'"),
                "mail_review_candidates": scalar("SELECT COUNT(*) FROM maintenance_findings WHERE status='open' AND finding_type='mail_contact_candidate'"),
                "latest_run": dict(latest) if latest else None,
            }
        finally:
            con.close()

    def items(self, *, kind: str = "all", status: str = "pending", query: str = "", limit: int = 250, offset: int = 0) -> list[dict]:
        allowed_kinds = {"all", "identity", "discoveries", "findings", "enrichment", "candidates"}
        if kind not in allowed_kinds:
            raise ValueError("invalid maintenance kind")
        if status not in {"", "pending", "open", "resolved", "dismissed", "superseded", "matched_existing", "enriched", "distinct_identity", "review_required"}:
            raise ValueError("invalid maintenance status")
        if limit < 1 or limit > 250:
            raise ValueError("limit must be between 1 and 250")
        if offset < 0:
            raise ValueError("offset must be zero or greater")

        con = self._open(self.maintenance_database)
        try:
            rows: list[dict] = []
            if kind in {"all", "identity"}:
                clauses = []
                params: list[object] = []
                if status:
                    clauses.append("status=?")
                    params.append("pending" if status == "open" else status)
                if query:
                    clauses.append("(normalized_value LIKE ? OR COALESCE(proposed_entity_name,'') LIKE ? OR rationale LIKE ?)")
                    needle = f"%{query}%"
                    params.extend([needle, needle, needle])
                where = " WHERE " + " AND ".join(clauses) if clauses else ""
                for r in con.execute(
                    "SELECT id,contact_point_id,resolution_kind,normalized_value,status,rationale,"
                    "matched_entity_id,proposed_entity_name,confidence,evidence_json,created_at,updated_at "
                    "FROM identity_resolution_queue" + where + " ORDER BY updated_at DESC,id DESC",
                    params,
                ).fetchall():
                    item = dict(r)
                    item.update({"maintenance_kind": "identity", "maintenance_item_id": r["id"], "action_level": "REVIEW_REQUIRED" if r["status"] == "review_required" else "AUTO_STAGE"})
                    try:
                        evidence = json.loads(r["evidence_json"] or "{}")
                    except (TypeError, json.JSONDecodeError):
                        evidence = {}
                    if isinstance(evidence, dict):
                        occurrence_count = int(evidence.get("occurrence_count") or 0)
                        item["occurrence_count"] = occurrence_count
                        item["legacy_status"] = evidence.get("legacy_status")
                        item["display_value"] = evidence.get("display_value") or r["normalized_value"]
                        item["review_priority"] = 50 + min(occurrence_count, 500)
                    rows.append(item)

            if kind in {"all", "discoveries"}:
                clauses = []
                params = []
                desired = "pending" if status in {"pending", "open"} else status
                if desired:
                    clauses.append("status=?")
                    params.append(desired)
                if query:
                    clauses.append("(sender_email LIKE ? OR sender_domain LIKE ? OR COALESCE(proposed_entity_name,'') LIKE ?)")
                    needle = f"%{query}%"
                    params.extend([needle, needle, needle])
                where = " WHERE " + " AND ".join(clauses) if clauses else ""
                for r in con.execute(
                    "SELECT id,sender_email,sender_domain,proposed_entity_name,message_count,evidence_json,status,matched_entity_id,created_at,updated_at "
                    "FROM contact_discovery_queue" + where + " ORDER BY message_count DESC,updated_at DESC,id DESC",
                    params,
                ).fetchall():
                    item = dict(r)
                    item.update({
                        "maintenance_kind": "discovery",
                        "maintenance_item_id": r["id"],
                        "action_level": "AUTO_STAGE",
                        "review_priority": 100 + min(int(r["message_count"] or 0), 100),
                        "normalized_value": r["sender_email"],
                        "title": r["proposed_entity_name"] or r["sender_domain"],
                        "review_summary": f"{r['sender_email']} · {int(r['message_count'] or 0)} messages · corroborated contact evidence",
                    })
                    try:
                        evidence = json.loads(r["evidence_json"] or "{}")
                    except (TypeError, json.JSONDecodeError):
                        evidence = {}
                    if isinstance(evidence, dict):
                        item["discovery_evidence"] = evidence
                    rows.append(item)

            if kind in {"all", "findings"}:
                clauses = []
                params = []
                desired = "open" if status in {"pending", "open"} else status
                if desired:
                    clauses.append("status=?")
                    params.append(desired)
                if query:
                    clauses.append("(title LIKE ? OR detail LIKE ? OR finding_type LIKE ?)")
                    needle = f"%{query}%"
                    params.extend([needle, needle, needle])
                where = " WHERE " + " AND ".join(clauses) if clauses else ""
                for r in con.execute(
                    "SELECT id,finding_type,severity,action_level,entity_id,contact_point_id,title,detail,status,first_seen_at,last_seen_at,occurrences "
                    "FROM maintenance_findings" + where + " ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,last_seen_at DESC,id DESC",
                    params,
                ).fetchall():
                    item = dict(r)
                    item.update({"maintenance_kind": "finding", "maintenance_item_id": r["id"]})
                    if str(r["finding_type"] or "").startswith("mail_contact_candidate"):
                        try:
                            detail = json.loads(r["detail"] or "{}")
                        except (TypeError, json.JSONDecodeError):
                            detail = {}
                        if isinstance(detail, dict):
                            item["candidate_type"] = detail.get("type")
                            item["normalized_value"] = detail.get("value")
                            item["evidence_count"] = detail.get("evidence_count")
                            item["example_message_id"] = detail.get("example_message_id")
                            item["source_kind"] = detail.get("source_kind")
                            item["source_reference"] = detail.get("source_reference")
                            item["representative_candidate_id"] = detail.get("representative_candidate_id")
                            bits = [
                                str(detail.get("type") or "contact"),
                                str(detail.get("value") or "").strip(),
                            ]
                            if detail.get("evidence_count"):
                                bits.append(f"{detail['evidence_count']} evidence occurrence(s)")
                            item["review_summary"] = " · ".join(bit for bit in bits if bit)
                            evidence_count = int(detail.get("evidence_count") or 0)
                            type_weight = {
                                "phone": 30,
                                "email": 28,
                                "postal_address": 20,
                                "job_title": 10,
                            }.get(str(detail.get("type") or ""), 5)
                            source_weight = {
                                "attachment": 20,
                                "message_header": 15,
                                "message_body": 5,
                            }.get(str(detail.get("source_kind") or ""), 0)
                            repeat_weight = min(evidence_count, 10) * 4
                            item["review_priority"] = type_weight + source_weight + repeat_weight
                    rows.append(item)

            if kind in {"all", "enrichment"}:
                clauses = []
                params = []
                desired = "pending" if status in {"pending", "open"} else status
                if desired:
                    clauses.append("status=?")
                    params.append(desired)
                if query:
                    clauses.append("(task_type LIKE ? OR rationale LIKE ?)")
                    needle = f"%{query}%"
                    params.extend([needle, needle])
                where = " WHERE " + " AND ".join(clauses) if clauses else ""
                for r in con.execute(
                    "SELECT id,entity_id,task_type,rationale,status,created_at,updated_at "
                    "FROM enrichment_queue" + where + " ORDER BY updated_at DESC,id DESC",
                    params,
                ).fetchall():
                    item = dict(r)
                    item.update({"maintenance_kind": "enrichment", "maintenance_item_id": r["id"], "action_level": "AUTO_STAGE"})
                    item["review_priority"] = {
                        "find_phone": 35,
                        "find_email": 32,
                        "find_address": 24,
                        "find_web_presence": 16,
                    }.get(str(r["task_type"] or ""), 10)
                    rows.append(item)

            if kind in {"all", "candidates"}:
                clauses = []
                params = []
                desired = "pending" if status in {"pending", "open"} else status
                if desired:
                    clauses.append("status=?")
                    params.append(desired)
                if query:
                    clauses.append("(target_table LIKE ? OR target_field LIKE ? OR rationale LIKE ? OR COALESCE(proposed_value,'') LIKE ?)")
                    needle = f"%{query}%"
                    params.extend([needle, needle, needle, needle])
                where = " WHERE " + " AND ".join(clauses) if clauses else ""
                for r in con.execute(
                    "SELECT id,action_level,entity_id,contact_point_id,target_table,target_field,current_value,proposed_value,rationale,status,created_at,updated_at "
                    "FROM candidate_changes" + where + " ORDER BY updated_at DESC,id DESC",
                    params,
                ).fetchall():
                    item = dict(r)
                    item.update({"maintenance_kind": "candidate", "maintenance_item_id": r["id"]})
                    rows.append(item)

            entity_ids = {
                int(value)
                for item in rows
                for value in (item.get("entity_id"), item.get("matched_entity_id"))
                if value is not None and str(value).isdigit()
            }
            names = self._entity_names(entity_ids)
            for item in rows:
                if item.get("entity_id") is not None:
                    item["entity_name"] = names.get(int(item["entity_id"]))
                if item.get("matched_entity_id") is not None:
                    item["matched_entity_name"] = names.get(int(item["matched_entity_id"]))

            rows.sort(
                key=lambda item: (
                    int(item.get("review_priority") or 0),
                    item.get("updated_at") or item.get("last_seen_at") or item.get("created_at") or "",
                ),
                reverse=True,
            )
            return rows[offset:offset + limit]
        finally:
            con.close()
