# search_global — max_concurrent sweep comparison

Date: 2026-05-30 19:20-19:58 UTC (2 runs per config)  
Testbed: Docker container on box3 (144.31.188.163)  
Account: Alexey (session f9Nd...)  
Settings: delay=5s, warmup=1, iterations=3, floodwait-retry=3, floodwait-cap=60s  
All results: 0 FloodWait hits across all 8 runs (4 configs × 2 re-runs)

### Median latencies (seconds)

| Scenario | unlimited (0) | c2 (default) | c4 | c8 |
|---|---|---|---|---|
| single_term (10) | **0.901** | 1.192 / 0.992 | 0.942 / 0.994 | 0.644 / 1.047 |
| two_terms (10) | **1.445** | 1.440 / 1.358 | 1.388 / 1.501 | 1.159 / 1.257 |
| three_terms (10) | 1.730 | 1.759 / 1.812 | 1.773 / 2.318 | **1.346** / 1.761 |
| five_terms (10) | **1.859** | 2.162 / 2.126 | 2.213 / 1.908 | 2.025 / 2.003 |
| three_terms_large (50) | 5.536 | 6.168 / 6.924 | 6.519 / 5.364 | **4.540** / 6.085 |
| dedup_check (15) | **2.094** | 2.357 / 2.526 | 4.085 / 2.566 | 2.220 / 4.288 |
| fairness_check (20) | 8.534 | 9.178 / 9.296 | **7.406** (vs 29.3 outlier) | 7.018 / 12.639 |

### Key observations
1. **Variance between runs >> variance between configs.** Two re-runs of the same config differ more (e.g. c8 fairness: 7.0s vs 12.6s) than different configs differ.
2. **max_concurrent has no measurable effect** on search_global SearchGlobalRequest performance. The semaphore is a safety valve that never engages during normal operation.
3. **FloodWait = 0 across all runs** — SearchGlobalRequest is not rate-limited on this account. The 80051s FloodWait only affects contacts.SearchRequest.
4. **Default of 2 is fine.** No change needed. The semaphore provides overhead protection without regression.

### Recommendation
Keep `_DEFAULT_MAX_CONCURRENT = 2`. The semaphore is a safety net for future edge cases (highly concurrent multi-term queries on accounts with stricter rate limits), not a performance lever for the current account/workload.
