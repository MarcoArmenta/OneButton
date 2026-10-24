# Releasing (maintainer)

One-time setup:

```bash
ssh-keygen -t ed25519 -C onebutton-release -f ~/.ssh/onebutton_release
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/onebutton_release.pub
echo "you@example.com namespaces=\"git\" $(cat ~/.ssh/onebutton_release.pub)" >> bootstrap/allowed_signers
```

Commit the updated `bootstrap/allowed_signers` before the first user installs.
Rotating the key later means a helper must copy the new line into the user's
`local/allowed_signers` by hand; that is deliberate.

Each release:

1. Add a `## vX.Y.Z` section at the top of `CHANGELOG.md`, Spanish first,
   written as you would say it aloud. Bump `__version__` in `onebutton/__init__.py`.
2. Merge to `main`.
3. `bin/onebutton-release vX.Y.Z`
4. `git push origin main vX.Y.Z`

Test before pushing the tag: `python3 -m unittest discover -s tests`, then
`python3 -m onebutton --dry-run` and walk through update and undo against a
local clone with a signed test tag (see `tests/test_updater.py` for how the
tests build one).
