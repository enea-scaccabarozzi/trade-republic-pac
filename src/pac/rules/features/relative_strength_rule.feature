Feature: Relative Strength Rule
  Detects flight-to-safety regime shifts by measuring gold's outperformance
  relative to equities via a gold/equity price ratio with MA breakout.

  Background:
    Given a market context with gold and equity price history

  Scenario: No signal when gold/equity ratio is near its MA
    Given the gold/equity ratio is within 2% of its 120-day MA
    When the relative strength rule evaluates
    Then no signals are emitted

  Scenario: Warning signal for moderate RS breakout
    Given the gold/equity ratio is 6% above its 120-day MA
    When the relative strength rule evaluates with default params
    Then a WARNING signal is emitted
    And the signal metadata includes breakout_pct of approximately 6.0

  Scenario: Critical signal for extreme RS breakout
    Given the gold/equity ratio is 12% above its 120-day MA
    When the relative strength rule evaluates with default params
    Then a CRITICAL signal is emitted

  Scenario: No signal when gold declines alongside equities
    Given both gold and equities have fallen, keeping the ratio near its MA
    When the relative strength rule evaluates
    Then no signals are emitted

  Scenario: No signal when market_ctx is None
    Given no market context is available
    When the relative strength rule evaluates
    Then no signals are emitted

  Scenario: Graceful handling of insufficient data
    Given only 30 days of price data are available
    When the relative strength rule evaluates with ma_window=120
    Then no signals are emitted
