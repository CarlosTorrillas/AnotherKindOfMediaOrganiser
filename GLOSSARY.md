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

## File Extension

The normalised, lowercase filename suffix used to classify and report a discovered file type, such as `.jpg` or `.xmp`. A File Extension is distinct from a Media Category: multiple extensions may belong to the same category. Files without an extension are retained in reporting and shown to users as `[no extension]`; that label does not represent a real extension.

## Recognised Media

A file that the application currently knows how to classify as supported media based on its filename extension. Extension matching is case-insensitive.

## Unsupported File

A file encountered during a Scan that is not currently classified as Recognised Media. An Unsupported File remains visible in the Scan Result rather than being silently ignored.

## Filesystem Modification Date

The filesystem timestamp currently used as the available date source for a Media Entry. This is an interim source that may later be replaced or complemented by embedded media metadata.

## Organisation Proposal

**Future concept — not implemented yet.**

A read-only representation of how Recognised Media could be organised without changing the source Media Collection. Its detailed model has not yet been defined.

## Ubiquitous language

When a user story introduces or materially changes a domain concept, identify that concept explicitly before implementation. Reuse an existing glossary term where appropriate, or update the glossary with the new agreed meaning.

Use these terms consistently in user stories, tests, code, and documentation so implementation terminology does not drift away from product terminology. Avoid introducing synonyms for an existing concept unless their product meanings genuinely differ. For example, do not replace Media Collection casually with terms such as “Media Root”, “Source Library”, “Input Folder”, or “Media Repository”.
