# Spec: quote_capture (local_client)

DRAFT, not approved. Design approved by the user (terminal, 2026-11-23); see `05-module-specs.md` ("Gap 2: quote_capture").

## What's copied in from source-of-truth (commit d22d770), kept mostly intact

```
local_client/
  harness_adapters/
    ai_cli_adapter_interface.py         AiCliAdapterInterface: get_current_session_id, register_user_prompt_submit_hook,
                                        inject_into_next_user_turn, inject_into_subagent_spawn, spawn_persistent_reviewer_session
    claude_code/
      ai_cli_adapter_claude_code.py     the Claude Code implementation
      user_prompt_submit_hook.py        verbatim prompt + pre-text
      claude_cli_get_recent_agent_messages.py   reads the preceding turn's agent output from the transcript
      post_tool_use_capture_askuserquestion_answers.py   answers given in question dialogs
      install.py                        hook scripts + settings.json patching
    (codex/ later, same interface)
  quote_capture/
    exchange_sender.py                  NEW: replaces raw_input_log_writer's local append
  client_credentials                    the install's quote key
```

## The one new piece

```python
class ExchangeSender:
    def send(self, session_id, user_message, pre_text) -> ReferenceId
        # POST to the server's store_user_exchange with the quote key; returns the new reference id
```

Called by the `UserPromptSubmit` hook and the AskUserQuestion capture in place of the local log write. If the server is unreachable: (open question, below).

## External integration tests (mocked server)

1. A submitted prompt is sent verbatim, with the preceding agent output as pre-text.
2. An interrupted previous turn still yields its pre-text on the next prompt.
3. An answer chosen in a question dialog is sent as an exchange (question + answer).
4. Only the quote key is used; the request carries no other credential.
5. A second adapter implementing AiCliAdapterInterface can be swapped in without changing quote_capture (proves Codex can plug in later).

## Open question

1. **Server unreachable when a prompt is captured.**
   a. Queue it locally and resend when the server is back (no quote is lost)
   b. Fail visibly in the session; nothing is queued
