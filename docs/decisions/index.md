# Decisions and Non-Goals

## Core Principle

Treat multiple Azure Foundry subscriptions as one logical model-capacity pool while preserving each subscription's safety margin and maximizing useful utilization before each credit period ends.

## Non-Goals

The first version is not a general API management platform. Do not add API Management, Front Door, AKS, Service Bus, Redis, SQL, complex distributed orchestration, user management, prompt management, fine-tuning, or semantic caching unless a concrete requirement justifies it.

## Initial Policy

Use credit-aware weighted routing during normal operation. Increase cycle urgency when projected unused credit is significant and the cycle is near completion. Stop intentional traffic at the reserve, cooldown quota and repeated errors, reduce confidence for stale cost data, and use weighted round-robin only when candidates are otherwise similarly positioned.

## Future Compatibility

The backend model supports arbitrary backend counts and leaves room for subscription, project, region, endpoint, and deployment dimensions. Geographic routing is not required initially.

## Architecture Records

- [ADR-005: State Management](adr/005-state-management.md)
- [ADR-006: Explainable Credit-Aware Routing](adr/006-routing-algorithm.md)
- [ADR-007: Provider-Aware Quota Routing](adr/007-provider-aware-quota-routing.md) (Proposed; maintainer approval pending)
