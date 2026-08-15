Feature: Generate an Organisation Proposal
  As a user
  I want the organiser to propose how my recognised media could be organised
  So that I can review the intended structure before any files are changed

  Scenario: Propose organisation by year and month
    Given recognised Media Entries with different Media Creation Dates
    When the user generates an Organisation Proposal
    Then each Media Entry is proposed under its corresponding year and month

  Scenario: Organise by Media Category
    Given recognised IMAGE, RAW, VIDEO and AUDIO Media Entries
    When the user generates an Organisation Proposal
    Then each proposed destination includes its Media Category

  Scenario: Preserve original filenames
    Given recognised Media Entries with distinct original filenames
    When the user generates an Organisation Proposal
    Then each proposed destination preserves its original filename exactly

  Scenario: Unsupported files are excluded
    Given a Scan Result containing Recognised Media and Unsupported Files
    When the user generates an Organisation Proposal
    Then only Recognised Media receives proposed destinations

  Scenario: Detect destination collisions
    Given two different Media Entries that produce the same proposed destination
    When the user generates an Organisation Proposal
    Then both Media Entries remain in the Organisation Proposal
    And the destination collision is reported

  Scenario: Proposal generation is read-only
    Given a Media Collection for proposal generation
    When the user generates an Organisation Proposal from the Media Collection
    Then the Media Collection remains unchanged

