# Support

pyjab is maintained by one person. This page says what you can expect for free, what
needs a commercial arrangement, and what to include so that a report can be acted on
rather than guessed at.

## Free, through GitHub issues

[Open an issue](https://github.com/gaozhao1989/pyjab/issues) for:

- a bug — something the library does that it should not, or fails to do that it should;
- a feature request, especially one with a use case behind it;
- a question about using the library, or about whether it can reach a particular control.

**Best effort, no response time promised.** Issues are read and answered; there is no
service level agreement behind this channel and it would be dishonest to imply one. If
you need an answer by a date, that is the commercial channel below.

There has never been an unanswered issue, and the intent is to keep it that way.

## Not free

- **Integrating pyjab into your application or CI**, or writing the automation itself.
- **A response time commitment**, an escalation path, or a private channel.
- **Custom development**, however small — a new action, a workaround for one vendor's
  Java build, an unusual accessibility interface.
- **Anything under an NDA**, or anything you cannot discuss in a public issue.

## Commercial support

Integration help, custom development and time-boxed support:
**`gaozhao89@qq.com`**. Say what the application is, what you need it to do, and your
timeline. A short description of the problem is more useful than a formal request.

## What to include in a bug report

Almost every report that cannot be acted on is missing the same few things. With these,
most issues can be answered in one reply:

1. **The JDK version** of the target application, and whether it is Java 8 or later.
2. **Your Python version** and the pyjab version (`python -c "import pyjab;
   print(pyjab.__version__)"`).
3. **What you ran**, and what happened instead — the smallest script that shows it.
4. **The window title** you bound to, and the locator that failed.
5. **The accessibility tree**, if a control cannot be found:

   ```console
   pyjab-inspect windows
   pyjab-inspect tree "<window title>" --depth 4
   pyjab-inspect find "<window title>" "<the locator that failed>"
   ```

   `find` reports which step of the locator stopped matching, which is usually the whole
   answer. If `windows` does not list your application, nothing else can work and the
   problem is the attachment rather than the locator.

A note on what pyjab can and cannot see: it reads the accessibility tree that Java
Access Bridge exposes, and **never modifies, restarts or injects into the target
application**. That is deliberate — it is the reason pyjab works on an application whose
launch parameters you cannot change. It also means a control that reports nothing
through the bridge is not reachable, whatever the screen shows. Canvas-drawn interfaces
and embedded browsers are the usual cases. See
[docs/6-Troubleshooting.md](docs/6-Troubleshooting.md).

## Security

Please do not open a public issue for a security problem. Email `gaozhao89@qq.com` with
enough to reproduce it, and allow time for a fix before disclosing it.
