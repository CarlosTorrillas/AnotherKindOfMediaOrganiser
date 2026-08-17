Feature: Verify destination collisions from the browser
  Deep verification remains read-only while reporting resumable progress.

  Scenario: Verify collisions from the browser
    Given an Organisation Proposal contains browser destination collisions
    When the user chooses Verify Collisions
    Then the existing deep collision verification workflow is executed
    And Exact Duplicates are reported in the browser
    And Potential Conflicts are reported in the browser
    And Unverified Conflicts are reported in the browser
    And browser verification modifies no media

  Scenario: Display verification progress
    Given browser collision verification is running
    When progress is reported by the existing application workflow
    Then the browser shows meaningful verification progress
    And the user can see that verification is still active

  Scenario: Reconnect to running verification
    Given browser collision verification is running
    When the user refreshes the verification page
    Then the current verification progress is displayed
    And the same verification job continues

  Scenario: Reuse cached verification work
    Given previous collision hashes are available in the persistent cache
    When browser verification is started again
    Then valid cached hashes are reused by browser verification
    And cache hits are visible in the browser result

  Scenario: Display limited verification examples
    Given browser verification contains many collision results
    When the browser verification result is displayed
    Then at most 5 deterministic verification examples are shown
    And the total number of browser verification collisions is visible

  Scenario: Cancel collision verification safely
    Given browser collision verification is running
    When the user cancels browser verification
    Then browser verification stops safely
    And completed hashes remain reusable
    And browser verification modifies no media

  Scenario: Verification fails safely
    Given browser collision verification cannot complete
    When the browser verification error occurs
    Then a clear browser verification error is displayed
    And no Python traceback is exposed by browser verification
    And browser verification modifies no media

  Scenario: Collision verification remains read-only
    Given the browser interface is open for verification
    When the user verifies collisions from the browser
    Then no files are copied, moved, deleted, or renamed by verification
