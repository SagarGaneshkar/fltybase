# Testing

Run the complete offline suite from the repository root:

```powershell
python -m pytest -q
```

The tests use temporary or in-memory databases and remove hosted provider keys for deterministic execution.

| Scenario | Input | Expected result |
|---|---|---|
| Vehicle extraction | Blue Ford F150 entering main gate | Vehicle with blue color, Ford F150 model, correct zone/activity |
| Multiple/empty/malformed detections | Person and sedan; empty text; unreadable text | Two entities for mixed text and no detections for empty/malformed input |
| Loitering and nighttime | Three consecutive gate-person frames from 00:01; perimeter person at 02:30 | One HIGH loitering alert timestamped 00:01 and HIGH night-person alerts |
| Normal daytime vehicle | Delivery van in driveway at 14:00 | No unknown-night alert |
| Telemetry safety | One altitude of 150 m and one battery level of 15% | One MEDIUM alert for each anomaly |
| Repeat vehicle entry | F150 entering at 07:10 and 18:20 | One LOW repeat-entry alert; two entering events in the index |
| Database time/object queries | Patrol frames indexed in SQLite | Correct 07:00–07:30 frames and seven F150 truck frames |
| Text search | Search `perimeter fence` | Matching descriptions with frame timestamps |
| Agent intents | The five documented questions | Correct object recap, two F150 entries, truck frames, night alerts, and 00:00–01:00 events |
| Out-of-order replay | A later frame passed before an earlier one | Simulator yields chronological order |
| End-to-end | Full 50-frame scenario | Expected alert rules, all frames persisted, alerts logged, and garage/F150 output printed |
