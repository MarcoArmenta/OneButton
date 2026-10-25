# Staying signed in without a keyboard

Claude Code normally signs in through a browser: a page opens, the person
clicks "Authorize", and a token is stored on the machine. That token refreshes
itself for a long time, but not forever, and when it finally lapses the stock
flow needs someone who can click. The user cannot. This page is how to make
that moment rare, and painless when it comes.

## Recommended: a long-lived token in `local/credentials.env`

Once, on the user's machine, signed in to the subscription account:

```
claude setup-token
```

It prints a token designed for unattended use (it is what people use in CI).
Paste it into `local/credentials.env`:

```
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
```

Restart OneButton. From then on the loop passes that token to every Claude
Code call. The browser login is no longer involved. Anthropic sets the
token's lifetime; expect to repeat this roughly yearly, and the spoken message
will say so when the time comes.

## Alternative: an API key

A key from <https://console.anthropic.com> never expires unless revoked.
Billing is per use rather than a subscription, so the maintainer can set a
monthly spend limit there and revoke the key remotely at any time.

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Use one or the other, not both.

## Who owns the account

Decide this early. A browser login needs the account's password and any
second factor. If the account belongs to the user, the helper at home must be
able to complete that login. If the maintainer owns the account used by the
kit, the maintainer can do it from anywhere given remote access to the
machine (below), and can also run `claude setup-token` on their own machine
and send the token to the helper to paste in.

## Remote access for the maintainer

Set up unattended remote desktop once (Chrome Remote Desktop, RustDesk or
similar, with a PIN only the maintainer knows). This is the safety net for
everything, not just login: any failure that needs a keyboard becomes a
five-minute fix from another country instead of a visit. Tell the user it
exists and when it is used.

## What the user hears

At startup the loop asks Claude Code whether it is signed in. If not, it
says so, names the helper from `helper_name` in the config, and keeps
listening so local commands still work. The same message is spoken if a
task fails with an authentication error. Nothing is retried silently.

## Check from a terminal

```
python -m onebutton --check-auth
```

prints Claude Code's own status as JSON and exits 0 when signed in.

## Security notes

- `local/credentials.env` is git-ignored and the agent is denied read access
  to `local/`. It is still a secret on disk: the machine's own user account
  should have a password, and the helper should not paste the token
  anywhere else.
- Updates cannot carry credentials, by design: the repository is public.
- Revoking: for a token, sign in on any machine and sign out all sessions
  from the account settings; for an API key, delete it in the Console.
