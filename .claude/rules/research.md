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

**Tools**: `ResearchContext.simulate()`, `ctx.compare()`, `ctx.sweep()`. Write `BacktestStrategy` or `SignalRule` subclasses inside the experiment's `strategies/` directory. Use Marimo notebooks (e.g., `consolidate.py`) as the primary interface.

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

**Tools**: `ctx.simulate_mc()`, `ctx.validate_oos()`, `ctx.walk_forward()`, `ctx.evaluate_events()`, `ctx.quantstats_report()`, `ctx.quantstats_rolling()`. Use a Marimo notebook (e.g., `validate.py`) as the primary interface.

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

**Rules**:
- Start it at the beginning of the experiment, not the end
- Include the hypothesis at the top
- Each phase gets its own section (Exploration, Consolidation, Validation, Conclusion)
- Link to artifacts and results rather than inlining large tables
- Record what didn't work, not just what did — the reasoning trail matters
- Be specific: include actual numbers, parameter values, metric results
- Keep it readable: a future researcher (human or agent) should understand the full story

## Experiment-Local Code

New strategies and signals live inside the experiment folder during research:

```
research/experiments/003-dd-threshold-sweep/
└── strategies/
    ├── aggressive_tilt.py      # BacktestStrategy subclass
    └── shallow_detector.py     # SignalRule subclass
```

- Experiments can have multiple strategy/signal files, multiple versions, alternative approaches
- This code is not auto-discovered by the production framework
- To use it in `ResearchContext`, import it explicitly in your notebook/script
- Do not import Python code from other experiments — reference their results by path instead

## Checklist Before Concluding

- [ ] `experiment.toml` has a filled-in `hypothesis`
- [ ] `FINDINGS.md` has at least Exploration and Conclusion sections
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
