# Delta Index

Delta Index is a free, public, machine-readable GitHub archive of events in:

- Shenzhen
- Hong Kong
- Guangzhou

There is no website, paid server, or Cloudflare layer in this version. GitHub stores the source archive, checks the event data, and updates the public JSON feeds automatically.

The repository starts with **no events**, so the fictional records in `examples/events.example.json` cannot accidentally appear in the public archive.

## Repository structure

```text
data/events.json               The one file you edit
examples/events.example.json   Clearly marked examples to copy
feeds/                         Public, automatically generated JSON
schema/event.schema.json       Definition of a valid event
scripts/build_feeds.py         Validation and feed builder
.github/workflows/             Daily GitHub automation
```

The automation creates:

```text
feeds/upcoming.json
feeds/upcoming-shenzhen.json
feeds/upcoming-hong-kong.json
feeds/upcoming-guangzhou.json
feeds/events.json
feeds/archive.json
```

Each event is marked `upcoming`, `ongoing`, `ended`, or `cancelled` automatically. Ended and cancelled events remain in the archive.

## Upload to GitHub

1. Sign in to [GitHub](https://github.com/).
2. Select **New repository**.
3. Name it `delta-index`.
4. Choose **Public**.
5. Do not add a README, `.gitignore`, or license on GitHub—the downloaded folder already contains the project files.
6. Create the repository.
7. In the empty repository, choose **uploading an existing file**.
8. Extract `delta-index-starter.zip`, then drag everything inside the extracted folder into the upload page. Upload the contents, not the enclosing folder.
9. On macOS, press **Command + Shift + .** in Finder if the `.github` folder is hidden. Make sure `.github` is included.
10. Choose **Commit changes**.

The repository's top level should show:

```text
.github
data
examples
feeds
schema
scripts
tests
README.md
```

GitHub will run **Rebuild event feeds** after upload. If GitHub does not let the workflow save the generated feeds, open **Settings → Actions → General → Workflow permissions**, select **Read and write permissions**, and save. Then open **Actions → Rebuild event feeds → Run workflow**.

## Public feed addresses

If your GitHub username were `YOUR-USERNAME`, the combined upcoming-event feed would be:

```text
https://raw.githubusercontent.com/YOUR-USERNAME/delta-index/main/feeds/upcoming.json
```

The complete archive would be:

```text
https://raw.githubusercontent.com/YOUR-USERNAME/delta-index/main/feeds/events.json
```

An AI application with browsing or web retrieval can open those addresses. A model without an internet-access tool cannot fetch them by itself.

## Add the first event

1. Open `examples/events.example.json` on GitHub.
2. Copy one complete event object—from its opening `{` to its closing `}`.
3. Open `data/events.json` and select the pencil icon.
4. Replace `[]` with an opening square bracket, the copied object, and a closing square bracket.
5. Replace every example value with information from the real event source.
6. Commit the change.

For one event, the file should have this shape:

```json
[
  {
    "id": "sz-2026-08-08-short-name-001",
    "title": "Real event title",
    "city": "shenzhen",
    "start": "2026-08-08T19:30:00+08:00",
    "end": "2026-08-08T21:00:00+08:00",
    "venue": {
      "name": "Real venue name",
      "address": "Full address"
    },
    "description": "A short factual description.",
    "source_url": "https://the-original-event-page.example",
    "last_verified": "2026-08-05",
    "price": "Free",
    "languages": ["zh-CN", "en"],
    "tags": ["art", "talk"],
    "cancelled": false
  }
]
```

Use these exact city names and ID prefixes:

| City | `city` value | ID begins with |
| --- | --- | --- |
| Shenzhen | `shenzhen` | `sz-` |
| Hong Kong | `hong-kong` | `hk-` |
| Guangzhou | `guangzhou` | `gz-` |

Dates and times must include the `+08:00` offset. Each ID must be unique and use only lowercase letters, numbers, and hyphens.

For two or more events, put a comma between the event objects:

```json
[
  { "first": "event" },
  { "second": "event" }
]
```

That tiny example only demonstrates commas; it is not valid event data by itself.

## What the automation does

Every day, and whenever the source data changes, GitHub will:

1. Check that every event has valid fields, dates, city values, IDs, and web links.
2. Stop and show an error instead of generating malformed data.
3. Calculate whether events are upcoming, ongoing, ended, or cancelled.
4. Rebuild the combined, city-specific, and archive JSON feeds.
5. Save the refreshed feeds back to the repository.

Scheduled workflows in inactive public repositories may be disabled by GitHub after 60 days without repository activity. Adding or correcting events normally counts as activity; the workflow can also be restarted manually from the Actions tab.

