# Architecture

## Data pipeline

```mermaid
flowchart LR
    S[Scenario JSON] --> SIM[Simulator: sorted frame replay]
    SIM --> DET[Detector: structured LLM or local rules]
    DET --> TR[Tracker: per-object/day context]
    TR --> AE[Alert engine: configured rules]
    DET --> DB[(SQLite indexer)]
    AE --> DB
    DB --> AG[Analyst: tools and offline intent routing]
    AE --> LOG[Alert log file]
    DB --> UI[Local browser dashboard]
    UI --> AG
```

- **Simulator:** loads typed frames and sorts by timestamp; optional replay speed inserts delays.
- **Detector:** extracts object type, color, model, activity, zone, and label from the simulated text. It uses a LangChain structured-output model only when a configured provider key exists.
- **Tracker:** accumulates first/last seen times, event counts, consecutive-frame counts, and zones visited.
- **Alert engine:** evaluates tracker state and telemetry with local rules, suppressing repeated object alerts.
- **Indexer:** stores source frames, detections, and alerts and maintains an FTS5 description index.
- **Analyst:** answers via the same indexer operations in either local intent-routing or optional tool-calling mode.
- **Dashboard:** serves a dependency-free local browser UI for patrol controls, live output, alerts, frame searches, and analyst Q&A.

## Database schema

```mermaid
erDiagram
    FRAMES ||--o{ OBJECTS : contains
    FRAMES ||--o{ ALERTS : raises
    FRAMES ||--|| FRAMES_FTS : indexes
    FRAMES {
        text id PK
        text ts
        text zone
        real lat
        real lon
        real altitude
        real battery
        text description
    }
    OBJECTS {
        integer id PK
        text frame_id FK
        text type
        text color
        text make_model
        text activity
        text label
    }
    ALERTS {
        integer id PK
        text frame_id FK
        text ts
        text rule
        text severity
        text message
    }
    FRAMES_FTS {
        text frame_id
        text description
    }
```

The frame ID is the scenario's stable ID. Object and alert rows reference that frame; deleting/replaying a frame replaces its associated records. `frames_fts` is an FTS5 virtual table kept in sync as each frame is indexed.
