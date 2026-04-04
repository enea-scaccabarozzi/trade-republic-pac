Feature: Signal dispatch pipeline
  The orchestrator evaluates signals and delivers results through channels.

  Scenario: Dispatch a configured signal that fires
    Given a portfolio with deviations above threshold
    And a signal "deviation_check" configured with rule "threshold_deviation"
    When the signal is dispatched
    Then the rule is evaluated with configured params
    And the message is sent to all configured channels

  Scenario: Dispatch a configured signal that does not fire
    Given a balanced portfolio within thresholds
    And a signal "deviation_check" configured with rule "threshold_deviation"
    When the signal is dispatched
    Then no messages are sent
    And the result shows zero signals

  Scenario: Dispatch an unknown signal
    When the signal "nonexistent" is dispatched
    Then a signal-not-found error is raised

  Scenario: Evaluate signal returns results without sending
    Given a portfolio with deviations above threshold
    And a signal "deviation_check" configured with rule "threshold_deviation"
    When the signal is evaluated without dispatch
    Then signals are returned
    But no messages are sent through channels

  Scenario: Dispatch continues when one channel fails
    Given a portfolio with deviations above threshold
    And a signal "deviation_check" configured with rule "threshold_deviation"
    And one channel is configured to fail on send
    When the signal is dispatched
    Then the result shows signals were delivered
    And the failing channel attempted to send

  Scenario: Dispatch with no configured channels skips delivery
    Given a portfolio with deviations above threshold
    And a signal "no_channel_check" configured with no channels
    When the signal "no_channel_check" is dispatched through the orchestrator
    Then the result shows signals were fired but delivered is true
