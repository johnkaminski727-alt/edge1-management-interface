# WW.CX Edge1 Operations Center Architecture

## Purpose

The Operations Center provides read-only operational visibility for Edge1.

It is separate from:
- Store Admin
- administrative mutation surfaces
- production control workflows

## Data Flow

Subsystem telemetry:

- Security Operations
- Bitcoin Operations
- Mining Operations

feeds:

- Health Model
- Timeline Exporter
- Change Exporter
- Correlation Exporter
- Daily Summary Exporter
- Report Exporter

The web interface consumes generated JSON artifacts.

## Design Principles

- Read-only by default
- Evidence driven
- No arbitrary command execution
- Separate operational visibility from administration

## Modules

- Security Operations
- Bitcoin Operations
- Mining Operations
- Automation Health
- Incident Context
- Reports
