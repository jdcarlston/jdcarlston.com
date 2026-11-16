#!/usr/bin/env python3
"""
medium_import.py — move a Medium export into jdcarlston.com as Markdown.

What it does, in one run:
  1. Reads every post in Medium's export (the unzipped folder with posts/ inside).
  2. Converts each one to Markdown, keeping poem line breaks and stanza breaks.
  3. Downloads every image and points the post at your own copy.
  4. Sorts posts into writing/poetry/ and writing/prose/ in your site repo, using
     the tags saved in the export, then "poetry:" / "song:" title prefixes, then
     a guess from line lengths.
  5. Puts drafts, and files that look like comment replies, in separate folders
     OUTSIDE the repo, so they never become public by accident.
  6. Writes a review spreadsheet (CSV) next to your export, also outside the repo.

Usage:
  python3 scripts/medium_import.py EXPORT_FOLDER REPO_FOLDER [options]

Example:
  python3 scripts/medium_import.py ~/Downloads/medium-export ~/Projects/jdcarlston.com

Options:
  --drafts-out FOLDER   where drafts go (default: ~/Documents/medium-drafts)
  --replies-out FOLDER  where likely comment replies go (default: ~/Documents/medium-replies)
  --no-images           skip downloading images (keeps Medium's image links)
  --overwrite           replace Markdown files from an earlier run
  --fresh               delete the Markdown in writing/poetry and writing/prose first,
                        then rebuild everything (downloaded images are kept)

Safe to run more than once: images already downloaded are skipped, and existing
Markdown files are left alone unless you pass --overwrite or --fresh.

Needs: pip install beautifulsoup4 requests
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import random
import shutil
import re
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    sys.exit("Missing libraries. Run:  pip install beautifulsoup4 requests")


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 medium-import/1.0"
)
POETRY_TAG_HINTS = ("poe", "verse", "haiku", "sonnet", "cynghanedd")
SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


# --------------------------------------------------------------------------
# Reading a Medium export file
# --------------------------------------------------------------------------

def slug_from_filename(name: str, strip_prefix: bool = False) -> str:
    """'2019-02-01_My-Poem-Title-1a2b3c4d5e6f.html' -> 'my-poem-title'."""
    stem = Path(name).stem
    stem = re.sub(r"^draft_", "", stem)
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", stem)
    stem = re.sub(r"-[0-9a-f]{10,16}$", "", stem)
    if strip_prefix:
        stem = re.sub(r"^(?i:poetry|poem|song)-+", "", stem)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return stem or "untitled"


def post_id_from(name: str, soup: BeautifulSoup) -> str | None:
    for a in soup.select("footer a[href]"):
        m = re.search(r"medium\.com/p/([0-9a-f]{8,16})", a["href"])
        if m:
            return m.group(1)
    m = re.search(r"-([0-9a-f]{10,16})$", Path(name).stem)
    return m.group(1) if m else None


def text_of(el: Tag | None) -> str:
    return re.sub(r"[ \t\r\n]+", " ", el.get_text()).strip() if el else ""


# --------------------------------------------------------------------------
# HTML -> Markdown, written for Medium's markup
# --------------------------------------------------------------------------

def md_escape_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")


def inline(node: Tag) -> str:
    """Convert the inside of a paragraph. <br> becomes a real line break."""
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            # Collapse ordinary whitespace but keep non-breaking spaces,
            # which poets use for indentation.
            out.append(md_escape_text(re.sub(r"[ \t\r\n]+", " ", str(child))))
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name
        if name == "br":
            out.append("\n")
        elif name in ("strong", "b"):
            out.append(wrap(inline(child), "**"))
        elif name in ("em", "i"):
            out.append(wrap(inline(child), "*"))
        elif name == "code":
            out.append("`" + child.get_text() + "`")
        elif name == "a" and child.get("href"):
            label = inline(child).strip() or child["href"]
            out.append(f"[{label}]({child['href']})")
        else:
            out.append(inline(child))
    return "".join(out)


def wrap(s: str, mark: str) -> str:
    """Put ** or * around text, keeping edge spaces outside the markers."""
    if not s.strip():
        return s
    edge = " \u00a0"
    lead = s[: len(s) - len(s.lstrip(edge))]
    trail = s[len(s.rstrip(edge)):]
    return f"{lead}{mark}{s.strip(edge)}{mark}{trail}"


LINE_START_SYMBOL = re.compile(r"^(\s*)([#>+\-])(\s|$)")
LINE_START_NUMBER = re.compile(r"^(\s*)(\d+)([.)])(\s|$)")


def clean_lines(s: str) -> str:
    lines = []
    for line in s.split("\n"):
        line = line.strip(" ")
        # A line like '# hope' or '1. morning' would turn into a heading or a
        # list; escape the first character so it stays literal.
        line = LINE_START_SYMBOL.sub(lambda m: m.group(1) + "\\" + m.group(2) + m.group(3), line)
        line = LINE_START_NUMBER.sub(lambda m: m.group(1) + m.group(2) + "\\" + m.group(3) + m.group(4), line)
        if re.fullmatch(r"[=\-]{2,}", line):
            line = "\\" + line
        lines.append(line)
    return "\n".join(lines).strip("\n")


class Converter:
    def __init__(self, title: str, subtitle: str, image_handler, known_poem: bool = False):
        self.known_poem = known_poem
        self.title = title
        self.subtitle = subtitle
        self.image_handler = image_handler
        self.blocks: list[tuple[str, str, int]] = []  # (kind, markdown, section)
        self.section = 0

    def _add(self, item: tuple[str, str]):
        self.blocks.append((item[0], item[1], self.section))

    def run(self, body: Tag) -> tuple[str, dict]:
        sections = body.select("section.section") or [body]
        for i, section in enumerate(sections):
            self.section = i
            if i > 0 and self.blocks:
                self._add(("break", "* * *"))
            inners = section.select("div.section-inner") or [section]
            for inner in inners:
                for el in inner.children:
                    if isinstance(el, Tag):
                        self.block(el)
        return self.assemble()

    def block(self, el: Tag):
        name = el.name
        classes = el.get("class", [])
        if name in ("h1", "h2", "h3", "h4"):
            t = text_of(el)
            def norm(x: str) -> str:
                return re.sub(r"\W+", "", x).lower()
            if "graf--title" in classes or (not self.blocks and norm(t) == norm(self.title)):
                return
            if "graf--subtitle" in classes or (len(self.blocks) <= 1 and t == self.subtitle):
                return
            level = "##" if name in ("h1", "h2", "h3") else "###"
            self._add(("heading", f"{level} {md_escape_text(t)}"))
        elif name == "p":
            raw = clean_lines(inline(el))
            if not raw.strip():
                self._add(("empty", ""))
            else:
                self._add(("p", raw))
        elif name == "blockquote":
            raw = clean_lines(inline(el))
            self._add(("quote", "\n".join("> " + l if l else ">" for l in raw.split("\n"))))
        elif name in ("ul", "ol"):
            items = []
            for n, li in enumerate(el.find_all("li", recursive=False), 1):
                marker = f"{n}." if name == "ol" else "-"
                items.append(f"{marker} {clean_lines(inline(li)).replace(chr(10), ' ')}")
            self._add(("list", "\n".join(items)))
        elif name == "figure":
            img = el.find("img")
            cap = el.find("figcaption")
            if img and img.get("src"):
                alt = (img.get("alt") or text_of(cap) or "").replace("]", "")
                src = self.image_handler(img["src"])
                md = f"![{alt}]({src})"
                if cap and text_of(cap):
                    md += f"\n*{clean_lines(inline(cap))}*"
                self._add(("image", md))
            else:
                iframe = el.find("iframe")
                link = el.find("a", href=True)
                url = (iframe.get("src") if iframe else None) or (link["href"] if link else None)
                if url:
                    self._add(("embed", f"[Embedded media]({url})"))
        elif name == "pre":
            self._add(("code", "```\n" + el.get_text() + "\n```"))
        elif name == "hr":
            self._add(("break", "* * *"))
        elif name == "div":
            link = el.find("a", href=True)
            if "graf--mixtapeEmbed" in classes and link:
                self._add(("embed", f"[{text_of(el)}]({link['href']})"))
            else:
                for child in el.children:
                    if isinstance(child, Tag):
                        self.block(child)

    def assemble(self) -> tuple[str, dict]:
        paras = [b for k, b, _ in self.blocks if k == "p"]
        empties = sum(1 for k, _, _ in self.blocks if k == "empty")
        breaks = sum(1 for k, _, _ in self.blocks if k == "break")
        lengths = [len(p) for p in paras if "\n" not in p]
        # "Line mode": a poem typed one line per paragraph, with empty
        # paragraphs or section dividers between stanzas. Lines get joined
        # back into stanzas, but only in sections where every paragraph is
        # short, so essays with a few short lines are left alone.
        poem_shaped = self.known_poem or bool(
            (empties >= 1 or breaks >= 2) and len(paras) >= 4
            and lengths and statistics.median(lengths) < 70
        )
        joinable = set()
        if poem_shaped:
            by_section: dict[int, list[str]] = {}
            for k, md, sec in self.blocks:
                if k == "p":
                    by_section.setdefault(sec, []).append(md)
            joinable = {sec for sec, ps in by_section.items()
                        if len(ps) >= 2 and all(len(p) < 150 and "\n" not in p for p in ps)}
        line_mode = bool(joinable)

        out: list[str] = []
        stanza: list[str] = []
        for kind, md, sec in self.blocks:
            if kind == "p" and sec in joinable:
                stanza.append(md)
                continue
            if stanza:
                out.append("\n".join(stanza))
                stanza = []
            if kind == "empty":
                continue
            out.append(md)
        if stanza:
            out.append("\n".join(stanza))
        while out and out[0] == "* * *":
            out.pop(0)
        text = "\n\n".join(out).strip() + "\n"

        # Signals for the poetry/prose guess.
        all_lines = [l for p in paras for l in p.split("\n") if l.strip()]
        multi_line_paras = sum(1 for p in paras if "\n" in p)
        stats = {
            "line_mode": line_mode,
            "paragraphs": len(paras),
            "multi_line_share": (multi_line_paras / len(paras)) if paras else 0.0,
            "median_line": statistics.median([len(l) for l in all_lines]) if all_lines else 0,
            "lines": len(all_lines),
            "words": len(re.findall(r"\w+", text)),
        }
        return text, stats


def guess_is_poetry(stats: dict) -> bool:
    if stats["words"] < 150:  # very short untagged pieces are almost always poems
        return True
    if stats["line_mode"]:
        return True
    if stats["multi_line_share"] >= 0.4:
        return True
    return stats["lines"] >= 6 and stats["median_line"] < 55


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

def bigger_image_url(url: str) -> str:
    url = re.sub(r"(cdn-images-\d\.medium\.com/)max/\d+/", r"\1max/2000/", url)
    url = re.sub(r"(miro\.medium\.com/(?:v2/)?)resize:fit:\d+/", r"\1resize:fit:2000/", url)
    return url


EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}


class ImageFetcher:
    """Downloads images slowly, and stops for this run if Medium cuts it off."""

    STOP_AFTER = 5  # failures in a row

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.failed_in_a_row = 0
        self.stopped = False

    def get(self, url: str, dest_dir: Path, index: int) -> Path | None:
        name = Path(urlparse(url).path).name or f"image{index}"
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
        existing = sorted(dest_dir.glob(f"{index:02d}-{Path(name).stem}*")) if dest_dir.exists() else []
        if existing:
            if ".." in existing[0].name:  # tidy names from an earlier version
                fixed = existing[0].with_name(re.sub(r"\.{2,}", ".", existing[0].name))
                existing[0].rename(fixed)
                return fixed
            return existing[0]
        if not self.enabled or self.stopped:
            return None
        dest_dir.mkdir(parents=True, exist_ok=True)
        time.sleep(0.75 + random.random() * 0.75)
        for candidate in (bigger_image_url(url), url):
            try:
                r = SESSION.get(candidate, timeout=30)
            except requests.RequestException:
                continue
            if r.status_code == 200 and r.content:
                ext = Path(name).suffix.lower()
                if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
                    ext = EXT_BY_TYPE.get(r.headers.get("Content-Type", "").split(";")[0], ".jpg")
                path = dest_dir / f"{index:02d}-{Path(name).stem}{ext}"
                path.write_bytes(r.content)
                self.failed_in_a_row = 0
                return path
            if r.status_code in (403, 429):
                break
            if candidate == url:
                break
        self.failed_in_a_row += 1
        if self.failed_in_a_row >= self.STOP_AFTER:
            self.stopped = True
            print("\n  Medium's image server stopped answering. Skipping the remaining images for now;"
                  "\n  wait an hour or so and run the same command again with --overwrite to finish them.\n")
        return None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

# Files that hold several unpublished poems, to be split into one file per
# poem wherever Medium section dividers separate them. Add post IDs here.
POEM_SETS: set[str] = set()  # none right now
# Unpublished poems that Medium exported as if they were posts. They go to
# the drafts folder (private), one file each. To add another, put its Medium
# post ID here: the 12-character code at the end of its export file name.
WHOLE_POEMS = {
    "f435ff354aa8",  # I hope you know
    "bb651c982ddb",  # A Week's Worth...
    "be7765a41d8d",  # Behind my desire lies a question...
    "ee0744aec619",  # Another good litmus is telling them "No"...
    "c1f4d7d10cc1",  # Call
    "2703689c66a0",  # Creating a listing...
    "25f93639d25b",  # i do so love the world...
    "eb7bb0e63f80",  # Ride around in a car with a bear growl.
    "cdd664053d88",  # This is rape.
    "41fcdca9d27a",  # we are the Shadow...
}


def split_set(soup: BeautifulSoup, body: Tag) -> list[tuple[str, Tag]]:
    """Split a set of poems at Medium's section dividers. Returns (title, body) pairs."""
    sections = body.select("section.section") or [body]
    groups: list[dict] = []
    carried_title = ""
    for i, sec in enumerate(sections):
        words = len(re.findall(r"\w+", sec.get_text(" ")))
        elements = [el for inner in sec.select("div.section-inner") for el in inner.children if isinstance(el, Tag)]
        is_last = i == len(sections) - 1
        if len(elements) <= 1 and words < 8 and not sec.find("img"):
            if not is_last:
                carried_title = text_of(sec)  # a lone short line titles the next poem
                continue
            if groups:
                groups[-1]["sections"].append(sec)  # e.g. a date stamp at the end
                continue
        first = elements[0] if elements else None
        heading = text_of(first) if first is not None and first.name in ("h3", "h4") else ""
        title = carried_title or heading
        carried_title = ""
        if not title:
            first_line = (first.get_text("\n") if first is not None else "").strip().split("\n")[0]
            words_list = first_line.split()
            title = " ".join(words_list[:8]) + ("…" if len(words_list) > 8 else "")
        groups.append({"title": title or "untitled", "sections": [sec]})
    out = []
    for g in groups:
        wrapper = soup.new_tag("div")
        for sec in g["sections"]:
            wrapper.append(copy.copy(sec))
        out.append((g["title"], wrapper))
    return out


