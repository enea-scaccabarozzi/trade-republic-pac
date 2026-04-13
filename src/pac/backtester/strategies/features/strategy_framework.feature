Feature: Backtest Strategy Framework
  The backtester uses a strategy ABC to translate signals into actions.
  Strategies are auto-discovered from the builtin package and registered
  by name for lookup.

  Scenario: Strategy receives params at initialization
    Given a strategy class with a params model requiring "threshold"
    When the strategy is instantiated with threshold 5.0
    Then the strategy stores the params on self

  Scenario: Strategy produces actions from signals
    Given a strategy that emits a hard rebalance on any signal
    And a portfolio with deviations above threshold
    When signals are fed to the strategy
    Then the strategy returns rebalance actions

  Scenario: Strategy adjusts PAC volumes on PAC date
    Given a strategy that overrides on_pac_date
    When on_pac_date is called
    Then a PacAdjustment is returned with new volumes

  Scenario: Default on_pac_date returns nothing
    Given a strategy with default on_pac_date
    When on_pac_date is called on the default strategy
    Then None is returned

  Scenario: Strategy discovery finds pac_alignment and cycle_exploit
    When the builtin strategies package is scanned
    Then "pac_alignment" is in the discovered strategies
    And "cycle_exploit" is in the discovered strategies
    And "crisis_exploit" is in the discovered strategies
    And exactly 3 strategies are discovered

  Scenario: Strategy registry instantiates with validated params
    Given a registered strategy "simple" with params model
    When the registry instantiates "simple" with threshold 3.0
    Then the strategy has threshold 3.0

  Scenario: Registry rejects unknown strategy name
    Given an empty strategy registry
    When instantiation is attempted for "unknown"
    Then a KeyError is raised
