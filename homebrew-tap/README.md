# homebrew-tap (template)

This directory holds the source-of-truth Homebrew formula for `neviri-cli`.
It's mirrored to the live tap repository at
`github.com/ArcLogiQ/homebrew-tap` by the release CI on every tagged release.

## One-time setup

These steps run by a human, exactly once, before the first GA release:

1. **Create the public tap repository.** On GitHub, create
   `github.com/ArcLogiQ/homebrew-tap` (must be public; the name must
   start with `homebrew-`). It can be empty.
2. **Generate a fine-grained Personal Access Token** (Settings → Developer
   settings → Fine-grained tokens) with **Contents: write** scope on
   `ArcLogiQ/homebrew-tap`.
3. **Add the token as a repo secret** on `ArcLogiQ/neviri-cli` named
   `HOMEBREW_TAP_TOKEN`.
4. **Initial seed**: copy this directory's `Formula/neviri.rb` to the new
   tap repo's `Formula/neviri.rb` and commit. (After this, CI takes over.)

## How users install

```bash
brew tap ArcLogiQ/tap
brew install neviri
```

Or in one command:

```bash
brew install ArcLogiQ/tap/neviri
```

## How updates flow

On every `v*` tag push to `ArcLogiQ/neviri-cli`:

1. `release.yml` builds the per-OS binaries
2. The tap-bump job computes SHA256 for each binary
3. It writes a new `Formula/neviri.rb` with the new version + checksums
4. It opens a PR against `ArcLogiQ/homebrew-tap` (or commits directly to
   `master`, depending on workflow config)
5. Once merged, `brew upgrade neviri` picks up the new release

## What's in this dir

- `Formula/neviri.rb` — the formula template. The `version`, `url`, and
  `sha256` fields are programmatically updated by CI.
- `README.md` — this file.
