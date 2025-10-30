#!/usr/bin/env python3
"""
Lightweight log watcher that tails the Nginx access log, detects pool failovers and elevated
upstream 5xx error rates, and posts alerts to Slack via an incoming webhook.

Behavior:
- Tails /var/log/nginx/access.log (shared volume from compose)
- Parses lines for fields: pool, release, upstream_status, upstream_addr, request_time, upstream_response_time
- Maintains a sliding window of recent upstream_status codes to compute error rate
- Sends Slack alerts on failover (pool change) and when error rate exceeds threshold
- Supports cooldowns and maintenance suppression via env vars
"""
import os
import re
import time
import json
from collections import deque
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv


load_dotenv()

LOG_PATH = os.getenv("NGINX_LOG_PATH", "/var/log/nginx/access.log")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
ERROR_RATE_THRESHOLD = float(os.getenv("ERROR_RATE_THRESHOLD", "2"))
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "200"))
ALERT_COOLDOWN_SEC = int(os.getenv("ALERT_COOLDOWN_SEC", "300"))
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() in ("1", "true", "yes")
WATCHER_DEBUG = os.getenv("WATCHER_DEBUG", "false").lower() in ("1", "true", "yes")


FIELD_RE = re.compile(r"pool:(?P<pool>\S+)\s+release:(?P<release>\S+)\s+upstream_status:(?P<upstream_status>\S+)\s+upstream_addr:(?P<upstream_addr>\S+)\s+request_time:(?P<request_time>\S+)\s+upstream_response_time:(?P<upstream_response_time>\S+)")


def send_slack_alert(text: str, title: str = "Alert"):
	if not SLACK_WEBHOOK_URL:
		print("SLACK_WEBHOOK_URL not set; skipping alert:", text, flush=True)
		return False
	payload = {
		"username": "log-watcher",
		"icon_emoji": ":rotating_light:",
		"attachments": [
			{
				"fallback": title + " - " + text,
				"color": "danger",
				"title": title,
				"text": text,
				"ts": int(time.time()),
			}
		],
	}
	try:
		r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
		r.raise_for_status()
		print(f"Slack alert sent: {title}", flush=True)
		return True
	except Exception as e:
		print("Failed to send Slack alert:", e, flush=True)
		return False


def tail_file(path):
	import io

	while not os.path.exists(path):
		time.sleep(0.5)
	with open(path, "r", encoding="utf-8", errors="ignore") as fh:
		# Try to seek to the end; if the underlying stream doesn't support seek, continue reading
		try:
			fh.seek(0, os.SEEK_END)
		except (io.UnsupportedOperation, OSError):
			pass

		while True:
			line = fh.readline()
			if not line:
				time.sleep(0.2)
				continue
			yield line.rstrip("\n")


def parse_line(line: str):
	m = FIELD_RE.search(line)
	if not m:
		return None
	return m.groupdict()


def is_5xx(status_str: str) -> bool:
	try:
		code = int(status_str)
		return 500 <= code < 600
	except Exception:
		return False


def main():
	print("Starting log watcher. Log path:", LOG_PATH)
	window = deque(maxlen=WINDOW_SIZE)
	last_failover_alert = datetime.min
	last_error_alert = datetime.min
	last_pool = None

	for line in tail_file(LOG_PATH):
		parsed = parse_line(line)
			print("Starting log watcher. Log path:", LOG_PATH, "DEBUG=" + str(WATCHER_DEBUG), flush=True)
			# Could not parse; skip
			continue

		pool = parsed.get("pool")
		upstream_status = parsed.get("upstream_status") or parsed.get("status")

		# Failover detection
		if last_pool is None:
			last_pool = pool

		if pool and last_pool and pool != last_pool:
			# potential failover
			now = datetime.utcnow()
			if MAINTENANCE_MODE:
				print(f"Maintenance mode ON: suppressing failover alert {last_pool} -> {pool}")
			elif (now - last_failover_alert).total_seconds() > ALERT_COOLDOWN_SEC:
				text = f"Failover detected: {last_pool} -> {pool}\nSample log: {line}"
				send_slack_alert(text, title="Failover Detected")
				last_failover_alert = now
			else:
				print("Failover detected but in cooldown; skipping")
			last_pool = pool

		# Rolling error window
		if upstream_status:
			window.append(1 if is_5xx(upstream_status) else 0)

		if len(window) == 0:
			continue

		error_rate = (sum(window) / len(window)) * 100.0
		if error_rate > ERROR_RATE_THRESHOLD:
			now = datetime.utcnow()
			if MAINTENANCE_MODE:
				print("Maintenance mode ON: suppressing error-rate alert")
					if WATCHER_DEBUG:
						print(f"window append: status={upstream_status} is_err={is_err} window_size={len(window)}", flush=True)
			elif (now - last_error_alert).total_seconds() > ALERT_COOLDOWN_SEC:
				text = (
					f"High upstream 5xx error rate detected: {error_rate:.2f}% over last {len(window)} requests\n"
					f"Threshold: {ERROR_RATE_THRESHOLD}%\n"
					f"Latest sample: pool={pool} status={upstream_status} upstream={parsed.get('upstream_addr')}"
				)
				send_slack_alert(text, title="High Error Rate")
				last_error_alert = now
			else:
				print("Error-rate high but in cooldown; skipping")


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		print("Exiting on user interrupt")
