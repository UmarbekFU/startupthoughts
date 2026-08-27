#!/usr/bin/env python3
"""
StartupThoughts static site generator.

Reads data/thoughts.json (+ optional data/thoughts.<lang>.json translations and
data/i18n.json UI strings) and writes a complete static site into site/.

URL structure mirrors musicthoughts.com:
    /                     home
    /new                  every thought, newest first
    /authors              top authors
    /author/<id>          one author's thoughts
    /contributors         top sources
    /contributor/<id>     one source's thoughts
    /t/<id>               a single thought
    /search               search
    /about                about
    /random               bounce to a random thought
"""

import html
import json
import os
import random
import re
import shutil
import unicodedata
from collections import OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
STATIC = os.path.join(ROOT, "static")
OUT = os.path.join(ROOT, "site")

SEED = 20260826  # stable ids and stable footer quotes across rebuilds


# ---------------------------------------------------------------- utilities

def esc(s):
    return html.escape(s, quote=True)


def slugify(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "x"


def smarten(s):
    """Curly quotes / dashes, the way a serif typographic site wants them."""
    s = re.sub(r"(?<=\w)'(?=\w)", "\u2019", s)          # don't -> don’t
    s = re.sub(r'(^|[\s(\[])"', "\\1\u201c", s)          # opening "
    s = s.replace('"', "\u201d")                          # closing "
    s = re.sub(r"(^|[\s(\[])'", "\\1\u2018", s)
    s = s.replace("'", "\u2019")
    return s


KAZAKH_LETTERS = set("\u04d9\u0493\u049b\u04a3\u04e9\u04b1\u04af\u04bb\u0456")


def guess_lang(text):
    """Tag the original in its own language, not whatever the default was.

    Uzbek is written in Latin here, so any Cyrillic is Kazakh or Russian; the
    letters above appear in Kazakh and not in Russian.
    """
    if not text:
        return "uz"
    if not any("\u0400" <= c <= "\u04ff" for c in text):
        return "uz"
    return "kk" if KAZAKH_LETTERS & set(text.lower()) else "ru"


def body_html(text):
    """Paragraph breaks inside a quote render the way musicthoughts does them."""
    parts = [p.strip() for p in re.split(r"\n{2,}|\n", text) if p.strip()]
    return " <br> <br>".join(esc(p) for p in parts)


def write(path, content):
    full = os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------- i18n

DEFAULT_STRINGS = {
    "site_name": "StartupThoughts",
    "tagline": "a quiet place to think about startups",
    "nav_new": "new",
    "nav_authors": "authors",
    "nav_sources": "sources",
    "nav_contributors": "contributors",
    "nav_add": "add a thought",
    "nav_random": "random thought",
    "nav_search": "search",
    "nav_about": "about",
    "title_new": "new StartupThoughts",
    "title_authors": "top authors",
    "title_sources": "top sources",
    "title_contributors": "top contributors",
    "title_add": "add a thought",
    "title_search": "search",
    "title_about": "about StartupThoughts",
    "title_notfound": "not found",
    "search_label": "search for any subject, founder, idea, anything\u2026",
    "search_button": "search",
    "search_none": "Nothing found.",
    "search_one": "1 thought",
    "search_many": "{n} thoughts",
    "from": "from",
    "added_by": "added by",
    "by": "thoughts by",
    "collected_from": "thoughts from",
    "added_by_page": "thoughts added by",
    "notfound_body": "That thought isn\u2019t here.",
    "meta_home": "A quiet place to think about startups \u2014 a collection of the best thoughts on building things, from the people who built them.",
}

LOCALES = OrderedDict([
    ("en", {"name": "English", "dir": "ltr", "base": ""}),
    ("es", {"name": "Espa\u00f1ol", "dir": "ltr", "base": "/es"}),
    ("fr", {"name": "Fran\u00e7ais", "dir": "ltr", "base": "/fr"}),
    ("de", {"name": "Deutsch", "dir": "ltr", "base": "/de"}),
    ("it", {"name": "Italiano", "dir": "ltr", "base": "/it"}),
    ("pt", {"name": "Portugu\u00eas", "dir": "ltr", "base": "/pt"}),
    ("ru", {"name": "\u0420\u0443\u0441\u0441\u043a\u0438\u0439", "dir": "ltr", "base": "/ru"}),
    ("ar", {"name": "\u0627\u0644\u0639\u0631\u0628\u064a\u0629", "dir": "rtl", "base": "/ar"}),
    ("ja", {"name": "\u65e5\u672c\u8a9e", "dir": "ltr", "base": "/ja"}),
    ("zh", {"name": "\u4e2d\u6587", "dir": "ltr", "base": "/zh"}),
])


CONFIG = {}


def load_config():
    path = os.path.join(DATA, "config.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_i18n():
    path = os.path.join(DATA, "i18n.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- data model

class Site:
    def __init__(self, thoughts):
        self.thoughts = thoughts
        self.by_id = {t["id"]: t for t in thoughts}

        self.authors = OrderedDict()       # who said it
        self.sources = OrderedDict()       # where they said it
        self.contributors = OrderedDict()  # who added it to this site
        for t in thoughts:
            self.authors.setdefault(t["author"], []).append(t)
            self.sources.setdefault(t["source"], []).append(t)
            if t["contributor"]:
                self.contributors.setdefault(t["contributor"], []).append(t)

        self.author_id = self._ids(self.authors)
        self.source_id = self._ids(self.sources)
        self.contributor_id = self._ids(self.contributors)
        # first thought each contributor added — breaks ties on the board
        self.first_seen = {n: min(t["id"] for t in ts)
                           for n, ts in self.contributors.items()}

    def board(self):
        """Everyone, ranked by count. Ties go to whoever got there first."""
        rows = list(self.contributors.items())
        rows.sort(key=lambda kv: (-len(kv[1]), self.first_seen[kv[0]]))
        return rows

    @staticmethod
    def _ids(group):
        return {n: i for i, n in
                enumerate(sorted(group, key=lambda n: (-len(group[n]), n)), 1)}

    @staticmethod
    def _top(group):
        return sorted(group.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    def top_authors(self):
        return self._top(self.authors)

    def top_sources(self):
        return self._top(self.sources)

    def top_contributors(self):
        return self._top(self.contributors)


# ---------------------------------------------------------------- templates

class Renderer:
    def __init__(self, site, lang, strings, available_locales, rng):
        self.site = site
        self.lang = lang
        self.s = strings
        self.locales = available_locales
        self.rng = rng
        self.base = LOCALES[lang]["base"]
        self.dir = LOCALES[lang]["dir"]

    def u(self, path):
        """URL within this locale."""
        return (self.base + path) or "/"

    # ---- chrome

    def head(self, title, page_path, description=""):
        alts = []
        for code in self.locales:
            if code == self.lang:
                continue
            alts.append(
                '<link rel="alternate" hreflang="%s" href="%s" />'
                % (code, (LOCALES[code]["base"] + page_path) or "/")
            )
        desc = ('<meta name="description" content="%s" />\n' % esc(description)) if description else ""
        return """<!doctype html>
<html lang="%(lang)s" dir="%(dir)s">
<head>
<meta charset="utf-8">
<title>%(title)s</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
%(desc)s<link rel="stylesheet" href="/css/startupthoughts.css" />
<link rel="icon" href="/img/favicon.svg" type="image/svg+xml" />
%(alts)s
</head>
""" % {
            "lang": self.lang,
            "dir": self.dir,
            "title": esc(title),
            "desc": desc,
            "alts": "\n".join(alts),
        }

    def header(self, body_id):
        rnd = self.rng.choice(self.site.thoughts)["id"]
        items = [
            (self.u("/new"), self.s["nav_new"], ""),
            (self.u("/authors"), self.s["nav_authors"], ""),
            (self.u("/contributors"), self.s["nav_contributors"], ""),
            (self.u("/add"), self.s["nav_add"], ""),
            (self.u("/t/%d" % rnd), self.s["nav_random"], ' id="randomlink"'),
            (self.u("/search"), self.s["nav_search"], ""),
            (self.u("/about"), self.s["nav_about"], ""),
        ]
        lis = "\n".join('\t<li><a href="%s"%s>%s</a></li>' % (h, a, esc(l)) for h, l, a in items)
        return """<body id="%(bodyid)s">
<div id="page">

<header id="bighead">
<hgroup>
<h1><a href="%(home)s">%(name)s</a></h1>
<h2>%(tagline)s</h2>
</hgroup>

<nav id="nav">
<ul>
%(lis)s
</ul>
</nav>
</header>
""" % {
            "bodyid": esc(body_id),
            "home": self.u("/"),
            "name": esc(self.s["site_name"]),
            "tagline": esc(self.s["tagline"]),
            "lis": lis,
        }

    def footer(self, path):
        t = self.rng.choice(self.site.thoughts)
        others = [c for c in self.locales if c != self.lang]
        if others:
            langs = """<nav id="langforms">
<ul>
%s
</ul>
</nav>
""" % "\n".join(
                '\t<li><a href="%s">%s</a></li>'
                % ((LOCALES[c]["base"] + path) or "/", esc(LOCALES[c]["name"]))
                for c in others
            )
        else:
            langs = ""
        return """
<footer id="bigfoot">
%(langs)s

<blockquote cite="%(href)s">
	<q>%(quote)s</q>
	<cite><a href="%(href)s">%(author)s</a></cite>
</blockquote>

</footer>

</div>
<script src="/js/startupthoughts.js"></script>
</body>
</html>
""" % {
            "langs": langs,
            "href": self.u("/t/%d" % t["id"]),
            "quote": body_html(t["text"]),
            "author": esc(t["author"]),
        }

    def page(self, body_id, title, path, content, description=""):
        return (
            self.head(title, path, description)
            + self.header(body_id)
            + '\n<section id="content">\n\n'
            + content
            + "\n</section>\n"
            + self.footer(path)
        )

    # ---- fragments

    def original_line(self, t):
        """The saying in its own language, under the English."""
        if not t.get("original"):
            return ""
        return '\n\t<p class="original" lang="%s">%s</p>' % (
            t.get("original_lang", "uz"), esc(t["original"]))

    def quote_block(self, t, standalone=False):
        author_href = self.u("/author/%d" % self.site.author_id[t["author"]])
        if standalone:
            out = ' <a href="%s" rel="nofollow noopener" target="_blank">\u2197</a>' % esc(
                t["source_url"]) if t.get("source_url") else ""
            credit = ""
            if t["contributor"]:
                credit = ' &middot; %s <a href="%s">%s</a>' % (
                    esc(self.s["added_by"]),
                    self.u("/contributor/%d" % self.site.contributor_id[t["contributor"]]),
                    esc(t["contributor"]))
            foot = '\n\t<footer>%s %s%s%s</footer>' % (
                esc(self.s["from"]), esc(t["source"]), out, credit)
            return """<blockquote>
	<q>%s</q>%s
	<cite><a href="%s">%s</a></cite>%s
</blockquote>""" % (body_html(t["text"]), self.original_line(t),
                    author_href, esc(t["author"]), foot)
        # No original-language line in list views: it doubles the weight of
        # every entry and makes /new hard to scan. It stays on /t/<id>.
        href = self.u("/t/%d" % t["id"])
        return """<blockquote cite="%s">
	<q>%s</q>
	<cite><a href="%s">%s</a></cite>
</blockquote>""" % (href, body_html(t["text"]), href, esc(t["author"]))

    def quote_list(self, thoughts):
        items = "\n".join("\n\t<li>%s\n\n</li>\n" % self.quote_block(t) for t in thoughts)
        return "<ul>\n%s</ul>\n" % items

    # ---- pages

    def build(self):
        s, site = self.s, self.site

        # home
        rnd = self.rng.choice(site.thoughts)["id"]
        homenav = "\n".join(
            '\t<li><a href="%s">%s</a></li>' % (h, esc(l))
            for h, l in [
                (self.u("/new"), s["nav_new"]),
                (self.u("/authors"), s["nav_authors"]),
                (self.u("/contributors"), s["nav_contributors"]),
                (self.u("/add"), s["nav_add"]),
                (self.u("/t/%d" % rnd), s["nav_random"]),
                (self.u("/search"), s["nav_search"]),
            ]
        )
        write(self._f("/"), self.page(
            "home", s["site_name"], "/",
            '<ul id="homenav">\n%s\n</ul>\n' % homenav, s["meta_home"]))

        # new
        write(self._f("/new"), self.page(
            "new", s["title_new"], "/new",
            "<h1>%s</h1>\n%s" % (esc(s["title_new"]), self.quote_list(list(reversed(site.thoughts))))))

        # authors index
        rows = "\n".join(
            '\n\t<li><a href="%s">%s</a> <small>(%d)</small></li>\n'
            % (self.u("/author/%d" % site.author_id[n]), esc(n), len(ts))
            for n, ts in site.top_authors()
        )
        write(self._f("/authors"), self.page(
            "authors", s["title_authors"], "/authors",
            '<h1>%s</h1>\n<ul class="linklist">\n%s</ul>\n' % (esc(s["title_authors"]), rows)))

        # each author
        for name, ts in site.authors.items():
            aid = site.author_id[name]
            write(self._f("/author/%d" % aid), self.page(
                "author", "%s \u2014 %s" % (name, s["site_name"]), "/author/%d" % aid,
                "<h1>%s</h1>\n%s" % (esc(name), self.quote_list(ts)),
                "%s %s" % (s["by"], name)))

        # contributors index — the people who added them
        write(self._f("/contributors"), self.page(
            "contributors", s["title_contributors"], "/contributors",
            '<h1>%s</h1>\n%s\n' % (esc(s["title_contributors"]),
                                    self.leaderboard())))

        for name, ts in site.contributors.items():
            cid = site.contributor_id[name]
            write(self._f("/contributor/%d" % cid), self.page(
                "contributor", "%s \u2014 %s" % (name, s["site_name"]), "/contributor/%d" % cid,
                "<h1>%s</h1>\n%s" % (esc(name), self.quote_list(ts)),
                "%s %s" % (s["added_by_page"], name)))

        # add a thought
        write(self._f("/add"), self.page("add", s["title_add"], "/add", self.add_body()))

        # each thought
        for t in site.thoughts:
            snippet = re.sub(r"\s+", " ", t["text"])[:60]
            write(self._f("/t/%d" % t["id"]), self.page(
                "t", "%s quote: %s\u2026" % (t["author"], snippet), "/t/%d" % t["id"],
                self.quote_block(t, standalone=True),
                re.sub(r"\s+", " ", t["text"])[:180]))

        # search
        write(self._f("/search"), self.page("search", s["title_search"], "/search", """<h1>%s</h1>

<form id="searchform" action="%s" method="get" role="search">
<label for="q">%s</label>
<input type="text" id="q" name="q" value="" size="10" autocomplete="off" autofocus>
<input type="submit" name="search" class="button" value="%s">
</form>

<div id="results"></div>
""" % (esc(s["title_search"]), self.u("/search"), esc(s["search_label"]), esc(s["search_button"]))))

        # about
        write(self._f("/about"), self.page("about", s["title_about"], "/about", self.about_body()))

        # random bouncer
        write(self._f("/random"), """<!doctype html>
<html lang="%s"><head><meta charset="utf-8"><title>%s</title>
<script>
var base=%s, ids=%s;
location.replace(base+"/t/"+ids[Math.floor(Math.random()*ids.length)]);
</script>
<meta http-equiv="refresh" content="0;url=%s"></head>
<body></body></html>
""" % (self.lang, esc(s["nav_random"]), json.dumps(self.base),
       json.dumps([t["id"] for t in site.thoughts]),
       self.u("/t/%d" % self.rng.choice(site.thoughts)["id"])))

        # search index
        idx = [
            {"i": t["id"], "t": t["text"], "a": t["author"], "s": t["source"]}
            for t in site.thoughts
        ]
        write((self.base + "/search-index.json").lstrip("/"),
              json.dumps({"base": self.base, "thoughts": idx}, ensure_ascii=False))

    def _f(self, path):
        p = (self.base + path).strip("/")
        return (p + "/index.html") if p else "index.html"

    def contribute_callout(self):
        return ('<p class="callout">Everything here was put here by somebody. '
                '<a href="%s"><strong>Add a thought</strong></a> \u2014 it takes about a minute, '
                'and you need no account.</p>' % self.u("/add"))

    def leaderboard(self):
        """A standings board. Rank is your count, and nothing else."""
        rows = self.site.board()
        top = len(rows[0][1]) if rows else 0

        out = []

        if not rows:
            return ('<p class="hint">Nobody is on the board yet. '
                    '<a href="%s">First one takes it.</a></p>' % self.u("/add"))

        out.append('<ol class="board">')
        for i, (name, ts) in enumerate(rows):
            n = len(ts)
            place = i + 1
            if i == 0:
                note = "holding first"
            else:
                need = len(rows[i - 1][1]) - n + 1
                note = ("%d to pass %s" % (need, esc(rows[i - 1][0]))) if need > 0 \
                    else "tied, %s got there first" % esc(rows[i - 1][0])
            cls = "place" + (" p%d" % place if place <= 3 else "")
            out.append(
                '\t<li class="%s">'
                '<span class="rank">%d</span>'
                '<a class="who" href="%s">%s</a>'
                '<span class="count">%d</span>'
                '<span class="note">%s</span>'
                "</li>" % (cls, place,
                           self.u("/contributor/%d" % self.site.contributor_id[name]),
                           esc(name), n, note))
        out.append("</ol>")

        out.append(
            '<p class="totake">To take first place you need <strong>%d</strong>. '
            '<a href="%s">Start.</a></p>' % (top + 1, self.u("/add")))
        return "\n".join(out)

    def add_body(self):
        if self.lang != "en" and "add" in self.s:
            return self.s["add"]
        repo = CONFIG.get("repo", "")
        rows = self.site.board()
        standing = ""
        if rows:
            leader, ts = rows[0]
            standing = (
                '<p class="callout">First place is <a href="%s"><strong>%s</strong></a> '
                'with %d. You need <strong>%d</strong> to take it. '
                '<a href="%s">See the board.</a></p>\n'
                % (self.u("/contributor/%d" % self.site.contributor_id[leader]),
                   esc(leader), len(ts), len(ts) + 1, self.u("/contributors")))
        return """<h1>add a thought</h1>
%(standing)s
""" % {"standing": standing} + """

<p>
One rule: it has to be something a real person really said or wrote, and you have to know where.
A line everyone repeats but nobody can source does not go in. That rule is the only reason this
collection is worth reading.
</p>

<form id="addform" data-repo="%(repo)s" autocomplete="off">

<label for="f_text">the thought</label>
<textarea id="f_text" name="text" rows="4" maxlength="400" required
	placeholder="Short. One or two sentences. No quotation marks around it."></textarea>
<p class="hint"><span id="f_count">0</span>/400</p>

<label for="f_original">the original, if it was not said in English <em>(optional)</em></label>
<input type="text" id="f_original" name="original"
	placeholder="Mehnat \u2014 baxt keltirar">

<label for="f_author">who said it</label>
<input type="text" id="f_author" name="author" required
	placeholder="Zafar Khashimov">

<label for="f_source">where they said it</label>
<input type="text" id="f_source" name="source" required
	placeholder="the essay, book, talk or interview it comes from">

<label for="f_url">a link to it <em>(optional, but it is what makes this checkable)</em></label>
<input type="url" id="f_url" name="source_url" placeholder="https://">

<label for="f_by">your name, so you get the credit</label>
<input type="text" id="f_by" name="contributor" required placeholder="how you want to be listed">

<input type="submit" id="f_submit" value="prepare it">
</form>

<div id="addpreview" hidden>
<h2>this is how it will look</h2>
<div id="addpreview_body"></div>

<h2>now send it</h2>
<p class="hint">Pick whichever is easiest. All three end up in the same place.</p>
<p id="addactions">
	<a href="#" id="act_pr" class="bigbutton">open a pull request</a>
	<a href="#" id="act_copy" class="bigbutton">copy the entry</a>
	<a href="#" id="act_dl" class="bigbutton">download it</a>
</p>
<p class="hint" id="act_note"></p>

<pre id="addjson"></pre>
</div>
""" % {"repo": esc(repo)}

    def about_body(self):
        if self.lang != "en" and "about" in self.s:
            return self.s["about"]
        return """<img src="/img/portrait.svg" alt="" width="200">
<p>
StartupThoughts is a collection of the best things ever said about starting things.
</p><p>
Every founder works mostly in the dark. The people in here worked in the same dark, and a few of
them wrote down what they found. When you are stuck, one good sentence from someone who has been
stuck in the same place is worth more than a whole shelf of advice.
</p><p>
So this is a quiet place. No feed, no scores, no comments, no popups, no tracking. One thought at
a time, big enough to read, with a link back to wherever it actually came from.
</p><p>
Every quote here is attributed to a real person and traced to a real source \u2014 an essay, a book, a
talk, a letter, an interview. If you find something misattributed, that is a bug, and it should be
fixed.
</p><p>
Much of it comes from closer to home than the usual Silicon Valley canon: the scholars of Bukhara
and Khorezm who worked out how to think carefully about the world, poets like Navoi and Abai who
were unusually blunt about work and money, and founders building in Tashkent, Almaty and Bishkek
today. Where a line was not said in English, the original is printed underneath.
</p><p>
The best way to use it is to press <a href="%s">random thought</a> until one of them lands.
</p><p>
Anyone can <a href="%s">add a thought</a>. It takes a minute and needs no account.
</p><p>
StartupThoughts is a totally free non-commercial site, here only for your inspiration.
</p><p>
It is modelled on <a href="https://musicthoughts.com/" rel="noopener">MusicThoughts</a>, Derek
Sivers\u2019 quiet place to think about music, which has been doing this since 1999.
</p>""" % (self.u("/random"), self.u("/add"))


# ---------------------------------------------------------------- driver

def load_thoughts(lang):
    name = "thoughts.json" if lang == "en" else "thoughts.%s.json" % lang
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    items = raw["thoughts"] if isinstance(raw, dict) else raw
    out = []
    for i, t in enumerate(items, 1):
        # A thought is an aphorism, not an excerpt. Anything long enough to be a
        # passage from someone's book has no place here and is dropped loudly.
        if len(t["text"]) > 320:
            raise ValueError(
                "thought %d (%s) is %d chars \u2014 too long to be a quotable line; "
                "trim it to the sentence that carries the idea"
                % (i, t.get("author", "?"), len(t["text"]))
            )
        out.append({
            "id": t.get("id", i),
            "text": smarten(t["text"].strip()),
            "author": smarten(t["author"].strip()),
            "source": smarten(t["source"].strip()),
            "source_url": (t.get("source_url") or "").strip(),
            "original": (t.get("original") or "").strip(),
            "original_lang": (t.get("original_lang") or guess_lang(
                t.get("original") or "")).strip(),
            "contributor": smarten((t.get("contributor") or "").strip()),
        })
    return out


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    global CONFIG
    CONFIG = load_config()
    i18n = load_i18n()
    available = [c for c in LOCALES if load_thoughts(c) is not None]
    print("locales:", ", ".join(available))

    for lang in available:
        thoughts = load_thoughts(lang)
        strings = dict(DEFAULT_STRINGS)
        strings.update(i18n.get(lang, {}))
        site = Site(thoughts)
        Renderer(site, lang, strings, available, random.Random(SEED + sum(map(ord, lang)))).build()
        print("  %-3s %d thoughts, %d authors, %d sources"
              % (lang, len(thoughts), len(site.authors), len(site.sources)))

    # static assets
    for sub in ("css", "img", "js"):
        src = os.path.join(STATIC, sub)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(OUT, sub), dirs_exist_ok=True)

    # 404
    en = Site(load_thoughts("en"))
    r = Renderer(en, "en", DEFAULT_STRINGS, available, random.Random(SEED))
    write("404.html", r.page("notfound", DEFAULT_STRINGS["title_notfound"], "/404",
          "<h1>%s</h1>\n<p>%s</p>\n<p><a href=\"/random\">%s</a></p>\n"
          % (esc(DEFAULT_STRINGS["title_notfound"]), esc(DEFAULT_STRINGS["notfound_body"]),
             esc(DEFAULT_STRINGS["nav_random"]))))

    # sitemap + robots
    urls = []
    for lang in available:
        b = LOCALES[lang]["base"]
        s2 = Site(load_thoughts(lang))
        urls += [b + "/", b + "/new", b + "/authors", b + "/contributors",
                 b + "/add", b + "/search", b + "/about"]
        urls += [b + "/t/%d" % t["id"] for t in s2.thoughts]
        urls += [b + "/author/%d" % i for i in s2.author_id.values()]
        urls += [b + "/contributor/%d" % i for i in s2.contributor_id.values()]
    write("sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "\n".join("<url><loc>https://startupthoughts.com%s</loc></url>" % (u or "/") for u in urls)
          + "\n</urlset>\n")
    write("robots.txt", "User-agent: *\nAllow: /\nSitemap: https://startupthoughts.com/sitemap.xml\n")

    n = sum(len(files) for _, _, files in os.walk(OUT))
    print("built %d files into %s" % (n, OUT))


if __name__ == "__main__":
    main()
