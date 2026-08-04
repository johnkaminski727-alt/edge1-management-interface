#!/usr/bin/env python3
"""Runtime-root-aware application loader for the outbound-mail gateway."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mail_identity_registry
import outbound_mail_gateway as gateway
import outbound_mail_gateway_server as base
import outbound_mail_policy
import outbound_mail_runtime_paths as runtime_paths


class RuntimeGatewayApplication:
    """Load immutable config from repo or /etc and mutable state from approved roots."""

    def __init__(
        self,
        config_path: str | Path,
        identities_path: str | Path = base.DEFAULT_IDENTITIES,
        *,
        config_root: str | Path = runtime_paths.DEFAULT_CONFIG_ROOT,
        state_root: str | Path = runtime_paths.DEFAULT_STATE_ROOT,
        require_root_owned_config: bool = True,
    ) -> None:
        self.repo_root = base.REPO_ROOT.resolve()
        self.config_path_input = Path(config_path)
        self.identities_path_input = Path(identities_path)
        self.config_root, self.state_root = runtime_paths.validate_runtime_roots(
            config_root,
            state_root,
        )
        self.require_root_owned_config = require_root_owned_config
        self.last_resolved_paths: dict[str, Path] = {}

    def _config_file(self, configured: str | Path) -> Path:
        return runtime_paths.resolve_config_file(
            configured,
            repo_root=self.repo_root,
            config_root=self.config_root,
            require_root_owned=self.require_root_owned_config,
        )

    def _state_path(self, configured: str | Path) -> Path:
        return runtime_paths.resolve_state_path(
            configured,
            repo_root=self.repo_root,
            state_root=self.state_root,
        )

    def load(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path, Path]:
        config_path = self._config_file(self.config_path_input)
        config = gateway.load_json(config_path)
        gateway.validate_gateway_config(config)

        policy_path = self._config_file(config["paths"]["policy"])
        identities_path = self._config_file(self.identities_path_input)
        audit_path = self._state_path(config["paths"]["audit_jsonl"])
        nonce_path = self._state_path(config["preparation_api"]["nonce_store"])

        policy = outbound_mail_policy.load_policy(policy_path)
        outbound_mail_policy.validate_policy(policy)
        identities = gateway.load_json(identities_path)
        mail_identity_registry.validate_registry(identities)

        self.last_resolved_paths = {
            "config": config_path,
            "policy": policy_path,
            "identities": identities_path,
            "audit": audit_path,
            "nonce": nonce_path,
        }
        return config, policy, identities, audit_path, nonce_path

    def resolved_path_summary(self) -> dict[str, str]:
        return {
            key: str(value)
            for key, value in sorted(self.last_resolved_paths.items())
        }
