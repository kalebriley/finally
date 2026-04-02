# Review

Reviewed the current working tree against `HEAD` (`6b568a9`) on 2026-04-02.

## Findings

1. High - The new Claude review automation is disabled by its own config (`.claude/settings.json:5-12`).

The change adds a `Stop` hook that shells out to `codex exec ...`, but the same file also sets `disableAllHooks` to `true`. Anthropic's Claude Code settings docs define that flag as a global hook kill switch, so this review command will never fire in practice.

Source: [Anthropic Claude Code settings](https://docs.anthropic.com/en/docs/claude-code/settings)

1. High - The README and plan now describe a runnable app scaffold that does not exist in the repo (`README.md:7-22`, `planning/PLAN.md:90-107`, `planning/PLAN.md:136`, `planning/PLAN.md:636-648`).

`README.md` tells users to run `cp .env.example .env` and `./scripts/start.sh`, and `PLAN.md` says `frontend/`, `backend/`, `scripts/`, `db/`, `test/`, `Dockerfile`, and `.env.example` are already present. In the current tree none of those files or directories exist. A fresh clone following the new README fails immediately, and agents treating `PLAN.md` as the repo contract will make incorrect assumptions about what is already scaffolded.

1. High - The Massive "free tier live data" design cannot work as documented (`planning/PLAN.md:170-190`).

The plan says the app can use Massive's free tier to poll live quotes from `GET /v3/quotes/{stockTicker}` at 5 calls/minute. Massive's current Stocks Basic access is end-of-day only at 5 calls/minute; quote and snapshot access are on higher tiers. That means the optional "real data on the free tier" path is not implementable as written.

Sources: [Massive pricing](https://massive.com/pricing?product=stocks), [Massive business pricing](https://massive.com/business?business-pricing=stocks-business), [Massive quotes docs](https://massive.com/docs/stocks/get_v3_quotes__stockticker)

1. Medium - The plan hard-codes "no batch endpoint" into the architecture even though that is, at most, a free-tier limitation rather than a platform-wide Massive constraint (`planning/PLAN.md:170`, `planning/PLAN.md:189-190`).

`PLAN.md` says there is no batch endpoint and builds round-robin polling, staleness budgets, and a tracked-symbol cap around one-request-per-ticker fetching. Massive also exposes stock snapshot endpoints, and their docs describe snapshot data products separately from per-ticker quote history. Even if the one-ticker approach is the only free-tier fallback, the current wording presents it as a universal API limitation and will push paid-tier implementations toward unnecessary complexity.

Sources: [Massive snapshot docs](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot), [Massive business pricing](https://massive.com/business?business-pricing=stocks-business)

1. Medium - The Massive tracked-symbol cap conflicts with the later "trade any ticker" guarantee (`planning/PLAN.md:190`, `planning/PLAN.md:478-479`).

The plan caps Massive free-tier tracking at 25 symbols across watchlist plus open positions, but later promises that off-watchlist tickers can always be synchronously seeded and traded. There is no rule for what happens when that trade would become symbol 26. An implementation either violates the cap immediately or opens a position that cannot continue receiving updates afterward.

1. Medium - The LLM contract promises Cerebras-specific behavior without actually pinning routing or requiring schema-capable providers (`README.md:20`, `planning/PLAN.md:489-508`, `planning/PLAN.md:522`).

The docs say the backend uses OpenRouter "with Cerebras" and relies on structured outputs, but the example request only sets the model name. OpenRouter's provider-routing docs say requests are load-balanced across top providers unless `provider.order` is set, and `require_parameters` defaults to `false`. As written, the implementation cannot rely on Cerebras latency or on every routed provider honoring the JSON-schema parameters the plan treats as mandatory.

Source: [OpenRouter provider routing](https://openrouter.ai/docs/features/provider-routing)

1. Low - The reviewer-agent replacement is not fully included in the tracked change set and is internally inconsistent (`.claude/agents/codex-reviewer.md:2-10`).

The tracked `change-reviewer.md` file is deleted, but the replacement `codex-reviewer.md` is still untracked, so committing the current diff as-is removes the reviewer agent entirely. The replacement description also says it reviews `PLAN.md` specifically, while its body instructs a full working-tree review of all changes since the last commit.

## Assumptions

- This review covers the current working tree, including the untracked `.claude/agents/codex-reviewer.md`.
- External API and provider findings were checked against the current vendor docs available on 2026-04-02.