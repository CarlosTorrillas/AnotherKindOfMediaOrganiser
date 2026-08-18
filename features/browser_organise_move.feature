Feature: Organise an accepted proposal by verified MOVE from the browser
  MOVE is explicit and delegates COPY, verification, and deletion safety to the existing executor.

  Scenario: Execute verified MOVE from the browser
    Given an accepted browser proposal for MOVE
    And browser MOVE Capacity Preflight succeeds
    When the user explicitly confirms browser MOVE
    Then each browser MOVE file is copied
    And its browser destination is verified
    And only then is its browser source deleted

  Scenario: MOVE is never the default
    Given the browser organisation execution page is displayed
    When the user has not explicitly selected browser MOVE
    Then no destructive browser operation is selected

  Scenario: Decline MOVE
    Given the destructive browser MOVE confirmation is displayed
    When the user declines browser MOVE
    Then no filesystem content is modified by browser MOVE

  Scenario: Verification fails
    Given a browser destination copy cannot be verified
    When browser MOVE processes that file
    Then the browser MOVE source file is not deleted
    And the browser verification failure is reported

  Scenario: Source deletion fails
    Given a browser destination has been copied and verified
    When browser source deletion fails
    Then the verified browser destination remains
    And the browser MOVE source remains
    And the browser deletion failure is reported

  Scenario: Partial MOVE completes
    Given only a browser Partial Organisation Proposal fits MOVE
    When the user accepts and completes browser MOVE
    Then only media in the accepted partial browser MOVE is moved
    And remaining browser source media is not modified

  Scenario: Browser reconnect does not duplicate MOVE
    Given browser MOVE execution is already running
    When the browser reconnects to MOVE progress
    Then the existing browser MOVE execution is shown
    And a second browser MOVE is not started
