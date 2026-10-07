#!/usr/bin/env python
"""Publish docs/*.md to the GitHub wiki.

The wiki is a separate git repository (``<repo>.wiki.git``), so pages have to be
copied across rather than linked.  This script clones it, copies the pages whose
names match the files in ``docs/``, rewrites the relative ``.md`` links used in
the repository into the link form the wiki expects, commits and pushes.

Pages that exist only on the wiki are left alone.

Usage
-----
    python tools/sync_wiki.py --dry-run     # show what would change
    python tools/sync_wiki.py               # publish
    python tools/sync_wiki.py --message "..." # custom commit message

The wiki remote is derived from the origin remote, or can be given explicitly
with --wiki-url.
"""

from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

#: Files in docs/ that are *not* wiki pages.
NOT_A_PAGE = {"README.md"}

#: A relative Markdown link ending in .md, optionally with a fragment.
#: Absolute URLs are deliberately excluded.
RELATIVE_MD_LINK = re.compile(r"\]\((?!https?://|mailto:)([^)#\s]+)\.md((?:#[^)\s]*)?)\)")


def wiki_pages() -> list[Path]:
    """Every *versioned* file in docs/ that should become a wiki page.

    Only files tracked by git are considered, so the maintainer notes that live
    in docs/ but are listed in .gitignore (issue triage, the roadmap, reply
    drafts) can never be published to the public wiki by accident.
    """
    if not DOCS_DIR.is_dir():
        raise SystemExit(f"no docs directory at {DOCS_DIR}")

    tracked = run(["git", "ls-files", "-z", "--", "docs/*.md"], cwd=REPO_ROOT)
    names = [name for name in tracked.stdout.split("\0") if name]

    pages = []
    for name in names:
        path = REPO_ROOT / name
        if path.parent != DOCS_DIR:
            continue
        if path.name in NOT_A_PAGE:
            continue
        pages.append(path)

    return sorted(pages)


def to_wiki_markdown(text: str) -> str:
    """Rewrite repository-relative .md links into wiki links."""
    return RELATIVE_MD_LINK.sub(r"](\1\2)", text)


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def default_wiki_url() -> str:
    """Derive the wiki URL from the origin remote."""
    result = run(["git", "remote", "get-url", "origin"], cwd=REPO_ROOT)
    url = result.stdout.strip()

    # git@github.com:owner/repo.git -> https://github.com/owner/repo.wiki.git
    ssh = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
    if ssh:
        host, path = ssh.groups()
        return f"https://{host}/{path}.wiki.git"

    https = re.match(r"https?://([^/]+)/(.+?)(?:\.git)?$", url)
    if https:
        host, path = https.groups()
        return f"https://{host}/{path}.wiki.git"

    raise SystemExit(f"could not derive a wiki URL from origin remote {url!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-url", help="Wiki git URL (default: derived from origin)")
    parser.add_argument("--message", default="Sync documentation from docs/", help="Commit message")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without pushing")
    parser.add_argument("--keep", action="store_true", help="Keep the temporary clone")
    args = parser.parse_args()

    pages = wiki_pages()
    if not pages:
        raise SystemExit("no wiki pages found in docs/")

    wiki_url = args.wiki_url or default_wiki_url()
    print(f"wiki      : {wiki_url}")
    print(f"pages     : {len(pages)}")
    for page in pages:
        print(f"  - {page.name}")

    workdir = Path(tempfile.mkdtemp(prefix="pyjab-wiki-"))
    clone = workdir / "wiki"
    try:
        print(f"\ncloning into {clone}")
        run(["git", "clone", "--depth", "1", wiki_url, str(clone)])

        changed: list[str] = []
        added: list[str] = []
        for page in pages:
            target = clone / page.name
            rendered = to_wiki_markdown(page.read_text(encoding="utf-8"))
            if target.exists():
                if target.read_text(encoding="utf-8") == rendered:
                    continue
                changed.append(page.name)
            else:
                added.append(page.name)
            if not args.dry_run:
                target.write_text(rendered, encoding="utf-8")

        if not changed and not added:
            print("\neverything is already up to date")
            return 0

        print("\nwould update:" if args.dry_run else "\nupdating:")
        for name in changed:
            print(f"  M {name}")
        for name in added:
            print(f"  A {name}")

        if args.dry_run:
            print("\n--dry-run: nothing was committed or pushed")
            return 0

        run(["git", "add", "-A"], cwd=clone)
        run(["git", "-c", "user.name=pyjab", "-c", "user.email=noreply@github.com",
             "commit", "-m", args.message], cwd=clone)
        pushed = run(["git", "push", "origin", "HEAD"], cwd=clone)
        print(pushed.stdout.strip() or "pushed")
        print("\ndone")
        return 0

    except subprocess.CalledProcessError as exc:
        print(f"\ncommand failed: {' '.join(exc.cmd)}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 1
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            print(f"kept temporary clone at {clone}")


if __name__ == "__main__":
    sys.exit(main())
