# Spec: quote_capture (local_client)

DRAFT, not approved. Design approved by the user (terminal, 2026-11-23); see `05-module-specs.md` ("Gap 2: quote_capture").

Recorded rule (Phase 2: references, answer 1): "The full session transcript stays local in the harness client; when something is referenced, the client sends only that reference to the server to be stored." So every prompt is captured to a **local client cache**; only exchanges that get referenced are synced to the server.

## What's copied in from source-of-truth (commit d22d770), kept mostly intact

```
local_client/
  harness_adapters/
    ai_cli_adapter_interface.py         AiCliAdapterInterface: get_current_session_id, register_user_prompt_submit_hook,
                                        inject_into_next_user_turn, inject_into_subagent_spawn, spawn_persistent_reviewer_session
    claude_code/
      ai_cli_adapter_claude_code.py     the Claude Code implementation
      user_prompt_submit_hook.py        verbatim prompt + pre-text, written to the local cache
      claude_cli_get_recent_agent_messages.py   reads the preceding turn's agent output from the transcript
      post_tool_use_capture_askuserquestion_answers.py   answers given in question dialogs, to the local cache
      install.py                        hook scripts + settings.json patching
    (codex/ later, same interface)
  quote_capture/
    raw_input_log_writer.py             kept: appends each exchange to the local client cache (as in SoT)
    raw_input_log_reader.py             kept: reads exchanges by local id
    reference_sync.py                   NEW: sends one exchange to the server when it is referenced
  client_credentials                    the install's quote key
```

## The one new piece

```python
class ReferenceSync:
    def sync(self, local_exchange_id) -> ReferenceId
        # reads the exchange from the local cache and POSTs it to the server's store_user_exchange
        # with the quote key; returns the server's reference id (same content = same reference)
```

Called when the agent cites a local exchange (e.g. through the CLI's cite command). Nothing else leaves the machine.

## External integration tests (mocked server)

1. A submitted prompt is written to the local cache verbatim, with the preceding agent output as pre-text; nothing is sent to the server.
2. An interrupted previous turn still yields its pre-text on the next prompt.
3. An answer chosen in a question dialog is written to the local cache as an exchange (question + answer).
4. Citing a local exchange syncs exactly that exchange to the server, using only the quote key, and returns its reference id.
5. Syncing the same exchange twice gives the same reference (hash reuse).
6. A second adapter implementing AiCliAdapterInterface can be swapped in without changing quote_capture (proves Codex can plug in later).
