# Domain glossary

This glossary defines the shared business vocabulary of AnotherKindOfMediaOrganiser. Definitions describe what each term means within this application.

## Media Collection

The source root directory selected by the user for scanning. A Media Collection may contain files and nested directories. Organisation Execution treats it as read-only and never uses it as the Destination Collection.

## Destination Collection

A separate root directory that receives organised copies during Organisation Execution. Its structure comes from an accepted Organisation Proposal. It must neither be inside nor contain the source Media Collection.

## Scan

A read-only inspection of a Media Collection. A Scan gathers information about the collection and must not modify it. A Scan is complete only when every path needed for traversal and media discovery could be inspected.

## Incomplete Scan

A Scan that encountered one or more inaccessible filesystem paths. Its Scan Result contains only information that could be inspected safely and records the inaccessible paths and reported reasons. An incomplete Scan may inform a partial Organisation Proposal or Collision Verification, but it must never be used for Organisation Execution.

## Scan Result

The information produced by a Scan. It currently summarises the total files encountered, recognised media, unsupported files, directories scanned, media counts by category, discovered File Extensions, discovered Media Entries, whether the Scan is complete, and any inaccessible paths.

## Media Entry

A recognised media file discovered during a Scan. A Media Entry currently identifies the file's path, its Media Category, and the Filesystem Modification Date used by the application.

## Media Category

The logical classification assigned to recognised media. The currently supported Media Categories are:

- `IMAGE`
- `RAW`
- `VIDEO`
- `AUDIO`

Media in this application is broader than photographs and video. It includes recognised image, RAW image, video, and audio assets that may be valuable to the user.

## Media Format

The concrete format of a media file, currently identified by its normalised File Extension. For example, `.mp3`, `.aac`, `.opus`, and `.amr` are distinct Media Formats within the `AUDIO` Media Category. Media Format and Media Category are not interchangeable concepts.

## File Extension

The normalised, lowercase filename suffix currently used to identify a Media Format and report a discovered file type, such as `.jpg` or `.xmp`. A leading-dot filename without another suffix, such as `.DS_Store`, is retained as an extension-like file type and reported in lowercase. A File Extension is distinct from both a Media Format and a Media Category: it is the application's current identification mechanism. Files without an extension are retained in reporting and shown to users as `[no extension]`; that label does not represent a real extension.

## Recognised Media

A file whose Media Format the application currently supports and can assign to a Media Category. Recognition is currently based on case-insensitive File Extension matching.

## Unsupported File

A file encountered during a Scan that is not currently classified as Recognised Media. An Unsupported File remains visible in the Scan Result rather than being silently ignored.

## Filesystem Modification Date

The filesystem timestamp currently used as the available date source for a Media Entry. This is an interim source that may later be replaced or complemented by embedded media metadata.

## Media Creation Date

The date that best represents when media was originally created or captured. Organisation Proposals use this concept to determine year and month. It is currently resolved from the Filesystem Modification Date as a temporary fallback; future metadata-aware resolution may replace that source without changing what Media Creation Date means.

## Organisation Proposal

A read-only plan showing how Recognised Media could be organised without changing the source Media Collection. It contains one Proposed Placement for every recognised Media Entry, detects Destination Collisions, and routes Name Conflicts to a review location. Generating the standard proposal does not inspect file content or classify files as identical or different, and performs no organisation operation.

## Organisation Execution

The explicit application of an accepted Organisation Proposal to a Destination Collection. It never silently overwrites an existing destination file. COPY and MOVE Organisation Execution use the same proposal and complete safety preflight.

## Capacity Preflight

A read-only check performed before Organisation Execution that compares the requested Organisation Proposal with usable destination capacity. Usable capacity is reported free space minus the explicit safety reserve. Capacity Preflight may select the full proposal, offer a Partial Organisation Proposal, or determine that no complete Year/Month group can be executed.

## Partial Organisation Proposal

A subset of an Organisation Proposal containing a continuous oldest-first prefix of complete chronological Year/Month groups selected because of destination capacity constraints. Selection stops at the first Year/Month group that does not fit and never skips ahead to include a later month, even if that later month would fit. Every included Proposed Placement retains exactly its original destination; excluded Media Entries remain untouched.

## COPY Organisation Execution

Organisation Execution that creates each Proposed Placement in the Destination Collection while leaving every source Media Entry unchanged. COPY is always the default mode.

## MOVE Organisation Execution

Organisation Execution in which a successfully moved Media Entry exists at its Proposed Placement and its original source is removed only after the completed destination has been verified as byte-for-byte identical. A failed or incomplete verification never authorises source deletion.

## Proposed Placement

The placement of one recognised Media Entry within an Organisation Proposal. It identifies the source Media Entry, proposed destination, normal proposed destination, Media Category, Media Creation Date used for organisation, and whether it participates in a Destination Collision.

## Destination Collision

A situation where two or more different Media Entries receive the same normal proposed destination in an Organisation Proposal. A Destination Collision does not prove that its files are duplicates. Collision counts represent distinct conflicting destination paths, not the number of Media Entries involved.

## Name Conflict

A non-canonical Media Entry that competes with another Media Entry for the same normal proposed destination. It receives a deterministic review destination under `nameConflicts/`. A Name Conflict records only competition for a proposed path; it does not imply that file contents are identical, different, or unreadable.

## Collision Verification

An explicit, potentially expensive, read-only analysis of Media Entries involved in Destination Collisions. Collision Verification compares file sizes and, when necessary, SHA-256 content digests to classify non-canonical entries as Exact Duplicates, Potential Conflicts, or Unverified Conflicts. It is separate from the standard lightweight Organisation Proposal and does not create the proposed review directories.

## Canonical Placement

The deterministic, neutral placement in a Destination Collision that retains the normal proposed destination. It is selected by stable source-path ordering and does not imply that its Media Entry is higher quality or more authoritative.

## Exact Duplicate

A non-canonical Media Entry whose file contents have been verified through explicit content analysis as byte-for-byte identical to the Canonical Placement. Exact Duplicate files receive deterministic proposed destinations under `exactDuplicates/`. The standard lightweight Organisation Proposal does not make this classification.

## Potential Conflict

A non-canonical Media Entry that competes for the same normal proposed destination but whose explicit content analysis differs from the Canonical Placement. Potential Conflict files remain available for human review under `potentialConflicts/`. The standard lightweight Organisation Proposal does not make this classification.

## Unverified Conflict

A Media Entry involved in explicit content analysis whose content could not be safely verified against the Canonical Placement. Unverified Conflict files remain represented under `unverifiedConflicts/` and are not counted as Exact Duplicates or Potential Conflicts. The standard lightweight Organisation Proposal does not make this classification.

## Ubiquitous language

When a user story introduces or materially changes a domain concept, identify that concept explicitly before implementation. Reuse an existing glossary term where appropriate, or update the glossary with the new agreed meaning.

Use these terms consistently in user stories, tests, code, and documentation so implementation terminology does not drift away from product terminology. Avoid introducing synonyms for an existing concept unless their product meanings genuinely differ. For example, do not replace Media Collection casually with terms such as “Media Root”, “Source Library”, “Input Folder”, or “Media Repository”.
