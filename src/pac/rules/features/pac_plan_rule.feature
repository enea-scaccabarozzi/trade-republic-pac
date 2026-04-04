Feature: PAC Plan Rule
  Computes a monthly savings plan and emits a summary signal
  with budget allocation details per asset.

  Background:
    Given a portfolio with target allocation 70/15/15 for stocks/gold/bonds

  Scenario: PAC plan emits summary signal with budget and allocation details
    Given a balanced portfolio at target allocation
    When the PAC plan rule evaluates with default params
    Then exactly 1 signal is emitted
    And the signal name is "pac_plan"
    And the signal severity is INFO
    And the signal metadata contains a monthly_budget of 500.0
    And the signal metadata contains allocations for all 3 assets

  Scenario: PAC plan with single-asset portfolio produces simple plan
    Given the portfolio has only stocks worth 10000
    When the PAC plan rule evaluates with default params
    Then exactly 1 signal is emitted
    And the signal severity is INFO
    And the signal metadata contains allocations for all 3 assets

  Scenario: PAC plan applies custom budget parameter
    Given a balanced portfolio at target allocation
    When the PAC plan rule evaluates with monthly_budget=1000.00
    Then exactly 1 signal is emitted
    And the signal metadata contains a monthly_budget of 1000.0
    And the signal message contains "1000.00"

  Scenario: PAC plan with no deviation uses target allocations
    Given a balanced portfolio at target allocation
    When the PAC plan rule evaluates with default params
    Then exactly 1 signal is emitted
    And each allocation percentage sums to 100
