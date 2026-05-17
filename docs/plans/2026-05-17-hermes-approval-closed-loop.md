# Video Review Hermes Approval Closed Loop Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build an event-driven approval closed loop for video-review delete operations: click delete in video-review, notify Hermes immediately, send approval prompts to Telegram/Weixin, bind replies/buttons to the operation, and execute the chosen safe file operation.

**Architecture:** Keep video-review as a generic Docker web app that only creates pending operation JSON and emits a local notification. Add a small, persistent approval state under `/nas/docker/video-review/data/operations` so Hermes gateway can associate Telegram/Weixin replies with a specific operation after restarts. The current repository work implements the video-review side of the loop: immediate notify hook, persistent approval state, reply resolver, watchdog fallback, tests, and docs. Hermes gateway message routing is intentionally not patched in this commit; that next step is handed off to Claude Code. Keep the existing 5-minute watchdog as a fallback notifier.

**Tech Stack:** FastAPI/Python app in `/nas/docker/video-review`; Hermes gateway Python code in `/opt/hermes/gateway`; local JSON state files; existing `send_message` tool/script path; pytest.

---

## Safety invariants

- video-review web service must never directly unlink or move NAS media files.
- Default action `1` moves files to `.video-review-trash`, not permanent deletion.
- Action `2` must not permanently delete on first reply; it enters a second explicit confirmation state.
- If multiple active approvals exist in one chat/thread and the user replies only `1/2/3`, Hermes must refuse ambiguity and ask for an operation code/token.
- State must be persisted so gateway restarts do not lose active approvals.
- Keep existing cron watchdog as fallback, but hook-triggered notification is the primary path.
- Hermes gateway 消息路由尚未接入；下一步交给 Claude Code 在 gateway 文本入口调用 `resolve-reply`。

---

### Task 1: Add persistent approval state module in video-review

**Objective:** Create a reusable module that records active approval prompts and resolves replies safely.

**Files:**
- Create: `scripts/hermes_operation_state.py`
- Test: `tests/test_hermes_operation_state.py`

**Implementation notes:**

State path:

`/nas/docker/video-review/data/operations/.hermes-approvals.json`

Each record should include:

```json
{
  "operation_id": "op_...",
  "token": "VR-D21E",
  "status": "awaiting_choice",
  "created_at": "...",
  "expires_at": "...",
  "notifications": {
    "telegram": [{"chat_id":"...", "thread_id":"...", "message_id":"..."}],
    "weixin": [{"chat_id":"...", "message_id":"..."}]
  }
}
```

Functions:

- `load_state(path) -> dict`
- `save_state(path, state)` with atomic write
- `upsert_operation(operation_id, token=None, expires_hours=72)`
- `record_notification(operation_id, platform, chat_id, thread_id=None, message_id=None, session_key=None)`
- `find_match(platform, chat_id, thread_id, text, reply_to_message_id=None)`
  - exact token match wins
  - reply_to message id match wins
  - single active approval in chat/thread allows bare `1/2/3`
  - multiple active approvals with bare `1/2/3` returns ambiguity
- `mark_resolved(operation_id, result)`

**Verification:**

Run:

```bash
uv run python -m pytest tests/test_hermes_operation_state.py -q
```

Expected: all tests pass.

---

### Task 2: Add immediate notify script

**Objective:** Notify Telegram and Weixin immediately when an operation is created, and persist approval bindings.

**Files:**
- Create: `scripts/hermes_pending_operation_notify.py`
- Modify: `scripts/hermes_pending_operation_watchdog.py`
- Test: `tests/test_hermes_pending_operation_notify.py`

**Implementation notes:**

The notify script accepts:

```bash
python3 scripts/hermes_pending_operation_notify.py op_xxx
```

It should:

1. Load operation plan using existing `hermes_operation_approval.py` helpers.
2. Generate or reuse short token `VR-XXXX`.
3. Render Weixin prompt with token and choices.
4. Render Telegram prompt with token and choices.
5. Send to both platforms using `send_message` CLI/tool-compatible path if available.
6. Record notification state.
7. Be idempotent: same operation should not spam unless called with `--force`.

Watchdog should call this script instead of duplicating send logic.

**Verification:**

Run:

```bash
python3 -m py_compile scripts/hermes_pending_operation_notify.py scripts/hermes_pending_operation_watchdog.py
uv run python -m pytest tests/test_hermes_pending_operation_notify.py -q
```

---

### Task 3: Wire notify hook into video-review delete operation creation

**Objective:** When the web app creates pending operation JSON, invoke the notify script asynchronously/best-effort.

**Files:**
- Modify: `app/operations.py` or `app/main.py` at the delete request creation call site
- Possibly modify: `app/config.py`
- Test: existing operation/delete tests plus new hook test

**Implementation notes:**

After `write_operation_request(...)` succeeds:

- Start subprocess:

```python
subprocess.Popen(
    ["python3", "/nas/docker/video-review/scripts/hermes_pending_operation_notify.py", operation_id],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
```

- Failures must not fail the web request; pending JSON is still the source of truth.
- Add env/config flag to disable hook for tests if needed, e.g. `VIDEO_REVIEW_HERMES_NOTIFY_ENABLED` default true.

