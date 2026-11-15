# The AI designer runs with only our prompt and tools, and is the only step that sends data off the computer
- status: accepted
- by: Alec-42, 2026-11-15

Replaces the privacy half of the superseded "nothing leaves the computer" decision.

- For now the designer runs through headless Claude Code on Alec's subscription, started so that it sees
  only our system prompt and our four tools: no Claude Code prompt, no built-in tools, no CLAUDE.md,
  settings, plugins, or skills. That makes it behave as it will through the API. The exact flags are in
  `docs/ARCHITECTURE.md`; `bricksnap/designer/parity.py` checks them.
- The prompt and tool definitions are plain files, so they move to the API unchanged. The API key is not
  used until Alec says so, because it costs money per run.
- Everything else runs locally. Starting a design run sends pictures and a text description of the model
  to Anthropic. Nothing else is ever sent anywhere: no analytics, no accounts, no uploads.

## Responses
