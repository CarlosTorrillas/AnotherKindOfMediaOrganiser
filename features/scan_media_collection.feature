Feature: Scan a media collection safely
  As a user
  I want to scan a folder containing my media
  So that I can understand what it contains before making any changes

  Scenario: Scan a folder containing supported media
    Given a directory containing these supported media files:
      | filename     |
      | portrait.jpg |
      | holiday.heic |
      | camera.arw   |
      | clip.mp4     |
    When the user scans the directory
    Then the scan reports 4 total files
    And the scan reports 4 recognised media files
    And the media counts are 2 images, 1 RAW file, and 1 video

  Scenario: Scan nested directories
    Given a directory containing media files in two nested directories
    When the user scans the directory
    Then the nested media files are included in the result
    And the scan reports 3 directories scanned

  Scenario: Unsupported files are reported
    Given a directory containing 1 supported media file and 2 unsupported files
    When the user scans the directory
    Then the scan reports 2 unsupported files
    And the scan reports 1 recognised media file

  Scenario: Extension matching is case-insensitive
    Given a directory containing mixed-case media extensions
    When the user scans the directory
    Then the media counts are 1 image, 1 RAW file, and 1 video

  Scenario: Scan an empty directory
    Given an empty directory
    When the user scans the directory
    Then the scan reports 0 total files
    And the scan reports 0 recognised media files
    And the scan reports 0 unsupported files

  Scenario: Do not follow directory symbolic links
    Given a directory containing a symbolic link to an external directory
    When the user scans the directory
    Then the symbolic link is not recursively followed

  Scenario: Report recognised file extensions
    Given a Media Collection containing these files:
      | filename       |
      | first.jpg      |
      | second.jpeg    |
      | negative.arw   |
      | recording.mp4  |
    When the user scans the Media Collection
    Then the recognised extension breakdown is:
      | extension | count |
      | .jpg      | 1     |
      | .jpeg     | 1     |
      | .arw      | 1     |
      | .mp4      | 1     |

  Scenario: Report unsupported file extensions
    Given a Media Collection containing these files:
      | filename  |
      | sidecar.xmp |
      | edit.aae  |
      | notes.pdf |
    When the user scans the Media Collection
    Then the unsupported extension breakdown is:
      | extension | count |
      | .xmp      | 1     |
      | .aae      | 1     |
      | .pdf      | 1     |

  Scenario: Extension counts are case-insensitive
    Given a Media Collection containing these files:
      | filename     |
      | first.jpg    |
      | second.JPG   |
      | third.JpG    |
      | first.XMP    |
      | second.xmp   |
    When the user scans the Media Collection
    Then the recognised extension breakdown is:
      | extension | count |
      | .jpg      | 3     |
    And the unsupported extension breakdown is:
      | extension | count |
      | .xmp      | 2     |

  Scenario: Report files without extensions
    Given a Media Collection containing these files:
      | filename |
      | README   |
    When the user scans the Media Collection
    Then the unsupported extension breakdown is:
      | extension      | count |
      | [no extension] | 1     |

  Scenario: Extension totals remain consistent with scan totals
    Given a Media Collection containing these files:
      | filename      |
      | photo.jpg     |
      | portrait.PNG  |
      | sidecar.xmp   |
      | README        |
    When the user scans the Media Collection
    Then recognised extension counts equal recognised media files
    And unsupported extension counts equal unsupported files
    And all extension counts equal total files
