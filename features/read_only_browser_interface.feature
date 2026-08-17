Feature: Review a Media Collection in a browser
  The browser interface exposes scanning and lightweight proposals without changing media.

  Scenario: Open the browser interface
    Given the web server is running
    When the user opens the root page
    Then the Media Collection form is displayed
    And no filesystem modification occurs

  Scenario: Scan a complete Media Collection
    Given a valid Media Collection path is provided
    When the user starts a browser scan
    Then the Scan Result is displayed
    And the browser scan is reported as complete
    And recognised and unsupported media counts are shown
    And directories scanned are shown

  Scenario: Display excluded paths
    Given a Media Collection contains an excluded path
    When the user scans the collection with that exclusion
    Then the excluded path is reported
    And excluded media is not included in the Scan Result
    And the excluded path is not reported as inaccessible

  Scenario: Warn about an incomplete scan
    Given a Media Collection scan reports an inaccessible non-excluded path
    When that Scan Result is displayed in the browser
    Then the browser scan is reported as incomplete
    And a prominent incomplete-scan warning is displayed
    And deterministic inaccessible-path examples are shown

  Scenario: Generate a lightweight Organisation Proposal
    Given a Media Collection has been scanned from the browser
    When the user requests an Organisation Proposal
    Then the existing lightweight proposal workflow is used
    And the proposal is displayed
    And no file content is hashed
    And no filesystem content is modified

  Scenario: Display Name Conflicts
    Given the lightweight Organisation Proposal contains destination collisions
    When the proposal is displayed in the browser
    Then the destination collision count is shown
    And the Name Conflict file count is shown
    And deterministic collision examples are displayed

  Scenario: Warn when a proposal is based on an incomplete scan
    Given the browser Scan Result is incomplete
    When the user requests a browser Organisation Proposal for the incomplete scan
    Then the proposal may include accessible media
    But a prominent proposal warning states that the underlying scan is incomplete

  Scenario: Reject a missing Media Collection
    Given the browser interface is open
    When the user submits a missing source
    Then a clear browser validation error is displayed
    And no Python traceback is exposed

  Scenario: Reject an unsafe exclusion
    Given the browser interface is open
    When the user submits an exclusion escaping the scan root
    Then the browser exclusion is rejected
    And scanning does not proceed with that unsafe exclusion

  Scenario: Escape browser-controlled values
    Given a submitted browser value contains executable markup
    When the value is rendered by the browser interface
    Then the browser value is safely escaped
    And it cannot inject executable markup

  Scenario: Browser workflow remains read-only
    Given a Media Collection has been scanned from the browser
    When the user requests an Organisation Proposal
    Then no media is copied, moved, deleted, or renamed
    And no proposed directories are created
