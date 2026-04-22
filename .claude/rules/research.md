# Research Experiment Rules

## When This Applies

Any time you are asked to investigate, test, validate, or research a strategy idea, signal hypothesis, or market behavior within the backtester/research framework. This includes prompts like:
- "What if we tilted harder during shallow corrections?"
- "Does lowering the drawdown threshold help?"
- "Investigate whether RSI divergence predicts recovery timing"
- "Run a backtest comparing X and Y"

## Before Starting

1. Read `research/README.md` — it defines the research process and conventions
2. Read the experiment template: `research/experiments/_template/`
3. If the idea relates to an existing strategy or rule, read its source in `src/pac/backtester/strategies/builtin/` or `src/pac/rules/builtin/`
4. Check `research/experiments/` for prior experiments that may serve as baseline or context

## The Research Process

Research moves through three regions: **Exploration**, **Consolidation**, and **Validation**. These are not sequential gates — you move between them as understanding develops. A failed validation sends you back to consolidation. A dead end in consolidation may require more exploration.

### Starting an Experiment

1. Scaffold: `just new-experiment <snake_case_name> --title "Human Title"`
2. Fill in `hypothesis` in `experiment.toml` — translate the user's idea into a testable statement
3. Add relevant `tags` (e.g., `["crisis", "sensitivity", "params"]`)
4. Create `FINDINGS.md` with the hypothesis and an Exploration section header

### Phase 1: Exploration — "Is there signal here?"

**Goal**: Determine if the idea has quantitative merit before writing any framework code.

**Tools**: pandas, yfinance, tulipy, matplotlib, Marimo notebooks, `ResearchContext.to_dataframe()`, `ctx.indicator_series()`.

**Where**: All exploration scripts and notebooks go in the `exploration/` folder.

**What to do**:
- Fetch relevant price data and compute indicators
- Look for the pattern or relationship the hypothesis describes
- Quantify it: correlations, conditional distributions, regime analysis
- Visualize: save plots to `artifacts/`
- Record what you find in FINDINGS.md under `## Exploration`

**What not to do**:
- Don't write `BacktestStrategy` or `SignalRule` code yet
- Don't run simulations yet
- Don't optimize parameters — you're looking for signal, not tuning

**When to move on**: You have evidence (statistical, visual, or logical) that the idea has merit. Or you have evidence that it doesn't — document why and conclude the experiment.

**When to stop entirely**: The data clearly contradicts the hypothesis. Document the negative result in FINDINGS.md and mark the experiment as rejected (`status = "rejected"` in experiment.toml). Negative results are valuable.

### Phase 2: Consolidation — "Can this work as a strategy?"

**Goal**: Translate the exploration insight into working framework code and confirm it produces reasonable results in the simulator.

**Tools**: `ResearchContext.simulate()`, `ctx.compare()`, `ctx.sweep()`. Write `BacktestStrategy` or `SignalRule` subclasses inside the experiment's `strategies/` directory. Use Marimo notebooks (e.g., `consolidation/consolidate.py`) as the primary interface.

**Where**: All consolidation scripts and notebooks go in the `consolidation/` folder.

**What to do**:
- Write strategy or signal code inside `<experiment>/strategies/`
- Multiple versions, alternative approaches — all fine, keep them in the folder
- If the experiment needs config variants (different allocations, tickers, contributions), create them in `<experiment>/configs/` and load via `ResearchContext.from_config("configs/variant.yaml")`
- Run quick simulations (N=1, deterministic, no slippage) via `ctx.simulate()`
- Compare against baseline: `ctx.compare()` with existing strategies
- Iterate: adjust logic, thresholds, timing based on results
- Run parameter sweeps (`ctx.sweep()`) to find promising regions
- Save comparison and sweep results to `results/` as JSON
- Update FINDINGS.md under `## Consolidation` with what was tried and what worked

**What not to do**:
- Don't run full MC simulations yet — they're slow and premature here
- Don't declare victory on a single quick-test result
- Don't spend time on code quality or documentation — the strategy code is experimental

**When to move on**: You have a strategy + parameters that consistently outperforms the baseline in quick simulations. The improvement is meaningful, not noise.

**When to go back to Exploration**: The strategy doesn't behave as expected — the underlying assumption may be wrong. Go back, look at the data differently.

### Housekeeping Before Validation

Before entering validation, **organize the experiment directory**. Research is messy — notebooks proliferate, ad-hoc files land in the root, artifacts scatter. This is fine during exploration and consolidation. But validation requires a clean workspace to produce reliable, traceable results.

