"""A stand-in for `claude -p --input-format stream-json` used by the agent tests.

Reads user messages from stdin and answers each with a `result` line, after an
optional delay (FAKE_CLAUDE_DELAY seconds). Records its argv to FAKE_CLAUDE_LOG.
A message whose text is "crash" makes it exit without answering. A message "pide <command>"
is answered as a turn in which that Bash command was refused by the permission rules.
"""

import json
import os
import sys
import time

log = os.environ.get("FAKE_CLAUDE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(sys.argv[1:]) + "\n")
delay = float(os.environ.get("FAKE_CLAUDE_DELAY", "0"))
sid = sys.argv[sys.argv.index("--session-id") + 1] if "--session-id" in sys.argv else \
    sys.argv[sys.argv.index("--resume") + 1] if "--resume" in sys.argv else "none"
print(json.dumps({"type": "system", "subtype": "init", "session_id": sid}), flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    text = msg["message"]["content"]
    if text == "crash":
        sys.exit(1)
    time.sleep(delay)
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": f"eco: {text}"}]}}), flush=True)
    refused = [{"tool_name": "Bash", "tool_use_id": "t1", "tool_input": {"command": text[5:]}}] if text.startswith("pide ") else []
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": f"eco: {text}",
                      "session_id": sid, "num_turns": 1, "permission_denials": refused}, ensure_ascii=False), flush=True)
