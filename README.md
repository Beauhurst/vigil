# vigilia

A CLI tool for generating technical summaries of code changes using LLMs.

`vigilia` takes git diffs, splits them into manageable fragments, and uses an LLM to produce readable documentation of what changed. It's designed for engineering teams who want to understand a codebase's evolution without reading every line of every diff.

##  Usage

Command line interface:

Process the git diff between the current HEAD and the `main` branch:

```sh
vigilia extract-patches <COMMIT_REF> HEAD --output out/patches
```

Assemble fragments from the generated patch files:

```sh
vigilia assemble-fragments out/patches --output out/fragments
```

Generate a consolidated summary from the assembled fragments:

```sh
vigilia summarize-fragments out/fragments --output out/summaries
```

The entire process can be run in one command:

```sh
vigilia summarise-changes <COMMIT_REF> HEAD --output out/
```

vigilia uses [pydantic-ai](https://github.com/pydantic/pydantic-ai), so any model it supports can be used by specifying the appropriate model identifier.

## Licence

MIT
