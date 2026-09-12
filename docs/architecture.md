# Architecture

PART 01 establishes the project boundary:

Next.js frontend -> FastAPI backend -> SQLAlchemy -> SQLite.

The later AI pipeline will follow the specification:
UNDERSTAND -> VALIDATE -> SEARCH -> EXTRACT -> NORMALIZE -> DEDUPLICATE -> FILTER -> SCORE -> RANK -> EXPLAIN -> SHOW EVIDENCE.
