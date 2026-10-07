#!/usr/bin/env python3
"""Read-only Contacts maintenance/review model.

The maintenance state database is intentionally separate from canonical
Unified Contacts. This module joins display metadata for operator review but
never mutates either database.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


class UnifiedContactsMaintenance:
    def __init__(
        self,
        maintenance_database: str | Path = "/var/lib/edge1-contacts-maintenance/maintenance.sqlite",
        contacts_database: str | Path = "/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite",
        phone_prefix_triage: str | Path = "/opt/edge1-management-interface/config/contacts/phone-prefix-triage.json",
    ) -> None:
        self.maintenance_database = Path(maintenance_database)
        self.contacts_database = Path(contacts_database)
        self.phone_prefix_triage = Path(phone_prefix_triage)

    def _open(self, path: Path) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    def _phone_prefix_metadata(self, number: str) -> dict:
        try:
            payload = json.loads(self.phone_prefix_triage.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        prefixes = payload.get("prefixes") if isinstance(payload, dict) else None
        if not isinstance(prefixes, dict):
            return {}
        matches = [
            (prefix, meta)
            for prefix, meta in prefixes.items()
            if str(number or "").startswith(str(prefix)) and isinstance(meta, dict)
        ]
        if not matches:
            return {}
        _, meta = max(matches, key=lambda item: len(item[0]))
        return dict(meta)

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

    @staticmethod
    def _organization_key(value: str) -> str:
        tokens = re.findall(r"[a-z0-9]+", str(value or "").casefold())
        suffixes = {
            "inc", "incorporated", "ltd", "limited", "llc", "lp", "corp",
            "corporation", "company", "co", "plc", "group",
        }
        while len(tokens) > 1 and tokens[-1] in suffixes:
            tokens.pop()
        return "".join(tokens)

    @classmethod
    def _domain_organization_key(cls, domain: str) -> str:
        parts = [part for part in str(domain or "").casefold().strip(".").split(".") if part]
        if len(parts) < 2:
            return ""
        public_suffix_pairs = {"co.uk", "org.uk", "com.au", "co.nz", "com.br"}
        suffix_pair = ".".join(parts[-2:])
        label = parts[-3] if suffix_pair in public_suffix_pairs and len(parts) >= 3 else parts[-2]
        return cls._organization_key(label)

    def _organization_suggestions(self) -> dict[str, tuple[int, str]]:
        con = self._open(self.contacts_database)
        try:
            grouped: dict[str, list[tuple[int, str]]] = {}
            for row in con.execute(
                "SELECT id,COALESCE(display_name,canonical_name) AS name "
                "FROM contact_entities WHERE entity_type='organization' AND lifecycle_status='active'"
            ).fetchall():
                key = self._organization_key(row["name"])
                if key:
                    grouped.setdefault(key, []).append((int(row["id"]), row["name"]))
            return {key: values[0] for key, values in grouped.items() if len(values) == 1}
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
                "enrichment_review_required": scalar("SELECT COUNT(*) FROM enrichment_queue WHERE status='review_required'"),
                "pending_identity_resolution": scalar("SELECT COUNT(*) FROM identity_resolution_queue WHERE status='pending'"),
                "pending_discoveries": scalar("SELECT COUNT(*) FROM contact_discovery_queue WHERE status='pending'"),
                "pending_relationship_suggestions": scalar("SELECT COUNT(*) FROM relationship_suggestion_queue WHERE status='pending'"),
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
        allowed_kinds = {"all", "identity", "discoveries", "relationships", "findings", "enrichment", "candidates"}
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
                    if status in {"pending", "open"}:
                        clauses.append("status IN ('pending','review_required')")
                    else:
                        clauses.append("status=?")
                        params.append(status)
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
                        source_document_count = int(evidence.get("source_document_count") or 0)
                        recovered_source_document_count = int(evidence.get("recovered_source_document_count") or 0)
                        source_family_count = int(evidence.get("source_family_count") or 0)
                        item["occurrence_count"] = occurrence_count
                        item["legacy_status"] = evidence.get("legacy_status")
                        item["display_value"] = evidence.get("display_value") or r["normalized_value"]
                        item["source_document_count"] = source_document_count
                        item["recovered_source_document_count"] = recovered_source_document_count
                        item["source_family_count"] = source_family_count
                        item["source_families"] = evidence.get("source_families")
                        if isinstance(evidence.get("sources"), list):
                            item["public_sources"] = evidence.get("sources")
                        if isinstance(evidence.get("contact_points"), list):
                            item["proposed_contact_points"] = evidence.get("contact_points")
                        item["public_resolution"] = evidence.get("public_resolution")
                        item["review_priority"] = (
                            50
                            + min(occurrence_count, 50)
                            + min(recovered_source_document_count, 10) * 2
                            + min(source_family_count, 3) * 10
                        )
                    prefix_meta = self._phone_prefix_metadata(r["normalized_value"])
                    if prefix_meta:
                        item["routing_class"] = prefix_meta.get("routing_class")
                        item["routing_carrier"] = prefix_meta.get("carrier")
                        item["routing_exchange_area"] = prefix_meta.get("exchange_area")
                        item["routing_source"] = prefix_meta.get("source")
                        if r["status"] == "pending" and prefix_meta.get("routing_class") == "wireless":
                            item["review_priority"] = max(0, int(item.get("review_priority") or 0) - 45)
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
                    sender_email = str(r["sender_email"] or "").casefold()
                    local = sender_email.split("@", 1)[0] if "@" in sender_email else sender_email
                    message_count = int(r["message_count"] or 0)
                    generic_local = local in {
                        "info", "hello", "news", "newsletter", "noreply", "no-reply", "no_reply",
                        "reminder", "renewals", "ebill", "notifications", "notification",
                        "marketing", "promotions", "offers", "catch",
                    }
                    named_local = bool(
                        re.fullmatch(r"[a-z][a-z'-]{1,40}\.[a-z][a-z'-]{1,40}", local)
                    )
                    service_local = local in {"support", "service", "customerservice", "customercare"}
                    priority = 40 + min(message_count, 20)
                    if r["proposed_entity_name"]:
                        priority += 55
                    if named_local:
                        priority += 70
                    if service_local:
                        priority += 35
                    if generic_local:
                        priority -= 30
                    item.update({
                        "maintenance_kind": "discovery",
                        "maintenance_item_id": r["id"],
                        "action_level": "AUTO_STAGE",
                        "review_priority": priority,
                        "normalized_value": r["sender_email"],
                        "title": r["proposed_entity_name"] or r["sender_domain"],
                        "review_summary": f"{r['sender_email']} · {message_count} messages · corroborated contact evidence",
                    })
                    try:
                        evidence = json.loads(r["evidence_json"] or "{}")
                    except (TypeError, json.JSONDecodeError):
                        evidence = {}
                    if isinstance(evidence, dict):
                        item["discovery_evidence"] = evidence
                    rows.append(item)

            if kind in {"all", "relationships"}:
                clauses = []
                params = []
                desired = "pending" if status in {"pending", "open"} else status
                if desired:
                    clauses.append("status=?")
                    params.append(desired)
                if query:
                    clauses.append("(proposed_person_name LIKE ? OR sender_email LIKE ? OR rationale LIKE ?)")
                    needle = f"%{query}%"
                    params.extend([needle, needle, needle])
                where = " WHERE " + " AND ".join(clauses) if clauses else ""
                for r in con.execute(
                    "SELECT id,discovery_id,proposed_person_name,sender_email,organization_entity_id,"
                    "relationship_type,confidence,rationale,evidence_json,status,created_at,updated_at "
                    "FROM relationship_suggestion_queue" + where + " ORDER BY updated_at DESC,id DESC",
                    params,
                ).fetchall():
                    item = dict(r)
                    item.update({
                        "maintenance_kind": "relationship_suggestion",
                        "maintenance_item_id": r["id"],
                        "action_level": "REVIEW_REQUIRED",
                        "title": f"{r['proposed_person_name']} → {r['relationship_type']}",
                        "normalized_value": r["sender_email"],
                        "review_summary": r["rationale"],
                        "review_priority": 180,
                    })
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
                enrichment_columns = {row[1] for row in con.execute("PRAGMA table_info(enrichment_queue)").fetchall()}
                research_fields = ["proposed_value", "evidence_json", "research_confidence", "research_checked_at"]
                research_select = ",".join(name if name in enrichment_columns else f"NULL AS {name}" for name in research_fields)
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
                    "SELECT id,entity_id,task_type,rationale,status,created_at,updated_at," + research_select + " "
                    "FROM enrichment_queue" + where + " ORDER BY updated_at DESC,id DESC",
                    params,
                ).fetchall():
                    item = dict(r)
                    item.update({"maintenance_kind": "enrichment", "maintenance_item_id": r["id"], "action_level": "REVIEW_REQUIRED" if r["status"]=="review_required" else "AUTO_STAGE"})
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
                for value in (item.get("entity_id"), item.get("matched_entity_id"), item.get("organization_entity_id"))
                if value is not None and str(value).isdigit()
            }
            names = self._entity_names(entity_ids)
            organization_suggestions = self._organization_suggestions()
            for item in rows:
                if item.get("entity_id") is not None:
                    item["entity_name"] = names.get(int(item["entity_id"]))
                if item.get("matched_entity_id") is not None:
                    item["matched_entity_name"] = names.get(int(item["matched_entity_id"]))
                if item.get("organization_entity_id") is not None:
                    item["organization_name"] = names.get(int(item["organization_entity_id"]))
                if (
                    item.get("maintenance_kind") == "discovery"
                    and not item.get("matched_entity_id")
                ):
                    domain_key = self._domain_organization_key(item.get("sender_domain") or "")
                    suggestion = organization_suggestions.get(domain_key)
                    if suggestion:
                        item["suggested_entity_id"] = suggestion[0]
                        item["suggested_entity_name"] = suggestion[1]
                        item["suggestion_reason"] = "unique organization-name match to sender domain"
                        item["review_priority"] = int(item.get("review_priority") or 0) + 45

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
