---
name: locking-protocol
description: >
  Shared locking protocol for arxiv-fidelity and coding-agent.
  Prevents two parallel agent runs from corrupting the same test directories.
  Load when starting any agent session that uses tests/runs/.
---

## Locking Protocol

Before starting any work, check for a lock file:

```python
LOCK_FILE = Path('tests/runs/.agent.lock')
```

- If the file exists and is **less than 4 hours old**: another agent run is
  in progress. Reply `"Lock held — another agent run is active. Waiting."` and stop.
- If the file exists and is **more than 4 hours old**: it is stale (likely a
  crashed run). Delete it and proceed.
- If the file does not exist: create it with your agent name and the current
  timestamp as content.

Always delete the lock file in a `finally` block — even if you crash or the
user interrupts the session.

If two Claude conversations are running in parallel (e.g. the user has two
browser tabs open), they will both see the same lock file and one will abort.
This is the intended behaviour.

### Step 1 — Acquire lock

Check and create the lock file as described above.

### Final step — Release lock

Always in a `finally` block. Never skip this even if earlier steps fail.
