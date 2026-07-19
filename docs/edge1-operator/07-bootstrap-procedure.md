# Edge1 Operator Bootstrap Procedure

## Purpose

This document defines the one-time installation path for enabling the persistent Edge1 Operator execution layer.

## Bootstrap goals

The installer should:

1. Verify the target host identity.
2. Create the dedicated `edge1-operator` service account.
3. Install the operator runtime.
4. Configure the systemd service.
5. Create protected evidence and audit directories.
6. Validate local health before enabling external connectivity.

## Safety requirements

- Runtime credentials remain outside Git.
- No una