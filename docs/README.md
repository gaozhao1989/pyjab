# pyjab documentation

This directory holds the project's user-facing documentation.

It is also the **source of truth for the GitHub wiki**: each file here maps to a
wiki page of the same name, and `tools/sync_wiki.py` publishes them.

```
docs/
├── README.md                    this file (not published to the wiki)
├── Home.md                      wiki landing page
├── 1-Overview.md                what pyjab is, and whether it fits your problem
├── 2-Getting-Started.md         install, prerequisites, first script
├── 3-pyjab.md                   the API guide
├── 4-Support-Packages.md        the libraries pyjab depends on
├── 5-About-this-documentation.md
├── 6-Troubleshooting.md         the problems people actually hit
└── 7-Changelog.md               points at CHANGELOG.rst
```

## Publishing to the wiki

The wiki is a separate git repository (`pyjab.wiki.git`), so the pages have to be
copied across. `tools/sync_wiki.py` does that, rewriting the relative `.md` links
used here into the link form the wiki expects:

```bash
python tools/sync_wiki.py --dry-run    # show what would change
python tools/sync_wiki.py              # clone, update, push
```

It clones the wiki to a temporary directory, copies every page listed above,
commits, and pushes. Nothing else in the wiki is touched -- pages that exist only
on the wiki are left alone.

## Writing style

* Use `.md` links between pages here (e.g. `2-Getting-Started.md`). The sync
  script converts them.
* Keep code samples runnable. Every API call in these pages should exist in the
  current release; if you change the code, change the docs in the same commit.
* Say what does **not** work. Undocumented limitations generate more issues than
  missing features do.