**Verification:**

- Unit test mocks subprocess and verifies it is called after pending JSON write.
- Existing delete operation tests still pass.

---

### Task 4: Add non-LLM approval action runner

**Objective:** Provide one script that gateway can call when a reply/button is received.

**Files:**
- Modify: `scripts/hermes_operation_approval.py`
- Test: `tests/test_hermes_operation_approval.py`

**Implementation notes:**

Add command:

```bash
python3 scripts/hermes_operation_approval.py resolve-reply \
  --platform weixin \
  --chat-id ... \
  --thread-id ... \
  --text 1 \
  --reply-to-message-id ...
```

Return JSON:

- handled trash:

```json
{"handled": true, "message": "已扔垃圾桶...", "operation_id":"op_..."}
```

- delete request:

```json
{"handled": true, "message": "永久删除需要二次确认...", "operation_id":"op_...", "requires_confirmation": true}
```

- ambiguity:

```json
{"handled": true, "message": "当前有多个待处理...请回复 1 VR-XXXX", "ambiguous": true}
```

- no match:

```json
{"handled": false}
```

**Verification:**

Run:

```bash
uv run python -m pytest tests/test_hermes_operation_approval.py tests/test_hermes_operation_state.py -q
```

---

### Task 5: Patch Hermes gateway text intercept

**Objective:** Before normal LLM dispatch, consume video-review approval replies from Telegram/Weixin.

**Files:**
- Modify: `/opt/hermes/gateway/run.py`
- Test: targeted Hermes gateway tests if practical; otherwise py_compile + manual smoke

**Implementation notes:**

Patch `_handle_message` after auth and before clarify/slash-confirm intercepts:

1. Only for `Platform.TELEGRAM` and `Platform.WEIXIN`.
2. Ignore slash commands.
3. If text looks like a video-review approval reply:
   - `1`, `2`, `3`
   - `1 VR-XXXX`, `2 VR-XXXX`, `3 VR-XXXX`
   - `DELETE_PERMANENTLY op_xxx` for second confirmation
4. Call:

```bash
python3 /nas/docker/video-review/scripts/hermes_operation_approval.py resolve-reply ...
```

5. If JSON says `handled: true`, return its message and skip LLM.
6. If `handled: false`, continue normal dispatch.

**Verification:**

```bash
python3 -m py_compile /opt/hermes/gateway/run.py
```

Manual smoke after restart:

- send normal chat: still works
- send `1` with no active approval: goes to normal Hermes, not swallowed
- send `1` with one active approval: executes trash

---

### Task 6: Patch Telegram inline callback handler

**Objective:** Telegram buttons should execute without requiring text reply.

**Files:**
- Modify: `/opt/hermes/gateway/platforms/telegram.py`

**Implementation notes:**

In `_handle_callback_query`, before built-in callback groups, handle data starting with `vr|`:

- `vr|trash|op_xxx` -> run action `1`
- `vr|delete_request|op_xxx` -> run action `2`
- `vr|cancel|op_xxx` -> run action `3`

Use existing callback authorization helper `_is_callback_user_authorized`.

On success:

- `query.answer(...)`
- edit original message to show result and remove keyboard
- send follow-up if needed for second confirmation

**Verification:**

```bash
python3 -m py_compile /opt/hermes/gateway/platforms/telegram.py
```

Manual smoke after restart: button click removes keyboard and executes/cancels.

---

### Task 7: Docs and deployment notes

**Objective:** Document user-facing workflow and rollback.

**Files:**
- Modify: `docs/hermes-operation-executor.md`
- Create or modify: `docs/hermes-approval-closed-loop.md`
- Modify: `docs/progress.md`

**Content:**

- Primary hook path
- Watchdog fallback
- Reply syntax
- Multiple pending behavior
- Permanent delete second confirmation
- Recovery/rollback steps
- Gateway restart requirement

---

### Task 8: Full verification and deploy

**Objective:** Validate repo tests, compile patched Hermes files, restart gateway only after confirmation.

**Commands:**

```bash
cd /nas/docker/video-review
uv run python -m pytest tests/test_hermes_operation_executor.py tests/test_hermes_operation_approval.py tests/test_hermes_operation_state.py tests/test_hermes_pending_operation_notify.py tests/test_operations.py -q
python3 -m py_compile scripts/hermes_operation_executor.py scripts/hermes_operation_approval.py scripts/hermes_operation_state.py scripts/hermes_pending_operation_notify.py scripts/hermes_pending_operation_watchdog.py
python3 -m py_compile /opt/hermes/gateway/run.py /opt/hermes/gateway/platforms/telegram.py
```

Restart gateway only after explicitly telling the user:

```bash
hermes gateway restart
```

or in NAS compose deployment, rebuild/recreate according to the existing Hermes NAS custom image workflow if source patches need to persist across container recreation.

---

## Rollback

- Revert video-review commits:

```bash
cd /nas/docker/video-review
git revert <commit>
```

- Revert Hermes gateway files from source control/custom image patch.
- Disable cron watchdog if needed:

```bash
hermes cron list
hermes cron pause <job_id>
```

Existing pending operation JSON files remain safe; they are not executed without explicit approval.
