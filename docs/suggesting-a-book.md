# Suggesting a book

Book suggestions are welcome even if you are not a programmer and have never contributed to a GitHub project before.

A suggestion adds a work to the editorial backlog for later investigation. It does **not** mean that the work is legally cleared, reserved for processing, accepted into the corpus, or ready to upload.

## Before you suggest a work

1. Search [`docs/book-backlog.md`](book-backlog.md) for the title and author.
2. Check the **Deferred** and **Screened out for now** sections as well as the main candidate tables.
3. Make sure the work is fiction or narrative literature relevant to fiction-model training.
4. Think about what it contributes that the backlog does not already contain.

Useful reasons include:

- a distinctive narrative voice or viewpoint;
- strong dialogue, subtext, action, suspense, humour, or description;
- an important genre or subgenre;
- short fiction with complete narrative arcs;
- better balance across authors, cultures, periods, audiences, or styles;
- historically important narrative structures for a specialist heritage pack.

“I love this book” is a perfectly good reason to begin the conversation, but the pull request should also explain its likely training value.

## Rights and editions

You do **not** need to complete a legal review before suggesting a title. Please flag anything you already know, especially:

- the author's death year;
- the first publication year;
- whether the work is a translation;
- the translator's name and death year, if known;
- whether only some editions appear to be public domain;
- whether the work is still protected in the United States, the EU, or another relevant jurisdiction;
- whether a commonly available edition is abridged, revised, or contains later material.

Do not mark a work as legally cleared merely because it appears on Project Gutenberg, the Internet Archive, another dataset, or a download site. Rights are reviewed later for the exact edition and jurisdiction.

## What to add to the backlog

Add the work to the most appropriate table in [`docs/book-backlog.md`](book-backlog.md).

Use:

- **Status:** `Candidate`
- **Priority:** usually `P1` or `P2`
- **Work:** the standard English title
- **Author:** the author's name
- **Notes / Primary value:** one concise explanation of its value or an important complication

Please do not assign `P0`; first-release priorities are set during editorial review. Premodern works such as *The Odyssey* should normally use the `Heritage` priority and go in the foundational-classics section.

Example:

```markdown
| Candidate | P1 | Example Novel | A. Writer | Fast ensemble adventure with clear action geography; translation rights need review |
```

Keep a suggestion pull request reasonably small: one work is ideal, and up to five closely related works is fine. Do not submit an uncurated dump of hundreds of titles.

## Opening the pull request

You can make the change entirely on the GitHub website:

1. Open [`docs/book-backlog.md`](book-backlog.md).
2. Select the pencil icon to edit the file.
3. GitHub will offer to create a fork if you do not have write access. Accept it.
4. Add your row without reformatting unrelated parts of the file.
5. Commit the change to a new branch in your fork.
6. Select **Propose changes** and open a pull request back to this repository.
7. Use the book-suggestion pull-request template when available, or copy the form below.

Suggested pull-request title:

```text
Suggest: Book Title by Author Name
```

Pull-request description:

```markdown
## Suggested work

- **Title:**
- **Author:**
- **Original publication year:**
- **Translator, if applicable:**

## Why it belongs

<!-- What would this add to the corpus? Mention genre, voice, structure, pacing, dialogue, representation, or another concrete training value. -->

## Known rights or edition complications

<!-- It is fine to write "Unknown." Do not guess. -->

## Backlog placement

- **Section:**
- **Proposed priority:** P1 / P2 / Heritage
```

No book file, ebook, manuscript, scraped text, or generated dataset should be attached or committed with a suggestion.

## What happens after submission

Maintainers may:

- accept the backlog entry;
- adjust its section, wording, or priority;
- move it to **Deferred** or **Screened out for now**;
- ask for a source or clarification;
- decline it because the corpus already has too much similar material.

Acceptance into the backlog means only that the work is worth considering. Exact source selection, rights review, extraction, cleaning, and dataset inclusion happen in later stages.
