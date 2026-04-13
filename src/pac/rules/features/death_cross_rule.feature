Feature: Death Cross Rule
  Detects bearish trend reversals via the classic 50/200 SMA death cross.
  Standalone indicator — not part of the composite crisis signal.

  Background:
    Given a market context with at least 200 days of equity price data

  Scenario: No signal in a bullish trend
    Given the 50-day SMA is above the 200-day SMA
    When the death cross rule evaluates
    Then no signals are emitted

  Scenario: Critical signal on crossover event
    Given the 50-day SMA just crossed below the 200-day SMA today
    When the death cross rule evaluates
    Then a CRITICAL signal is emitted
    And the signal metadata includes cross_event as true

  Scenario: Warning signal during ongoing bearish regime
    Given the 50-day SMA has been below the 200-day SMA for 30 days
    When the death cross rule evaluates
    Then a WARNING signal is emitted
    And the signal metadata includes bearish_regime as true
    And the signal metadata includes cross_event as false

  Scenario: No signal when market_ctx is None
    Given no market context is available
    When the death cross rule evaluates
    Then no signals are emitted

  Scenario: Graceful handling of insufficient data
    Given only 100 days of price data are available
    When the death cross rule evaluates with long_window=200
    Then no signals are emitted
