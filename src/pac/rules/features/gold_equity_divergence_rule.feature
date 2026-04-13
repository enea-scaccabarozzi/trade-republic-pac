Feature: Gold-Equity Divergence Rule
  Detects flight-to-safety flows where gold appreciates while equities
  decline, a hallmark of Type A crisis events.

  Background:
    Given a market context with gold and equity price history

  Scenario: No signal when gold and equities move together
    Given gold and equities both returned +5% over 40 trading days
    When the gold-equity divergence rule evaluates
    Then no signals are emitted

  Scenario: Warning signal for moderate divergence
    Given gold returned +5% and equities returned -8% over 40 days
    When the gold-equity divergence rule evaluates with default params
    Then a WARNING signal is emitted
    And the signal metadata includes divergence_pct of approximately 13.0

  Scenario: Critical signal for extreme divergence
    Given gold returned +10% and equities returned -15% over 40 days
    When the gold-equity divergence rule evaluates with default params
    Then a CRITICAL signal is emitted

  Scenario: Signal when gold declines less than equities (positive divergence)
    Given gold returned -5% and equities returned -15% over 40 days
    When the gold-equity divergence rule evaluates with default params
    Then a WARNING signal is emitted
    And the divergence is 10% (gold declined less)

  Scenario: No signal when market_ctx is None
    Given no market context is available
    When the gold-equity divergence rule evaluates
    Then no signals are emitted