**Do**:
- Move plots and figures to `artifacts/`
- Move result files to `results/`
- Move config variants to `configs/`
- Group strategy/signal code into `strategies/`
- Extract shared logic from notebooks into standalone modules if needed

**Do NOT**:
- Never delete files, even failed attempts — every path taken must remain in the experiment folder
- Never hide unsuccessful results — move them to `results/` with clear names (e.g., `attempt_1_rsi_only.json`)
- Never remove abandoned strategy versions — they are evidence of the research process

The experiment directory is a complete record. What was tried and what wasn't useful is captured in FINDINGS.md through narrative — not by removing files.

### Phase 3: Validation — "Does this hold up under scrutiny?"

**Goal**: Stress-test the candidate strategy with the full validation toolkit. Gather enough evidence for a go/no-go decision.

**Tools**: `ctx.simulate_mc()`, `ctx.validate_oos()`, `ctx.walk_forward()`, `ctx.evaluate_events()`, `ctx.quantstats_report()`, `ctx.quantstats_rolling()`. Use a Marimo notebook (e.g., `validation/validate.py`) as the primary interface.

**Where**: All validation scripts and notebooks go in the `validation/` folder.

**What to do** (run all that apply):
- **Monte Carlo**: `ctx.simulate_mc(strategy, params, iterations=50, seed=42)` — does it work across random slippage scenarios?
- **OOS Holdout**: `ctx.validate_oos(strategy, params, split_ratio=0.7)` — does it generalize beyond the training period? Check `degradation_ratio < 0.3` as a rule of thumb.
- **Walk-Forward**: `ctx.walk_forward(strategy, params, window_years=10, step_years=5)` — is performance stable across time windows? Check `stability_score`.
- **Event Analysis**: `ctx.evaluate_events(strategy, params, calendar=ctx.calendars["crises"])` — how does it perform during known market events?
- **Parameter Sensitivity**: Sweep nearby parameter values — does performance degrade sharply? Fragile optima are a red flag.
- **QuantStats Tearsheet**: `ctx.quantstats_report(result, output="artifacts/tearsheet.html")` — full performance report.
- Save all results to `results/` and tearsheets to `artifacts/`
- Update FINDINGS.md under `## Validation` with all quantitative results

**When to go back to Consolidation**: Validation reveals a specific failure mode (e.g., poor crisis performance, unstable walk-forward). Adjust the strategy and re-validate.

**When to conclude**: You have run enough validations to make a confident decision. Write the `## Conclusion` section in FINDINGS.md.

## Writing FINDINGS.md

FINDINGS.md is the primary deliverable. It grows as you work. Each phase adds content.

**Core principle**: A reader must be able to reconstruct the full research methodology from FINDINGS.md alone, drilling into scripts, results, and reports only when they need implementation detail. FINDINGS.md is the vertical entry point — everything else is a drill-down.

**Rules**:
- Start it at the beginning of the experiment, not the end
- Include the hypothesis at the top
- Each phase gets its own section (Exploration, Consolidation, Validation, Conclusion)
- Record what didn't work, not just what did — the reasoning trail matters
- Be specific: include actual numbers, parameter values, metric results
- Keep it readable: a future researcher (human or agent) should understand the full story

### Script and Notebook Index

Every script or notebook used in a phase MUST be referenced inline where its results are discussed, with a one-line description of what it does and why it was created. Group these at phase level in the order they were created/used.

Format: `[script_name.py](script_name.py)` — one-line purpose

Example:
```markdown
1. [check_tickers.py](check_tickers.py) — survey yfinance data availability for 18 ticker candidates
2. [proxy_quality_analysis.py](proxy_quality_analysis.py) — first proxy quality check without FX conversion (abandoned — see "FX Conversion Failure" below)
3. [proxy_deep_analysis.py](proxy_deep_analysis.py) — multi-frequency correlation analysis that resolved the timezone misalignment issue
```

### Phase Deliverables

Each phase section MUST end with a **Phase Deliverables** subsection listing the key outputs produced (artifacts, result files, configs, strategy code) with relative links:

```markdown
### Phase Deliverables

| Deliverable | Path | Description |
|---|---|---|
| Proxy quality data | [results/proxy_deep_analysis.json](results/proxy_deep_analysis.json) | Multi-frequency correlation for all pairs |
| Tearsheet | [artifacts/tearsheet.html](artifacts/tearsheet.html) | Full QuantStats performance report |
```

### Failing Paths and Dead Ends

