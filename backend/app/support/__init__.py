"""
VIDHIVEDA User Guide & Support Assistant subsystem.

This package is intentionally separate from ``app/rag`` (legal research). The two
answer different questions and draw on different stores:

* ``app/rag``   — retrieves legal authorities from the indexed case-law corpus.
* ``app/support`` — explains how the product works, from project-owned support
  articles, structured troubleshooting data, a capability registry and the demo
  example gallery.

The support assistant never performs a legal search and never writes into the
legal corpus or the OKF bundle.
"""
