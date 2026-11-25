# Feature specification

## Value to property owners

The prototype gives a property owner a searchable daily patrol record instead of requiring a manual review of every drone pass. It highlights unusual people, unknown vehicles at night, repeat vehicle entries, and telemetry outside safe bounds while preserving the original frame descriptions for later review.

## Three key requirements

1. **Capture context:** replay timestamped telemetry and frame descriptions in time order; record each frame, detected object, and alert in SQLite.
2. **Surface actionable events:** apply explicit loitering, night-person, unknown-night-vehicle, repeat-entry, altitude, and battery rules, with severity and a persistent alert log.
3. **Support follow-up questions:** search by time, object attributes, alerts, and frame text, then answer common questions deterministically offline or through optional LangChain tools when configured.

## Out of scope

Live flight control, actual visual recognition, dispatching emergency services, and guarantees of identity or intent are outside this prototype.
