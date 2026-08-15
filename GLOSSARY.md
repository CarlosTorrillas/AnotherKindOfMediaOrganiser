# Domain glossary

This glossary defines the shared business vocabulary of AnotherKindOfMediaOrganiser. Definitions describe what each term means within this application.

## Media Collection

The root directory selected by the user for scanning. A Media Collection may contain files and nested directories.

## Scan

A read-only inspection of a Media Collection. A Scan gathers information about the collection and must not modify it.

## Scan Result

The information produced by a Scan. It currently summarises the total files encountered, recognised media, unsupported files, directories scanned, media counts by category, discovered File Extensions, and discovered Media Entries.

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

A read-only plan showing how Recognised Media could be organised without changing the source Media Collection. It contains one Proposed Placement for every recognised Media Entry and reports proposed destinations that collide. Generating a proposal performs no organisation operation.

## Proposed Placement

The placement of one recognised Media Entry within an Organisation Proposal. It identifies the source Media Entry, proposed destination, Media Category, Media Creation Date used for organisation, and whether another Proposed Placement has the same destination.

## Ubiquitous language

When a user story introduces or materially changes a domain concept, identify that concept explicitly before implementation. Reuse an existing glossary term where appropriate, or update the glossary with the new agreed meaning.

Use these terms consistently in user stories, tests, code, and documentation so implementation terminology does not drift away from product terminology. Avoid introducing synonyms for an existing concept unless their product meanings genuinely differ. For example, do not replace Media Collection casually with terms such as “Media Root”, “Source Library”, “Input Folder”, or “Media Repository”.
