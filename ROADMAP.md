# Roadmap

## v0.1.0 Project skeleton
- Docker service starts
- FastAPI health check
- SQLite path/config wiring
- project docs and Git repository

## v0.2.0 Scan and metadata
- create review jobs
- scan video files
- ffprobe metadata extraction
- job list UI

## v0.3.0 Screenshot batches
- default multi-frame screenshots
- per-video regenerate
- uniform/random/manual timestamp strategies
- screenshot batch history

## v0.4.0 Review decisions
- save per-video decisions
- filters and progress
- batch decision updates

## v0.5.0 Organization suggestions
- movie/series/anime/documentary heuristics
- target path suggestions
- sample/incomplete detection

## v0.6.0 Dry-run execution plans
- generate plan from reviewed decisions
- show moves/renames/trash candidates
- no filesystem mutation

## v0.7.0 Safe executor
- execute only after external confirmation
- move companion subtitle/nfo/artwork files
- trash instead of delete
- execution log

## v0.8.0 Hermes integration
- command-triggered scan
- notification links
- review-state checks
- plan/execution orchestration

## v1.0.0 Stable daily workflow
- complete review-to-execute loop
- Lucky deployment docs
- tests and migration story
