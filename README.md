# howto

`howto` answers "how do I do this" at the terminal. It searches a library of reference cards,
hands-on Labs and a tool registry, together with what your own shell defines: functions, aliases,
git aliases, forgit shortcuts, tmux keybindings and zsh keys. Pick a row and it shows everything
known about that name, from every collection that has it. It is an advanced `tldr` for your own
setup.

howto is a reader. It keeps no records about you: no history, no schedule, no favorites.

## Install

```bash
uv tool install --index https://pypi.ichrisbirch.com/simple/ howto
```

The index is named because PyPI's `howto` is an unrelated project. `howto update` upgrades it in
place from the same index.

It runs on Python 3.13 or later. These are optional, and each one switches on a part of howto:

- **`fzf`** — the picker behind `find`, `choose` and `labs choose`. Without it, `show` and `list`
  still work.
- **`bat`** — renders cards and Labs with highlighting. Without it, they print as plain text.
- **`tldr`** — adds a page of common examples under a registry entry in `show`.
- **`zsh`** — the `zsh` collection asks your live shell which keys it binds.

## First run

```bash
howto library status        # the first run clones the library; prints where it went
howto find stash            # search everything; Enter shows what you picked
howto show rg               # everything known about one name, on one page
howto cards show git-rebase # one reference card
howto labs choose           # a Lab to work through in a second pane
howto tools unresolved      # registry rows naming something this machine cannot run
```

The first command clones the library from
[terminal-library](https://github.com/datapointchris/terminal-library) into
`$XDG_DATA_HOME/terminal-library/`. Every later command starts a `git pull --ff-only` there in the
background and never waits for it. A failed pull is reported on the next run, and
`howto library sync` retries it in the foreground.

## Commands

```text
howto find [term]           fuzzy-search every collection, and show the row you pick
howto show <name>           everything known about one name
howto choose [term]         pick a row and print its invocation, for $(howto choose)
howto list [--json]         every indexed row, as the picker sees it

howto cards list|show|new|random
howto tools list|show|categories|unresolved
howto labs list|show|choose|flash|new|edit
howto library sync|status|path|edit
howto shell widgets|completion
```

`find`, `choose` and `show` take `--source` to search one collection: `tool`, `card`, `func`,
`alias`, `git`, `forgit`, `tmux` or `zsh`. Every group prints its own help when run bare.

## The library is a git checkout you can write in

The library holds three directories:

- **`cards/`** — markdown reference cards. One tool's commands and keys, or one goal carried through
  several tools in order.
- **`labs/`** — hands-on Labs. Each one stages a scratch directory and walks through a tool step by
  step, with what to expect and why.
- **`tools/registry.yml`** — one entry per thing you can type: what it is, why to reach for it, its
  usage and examples. `howto labs flash` turns the examples into a recall drill.

Search reads a card's filename, its first `# ` heading and its front-matter `tags`, never its body.

`howto cards new <name>` and `howto labs new <name>` write a file from a template and open it in
`$EDITOR`. `howto library edit <id>` opens an existing one. They write into the checkout howto
reads, so a new card is searchable at once. Commit and push it with git as usual. The background
pull is fast-forward only, so it never merges into, or overwrites, a card you are still writing.

## Pointing howto somewhere else

| Setting                 | What it sets                                                        |
| ----------------------- | ------------------------------------------------------------------- |
| `$HOWTO_LIBRARY_DIR`    | The library checkout, for this shell                                |
| `library_dir`           | The same, in `$XDG_CONFIG_HOME/howto/config.toml`, for this machine |
| `$HOWTO_LIBRARY_REMOTE` | Where the first-run clone comes from, such as a fork                |
| `$SHELL_DIR`            | The directory of `*.sh` files read for functions and aliases        |
| `$FORGIT_PLUGIN`        | The forgit plugin file read for its shortcuts                       |

The variable beats the config file, and the config file beats the default. `howto library status`
names which one chose the path. Pointing the library at a checkout you already author in makes
writing a card and reading it the same file.

Functions are indexed when annotated in their shell file:

```bash
#@extract
#--> Unpack any archive by its extension
extract() { ... }
```

An alias takes the comment line directly above it as its description.

## Shell integration

```zsh
howto shell completion zsh > "${fpath[1]}/_howto"   # before compinit
eval "$(howto shell widgets zsh)"
bindkey '^X^D' howto-choose-widget
```

The completion completes verbs, and card and Lab ids out of the library, without starting Python on
Tab. The widget opens the picker and puts the chosen command on your prompt, ready to edit or run.
`howto-choose-next` does the same at the next prompt and leaves the current line alone. In any
other shell, `$(howto choose)` prints the pick.

## What it writes

- **The library checkout**, under `$XDG_DATA_HOME`, and the cards and Labs you create in it.
- **A cache** under `$XDG_CACHE_HOME/howto/`: the outcome of the last background pull, and what this
  machine declares it installs. Deleting it costs one recompute.
- **The update check's timestamp**, at `$XDG_STATE_HOME/howto/autoupdate-<machine>.json`. Set
  `NO_AUTO_UPDATE` and it never checks or writes.
