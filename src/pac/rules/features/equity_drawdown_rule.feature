Feature: Equity Drawdown Rule
  Detects significant equity drawdowns from rolling peak and measures
  the velocity of decline to distinguish fast crashes from slow corrections.

  Background:
    Given a market context with equity price history

  Scenario: No signal when market is near highs
    Given equity prices have been rising steadily for 252 days
    When the equity drawdown rule evaluates
    Then no signals are emitted

  Scenario: Warning signal for moderate drawdown depth
    Given equity has drawn down 12% from its 252-day peak
    When the equity drawdown rule evaluates with default params
    Then a WARNING signal is emitted
    And the signal metadata includes drawdown_pct of approximately -0.12

  Scenario: Critical signal for severe drawdown depth
    Given equity has drawn down 25% from its 252-day peak
    When the equity drawdown rule evaluates with default params
    Then a CRITICAL signal is emitted

  Scenario: Warning signal for moderate drawdown velocity
    Given equity has fallen 6% in 20 days from peak (velocity ~ -0.30%/day)
    When the equity drawdown rule evaluates with default params
    Then a signal with metadata indicator "drawdown_velocity" is emitted

  Scenario: No signal when market_ctx is None
    Given no market context is available
    When the equity drawdown rule evaluates
    Then no signals are emitted

  Scenario: Graceful handling of insufficient price data
    Given only 10 days of equity price data are available
    When the equity drawdown rule evaluates with lookback_bars=252
    Then no signals are emitted
