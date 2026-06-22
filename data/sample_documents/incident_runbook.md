# Production Incident Response Runbook

## Severity Levels
- **Sev-1:** Full outage or data loss affecting all tenants. Page on-call
  immediately.
- **Sev-2:** Major feature degraded for many tenants; no data loss.
- **Sev-3:** Minor or cosmetic issue affecting few users.

## Sev-1 Response Steps
1. Acknowledge the page within 5 minutes and declare an incident in the
   #incidents channel.
2. Assign an Incident Commander (IC) who owns coordination, not debugging.
3. Open a shared incident document and start a timeline of actions.
4. Mitigate first (roll back the last deploy, fail over, or disable the broken
   feature flag) before attempting a root-cause fix.
5. Communicate status to stakeholders every 30 minutes until resolved.
6. Once stable, downgrade severity and schedule a blameless post-mortem within
   48 hours.

## Rollback Procedure
Identify the last known-good release tag and run `deploy rollback <tag>`.
Confirm health checks return green and error rates fall below baseline before
declaring recovery.

## Post-Mortem
Every Sev-1 and Sev-2 requires a written post-mortem covering impact, timeline,
root cause, and action items with owners and due dates. Post-mortems are
blameless and shared company-wide.
