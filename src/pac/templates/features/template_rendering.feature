Feature: Template Rendering
  The template engine renders Jinja2 templates with format
  adapters to produce channel-agnostic RenderedMessages.

  Background:
    Given a template engine with builtin templates

  Scenario: Render threshold alert with MarkdownV2
    Given a threshold signal with WARNING severity
    And a MarkdownV2 adapter
    When rendering the "threshold_alert" template
    Then a RenderedMessage is produced
    And the message format is "markdown_v2"
    And the message contains bold signal name
    And the message contains the severity

  Scenario: Render threshold alert with PlainText
    Given a threshold signal with WARNING severity
    And a PlainText adapter
    When rendering the "threshold_alert" template
    Then a RenderedMessage is produced
    And the message format is "plain_text"
    And the message contains the signal name
    And the message contains the severity

  Scenario: Render PAC plan with MarkdownV2
    Given a PAC plan with 3 asset allocations
    And a MarkdownV2 adapter
    When rendering the "pac_plan" template
    Then a RenderedMessage is produced
    And the message contains "Monthly PAC Redistribution"
    And the message contains each asset allocation

  Scenario: Render portfolio status with MarkdownV2
    Given a portfolio with deviations for 3 assets
    And a MarkdownV2 adapter
    When rendering the "portfolio_status" template
    Then a RenderedMessage is produced
    And the message contains each asset's deviation

  Scenario: Same template produces different output per adapter
    Given a threshold signal with CRITICAL severity
    When rendering "threshold_alert" with MarkdownV2 adapter
    And rendering "threshold_alert" with PlainText adapter
    Then the two outputs have different content
    But both contain the signal name

  Scenario: Render cycle alert with MarkdownV2
    Given a threshold signal with WARNING severity
    And a MarkdownV2 adapter
    When rendering the "cycle_alert" template
    Then a RenderedMessage is produced
    And the message format is "markdown_v2"
    And the message contains the signal name
    And the message contains the severity

  Scenario: Unknown template raises an error
    Given a MarkdownV2 adapter
    When rendering a template named "nonexistent"
    Then a template-not-found error is raised

  Scenario: Missing template variable raises an error
    Given a MarkdownV2 adapter
    When rendering "threshold_alert" with empty data
    Then an undefined-variable error is raised

  Scenario: Data key collision with reserved name raises error
    Given a MarkdownV2 adapter
    When rendering "threshold_alert" with a data key that shadows a reserved name
    Then a data-key-collision error is raised
