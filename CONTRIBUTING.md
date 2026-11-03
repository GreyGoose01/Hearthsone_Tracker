# Contributing

`main` is always releasable. All work happens on short-lived branches and comes in through a pull request.

1. Create a branch from `main`: `feat/<topic>` for features, `fix/<topic>` for bug fixes,
   `docs/<topic>` for documentation.
2. Commit as often as you like on the branch.
3. Run the tests: `python -m pytest`. New visible texts need a German translation in
   `hearthwatch/locale/de.py` (a test checks this).
4. Open a pull request. The *Tests* workflow must pass.
5. Merge with **Squash and merge**, so every pull request becomes one clean commit on `main`.

## Releases

1. Raise the version in `hearthwatch/__init__.py` and `pyproject.toml` (in a pull request).
2. After the merge: Actions → *Release* → *Run workflow*. It runs the tests, builds the `.deb`,
   tags `v<version>` and publishes the release.

## Bug reports

Please attach `~/.local/state/hearthwatch/hearthwatch.log`. A `Power.log` helps too, but it contains
your BattleTag: remove it first.
