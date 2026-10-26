# T27 ESP32 live relay acceptance — 2026-10-27

## Scope

This is a local runtime acceptance record for the token-loader integration. It does not alter the dirty main checkout and does not authorize a remote push or release.

- Branch: `codex/t27-relay-launch-secret-current`
- Worktree: `E:\coding\Worktrees\t27-relay-launch-secret-current\SiroV2`
- Source implementation commit: `69d86ff8310509d073260b2c90c89ac580ae798d`
- Evidence commit: recorded with this report
- Data directory: `/home/pepepig/.local/share/siro/data`
- Relay: Windows `0.0.0.0:8765`, existing process PID 50012

## Controlled restart

After the user handed over the active SIRO launcher, the previous Gateway tree (17777 → 17786 → 17789) was stopped with SIGTERM. The 8765 relay was left running. A first restart attempt was allowed to fail closed because `uv` tried to create a worktree-local `.venv` on `/mnt/e` and missed the readiness deadline. The successful run used the ext4 venv `/home/pepepig/.venvs/sirov2` and the private token file; no token value was logged.

The current Gateway is the foreground process from this worktree, PID 20351, listening on `127.0.0.1:8000`. `GET /health/live` returned HTTP 200. Its environment contains `SIRO_ESP32_RELAY_TOKEN` (value redacted). A direct POST to `/v1/devices/esp32/events` with the private token and an intentionally unknown event returned HTTP 400, proving the request passed token authentication and reached event validation; the disabled-ingress response would be 503.

## Fresh World State evidence

Read-only SQLite inspection after the restart found fresh observations with source `device:siro-node-01:esp32_http`:

| property | value | observed_at (UTC) |
| --- | ---: | --- |
| illuminance | 228.3 | 2026-10-26T16:41:02.529405+00:00 |
| illuminance | 231.7 | 2026-10-26T16:41:12.546826+00:00 |
| illuminance | 233.3 | 2026-10-26T16:41:22.526218+00:00 |
| illuminance | 233.3 | 2026-10-26T16:41:32.553598+00:00 |
| illuminance | 230.0 | 2026-10-26T16:41:52.546738+00:00 |
| illuminance | 230.8 | 2026-10-26T16:42:02.638876+00:00 |

The light stream is fresh at roughly ten-second intervals and is evidence of ESP32 → Windows relay → Gateway → World State persistence. The latest persisted motion rows are older (`2026-10-23T21:02:57Z`); no button row was produced during this observation window, so a new physical PIR/button acceptance is not claimed here.

## Automated validation

- `bash -n scripts/start-companion scripts/load-esp32-relay-token`: PASS.
- Token-loader plus desktop entry tests: 49 passed in 12.05s.
- ESP32 ingress, parser, telemetry, Gateway, device registry, and room automation tests: 45 passed in 18.18s (one Starlette deprecation warning).
- Python Ruff check and format check for affected tests: PASS.

## Limits and next action

The live service is running from the isolated local worktree and is `LOCAL_ONLY / NOT PUSHED`. The main checkout still has the user's uncommitted `desktop/host.js`; it was not changed. A future owner can stop the foreground Gateway session, integrate the two local commits into an explicitly selected branch, and repeat the real hardware motion/button check if needed.
