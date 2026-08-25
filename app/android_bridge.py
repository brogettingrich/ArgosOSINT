"""
Shared state between the Starlette server (app/main.py) and the Android
native layer (root main.py).

The URL queue is the bridge for external-link opening:
  1. JS clicks "OPEN PROFILE" on a found result
  2. JS posts to /api/open-external?url=...
  3. Starlette puts the URL here
  4. A background thread in main.py pops it and fires an Android Intent
"""
import queue

# Thread-safe queue for URLs that should be opened externally via Android Intent
pending_external_urls: queue.Queue = queue.Queue()
