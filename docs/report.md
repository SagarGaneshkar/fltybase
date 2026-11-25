# Project report

## Approach

The implementation is a single-process replay pipeline: load JSON telemetry and text descriptions, extract entities, update cross-frame state, evaluate alert rules, and write the frame/object/alert result to SQLite. The user-facing CLI shares the indexer with its query, summary, and question-answering commands. The system is offline-first; optional hosted models do not participate in tests.

## Assumptions

- The simulated descriptions accurately state the visible objects and activities.
- The 50 frames represent one patrol day on a single property with five known zones.
- The rule-based extractor is a deterministic prototype, not a visual model.
- The configured LLM choice is `openai` or `gemini`; a missing provider key selects the local fallback.
- “Consecutive frames” means detections in neighboring replay frames, while the two-minute rule uses the elapsed time between a track's first observation and the current frame.
- A known vehicle list currently includes the blue Ford F150 and delivery van.

## Tool and design justifications

- **SQLite FTS5 vs. a vector database:** relational telemetry, objects, and alerts fit SQLite and need no service. FTS5 supports exact keyword lookup and is adequate for this fixed prototype; embeddings and semantic retrieval are future work.
- **BLIP vs. CLIP:** BLIP is used only as an optional image-caption demo because the desired output is a text caption. CLIP is more appropriate for image/text similarity or zero-shot matching, which is not on the critical path here.
- **Agent design:** common questions route to typed indexer operations locally for predictable, testable output. With a provider key, the same operations are exposed as LangChain tools and chat history is retained. This avoids an LLM dependency for ordinary runs.
- **SQLite schema:** frame rows retain original source context; object and alert rows are separately queryable and linked by frame ID; FTS5 indexes frame descriptions.

## Sample output

```text
Blue Ford F150 truck spotted at garage, 12:00.
[HIGH] Person loitering at main_gate, 00:01
[MEDIUM] Altitude anomaly: 150 m at garage, 11:30
The blue Ford F150 entered 2 times today.
```

## Improvements with more time

- Ingest real video and telemetry through OpenCV and a production VLM.
- Add embeddings/vector search for semantically similar events.
- Generate video/shift summaries with evidence links and confidence.
- Support multiple drones, properties, and tenant isolation.
- Deliver streaming alerts through a webhook or Slack integration.
- Improve visual identity tracking and configure alert thresholds per property.

## AI tools assisted

_Fill in the AI tools used, what they contributed, and how generated code or documentation was reviewed and validated._
