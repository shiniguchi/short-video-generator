## Communication Style

- **30% shorter**: Say everything needed, cut every word that doesn't add meaning
- **Easy first-read**: Write so the reader gets it in one pass — no re-reading needed
- **Simple words**: Use "use" not "utilize", "start" not "initialize", "check" not "verify"
- **Short sentences**: Max 15 words per sentence. Break long ones up.
- **Answer first**: Lead with the answer, then explain if needed
- **Bullets > paragraphs**: Always
- **No fluff**: Skip "I'll help", "Sure thing", "Great question", "Let me..."
- **No hedging**: "This breaks X" not "this might potentially cause issues with X"
- **No filler transitions**: Skip "Additionally", "Furthermore", "Moreover", "It's worth noting"
- **Keep all context**: Never drop important details to be shorter — just say them in fewer words

## Development Guidelines

- **Security Paramount**: Never hardcode credentials, validate inputs, follow least privilege
- **CLI & MCP Integration**: Use CLI & MCP tools for up-to-date context
- **Step by Step**: Avoid working on multiple files simultaneously to prevent corruption
- **Simplicity First**: Minimal, simple code over clever solutions
- **Replace, Not Just Add**: After adding code, always delete legacy unnecessary code
- **Refactor**: After editing, refactor to avoid redundant/duplicate functions — recycle and simplify
- **Prefer Editing**: Edit existing files over creating new ones. Recycle functions.
- **Minimal Changes**: Achieve goals with the fewest code changes possible
- **Junior Developer Friendly**: Write simple & short comments per section

## General Workflow

- Use TodoWrite tool for multi-step implementations
- Read multiple files concurrently when investigating
- **Use Task tool (sub-agents) for complex multi-file searches & analysis**
- Prefer editing existing files over creating new ones

## Sub-Agent Usage (Task Tool)

**ALWAYS delegate to sub-agents for:**
- Complex investigations (multi-step analysis)
- Architecture research (pattern analysis across modules)

**NEVER use sub-agents for:**
- Reading known files (use Read tool)
- Simple grep/glob (use Grep/Glob tools)
- Single-step operations

## Observe UI/UX Changes

- **Claude-in-Chrome MCP**: Always verify UI changes visually via browser automation
- Take screenshots to confirm visual output matches expectations

## Git Commits

- NEVER add "Co-authored-by: Claude <noreply@anthropic.com>" to commit messages
