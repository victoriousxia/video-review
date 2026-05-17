"""Hermes gateway integration example for video-review approval interceptor.

Copy this snippet into /opt/hermes/gateway/run.py, BEFORE the normal LLM
dispatch logic. Adjust the import path or use subprocess mode depending on
your deployment.

Option A: Direct import (same filesystem, e.g. NAS host or shared volume)
Option B: Subprocess call (cross-container or isolated environments)
"""

# ===========================================================================
# Option A: Direct import
# ===========================================================================
#
# Add to the top of /opt/hermes/gateway/run.py:
#
#   import sys
#   sys.path.insert(0, "/nas/docker/video-review/scripts")
#   from hermes_gateway_interceptor import try_intercept
#
# Then in your message handler, before LLM dispatch:
#
#   def handle_message(platform, chat_id, text, thread_id=None, reply_to_message_id=None):
#       # --- video-review approval interceptor ---
#       vr_result = try_intercept(
#           platform=platform,        # "telegram" or "weixin"
#           chat_id=chat_id,
#           text=text,
#           thread_id=thread_id,
#           reply_to_message_id=reply_to_message_id,
#       )
#       if vr_result["handled"]:
#           send_reply(chat_id, vr_result["message"], thread_id=thread_id)
#           return  # skip LLM dispatch
#       # --- end interceptor ---
#
#       # ... normal Hermes LLM dispatch continues here ...


# ===========================================================================
# Option B: Subprocess call
# ===========================================================================
#
#   import json
#   import subprocess
#
#   def try_vr_intercept(platform, chat_id, text, thread_id=None, reply_to_message_id=None):
#       cmd = [
#           "python3",
#           "/nas/docker/video-review/scripts/hermes_gateway_interceptor.py",
#           "--platform", platform,
#           "--chat-id", chat_id,
#           "--text", text,
#       ]
#       if thread_id:
#           cmd.extend(["--thread-id", thread_id])
#       if reply_to_message_id:
#           cmd.extend(["--reply-to-message-id", reply_to_message_id])
#
#       try:
#           proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
#           if proc.returncode == 0:
#               return json.loads(proc.stdout)
#       except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
#           pass
#       return {"handled": False}
#
# Then in your message handler:
#
#   def handle_message(platform, chat_id, text, thread_id=None, reply_to_message_id=None):
#       vr_result = try_vr_intercept(platform, chat_id, text, thread_id, reply_to_message_id)
#       if vr_result["handled"]:
#           send_reply(chat_id, vr_result["message"], thread_id=thread_id)
#           return
#       # ... normal Hermes LLM dispatch ...


# ===========================================================================
# Key behaviors:
# ===========================================================================
#
# 1. "1", "2", "3" (bare digits):
#    - If exactly one active approval in this chat/thread: executes the action.
#    - If multiple active approvals: returns ambiguity message with VR codes.
#    - If no active approvals: handled=false, continues to LLM.
#
# 2. "1 VR-XXXX", "2 VR-XXXX", "3 VR-XXXX":
#    - Matches the specific operation by its VR token.
#
# 3. "DELETE_PERMANENTLY <operation_id>":
#    - Executes permanent deletion (only after user chose option 2 first).
#
# 4. Any other text (e.g. "hello", "what's the weather"):
#    - Quick regex check fails → handled=false immediately.
#    - No subprocess call, no latency added to normal messages.
