# Exchange Rate Tracker — Design

## Overview

Full-stack exchange rate tracker for PyFlow. Monitors USDCOP (default) via ExchangeRate-API, stores history in local JSON, and sends alerts via webhook when significant changes occur.

## New Nodes

### AlertNode (`alert`)
- Sends HTTP POST to configurable webhook URL (Slack, Discord, Teams)
- Config: `webhook_url` (required), `message` (required, supports templates)
- Returns: `{status, response}`
- Handles errors gracefully (logs warning, doesn't crash workflow)

### StorageNode (`storage`)
- Reads/writes/appends JSON data to local files
- Config: `path` (required), `action` (read | write | append), `data` (for write/append)
- Actions:
  - `read`: returns parsed JSON from file (empty array if file doesn't exist)
  - `write`: overwrites file with JSON data
  - `append`: reads existing array, appends new item, writes back
- Returns: the data read or written

## Workflow: exchange_rate_tracker.yaml

```yaml
name: exchange-rate-tracker
description: Monitors USDCOP exchange rate and alerts on significant changes
trigger:
  type: schedule
  config:
    cron: "0 * * * *"  # every hour
nodes:
  - id: fetch_rate
    type: http
    config:
      url: "https://v6.exchangerate-api.com/v6/latest/USD"
      timeout: 15
  - id: extract_cop
    type: transform
    depends_on: [fetch_rate]
    config:
      input: "{{ fetch_rate }}"
      expression: "$.body.conversion_rates.COP"
  - id: load_history
    type: storage
    config:
      path: "data/exchange_history.json"
      action: read
  - id: check_change
    type: condition
    depends_on: [extract_cop, load_history]
    config:
      if: "len(load_history) == 0 or abs(extract_cop - load_history[-1]['rate']) / load_history[-1]['rate'] > 0.02"
  - id: save_history
    type: storage
    depends_on: [extract_cop, load_history]
    config:
      path: "data/exchange_history.json"
      action: append
      data:
        pair: "USDCOP"
        rate: "{{ extract_cop }}"
        timestamp: "{{ __now__ }}"
  - id: alert_slack
    type: alert
    depends_on: [check_change, extract_cop]
    when: "check_change == True"
    config:
      webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
      message: "USDCOP rate changed significantly! Current rate: {{ extract_cop }}"
```

## Data Format (history.json)

```json
[
  {"pair": "USDCOP", "rate": 4150.50, "timestamp": "2026-02-27T09:00:00Z"},
  {"pair": "USDCOP", "rate": 4235.75, "timestamp": "2026-02-27T10:00:00Z"}
]
```

## Testing

- AlertNode: mock HTTP POST, verify payload format, test error handling
- StorageNode: test read/write/append with temp files, test missing file handling
- Register both nodes in default_registry
- Integration test with fixture workflow
