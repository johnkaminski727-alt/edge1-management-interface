#!/usr/bin/env python3
"""Bounded durable reservation state for AVA physical effects."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time


STATE_VERSION = 1
DEFAULT_MAX_RECORDS = 256


class PhysicalEffectsStateError(RuntimeError):
    """Raised when durable physical-effect state cannot be trusted."""



def _reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise PhysicalEffectsStateError(
                "duplicate state field"
            )
        result[key] = value

    return result


class DurableReservationLedger:
    def __init__(
        self,
        path,
        *,
        dedupe_seconds,
        max_records=DEFAULT_MAX_RECORDS,
        wall_clock=time.time,
    ):
        self.path = Path(path)

        if (
            isinstance(dedupe_seconds, bool)
            or not isinstance(dedupe_seconds, (int, float))
            or dedupe_seconds <= 0
        ):
            raise PhysicalEffectsStateError(
                "dedupe_seconds must be positive"
            )

        if (
            type(max_records) is not int
            or max_records <= 0
        ):
            raise PhysicalEffectsStateError(
                "max_records must be a positive integer"
            )

        self.dedupe_seconds = float(dedupe_seconds)
        self.max_records = max_records
        self._wall_clock = wall_clock

    def _now(self):
        value = self._wall_clock()

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            raise PhysicalEffectsStateError(
                "wall clock returned invalid value"
            )

        return float(value)

    def _empty(self):
        return {
            "version": STATE_VERSION,
            "reservations": {},
        }

    def _validate(self, data):
        if not isinstance(data, dict):
            raise PhysicalEffectsStateError(
                "state root must be an object"
            )

        if set(data) != {"version", "reservations"}:
            raise PhysicalEffectsStateError(
                "state schema mismatch"
            )

        if type(data["version"]) is not int:
            raise PhysicalEffectsStateError(
                "state version must be an integer"
            )

        if data["version"] != STATE_VERSION:
            raise PhysicalEffectsStateError(
                "unsupported state version"
            )

        reservations = data["reservations"]

        if not isinstance(reservations, dict):
            raise PhysicalEffectsStateError(
                "reservations must be an object"
            )

        if len(reservations) > self.max_records:
            raise PhysicalEffectsStateError(
                "state exceeds reservation bound"
            )

        clean = {}

        for request_id, record in reservations.items():
            if not isinstance(request_id, str):
                raise PhysicalEffectsStateError(
                    "invalid reservation identifier"
                )

            if not isinstance(record, dict):
                raise PhysicalEffectsStateError(
                    "invalid reservation record"
                )

            if set(record) != {
                "catalogue_effect",
                "reserved_at",
            }:
                raise PhysicalEffectsStateError(
                    "reservation schema mismatch"
                )

            effect = record["catalogue_effect"]
            reserved_at = record["reserved_at"]

            if not isinstance(effect, str):
                raise PhysicalEffectsStateError(
                    "invalid reservation effect"
                )

            if (
                isinstance(reserved_at, bool)
                or not isinstance(reserved_at, (int, float))
            ):
                raise PhysicalEffectsStateError(
                    "invalid reservation timestamp"
                )

            clean[request_id] = {
                "catalogue_effect": effect,
                "reserved_at": float(reserved_at),
            }

        return {
            "version": STATE_VERSION,
            "reservations": clean,
        }

    def _read(self):
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return self._empty()
        except OSError as exc:
            raise PhysicalEffectsStateError(
                "cannot read durable state"
            ) from exc

        try:
            data = json.loads(
                raw,
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PhysicalEffectsStateError(
                "durable state is malformed"
            ) from exc

        return self._validate(data)

    def _prune(self, data, now):
        cutoff = now - self.dedupe_seconds

        reservations = {
            request_id: record
            for request_id, record
            in data["reservations"].items()
            if record["reserved_at"] > cutoff
        }

        return {
            "version": STATE_VERSION,
            "reservations": reservations,
        }

    def _write(self, data):
        data = self._validate(data)
        parent = self.path.parent

        if not parent.is_dir():
            raise PhysicalEffectsStateError(
                "state directory does not exist"
            )

        payload = (
            json.dumps(
                data,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

        temp_name = None

        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=".broker-state-",
                dir=str(parent),
            )

            try:
                os.fchmod(fd, 0o600)

                with os.fdopen(fd, "wb", closefd=True) as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())

                os.replace(temp_name, self.path)
                temp_name = None

                directory_fd = os.open(
                    str(parent),
                    os.O_RDONLY | os.O_DIRECTORY,
                )

                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)

            except Exception:
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise

        except OSError as exc:
            raise PhysicalEffectsStateError(
                "cannot commit durable state"
            ) from exc

        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass

    def lookup(self, request_id):
        now = self._now()
        data = self._prune(self._read(), now)
        return data["reservations"].get(request_id)

    def reserve(self, request_id, catalogue_effect):
        now = self._now()
        data = self._prune(self._read(), now)
        reservations = data["reservations"]

        existing = reservations.get(request_id)

        if existing is not None:
            return False

        if len(reservations) >= self.max_records:
            raise PhysicalEffectsStateError(
                "durable reservation bound reached"
            )

        reservations[request_id] = {
            "catalogue_effect": catalogue_effect,
            "reserved_at": now,
        }

        self._write(data)
        return True