# Which site each essay belongs on. Poems all go to Madder Craft; an essay not
# listed here is marked "unassigned". Keys are Medium post IDs.
JD, RTL, MC = "jdcarlston.com", "red-thread-labs.com", "maddercraft.com"
ESSAY_SITES = {
    "de966cdf7c0d": [JD],   # What in the World Is World-Class Engineering?
    "4b384c74dc19": [JD],   #   ... Part 2
    "7c4ccde0b454": [JD],   #   ... Part 3
    "6cda3e3099e": [JD],    # When Quality is Important
    "95e4663588fd": [JD],   # Trust is a Jenky State Machine
    "ef934bc97411": [JD],   # Becoming Resilient in the Age of A.I.
    "5e729afc07ec": [JD],   # Leaning Tower Mistakes Cost Companies Billions
    "c4d34e1987ce": [JD],   # Blueprints for Success
    "2e52874a0a44": [JD],   # May I have a few words with you...
    "faa9ebe95e9c": [JD],   # Life is Weird Right Now.
    "24015cf0d159": [JD],   # My Learning Journey Through the Apparel Industry
    "a1b336bac305": [JD],   #   ... Part 2
    "3ef3c20d90db": [JD],   #   ... Part 3
    "e6c254b554fc": [JD],   #   ... Part 4
    "fef57251277b": [RTL],  # I'm Sorry You Feel That Way.
    "d7d204c8262a": [RTL],  # You Have Been Chosen
    "a0e6021cc06d": [JD, RTL],  # Diversity Brings Conflict
    "dc0f77ce8890": [MC],   # The Witch Wound
    "2c03afe3d8cb": [MC],   # On Being an Entrepreneur
    "47f47f1de487": [MC],   # On Being An Entrepreneur (second version)
    "a32869755e66": [MC],   # What I Care About
    "b4da56b6cf06": [MC],   # My Foundations are Shook
}


