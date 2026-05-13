# Safety Rules

1. Review generation must not move, rename, or delete media files.
2. The web UI may save review decisions but must not directly perform destructive operations in early versions.
3. Delete means move to a task-specific trash folder first, never direct removal by default.
4. Execution requires an explicit external confirmation message from the user.
5. Recently modified, incomplete, or locked files are skipped by default.
6. Every execution plan must be reviewable before it mutates files.
7. Every mutation must write before/after paths to an execution log.
