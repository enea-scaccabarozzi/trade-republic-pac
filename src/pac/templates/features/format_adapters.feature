Feature: Format Adapters
  Format adapters translate abstract formatting calls into
  channel-specific markup. Templates use adapter methods
  without knowing the target format.

  Scenario: MarkdownV2 adapter escapes special characters
    Given a MarkdownV2 adapter
    When escaping the text "price: $100.00 (50% off)"
    Then the result contains backslash-escaped special characters

  Scenario: MarkdownV2 adapter produces bold markup
    Given a MarkdownV2 adapter
    When formatting "Portfolio Status" as bold
    Then the result is "*Portfolio Status*"

  Scenario: MarkdownV2 adapter produces inline code
    Given a MarkdownV2 adapter
    When formatting "WARNING" as code
    Then the result is "`WARNING`"

  Scenario: MarkdownV2 adapter maps severity emoji
    Given a MarkdownV2 adapter
    When requesting emoji for "warning"
    Then the result is "⚠️"

  Scenario: PlainText adapter applies no markup
    Given a PlainText adapter
    When formatting "hello" as bold
    Then the result is "hello"

  Scenario: PlainText adapter does not escape text
    Given a PlainText adapter
    When escaping the text "price: $100.00"
    Then the result is "price: $100.00"

  Scenario: PlainText adapter uses text markers for severity
    Given a PlainText adapter
    When requesting emoji for "critical"
    Then the result is "[CRITICAL]"

  Scenario: PlainText adapter formats links with URL in parentheses
    Given a PlainText adapter
    When formatting a link with text "docs" and URL "https://example.com"
    Then the result is "docs (https://example.com)"

  Scenario Outline: Adapter name matches expected identifier
    Given a <adapter> adapter
    Then the adapter name is "<name>"

    Examples:
      | adapter    | name        |
      | MarkdownV2 | markdown_v2 |
      | PlainText  | plain_text  |

  Scenario: MarkdownV2 adapter escapes structural literal characters
    Given a MarkdownV2 adapter
    When wrapping "(" in literal
    Then the result contains backslash-escaped special characters

  Scenario: PlainText adapter literal is identity
    Given a PlainText adapter
    When wrapping "(" in literal
    Then the result is "("

  Scenario: PlainText adapter code_block is identity
    Given a PlainText adapter
    When formatting "x = 1" as code_block
    Then the result is "x = 1"
