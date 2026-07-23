# Telephony Analytics Snapshot Collector Design

## Purpose

The snapshot collector bridges the live read-only telephony status payload
with the local analytics history database.

## Flow











## Safety Boundary

The collector:

- reads telemetry only;
- stores analytics history only;
- does not control services;
- does not modify PBX configuration;
- does not modify carrier routing;
- does not handle credentials.

## Current Operation

The collector is manually invoked.

Future scheduling requires separate review.