Every approach that was tried and abandoned MUST be documented with:
1. **What was tried** — the specific approach or tool
2. **What went wrong** — the error, unexpected result, or logical flaw
3. **Why it was abandoned** — the reasoning for moving to a different approach
4. **What it taught us** — the insight gained that informed the next attempt

Don't just say "X didn't work." Explain the chain: attempt → failure → insight → next approach. This is the research trail.

### WHY/HOW Depth

For every significant result or decision, document:
- **WHY** — what motivated this particular approach? What question was it answering?
- **HOW** — what method was used? What parameters, what data window, what tool?
- **WHAT** — what was the result? (This is the easy part — most people only write this.)
- **SO WHAT** — what does this mean for the experiment? What decision does it inform?

Bad: "Monthly correlations are higher than daily correlations."
Good: "Monthly correlations (0.96-0.99 same-currency) are dramatically higher than daily (0.65-0.78) because cross-timezone assets close at different hours, injecting noise into daily return alignment. Since this is a monthly DCA strategy, monthly correlations are the operationally relevant metric. This resolved what appeared to be poor proxy quality into an acceptable proxy chain."

### Linking to Artifacts

Keep FINDINGS.md readable by linking to detailed outputs rather than inlining them. But always provide enough context in the narrative that the reader doesn't NEED to open the linked file to understand the conclusion.

## Experiment-Local Code

New strategies and signals live inside the experiment folder during research:

```
research/experiments/003-dd-threshold-sweep/
├── exploration/                # Phase 1 scripts & notebooks
├── consolidation/              # Phase 2 scripts & notebooks
├── validation/                 # Phase 3 scripts & notebooks
└── strategies/
    ├── aggressive_tilt.py      # BacktestStrategy subclass
    └── shallow_detector.py     # SignalRule subclass
```

- Scripts and notebooks are grouped by phase in `exploration/`, `consolidation/`, `validation/`
- Strategy/signal code stays in `strategies/` (shared across phases)
- Results go to `results/`, artifacts to `artifacts/`, configs to `configs/` (all at experiment root)
- Experiments can have multiple strategy/signal files, multiple versions, alternative approaches
- This code is not auto-discovered by the production framework
- To use it in `ResearchContext`, import it explicitly in your notebook/script
- Do not import Python code from other experiments — reference their results by path instead

## Checklist Before Concluding

- [ ] `experiment.toml` has a filled-in `hypothesis`
- [ ] `FINDINGS.md` has at least Exploration and Conclusion sections
- [ ] Every script/notebook is referenced inline in FINDINGS.md with its purpose
- [ ] Each phase ends with a Phase Deliverables table
- [ ] Failing paths documented with attempt → failure → insight → next approach
- [ ] Results include WHY/HOW reasoning, not just WHAT was achieved
- [ ] FINDINGS.md is self-contained — a reader can reconstruct the methodology without opening scripts
- [ ] Key results saved to `results/` (JSON or CSV)
- [ ] Experiment directory is organized (housekeeping done)
- [ ] All attempted approaches are preserved (nothing deleted)
- [ ] Conclusion states a clear go/no-go with supporting numbers
- [ ] Negative results are documented (what was tried and why it failed)
- [ ] Any referenced experiments are linked in FINDINGS.md and `depends_on`

## Common Pitfalls

| Pitfall | What to do instead |
|---|---|
| Jumping straight to MC simulation | Start with exploration — understand the data first |
| Optimizing params without a baseline | Always establish baseline numbers before comparing |
| Declaring success on a single quick-test | Validate with OOS, walk-forward, and MC |
| Tweaking params inside validation | Go back to consolidation, freeze params, then re-validate |
| Not recording negative results | Document why it failed — this prevents others from repeating the work |
| Writing framework code during exploration | Use pandas/tulipy first — framework code comes in consolidation |
| Importing code from other experiments | Reference their results by path, not their Python modules |
| Deleting failed attempts or dead-end files | Keep everything — move to appropriate subfolders, document in FINDINGS.md |
| Entering validation with a messy directory | Organize first: artifacts/, results/, configs/, strategies/ |
| Using plain scripts instead of Marimo notebooks | Prefer Marimo for all phases — interactive, visual, version-control friendly |
| Writing FINDINGS.md as a summary of results | Write it as a research narrative — include WHY decisions were made, failed paths, script links, and phase deliverables |
| Not linking scripts/notebooks inline | Every script must be referenced where its results are discussed, with a one-line purpose |
| Omitting failing paths | Document the full chain: attempt → failure → insight → next approach |
