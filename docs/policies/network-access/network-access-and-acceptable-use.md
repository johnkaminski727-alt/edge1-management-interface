# Proposed Network Access & Acceptable Use Policy

Status: **DRAFT / NOT ACTIVE**  
Audience: WW.CX account holders using private-network or VPN access  
Acceptance required before enforcement: **proposed yes**

## Purpose

WW.CX network access is provided to support authorized work, administration, communication, research, testing, and reasonable personal use that does not interfere with other users or systems.

## Proposed user responsibilities

Users should:

- use only accounts, devices, credentials, addresses, services, and permissions assigned to them;
- keep account credentials, WireGuard profiles, recovery methods, and device unlock credentials private;
- promptly revoke or report a lost, stolen, transferred, or compromised device;
- keep devices reasonably current with security updates and endpoint protections appropriate to the device;
- respect capacity limits and avoid activity that materially degrades service for other users;
- comply with applicable law and any service-specific rules that apply to the activity being performed.

## Proposed prohibited activity

The network must not be used to knowingly:

- gain or attempt unauthorized access to systems, accounts, data, networks, or devices;
- bypass or defeat authentication, segmentation, quarantine, rate limits, policy controls, or security monitoring;
- share private-network credentials or VPN profiles with another person or device;
- impersonate another user or deliberately falsify device ownership or addressing information;
- intercept another user's traffic or credentials without explicit authorization;
- distribute malware, conduct abusive scanning, denial-of-service activity, credential attacks, spam, fraud, or other harmful activity;
- operate an unauthorized public relay, exit service, proxy, tunnel, or gateway that exposes WW.CX private access to third parties;
- use private-network access to interfere with emergency, safety, telecommunications, or production services.

Authorized security testing, diagnostics, monitoring, and automation performed within an approved scope are not prohibited merely because they resemble scanning or administrative activity.

## Private-network boundary

Private/VPN access is tied to an account-owned device registration. Discovery on a local network, possession of an IP address, or physical proximity does not itself create trust.

A user must not rely on the guest network as a route into private WW.CX resources. Guest access is intentionally a separate internet-only service.

## Availability

Network access may be unavailable during maintenance, incident response, upstream outages, policy expiry, device revocation, or security quarantine. WW.CX should provide reasonable operational notice where practical, but this proposal does not promise uninterrupted service.

## Policy changes

Material changes should create a new policy version. Where renewed acceptance is required, existing registered devices move to a policy-update-required state until the account holder accepts the new version or an authorized exemption applies.

## Enforcement boundary

This document does not itself authorize network enforcement. Firewall, DNS, proxy, captive-portal, quarantine, or VPN enforcement requires a separately reviewed implementation, activation approval, validation plan, and rollback procedure.