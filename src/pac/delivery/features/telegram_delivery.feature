Feature: Telegram Delivery Channel
  The Telegram channel sends rendered messages to a configured chat
  via the Telegram Bot API.

  Scenario: Send a rendered message
    Given a started Telegram channel
    When a rendered message is sent through the channel
    Then the message is delivered to the configured chat
    And the message uses MarkdownV2 parse mode

  Scenario: Sending before start raises error
    Given an unstarted Telegram channel
    When a rendered message is sent through the channel
    Then a RuntimeError is raised

  Scenario: Sending after stop raises error
    Given a started Telegram channel that has been stopped
    When a rendered message is sent through the channel
    Then a RuntimeError is raised

  Scenario: Channel reports supported formats
    Given a Telegram channel configuration
    When the channel is created
    Then the supported formats include "markdown_v2"

  Scenario: Channel name is telegram
    Given a Telegram channel configuration
    When the channel is created
    Then the channel name is "telegram"

  Scenario: Webhook secret from config
    Given a Telegram channel with webhook configured
    When the channel is created
    Then the webhook secret matches the configured value

  Scenario: No webhook secret when webhook not configured
    Given a Telegram channel without webhook configured
    When the channel is created
    Then the webhook secret is None

  Scenario: Lifecycle — start, send, stop
    Given a Telegram channel configuration
    When the channel is started
    And a rendered message is sent
    And the channel is stopped
    Then the message was delivered successfully
    And the channel is no longer running
