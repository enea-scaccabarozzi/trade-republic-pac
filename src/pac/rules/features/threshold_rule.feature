Feature: Threshold Deviation Rule
  Detects assets that deviate from their target allocation
  beyond configurable warning and critical thresholds.

  Background:
    Given a portfolio with target allocation 70/15/15 for stocks/gold/bonds

  Scenario: No signals when allocation is within threshold
    Given the portfolio is perfectly balanced at 70/15/15
    When the threshold rule evaluates with default params
    Then no signals are emitted

  Scenario: Warning signal for moderate overweight
    Given stocks are at 73% (3pp above target)
    When the threshold rule evaluates with default params
    Then a WARNING signal is emitted for stocks
    And the signal indicates "overweight"

  Scenario: Critical signal for large overweight
    Given stocks are at 76% (6pp above target)
    When the threshold rule evaluates with default params
    Then a CRITICAL signal is emitted for stocks

  Scenario: Underweight direction is correctly identified
    Given bonds are at 9% (6pp below target)
    When the threshold rule evaluates with default params
    Then a CRITICAL signal is emitted for bonds
    And the signal indicates "underweight"

  Scenario: Custom thresholds override defaults
    Given stocks are at 72% (2pp above target)
    When the threshold rule evaluates with warning_pct=1.0 and critical_pct=3.0
    Then a WARNING signal is emitted for stocks

  Scenario Outline: Severity classification
    Given an asset deviating by <deviation>pp
    When the threshold rule evaluates with warning_pct=3.0 and critical_pct=5.0
    Then <outcome>

    Examples:
      | deviation | outcome                      |
      | 2.0       | no signal is emitted         |
      | 3.0       | a WARNING signal is emitted  |
      | 5.0       | a CRITICAL signal is emitted |
