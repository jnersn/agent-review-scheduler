# agent-review-scheduler

`review-next` decides which code review would be most useful for a project
right now, runs it with an AI coding agent that can only read the code, and
delivers the report: printed in the terminal, filed as an issue, or both.
Run it by hand, or nightly from launchd or a systemd timer.

Instead of the same broad review every night, it rotates through review types
such as regression, focused bug hunts, maintainability, unused code,
performance, tests, security and privacy, UI and accessibility, docs, and
release readiness. Each run picks the types that matter most given what has
changed since they last ran.

It is a single Python 3 script with no dependencies. The default reviewer is
[Claude Code](https://docs.claude.com/en/docs/claude-code), but any command
that takes a prompt and prints a report works.

## How it picks

A plan file lists the review types to use, how often each should run and what
it covers. Each type has one of four scopes:

| Scope | Covers | Delivered |
|---|---|---|
| `diff` | merged commits no regression review has covered yet | printed |
| `area` | one narrow feature area from the areas file | printed |
| `layer` | one layer of the code, such as the API or the UI | issue |
| `app` | the whole project | issue |

Every type gets a score from:

- **How overdue it is** against its cadence. Types that have never run start
  high.
- **Churn** in the code (`churn_boost`) or the docs (`docs_boost`) since the
  type last ran.
- **Recent issues** whose titles match the type's `issue_keywords`.
- **An open milestone due within three weeks** (`release_boost`).
- **What the type's last run found**: critical or high findings raise its
  score, an empty report lowers it.
- **A cooldown**, so repeated runs on the same day move on to other types.

For a regression review, the score grows with the number of unreviewed
commits. For `area` and `layer` types, the area or layer is chosen by how many
of its files have changed and how long ago it was last reviewed.

The top two types run in parallel. Every run is appended to `ledger.jsonl` in
the state directory, and the next pick reads it from there.

```
$ review-next example-web --plan
Scores:
   2.10  regression         22 merged commit(s) not yet regression-reviewed
   1.50  area-bug-hunt      never run
   1.20  maintainability    last run 8.4 days ago (cadence 7 days); 1830 lines changed since
  ...

Picks:
  1. regression on 3f2a91c0..8be4d7a1 (22 commits) -> print
     because: 22 merged commit(s) not yet regression-reviewed
  2. area-bug-hunt on Checkout and payments -> print
     because: never run; never reviewed by area-bug-hunt; 14 file(s) changed in the last 30 days
```

## Install

```sh
git clone https://github.com/jnersn/agent-review-scheduler.git
agent-review-scheduler/install.sh        # links ~/.local/bin/review-next
```

You need `git` and Python 3.8 or later. The default reviewer needs the
`claude` CLI, signed in. Filing issues on GitHub needs `gh`, signed in.

## Set up a project

```sh
mkdir -p ~/.config/agent-review-scheduler/example-web
cp agent-review-scheduler/examples/{review-plan.json,areas.txt} ~/.config/agent-review-scheduler/example-web/
# edit both, then:
review-next example-web --plan
```

Before the first regression review, mark where to start, usually the current
main branch:

```sh
review-next example-web --record regression
```

## Usage

```sh
review-next PLAN                  # pick the top two types and run them
review-next PLAN --plan           # show the scores and the picks; run nothing
review-next PLAN --count 1        # run only the top pick
review-next PLAN --type maintainability:api --type unused-code   # run these instead
review-next PLAN --dry            # cheap model; prints the reports; no issue, no ledger entry
review-next PLAN --deliver print  # print everything, file nothing (also: issue, auto)
review-next PLAN --record security-privacy   # log a review you did another way
review-next PLAN --nightly        # the scheduled run: once a day, one combined issue
```

`PLAN` is a `review-plan.json` file, a directory that holds one, or a name
looked up as `~/.config/agent-review-scheduler/<name>/review-plan.json`.

`--nightly` exits right away if a nightly run already happened that day. Use
`--force` to run it again. The whole report goes into one issue, split into
more than one only if it's too long for a single issue body.

The exit code is 1 when a review failed or a report couldn't be filed, so your
scheduler shows the failure.

## The plan

See [examples/review-plan.json](examples/review-plan.json). Paths in the plan
can start with `~`, and relative paths are relative to the plan file. The same
applies to the program in a reviewer, key or issue command when it starts with
`~`, `./` or `../`. Other program names are looked up on `PATH`.

| Key | Default | What |
|---|---|---|
| `repo` | required | The project's git checkout |
| `app_paths` | required | Source paths that count as code for diffs and churn |
| `types` | required | Review types to use: `scope`, `cadence_days` (not for `diff`) and optional boosts |
| `name` | plan directory name | Used in the state path and issue request ids |
| `app` | `name` | Project name shown to the reviewer and in reports |
| `ref` | `origin/main` | The ref reviews run on. A remote-tracking ref is fetched before each run. |
| `layers` | `{}` | `{key: {title, paths}}` for `layer` types. A path starting with `!` is excluded. |
| `areas_file` | none | Areas for `area` types, one `Title \| scope` per line |
| `diff_excludes` | `[]` | Globs left out of regression diffs, such as lock files |
| `doc_paths` | `[]` | Paths that count as docs for `docs_boost` |
| `issues` | none | Issue tracker; see below. Without it, reports stay in the state directory. |
| `model`, `effort` | `opus`, `medium` | Passed to the reviewer |
| `dry_model`, `dry_effort` | `haiku`, `low` | Used with `--dry` |
| `reviewers` | read-only Claude Code | Reviewer commands, tried in order; see below |
| `types_dir` | the bundled `review-types/` | Your own review rules |
| `state_dir` | `~/.local/state/agent-review-scheduler/<name>` | Ledger, reports, logs and the review worktree |
| `issue_footer` | none | Text added to the end of every filed issue |

Type options: `churn_boost`, `docs_boost`, `release_boost` (booleans) and
`issue_keywords` (lowercase substrings matched against issue titles).

## Review types

`review-types/` holds the rules the reviewer follows. Each file is plain
Markdown: `common.md` applies to every review, and each type has its own
file. They're written for any language and stack. To adapt them, copy the
directory, edit it and point `types_dir` at your copy. The reviewer is told
to read the project's own agent instructions (CLAUDE.md, AGENTS.md) first, so
project conventions take precedence over the generic rules.

To add a type, add `<type>.md` to your types directory and an entry under
`types` in the plan.

## Reviewers

Reviews run in a separate git worktree under the state directory, checked
out at `ref` (detached), so your own checkout is never touched. The inputs
for the reviewer (the type rules, known issues, the diff) go into `.review/`
inside it.

The default reviewer is Claude Code, limited to reading:

- tools are `Read`, `Glob` and `Grep` only: no shell, file edits, web access
  or subagents
- no MCP servers
- only your user settings are loaded, so hooks and permissions in the
  reviewed repository's `.claude/` don't apply

If you review code you don't trust, run it in a container or a separate
account anyway. A read-only agent still reads everything in the repository,
including prompt-injection attempts, and its report could be misleading.

To use another agent, or more than one, set `reviewers`. They're tried in
order until one produces a report:

```json
"reviewers": [
  {
    "label": "claude (API key)",
    "command": ["claude", "--model", "{model}", "--effort", "{effort}", "--tools", "Read,Glob,Grep",
                "--setting-sources", "user", "--strict-mcp-config", "--mcp-config", "{\"mcpServers\":{}}",
                "-p", "{prompt}", "--output-format", "json"],
    "output": "claude-json",
    "api_key_command": ["pass", "show", "anthropic/review"]
  },
  {
    "label": "my-agent",
    "command": ["my-agent", "--read-only", "--prompt", "{prompt}"]
  }
]
```

| Key | What |
|---|---|
| `command` | Argument list. `{model}`, `{effort}` and `{prompt}` are replaced when they're a whole argument. Runs in the worktree. |
| `output` | `text` (default): stdout is the report. `claude-json`: Claude Code's `--output-format json`, which also records cost and turns in the ledger. |
| `api_key_command` | Prints an API key. If it fails or prints nothing, this reviewer is skipped. |
| `api_key_env` | Variable that receives the key (default `ANTHROPIC_API_KEY`) |
| `unset_env` | Variables removed from the reviewer's environment, for example to make it use a subscription login instead of a key |
| `label` | Name shown in reports |

A reviewer counts as failed when it prints nothing, reports an error, or its
output starts with a usage or rate limit message. The reviewers' stderr goes
to `reviewer.err` in the state directory.

## Issues

```json
"issues": {"repo": "example-org/example-web", "labels": ["review"]}
```

By default issues go to GitHub through `gh`. Existing issues, open and
closed, are passed to the reviewer as known issues, so it doesn't report
them again. Their titles also feed `issue_keywords`, and their milestones
feed `release_boost`. Rerunning the same report doesn't file a duplicate,
because an open issue with the same title is reused.

For another tracker, set `issues.command` to your own scripts:

```json
"issues": {
  "repo": "PROJ",
  "command": {"list": ["my-tracker", "list", "{repo}"], "create": ["my-tracker", "create"]},
  "body_limit": 30000
}
```

- `list` prints a JSON array of
  `{"number", "title", "state": "open"|"closed", "created_at": ISO 8601, "milestone": {"title", "due_on"} | null}`.
- `create` reads `{"repo", "title", "body", "labels", "request_id"}` as JSON
  on stdin and prints `{"ref", "url"}`. `request_id` is stable for the same
  report, so you can use it to skip duplicates. A non-zero exit means the
  issue wasn't filed.

Every report is also saved under `reports/` in the state directory, whether
or not it was filed.

## Scheduling

**macOS:** edit [examples/launchd.plist](examples/launchd.plist) and load it
with `launchctl bootstrap gui/$UID <plist>`. launchd runs a job missed during
sleep when the Mac wakes.

**Linux:** copy [examples/systemd/](examples/systemd) to
`~/.config/systemd/user/`, then:

```sh
systemctl --user daemon-reload
systemctl --user enable --now review-next@example-web.timer
loginctl enable-linger "$USER"     # run while you're logged out
```

The reviewer needs its login or API key available to the scheduled job,
which doesn't have your shell's environment. Use `api_key_command` for keys.

## Tests

```sh
python3 -m unittest discover tests
```

## License

MIT. See [LICENSE](LICENSE).
