Feature: Historical Market Data Access
  The backtester fetches historical OHLCV price data from Yahoo Finance
  for configured assets, using locally-cached results to avoid repeated downloads.

  Background:
    Given the backtest dependency group is installed

  Scenario: Fetch daily price data for a ticker
    Given a data request for "EUNL.DE" from "2024-01-01" to "2024-03-31"
    When market data is fetched
    Then a price series is returned with at least 50 bars
    And each bar has open, high, low, close, and volume fields
    And all prices are positive decimals

  Scenario: No data returned for invalid ticker
    Given a data request for "XXXXXXXXX.XX" from "2024-01-01" to "2024-03-31"
    When market data is fetched
    Then a ValueError is raised mentioning "No data returned"

  Scenario: Date range validation rejects invalid range
    Given a data request with start "2024-12-31" after end "2024-01-01"
    Then the request is rejected with a validation error

  Scenario: Price bar rejects low above high
    Given a price bar with low "110.00" and high "100.00"
    Then the bar is rejected with a validation error

  Scenario: Resolve tickers from asset configuration
    Given assets configured with tickers in pac.yaml
    When tickers are resolved from settings
    Then each asset ID maps to its configured ticker

  Scenario: Missing ticker detected before backtest
    Given an asset without a ticker field
    When tickers are resolved from settings
    Then a ValueError is raised listing the asset missing a ticker

  Scenario: Backtester unavailable without extras
    Given yfinance is not installed
    When MarketDataProvider is instantiated
    Then an ImportError is raised with install instructions

  Scenario: Slice price series by date range
    Given a price series for "EUNL.DE" from "2024-01-01" to "2024-06-30"
    When the series is sliced from "2024-03-01" to "2024-03-31"
    Then the resulting series contains only bars within that range

  Scenario: Fetch multiple tickers at once
    Given data requests for "EUNL.DE" and "4GLD.DE" from "2024-01-01" to "2024-03-31"
    When multiple market data fetches are executed
    Then a dictionary mapping each ticker to its price series is returned