TITLE_PREFIX = re.compile(r"^\s*(poetry|poem|song)\s*:\s*", re.I)


def yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # JSON strings are valid YAML


def main():
    ap = argparse.ArgumentParser(description="Import a Medium export into jdcarlston.com")
    ap.add_argument("export", type=Path, help="unzipped Medium export (or its posts/ folder)")
    ap.add_argument("repo", type=Path, help="your jdcarlston.com repo folder")
    ap.add_argument("--drafts-out", type=Path, default=Path.home() / "Documents" / "medium-drafts")
    ap.add_argument("--replies-out", type=Path, default=Path.home() / "Documents" / "medium-replies")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    export = args.export.expanduser().resolve()
    posts_dir = export / "posts" if (export / "posts").is_dir() else export
    if posts_dir.name == "posts" and export == posts_dir:
        export = posts_dir.parent
    repo = args.repo.expanduser().resolve()
    drafts_out = args.drafts_out.expanduser().resolve()
    replies_out = args.replies_out.expanduser().resolve()
    if not posts_dir.is_dir():
        sys.exit(f"Can't find the posts folder in {export}")
    if not (repo / ".git").exists():
        sys.exit(f"{repo} doesn't look like a git repo. Point the second argument at jdcarlston.com.")
    for folder, flag in ((drafts_out, "--drafts-out"), (replies_out, "--replies-out")):
        if folder == repo or repo in folder.parents:
            sys.exit(f"That folder must be outside the repo, which is public. Choose another {flag}.")

    files = sorted(posts_dir.glob("*.html"))
    if not files:
        sys.exit(f"No .html files in {posts_dir}")
    print(f"Found {len(files)} files in {posts_dir}\n")

    if args.fresh:
        for cat in ("poetry", "prose"):
            for md in (repo / "writing" / cat).glob("*.md"):
                md.unlink()
        args.overwrite = True

    report_path = export.parent / "medium-import-report.csv"
    images = ImageFetcher(enabled=not args.no_images)
    used_slugs: dict[str, set] = {}
    rows = []

    for n, f in enumerate(files, 1):
        is_draft = f.name.startswith("draft_")
        soup = BeautifulSoup(f.read_text(encoding="utf-8"), "html.parser")
        raw_title = text_of(soup.select_one("h1.p-name")) or text_of(soup.title) or slug_from_filename(f.name)
        prefix = TITLE_PREFIX.match(raw_title)
        form = prefix.group(1).lower() if prefix else ""
        title = raw_title[prefix.end():].strip() if prefix else raw_title
        # Only a real subtitle; Medium's export also stores an automatic preview.
        subtitle = text_of(soup.select_one('section[data-field="body"] .graf--subtitle'))
        when = soup.select_one("time.dt-published")
        date = (when.get("datetime", "")[:10] if when else "") or (re.match(r"\d{4}-\d{2}-\d{2}", f.name) or [""])[0]
        canonical = soup.select_one("a.p-canonical")
        url = canonical["href"] if canonical else None
        tag_list = [text_of(a) for a in soup.select("footer a.p-tag")]
        has_title_block = soup.select_one(".graf--title") is not None

        # Medium exports comment replies as posts. They have no title block
        # and can't be tagged; their "title" is just their opening words.
        is_reply = not is_draft and not has_title_block and not tag_list and not prefix

        post_id = post_id_from(f.name, soup)
        if not is_draft and post_id in WHOLE_POEMS:
            body = soup.select_one('section[data-field="body"]') or soup.body
            whole_slug = slug_from_filename(f.name)
            print(f"[{n}/{len(files)}] UNPUBLISHED POEM {raw_title}")
            for stale in [repo / "writing" / c / f"{whole_slug}.md" for c in ("poetry", "prose")] + \
                         [replies_out / f"{whole_slug}.md"]:
                if stale.exists():
                    stale.unlink()
            stale_dir = drafts_out / "poem-sets" / whole_slug  # from a version that split it
            if stale_dir.exists():
                shutil.rmtree(stale_dir)
            img_dir = drafts_out / "images" / whole_slug
            ok, counter = [0], [0]

            def whole_image(src: str) -> str:
                counter[0] += 1
                path = images.get(src, img_dir, counter[0])
                if path:
                    ok[0] += 1
                    return f"images/{whole_slug}/{path.name}"
                return src

            md, st = Converter(raw_title, "", whole_image, known_poem=True).run(body)
            out_path = drafts_out / f"{whole_slug}.md"
            front = ["---", f"title: {yaml_str(raw_title)}"]
            if date:
                front.append(f"date: {date}")
            front += ["category: poetry", "draft: true"]
            if url:
                front.append(f"medium_url: {url}")
            front.append("---\n")
            note = ""
            if out_path.exists() and not args.overwrite:
                note = "kept existing file (use --overwrite to rebuild)"
            else:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text("\n".join(front) + "\n" + md, encoding="utf-8")
            rows.append({
                "kind": "unpublished poem (draft)", "title": raw_title, "date": date,
                "category": "poetry", "sorted_by": "your list", "form": "",
                "medium_tags": "", "words": st["words"],
                "poem_typed_line_per_paragraph": "yes" if st["line_mode"] else "",
                "images_downloaded": ok[0], "images_failed": 0, "output": str(out_path),
                "medium_url": url or "", "source_file": f.name, "notes": note,
            })
            continue

        if not is_draft and post_id in POEM_SETS:
            body = soup.select_one('section[data-field="body"]') or soup.body
            set_slug = slug_from_filename(f.name)
            set_dir = drafts_out / "poem-sets" / set_slug
            pieces = split_set(soup, body)
            print(f"[{n}/{len(files)}] SET ({len(pieces)} poems) {raw_title}")
            # Remove anything an earlier run put in the public repo or replies folder.
            for stale in [repo / "writing" / c / f"{set_slug}.md" for c in ("poetry", "prose")] + \
                         [replies_out / f"{set_slug}.md"]:
                if stale.exists():
                    stale.unlink()
            for part, (piece_title, piece_body) in enumerate(pieces, 1):
                piece_slug = f"{part:02d}-" + (re.sub(r"[^A-Za-z0-9]+", "-", piece_title).strip("-").lower()[:50] or "untitled")
                img_dir = set_dir / "images" / piece_slug
                ok, counter = [0], [0]

                def set_image(src: str, img_dir=img_dir, piece_slug=piece_slug, ok=ok, counter=counter) -> str:
                    counter[0] += 1
                    path = images.get(src, img_dir, counter[0])
                    if path:
                        ok[0] += 1
                        return f"images/{piece_slug}/{path.name}"
                    return src

                md, st = Converter(piece_title, "", set_image, known_poem=True).run(piece_body)
                out_path = set_dir / f"{piece_slug}.md"
                front = ["---", f"title: {yaml_str(piece_title)}", f"set: {yaml_str(raw_title)}",
                         f"part: {part}"]
                if date:
                    front.append(f"date: {date}")
                front += ["category: poetry", "draft: true"]
                if url:
                    front.append(f"medium_url: {url}")
                front.append("---\n")
                if out_path.exists() and not args.overwrite:
                    note = "kept existing file (use --overwrite to rebuild)"
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text("\n".join(front) + "\n" + md, encoding="utf-8")
                    note = ""
                rows.append({
                    "kind": "poem set (draft)", "title": piece_title, "date": date,
                    "category": "poetry", "sorted_by": "your list", "form": "",
                    "medium_tags": "", "words": st["words"],
                    "poem_typed_line_per_paragraph": "yes" if st["line_mode"] else "",
                    "images_downloaded": ok[0], "images_failed": 0, "output": str(out_path),
                    "medium_url": url or "", "source_file": f.name,
                    "notes": f"part {part} of {len(pieces)} from \"{raw_title}\"" + (f"; {note}" if note else ""),
                })
            continue

        old_slug = slug_from_filename(f.name)
        base_slug = slug_from_filename(f.name, strip_prefix=bool(prefix))
        bucket = "drafts" if is_draft else ("replies" if is_reply else "posts")
        taken = used_slugs.setdefault(bucket, set())
        slug, k = base_slug, 2
        while slug in taken:
            slug, k = f"{base_slug}-{k}", k + 1
        taken.add(slug)

        label = "DRAFT " if is_draft else ("REPLY? " if is_reply else "")
        print(f"[{n}/{len(files)}] {label}{raw_title}")

        # Images go beside wherever the post ends up.
        if is_draft:
            img_dir, img_url_prefix = drafts_out / "images" / slug, f"images/{slug}"
        elif is_reply:
            img_dir, img_url_prefix = replies_out / "images" / slug, f"images/{slug}"
            # Move images an earlier run saved inside the public repo.
            old_dir = repo / "writing" / "images" / old_slug
            if old_dir.exists() and not img_dir.exists():
                img_dir.parent.mkdir(parents=True, exist_ok=True)
                old_dir.rename(img_dir)
        else:
            img_dir, img_url_prefix = repo / "writing" / "images" / slug, f"/writing/images/{slug}"
            # Reuse images an earlier run saved under the old "poetry-..." name.
            old_dir = repo / "writing" / "images" / old_slug
            if old_slug != slug and old_dir.exists() and not img_dir.exists():
                old_dir.rename(img_dir)
        img_ok, img_failed, counter = [0], [0], [0]

        def handle_image(src: str) -> str:
            counter[0] += 1
            path = images.get(src, img_dir, counter[0])
            if path:
                img_ok[0] += 1
                return f"{img_url_prefix}/{path.name}"
            if not args.no_images:
                img_failed[0] += 1
            return src

        body = soup.select_one('section[data-field="body"]') or soup.body
        markdown, stats = Converter(raw_title, subtitle, handle_image).run(body)

        # Sorting: poetry tag > title prefix > guess
        if any(h in t.lower() for t in tag_list for h in POETRY_TAG_HINTS):
            category, sorted_by = "poetry", "tags"
        elif prefix:
            category, sorted_by = "poetry", "title prefix"
        else:
            category = "poetry" if guess_is_poetry(stats) else "prose"
            sorted_by = "guess"

        front = ["---", f"title: {yaml_str(title)}"]
        if subtitle:
            front.append(f"subtitle: {yaml_str(subtitle)}")
        if date:
            front.append(f"date: {date}")
        front.append(f"category: {category}")
        if form == "song":
            front.append("form: song")
        front.append(f"sorted_by: {sorted_by}")
        sites = [MC] if category == "poetry" else ESSAY_SITES.get(post_id or "", ["unassigned"])
        front.append("sites: [" + ", ".join(sites) + "]")
        if tag_list:
            front.append("medium_tags: [" + ", ".join(yaml_str(t) for t in tag_list) + "]")
        if url:
            front.append(f"medium_url: {url}")
        if is_draft:
            front.append("draft: true")
        front.append("---\n")
        content = "\n".join(front) + "\n" + markdown

        others: list[Path] = []
        if is_draft:
            out_path = drafts_out / f"{slug}.md"
        elif is_reply:
            out_path = replies_out / f"{slug}.md"
            others = [repo / "writing" / c / f"{s}.md" for c in ("poetry", "prose") for s in {slug, old_slug}]
        else:
            out_path = repo / "writing" / category / f"{slug}.md"
            other_cat = "prose" if category == "poetry" else "poetry"
            others = [repo / "writing" / other_cat / f"{slug}.md"]
            if old_slug != slug:
                others += [repo / "writing" / c / f"{old_slug}.md" for c in ("poetry", "prose")]

        note = ""
        if out_path.exists() and not args.overwrite:
            note = "kept existing file (use --overwrite to rebuild)"
        else:
            if args.overwrite:
                for p in others:
                    if p.exists():
                        p.unlink()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
        if is_reply:
            note = (note + "; " if note else "") + "no title or tags: probably a comment reply, check"

        rows.append({
            "kind": "draft" if is_draft else ("reply?" if is_reply else "post"),
            "title": title,
            "date": date,
            "category": category,
            "sorted_by": sorted_by,
            "form": form,
            "sites": " + ".join(sites) if not is_draft and not is_reply else "",
            "medium_tags": ", ".join(tag_list),
            "words": stats["words"],
            "poem_typed_line_per_paragraph": "yes" if stats["line_mode"] else "",
            "images_downloaded": img_ok[0],
            "images_failed": img_failed[0],
            "output": str(out_path),
            "medium_url": url or "",
            "source_file": f.name,
            "notes": note,
        })

    with report_path.open("w", newline="", encoding="utf-8") as fh:
        fields = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    posts = [r for r in rows if r["kind"] == "post"]
    replies = [r for r in rows if r["kind"] == "reply?"]
    print("\nDone.")
    print(f"  Posts on the site: {len(posts)}  "
          f"(poetry {sum(r['category'] == 'poetry' for r in posts)}, "
          f"prose {sum(r['category'] == 'prose' for r in posts)})")
    for how in ("tags", "title prefix", "guess"):
        print(f"    sorted by {how}: {sum(r['sorted_by'] == how for r in posts)}")
    print(f"  Probable replies: {len(replies)}  ->  {replies_out}")
    print(f"  Drafts: {sum(r['kind'] == 'draft' for r in rows)}  ->  {drafts_out}")
    sets = [r for r in rows if r["kind"] == "poem set (draft)"]
    if sets:
        print(f"  Poem sets: {len({r['source_file'] for r in sets})} split into {len(sets)} poems"
              f"  ->  {drafts_out / 'poem-sets'}")
    print(f"  Images downloaded: {sum(r['images_downloaded'] for r in rows)}   "
          f"not downloaded: {sum(r['images_failed'] for r in rows)}")
    print(f"  Review spreadsheet: {report_path}")


if __name__ == "__main__":
    main()
