# Prompt/context management

`PromptBuilder` assembles labeled sections in this order: system
instructions, developer context, conversation history, tool-produced evidence,
and current user message. Tool evidence is explicitly labeled and passed as
structured evidence rather than being presented as an assistant claim.

`POST /prompts/preview` exposes the assembled public message structure for
debugging. It does not expose hidden model scratchpads or provider internals.
