# Runbook — Log Watcher & Alerts

This runbook explains the alerts produced by the log-watcher sidecar and how operators should respond.

## Alerts

1) Failover Detected

- What it means: The pool that served requests changed (e.g., `blue` → `green`). This usually indicates the primary pool became unhealthy and traffic failed over to the backup.
- Operator action:
  - Check the health and logs of the primary container (e.g., the `blue_app` container).
  - Inspect Nginx access logs and upstream logs for the error that caused failover.
  - If primary container is unhealthy, consider restarting it or reverting recent deploys.
  - If this was expected (planned failover), acknowledge in Slack and set `MAINTENANCE_MODE=true` in `.env` while performing maintenance.

2) High Error Rate

- What it means: The log watcher detected a high rate of upstream 5xx responses above the configured threshold over the sliding window.
- Operator action:
  - Inspect the recent Nginx access logs for patterns (endpoints, client IPs, upstream addresses).
  - Check upstream (app) container logs for exceptions or resource exhaustion.
  - If caused by a deployment, consider rolling back or scaling up.
  - Consider temporarily switching ACTIVE_POOL to the healthy pool if one exists.

3) Recovery / Resolved

- When traffic returns to the primary pool or error rate falls back under threshold, the watcher won't spam a second alert due to cooldowns. Manually acknowledge in Slack as needed.

## Suppressing Alerts

- For planned maintenance or noisy load tests, set `MAINTENANCE_MODE=true` in your `.env` before starting the test. This prevents failover and error-rate alerts from being sent.

## Tuning Parameters

- `ERROR_RATE_THRESHOLD` — percent of requests that may be 5xx before alerting (default: 2)
- `WINDOW_SIZE` — number of most recent requests to include in the sliding window (default: 200)
- `ALERT_COOLDOWN_SEC` — seconds to wait between repeated alerts of the same type (default: 300)

## Quick Recovery Steps

1. Check docker-compose service status:

   docker-compose ps

2. Inspect Nginx logs (shared volume):

   docker-compose exec log_watcher sh -c "tail -n 200 /var/log/nginx/access.log"

3. Inspect app container logs (example):

   docker-compose logs --no-color blue_app

4. If primary is unhealthy and you need to revert traffic back, investigate the cause, fix or restart the primary, and observe logs until traffic is stable.
