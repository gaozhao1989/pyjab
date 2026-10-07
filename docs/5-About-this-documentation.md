# About this documentation

These pages are maintained as part of the pyjab project.

## Where the text lives

The Markdown files in the repository's `docs/` directory are the source of
truth. The wiki is generated from them, not edited independently — otherwise the
two drift apart and readers cannot tell which is current.

`tools/sync_wiki.py` publishes `docs/*.md` to the wiki. It rewrites the relative
`.md` links these pages use into the form the wiki expects, commits, and pushes:

```console
> python tools/sync_wiki.py --dry-run
> python tools/sync_wiki.py
```

Pages that exist only on the wiki are left untouched.

## Editing

Contributions to these pages are welcome, and are usually the most useful kind of
pull request — a confusing paragraph costs users more time than a missing
feature.

A few rules:

* **Keep code samples runnable.** Every method named here should exist in the
  current release. If you change the API, change the docs in the same commit.
* **Document what does not work.** Undocumented limitations generate issues;
  documented ones generate understanding. The *Limitations* and *Known rough
  edges* sections exist for that reason.
* **Say where the numbers come from.** When a page mentions a version or a
  default, it should be the one that ships.
* **Prefer plain language.** Most readers arrive from a search engine and want
  the answer, not the history.

## Reporting a problem with these pages

Open an issue on
[GitHub](https://github.com/gaozhao1989/pyjab/issues) and say which page and
which sentence. If a sample does not run, include the traceback.

## History

This documentation was rewritten in 1.2.0. The previous version described a
`get_screenshot_as_file()` call on the wrong object and omitted the locator
guidance entirely, which is what prompted
[issue #75](https://github.com/gaozhao1989/pyjab/issues/75).
