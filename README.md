# StartupThoughts

*a quiet place to think about startups*

Quotes about building companies. One per page, each attributed to a named person and linked to
the source it came from.

It copies [musicthoughts.com](https://musicthoughts.com/), Derek Sivers' site about music: the
same page structure, URL scheme and serif typography.

## Running it

```
python3 build.py     # data/ + static/ -> site/
python3 serve.py     # http://localhost:4173
```

`build.py` regenerates `site/` from scratch every time, so it is safe to delete.

## Pages

| URL | What it is |
| --- | --- |
| `/` | home, and nothing but the way in |
| `/new` | every thought, newest first |
| `/authors` | authors, most-quoted first |
| `/author/<id>` | one author's thoughts |
| `/sources` | sources, most-quoted first |
| `/source/<id>` | everything drawn from one source |
| `/contributors` | the people who added thoughts |
| `/contributor/<id>` | one person's contributions |
| `/add` | add a thought: form, live preview, one-click hand-off |
| `/t/<id>` | a single thought |
| `/random` | bounces to a random thought |
| `/search` | search, run entirely in the browser |
| `/about` | about |

## Adding a thought

Append to `data/thoughts.json` and rebuild. Ids are the array position, so add to the end.
Never insert into the middle, or existing links will point at the wrong thought.

```json
{
  "text": "the quote, as the person actually wrote or said it",
  "original": "the saying in its own language (optional)",
  "original_lang": "uz",
  "author": "Their Name",
  "source": "the essay, book, talk or interview it comes from",
  "source_url": "https://...",
  "contributor": "who added it (optional, defaults to the curator)"
}
```

Or just use the `/add` page, which builds this for you and hands you the JSON.

Three fields carry the site's meaning and should not be muddled:

- **author**: who said it. Always a named person; the site does not carry anonymous or folk material.
- **source**: where they said it. An essay, book, talk, letter or interview.
- **contributor**: who put it on this site. Defaults to `curator` in `data/config.json`.

`text` may contain blank lines; they render as paragraph breaks inside the quote. Straight
quotes and apostrophes are converted to typographic ones at build time, so you can type them
plainly.

The one rule: **every quote is attributed to someone who actually said it, and traced to where
they said it.** Startup culture is full of confident misattribution. A quote that cannot be
sourced does not go in.

## Layout

```
build.py                 generator
serve.py                 dev server with clean URLs and a real 404
data/thoughts.json       the collection
data/config.json         repo for the pull-request button, curator name
data/i18n.json           UI strings per language (optional)
data/thoughts.<lang>.json translated collections (optional)
static/css/              stylesheet
static/js/               search, random thought, add-a-thought (site works without them)
check.py                 link / duplicate / attribution validator
static/img/              favicon, about-page image
site/                    generated output, do not edit
```

## Translations

Drop `data/thoughts.<lang>.json` and a matching block in `data/i18n.json` and that language is
built at `/<lang>/` and appears in the footer switcher. Languages with no data file are simply
skipped. Supported codes: `es fr de it pt ru ar ja zh`.

## Deploying

`site/` is plain static files. Any host works. On Netlify, Vercel, GitHub Pages or S3 the
directory-index URLs (`/t/12/index.html` served at `/t/12`) work with no configuration.

## Contributions

`/add` is the whole flow. Someone types the thought, sees exactly how it will look, and gets three
ways to send it. All three produce the same JSON entry:

1. **open a pull request**: a prefilled GitHub issue. Set `"repo": "you/startupthoughts"` in
   `data/config.json` and the button appears.
2. **copy the entry**: to the clipboard, ready to paste.
3. **download it**: as a `.json` file.

Nothing is sent anywhere without a click, and there is no account, no backend, and no tracking.

Merging a contribution is: paste the object into `data/thoughts.json`, `python3 build.py`,
`python3 check.py`. The contributor then appears on `/contributors` with their own page.

## The one rule

Every thought is attributed to someone who actually said it, and traced to where they said it.
Startup culture repeats a great many lines that nobody can source. Those do not go in. `check.py`
enforces the mechanical part; the rest is judgement.
