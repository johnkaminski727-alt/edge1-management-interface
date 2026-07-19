# Geographic Registry API Integration

## Purpose

The geographic registry provides a shared reference layer for country identity, telephone numbering, and time calculations.

## Planned Consumers

- Edge1 operations services
- BigBird AI gateway metadata services
- Telephony and messaging systems
- Scheduling and timekeeping services

## Recommended Endpoints

```
GET /api/registry/countries
GET /api/registry/timezones
GET /api/registry/calling-codes
GET /api/registry/countries/{iso_alpha2}
```

## Design Principles

- Registry data should be versioned.
- Runtime services should consume generated data rather than maintain copies.
- Updates should be validated before deployment.
