Feature: Backtest Simulation Engine
  The simulation engine replays historical market data through the signal
  rule pipeline, applying strategy-driven actions with realistic Trade
  Republic constraints (PAC dates, fees, spread).

  Background:
    Given a portfolio with 3 assets: stocks (70%), gold (15%), bonds (15%)
    And initial cash of €10,000
    And a monthly contribution of €500
    And PAC execution dates on the 2nd and 16th

  Scenario: PAC executions occur on configured dates
    Given price data from "2024-01-01" to "2024-03-31"
    And a no-op strategy
    When a single simulation iteration runs
    Then PAC buy trades appear only on PAC dates (2nd/16th or next trading day)
    And no fees are charged on PAC trades

  Scenario: Monthly contribution split across PAC dates
    Given price data from "2024-01-01" to "2024-01-31"
    And a no-op strategy with zero PAC volumes
    When PAC executes on the first PAC date
    Then €250 is added to cash (€500 / 2 configured days)

  Scenario: Hard rebalance buy skipped when cash insufficient
    Given price data from "2024-01-01" to "2024-02-28"
    And a strategy that emits a hard rebalance buy of €50,000 for stocks
    And the portfolio has only €1,000 initial cash
    When a single simulation iteration runs
    Then skipped trades are recorded in the trade log

  Scenario: Hard rebalance applies fee and spread
    Given price data from "2024-01-01" to "2024-02-28"
    And a strategy that emits a hard rebalance buy of €1000 for stocks
    And a spread of 10 basis points
    When a single simulation iteration runs
    Then hard rebalance trades have a €1 settlement fee

  Scenario: Monte Carlo produces distribution of outcomes
    Given price data from "2024-01-01" to "2024-06-30"
    And 5 Monte Carlo iterations
    And slippage range of 0 to 3 days
    And a no-op strategy
    When the full simulation runs
    Then 5 iteration results are produced

  Scenario: Deterministic simulation with fixed seed
    Given price data from "2024-01-01" to "2024-03-31"
    And a no-op strategy
    And a fixed random seed of 42
    When the simulation runs twice with the same parameters
    Then both runs produce identical final values
