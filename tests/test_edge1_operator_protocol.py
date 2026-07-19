#!/usr/bin/env python3
"""Validation checks for the Edge1 Operator protocol boundary."""

from pathlib import Path


def test_protocol_module_exists():
    assert Path("server/edge1_operator_mcp_protocol.py").exists()


def test_operator_runtime_exists():
    assert Path("server/edge1_operator_runtime.py").exists()


def test_service_install_assets_exist():
    assert Path("deploy/edge1-operator/install-edge1-operator.sh").exists()
