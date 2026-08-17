Feature: Organise an accepted proposal by COPY from the browser
  Browser COPY uses existing capacity and execution workflows without deleting sources.

  Scenario: Execute COPY from the browser
    Given an accepted browser Organisation Proposal
    And the browser destination passes Capacity Preflight
    When the user explicitly confirms browser COPY
    Then the existing COPY Organisation Execution is used
    And proposed media is copied to the browser destination
    And browser source media remains untouched

  Scenario: Review Capacity Preflight before COPY
    Given a browser Organisation Proposal
    When the user selects a browser destination
    Then browser Capacity Preflight is displayed
    And no filesystem modification has occurred before browser confirmation

  Scenario: Accept a partial COPY
    Given the complete browser proposal does not fit
    And a browser Partial Organisation Proposal does fit
    When the user explicitly accepts the partial browser COPY
    Then only the accepted partial browser proposal is executed
    And excluded browser media remains untouched

  Scenario: Decline COPY
    Given browser COPY confirmation is displayed
    When the user declines browser COPY
    Then no filesystem content is modified by browser COPY

  Scenario: COPY fails
    Given browser COPY execution encounters a filesystem error
    When browser COPY execution stops
    Then the browser COPY failure reason is displayed
    And browser source media remains untouched
    And completed browser copies remain completed

  Scenario: Prevent duplicate execution
    Given browser COPY is already running
    When the browser submits COPY execution again
    Then a second browser COPY is not started
