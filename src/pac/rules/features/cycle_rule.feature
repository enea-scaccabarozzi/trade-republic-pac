Feature: Cycle Inversion Rule
  Detects diverging asset pairs where one is overweight
  while another is underweight, suggesting a market cycle shift.

  Background:
    Given a portfolio with target allocation 70/15/15 for stocks/gold/bonds

  Scenario: No signals when all deviations are in the same direction
    Given all assets are slightly underweight due to cash drag
    When the cycle inversion rule evaluates with default params
    Then no signals are emitted

  Scenario: Inversion detected for opposing deviations
    Given stocks are 6pp overweight and bonds are 6pp underweight
    When the cycle inversion rule evaluates with default params
    Then a cycle inversion signal is emitted
    And the signal identifies stocks as overweight and bonds as underweight

  Scenario: Below minimum threshold yields no signal
    Given all deviations are below 3pp
    When the cycle inversion rule evaluates with default params
    Then no signals are emitted

  Scenario: Severity scales with combined divergence
    Given stocks are 6pp overweight and bonds are 6pp underweight
    When the cycle inversion rule evaluates with default params
    Then the signal severity is CRITICAL

  Scenario: Custom minimum threshold
    Given deviations of 1.5pp in opposing directions
    When the cycle inversion rule evaluates with min_pct=1.0
    Then a cycle inversion signal is emitted

  Scenario: Deviations at exactly the minimum threshold trigger signal
    Given deviations of 3pp in opposing directions
    When the cycle inversion rule evaluates with default params
    Then a cycle inversion signal is emitted

  Scenario: Deviations in the 2-3pp gap do not trigger with new default
    Given deviations of 2.5pp in opposing directions
    When the cycle inversion rule evaluates with default params
    Then no signals are emitted
