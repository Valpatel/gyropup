# A delivered message does not wake a completed worker

On 2026-11-11 during PR #315 closeout, follow-up instructions were sent with
`collaboration.send_message` after the target workers had returned final
answers. A later `collaboration.list_agents` result still showed the guide
author and reviewer as `completed`; the expected correction files did not
exist. The instructions were queued, but no new worker turn had started.

The coordinator resumed both tasks with `collaboration.followup_task`. By
09:47 UTC the reviewer had returned the requested resource-policy decision,
and the author had received the active correction task. No source edit,
capture, branch or remote action had happened during the stalled handoff.

Before assigning more work, check whether the worker is running or completed.
Use `followup_task` to start a new turn for a completed worker. Use
`send_message` for steering an already running worker. Confirm the resulting
state or acknowledgement; successful delivery alone is not execution or
progress. Apply the same distinction when reporting progress to the user.

Limits: this incident concerns the collaboration API available in this
session. It does not establish the lifecycle of another agent system, explain
earlier project delays, or require a product-code change. There is no local
repository harness for these external tool lifecycle semantics; the concrete
state check and dispatch correction are the evidence.
