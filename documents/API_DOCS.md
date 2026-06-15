# KOL API Notes

Simulator và realtime dashboard dùng chung bộ KOL sample:

```text
yt_beauty_02     Glow Lab          trusted
tt_food_03       Saigon Food Map   trusted
yt_tech_01       Tech Insight VN   trusted
yt_finance_04    Money Signal      risky
tt_lifestyle_05  Daily Style       watch
```

Simulator local:

```text
http://127.0.0.1:8010
```

Realtime API local:

```text
http://127.0.0.1:8000
```

API shape dùng chung:

```text
GET /api/kols
GET /api/kols/{kol_id}/live
GET /api/kols/{kol_id}/metrics
GET /api/kols/{kol_id}/events?limit=100
GET /api/kols/{kol_id}/export/bundle
GET /api/kols/{kol_id}/export/features
GET /api/kols/{kol_id}/export/kol_events.jsonl?limit=500
```

Example:

```text
http://127.0.0.1:8010/api/kols/yt_finance_04/live
http://127.0.0.1:8010/api/kols/yt_finance_04/export/features
http://127.0.0.1:8000/api/kols/yt_finance_04/live
```
