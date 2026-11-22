# Performance Report

## Measured

Environment: local Docker Desktop, API container, PostgreSQL container, warm caches, single
client, one pass per endpoint. Session authenticated as `ops@demo.roadguard.ai`.

Method: log in, fetch `/openapi.json`, then time every parameterless `GET` operation.

```
GET endpoints measured: 23
median 5 ms | p95 7 ms | max 9 ms
9 ms  200  35190 B  /api/v1/incidents
7 ms  200   7054 B  /api/v1/contracts
7 ms  200    545 B  /api/v1/incidents/analytics
6 ms  200  33232 B  /api/v1/investigations
6 ms  200   3546 B  /api/v1/hotspots/geojson
5 ms  200  29181 B  /api/v1/jobs
5 ms  200   8720 B  /api/v1/accident-records
5 ms  200  21869 B  /api/v1/work-orders
```

`/api/v1/health/ready` measured 24 ms on a cold probe (first DB round-trip); steady-state
health checks are sub-millisecond in the API log.

Frontend: the command dashboard issues 8–10 parallel requests and rendered fully within the
browser snapshot; no request exceeded 10 ms server-side. OSM tiles are external and dominate
visual load time.

## Not measured (do not infer)

| Area | Why |
| --- | --- |
| Upload throughput for large files | No large fixture; only the 12 s clip |
| Worker CPU/memory and queue backlog under load | No instrumentation or load generator |
| WebSocket stability over time | Only connection establishment verified |
| Browser memory / re-render profiling | No DevTools trace captured |
| Database performance at 10⁶+ rows | Demo volume is 3,009 detections, 27 incidents |
| Concurrent-user behaviour | Single client |

## Observations

- Hotspot GeoJSON (3.5 KB) is cheap because aggregation runs in PostGIS, not in Python.
- Incident list (35 KB) is the heaviest response; pagination parameters exist but the default
  page is large. At production volume this should be paginated client-side.
- No N+1 pattern appeared in the measured endpoints; the largest responses are single queries
  with serialisation cost.

## Conclusion

The API is fast at demo scale. No claim is made about production-scale performance, and no
load test was run — the brief allowed load testing "against the isolated development environment
only", but no load tooling is installed here.
