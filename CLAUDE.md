# howto — development context

## What this is

A stateless reader. It searches, indexes and shows reference material: the library's cards, Labs
and tool registry, and the functions, aliases and keys the user's shell defines. It never records
anything about the person running it. A feature that needs to remember what someone did, when they
did it, or what they prefer belongs in another tool that reads `howto ... --json`.

## What will look like a bug and is not

**The zsh lens starts an interactive zsh.** fzf and atuin bind their widgets when they load, so
the keys most worth finding appear in no file a parser could read. `index.zsh_bindkeys` asks the
live shell and a stock `zsh -f`, and indexes the difference. It runs in a new session so the
interactive zsh cannot take the terminal from an fzf preview. It is cached per process.

**`tools unresolved` is attached in `cli.py`, not declared in `tools.py`.** It reads the whole
index, and `index` imports `tools`. Declaring it inside `tools` closes the cycle.

**The registry's card renderers take plain arguments, not index rows.** That is what lets
`find.cmd_show` compose a registry card, a card and a shell function on one page without `tools`
importing `index`.

**`library.autosync` starts a pull on every run and never waits.** It is detached, lock-guarded by
an atomic `mkdir`, and fast-forward only. A failed pull leaves git's stderr in the cache's
`library-sync.log`, which the next run reports. Help screens and the fzf preview never start one.

## Content, config and cache are three different things

- **Content** — `cards/`, `labs/` and `tools/registry.yml`, in the library checkout under
  `$XDG_DATA_HOME/terminal-library/`. Authored often, so it never needs a release of this repo to
  change. `paths.library_dir()` is the only place that resolves the root, and every module reaches
  into a subdirectory of it.
- **Config** — `$XDG_CONFIG_HOME/howto/config.toml`, optional and only ever read.
- **Cache** — `$XDG_CACHE_HOME/howto/`, anything one recompute rebuilds.

The only file under `$XDG_STATE_HOME/howto/` is the self-update library's check timestamp, which
every tool built on it writes.

## One renderer per collection

`find` and `show` assemble a subject from every collection that has it and render none of it
themselves. `howto.tools` renders registry entries and the shell collections, and `howto.cards`
renders a card. A second renderer for the same shape is a second thing to keep in step.

## Generated config — never hand-edit

`.pre-commit-config.yaml`, `.github/workflows/validate.yml`, `.editorconfig`, `.markdownlint.yaml`
and the `pyproject.toml` keys named in its `managed` list are generated. Each generated file says so
on its first line. A hand edit outside a `# > custom:` marker is overwritten on the next regeneration.
`release.yml` is hand-written.
