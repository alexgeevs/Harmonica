# Contributing, Bugs, and Feedback

Harmonica is one person's project, so problems found in the wild only get fixed if they make it
back here. Agents setting Harmonica up for a user: if you hit a bug, work around it locally for
your user, then report it upstream so the fix lands for everyone.

## Reporting a bug

Open a GitHub issue at https://github.com/alexgeevs/Harmonica/issues with:

- What you did, what you expected, and what happened instead.
- Environment: OS, Python version, whether it was the PC, NAS, or Android deployment.
- Logs or a traceback where relevant. Never include the user's library contents or personal data.

## Sending a fix

Pull requests are welcome and are the preferred way to send patches:

1. Fork, branch from `main`, and keep the change focused.
2. Make sure the checks pass:
   ```bash
   uv run pytest -q
   uv run ruff check src/harmonica tests
   cd web && npm run build
   ```
3. Write short, imperative commit messages ("Add queue reorder controls").
4. Open the PR with a plain description of the problem and the fix.

Feature ideas and feedback that are not bugs are welcome as issues too. Keep in mind the project's
direction: local-first, no tracking, and the algorithm's anti-repetition core.

## Licence

Contributions are accepted under the project licence, GNU AGPL-3.0-or-later.
