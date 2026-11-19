# Dev log

Notable changes between commits. Supplement git history with a short note here when you make significant changes.

---

- **Snapshot restore:** Preserve all world-owned tables, scope child rows through their parents, and restore in foreign-key dependency order without silently swallowing serialization errors.

- **Weekly conditioning:** Batch active-wrestler stats and recent match counts per world; retain standalone conditioning lookups. Added constant-query regression coverage and a seeded 28-day parity benchmark (`scripts/benchmark_weekly_conditioning.py`).

- **Daily social posts:** Load gimmicks, backstories, active contracts and federations once per daily tick, on the first post, instead of per posting wrestler; post content and RNG order are unchanged.

- **Friday persona tick:** Batch persona reads for each world while preserving lazy backstory creation and the order of life-event effects and collision rolls.

- **Double elimination (#68):** Added explicit winner/loser destination slots, deterministic winners/losers topology, loss-free bye propagation, dependency-based readiness, and a conditional reset final. Existing single-elimination progression is unchanged. Policy and compatibility details are in `docs/TOURNAMENTS.md`.

- **Root reorg:** Moved long-form docs to `docs/` (ANALYSIS, USAGE_GUIDE, ENHANCEMENT_PROPOSAL, codebase, security, implementation summaries, etc.) and demo/helper scripts to `scripts/` (demo.py, demo_multi.py, activate_env.sh). Updated README, AGENTS.md, and in-repo links accordingly.

- **Project review cleanup:** Added AGENTS.md (layout and run commands), DEVLOG.md, Pydantic v2 fix, pyproject.toml for editable install, engine DB session per tick, README frontend clarification.

- **Documentation consolidation:** Added `docs/STATUS.md` as the current source of truth for known limitations and priorities, clarified the two frontend surfaces, and labeled older audits, implementation summaries, and proposals as historical or aspirational.
