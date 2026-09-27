#!/usr/bin/env python3
"""G3 explicitly bounded read-only live host metrics. No subprocess or shell.

The API runs as the non-privileged operator and reads only system-generated
/proc summaries and statvfs(/). These are observations, not operational tests.
"""
from __future__ import annotations
import os
from pathlib import Path

def read_metrics(*, loadavg: Path = Path("/proc/loadavg"),
                 meminfo: Path = Path("/proc/meminfo"),
                 uptime: Path = Path("/proc/uptime"),
                 disk: str = "/") -> dict:
    result = {
        "available": False, "load_1m": None, "cpu_count": None,
        "memory_total_mib": None, "memory_available_mib": None,
        "memory_used_percent": None, "root_disk_total_gib": None,
        "root_disk_available_gib": None, "root_disk_used_percent": None,
        "uptime_seconds": None,
        "limits": "Read-only kernel observations. Load average is not CPU utilization; root disk only.",
    }
    try:
        for source in (loadavg, meminfo, uptime):
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 128 * 1024:
                return result
        load = float(loadavg.read_text(encoding="ascii").split()[0])
        cpus = os.cpu_count()
        if not (0 <= load < 1_000_000 and type(cpus) is int and 1 <= cpus <= 16384):
            return result
        mem = {}
        for line in meminfo.read_text(encoding="ascii").splitlines():
            key, _, val = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                mem[key] = int(val.strip().split()[0])
        total = mem["MemTotal"]
        available = mem["MemAvailable"]
        if not (0 < total <= 1_000_000_000_000 and 0 <= available <= total):
            return result
        up = float(uptime.read_text(encoding="ascii").split()[0])
        if not 0 <= up < 10**12:
            return result
        stat = os.statvfs(disk)
        total_disk = stat.f_blocks * stat.f_frsize
        available_disk = stat.f_bavail * stat.f_frsize
        if not (0 < total_disk < 10**21 and 0 <= available_disk <= total_disk):
            return result
        mib = 1024**2
        gib = 1024**3
        result.update(
            available=True, load_1m=round(load, 2), cpu_count=cpus,
            memory_total_mib=round(total / 1024), memory_available_mib=round(available / 1024),
            memory_used_percent=round((total-available)/total*100, 1),
            root_disk_total_gib=round(total_disk/gib, 1),
            root_disk_available_gib=round(available_disk/gib, 1),
            root_disk_used_percent=round((total_disk-available_disk)/total_disk*100, 1),
            uptime_seconds=round(up),
        )
    except (OSError, UnicodeError, ValueError, IndexError, KeyError, ZeroDivisionError):
        pass
    return result
