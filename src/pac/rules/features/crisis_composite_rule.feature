Feature: Crisis Composite Rule
  Combines multiple crisis indicators with N-of-M voting
  to produce high-confidence crisis alerts.

  Background:
    Given a market context with equity, gold, and bond price history
    And a portfolio with target allocation 70/15/15 for stocks/gold/bonds

  Scenario: No signal when markets are calm
    Given all indicators are below their warning thresholds
    When the crisis composite rule evaluates
    Then no signals are emitted

  Scenario: No signal with only 1 active indicator
    Given equity drawdown is -12% (WARNING) but all other indicators are inactive
    When the crisis composite rule evaluates with min_active=3
    Then no signals are emitted

  Scenario: No signal with only 2 active indicators
    Given equity drawdown is -12% and death cross is bearish
    But divergence is below threshold
    When the crisis composite rule evaluates with min_active=3
    Then no signals are emitted

  Scenario: WARNING signal with 3 active indicators at WARNING level
    Given equity drawdown is -15% (WARNING)
    And death cross is bearish (WARNING)
    And gold-equity divergence is 15% (WARNING)
    When the crisis composite rule evaluates with min_active=3
    Then a WARNING composite signal is emitted
    And the signal metadata shows 3 active indicators

  Scenario: CRITICAL signal when 2+ indicators at CRITICAL
    Given equity drawdown is -25% (CRITICAL)
    And drawdown velocity is -0.80 (CRITICAL)
    And death cross just crossed (CRITICAL)
    And gold-equity divergence is 15% (WARNING)
    When the crisis composite rule evaluates
    Then a CRITICAL composite signal is emitted

  Scenario: No signal when market_ctx is None
    Given no market context is available
    When the crisis composite rule evaluates
    Then no signals are emitted

  Scenario: Indicator with insufficient data counts as inactive
    Given equity has enough data for drawdown but not for death cross
    And drawdown is -15% (WARNING)
    And gold-equity divergence is 12% (WARNING)
    When the crisis composite rule evaluates with min_active=3
    Then no signals are emitted because only 2 indicators are active
