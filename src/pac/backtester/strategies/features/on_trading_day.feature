Feature: Daily Portfolio Observation
  Strategies can observe daily portfolio state to build running
  statistics (e.g., moving averages of allocations) for use in
  PAC date decisions.

  Background:
    Given a strategy that records daily portfolio observations

  Scenario: Strategy observes every trading day
    Given a simulation spanning 5 trading days
    When the simulation completes
    Then the strategy recorded 5 daily observations

  Scenario: Daily observations include allocation data
    Given a simulation with a portfolio holding stocks and bonds
    When the simulation completes
    Then each observation includes allocation percentages for all assets

  Scenario: Daily observations include drift data
    Given a simulation with a portfolio holding stocks and bonds
    When the simulation completes
    Then each observation includes signed deviation from target for each asset

  Scenario: Observations accumulate in chronological order
    Given a simulation spanning 5 trading days
    When the simulation completes
    Then the observations are ordered by date

  Scenario: Observations reset between Monte Carlo iterations
    Given a completed simulation iteration with accumulated observations
    When a new iteration begins
    Then no prior observations remain

  Scenario: Default on_trading_day is a no-op
    Given a strategy with default on_trading_day
    When on_trading_day is called with a portfolio snapshot
    Then no error is raised and no state changes
