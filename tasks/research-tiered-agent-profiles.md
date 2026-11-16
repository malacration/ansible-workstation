# Research: tiered supervisor and generic developer agent examples

Checked 2026-11-16. All links below were opened and their relevant content inspected. These are examples and documentation, not independently tested implementations. Licenses refer to the repository where identified, not necessarily all linked documentation or dependencies.

## Best findings

| Finding and exact URL | What it offers and limits | Visible license |
|---|---|---|
| [Claude Harness orchestrator](https://github.com/agaleraib/claude-harness) | Closest combined example: universal orchestrator classifies spec tasks at runtime, delegates by Haiku/Sonnet/Opus and also selects `low`–`xhigh` effort; includes verification and escalation. The README says routing needs `model_routing: on`; its linked full orchestrator file returned 404 when opened, so the README is the verified source. No separately verified generic developer prompt. | MIT |
| [Tiered Claude routing gist](https://gist.github.com/mrx-arafat/b88454ffb3507c59947a4a03242c341c/c2c8166f17b293f75b363b8d5ae235b305512246) | Concrete supervisor instructions and generic task workers with models fixed by tier. Mechanical → Haiku, clear-scope coding → Sonnet, difficult/high-stakes → Opus; ambiguity, scope and risk escalate. The Sonnet prompt includes coding, tests and escalation, but is not exclusively a developer. No effort setting shown. | Not visible |
| [claude-orchestrate](https://github.com/midego1/claude-orchestrate/blob/main/README.md) | A detailed four-tier coding rubric, from mechanical edits to ambiguous investigation, with model aliases, verification and retry policy. Standard tier includes implementation and tests; no generic developer profile or effort setting established from this page. | MIT |
| [model-router](https://github.com/strikeout/model-router) | Routing rubric based on judgment and blast radius, with task examples, named model tiers and escalation. Covers general coding, but the opened README alone does not establish a standalone generic developer prompt or per-agent effort. | MIT |
| [CAO built-in supervisor](https://github.com/awslabs/cli-agent-orchestrator/blob/main/src/cli_agent_orchestrator/agent_store/code_supervisor.md) and [developer](https://github.com/awslabs/cli-agent-orchestrator/blob/main/src/cli_agent_orchestrator/agent_store/developer.md) | Real supervisor/developer pair; developer's body is broadly applicable to software work, although its metadata advertises Python and pytest capabilities. The supervisor delegates by role; these profiles do not supply a low/medium/high complexity rubric or per-profile effort. | Apache-2.0, per [repository](https://github.com/awslabs/cli-agent-orchestrator) |
| [CAO Codex profile configuration](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/codex-cli.md#inline-codex-config-overrides) | Actual frontmatter example sets `codexConfig.model_reasoning_effort: "xhigh"`, plus service tier and fast mode, on a developer profile. Per-profile static configuration, not a supervisor rubric or evidence of dynamic effort selection. | Apache-2.0, per CAO repository |
| [CAO decisions and matching](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/decisions.md) | Documented model-size routing (`small`, `medium`, `large`), effort routing (`low`, `medium`, `high`) and task-feature matching; includes configuration examples. Automatic effort applies only to ephemeral `effort: "auto"` helpers, not normal installed-profile delegation. Fixed tables keyed by profile or role cannot match ephemeral effort requests. No concrete supervisor classification prompt verified. | Apache-2.0, per CAO repository |
| [Claude Code custom subagents](https://code.claude.com/docs/en/sub-agents) | Official model and effort frontmatter, plus invocation overrides for non-fork agents. Per-invocation effort requires v2.1.292 or later; environment settings can take precedence. This is an enabling mechanism, not a complexity rubric or generic coding profile. | Not visible |
| [OpenAI Agents SDK routing example](https://github.com/openai/openai-agents-python/blob/main/examples/agent_patterns/routing.py) and [model configuration](https://github.com/openai/openai-agents-python/blob/main/docs/models/index.md) | Concrete triage-and-handoff example routes by language, not coding complexity; documentation allows per-agent models and model settings including reasoning effort. Pre-run routing selects the starting agent, not models for later handoffs automatically. No generic developer or complexity rubric in the example. | Not verified |
| [LangChain Open SWE model router discussion](https://www.langchain.com/blog/how-to-build-a-model-router-in-the-harness) | Explains a classifier prompt, tier criteria and selection of the least expensive capable model for coding tasks. The described router chooses once per thread, not each worker invocation; the opened article does not reproduce a complete generic developer profile. | Not visible |

## Short verbatim excerpts

The excerpts are deliberately short; follow the links for context and licensing.

**Tiered routing supervisor**, [gist](https://gist.github.com/mrx-arafat/b88454ffb3507c59947a4a03242c341c/c2c8166f17b293f75b363b8d5ae235b305512246):

> Escalators (bump one tier up): ambiguity, scope ≥3 files/systems, production/security/data-loss stakes, novelty

**claude-orchestrate supervisor heuristic**, [README](https://github.com/midego1/claude-orchestrate/blob/main/README.md):

> Wrong answer expensive to detect → route up rather than rely on retry.

**CAO generic developer prompt**, [developer.md](https://github.com/awslabs/cli-agent-orchestrator/blob/main/src/cli_agent_orchestrator/agent_store/developer.md):

> Your primary responsibility is to write high-quality, maintainable code based on specifications and requirements provided to you.

**General worker instructions**, [tier-sonnet](https://gist.github.com/mrx-arafat/b88454ffb3507c59947a4a03242c341c/c2c8166f17b293f75b363b8d5ae235b305512246):

> Clear scope, apply judgment, ship quality. Follow existing patterns in codebase.

## CAO-specific conclusion

Yes: CAO documents a **static per-profile reasoning effort** through `codexConfig`, including a complete frontmatter example with `model_reasoning_effort: "xhigh"`. The [configuration reference](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/configuration.md) and [decisions guide](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/decisions.md) also describe automated model and effort decisions. In particular, the guide describes a decider judging task complexity for model size and matching task features against configured models.

The important limitation is that these are distinct mechanisms: installed profiles do not ask `effort.route`, while the automatic effort decision is applied to claimed ephemeral helpers declaring `effort: "auto"`. The documented fixed-table profile/role entries do not match those ephemeral effort requests. The built-in `code_supervisor` and `developer` profiles do not themselves show a concrete complexity rubric selecting worker effort. I did not find a verified CAO example combining that entire prompt-and-routing pattern; this is a search result, not proof no such example exists.

For a practical starting point, the tiered gist supplies explicit classification and escalation instructions, CAO supplies the generic developer body and static Codex effort controls, and Claude Harness supplies the strongest documented example of selecting both model and effort at runtime. Combining them would be a new design, not an existing verified CAO example. Verify actual provider and version support before adopting it.
