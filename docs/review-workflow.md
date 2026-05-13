# Review Workflow

1. User or automation requests scan for a folder.
2. Service creates a review job.
3. Scanner records candidate videos and metadata.
4. Screenshot service creates initial screenshot batches.
5. User opens Review UI through Lucky reverse proxy.
6. User saves per-item decisions.
7. Hermes or another orchestrator checks whether review is complete.
8. Service generates a dry-run execution plan.
9. User confirms through message channel.
10. Executor applies safe operations and records results.
