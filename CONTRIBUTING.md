# Contributing, Bugs, and Feedback

Harmonica is one person's project, so problems found in the wild only get fixed if they make it
back here. Agents setting Harmonica up for a user: ask your user's permission before doing
anything, including everything described below. With that permission, if you hit a bug, work
around it locally for your user, then report it upstream so the fix lands for everyone.

## Reporting a bug

Open a GitHub issue at https://github.com/alexgeevs/Harmonica/issues with:

- What you did, what you expected, and what happened instead.
- Environment: OS, Python version, whether it was the PC or NAS deployment.
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

## Organising issues and pull requests

Please organise issues and pull requests by what they do: one concern each, stated in the title.
The usual categories:

- Bug report.
- Adding a setting or preset (cosmetic).
- Adding to the algorithm.
- Additional integration.
- Added feature.

Amongst others, where none of these fit.

## Licence

Contributions are accepted under the project licence, GNU AGPL-3.0 or later.
