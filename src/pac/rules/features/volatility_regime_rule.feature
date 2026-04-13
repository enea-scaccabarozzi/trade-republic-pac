Feature: Volatility Regime Rule
  Detects transitions from low-volatility to high-volatility regimes
  by comparing short-term (20d) vs long-term (60d) realized volatility.

  Background:
    Given a market context with equity price history

  Scenario: No signal in stable volatility environment
    Given equity volatility has been steady at ~15% annualized for 60 days
    When the volatility regime rule evaluates
    Then no signals are emitted

  Scenario: Warning signal when short-term vol spikes
    Given 20-day vol is 27% and 60-day vol is 15% (ratio ~1.8)
    When the volatility regime rule evaluates with default params
    Then a WARNING signal is emitted

  Scenario: Critical signal for extreme vol expansion
    Given 20-day vol is 50% and 60-day vol is 18% (ratio ~2.8)
    When the volatility regime rule evaluates with default params
    Then a CRITICAL signal is emitted

  Scenario: No signal during slow grind (both vols elevated)
    Given 20-day vol is 25% and 60-day vol is 22% (ratio ~1.1)
    When the volatility regime rule evaluates
    Then no signals are emitted

  Scenario: No signal when market_ctx is None
    Given no market context is available
    When the volatility regime rule evaluates
    Then no signals are emitted
