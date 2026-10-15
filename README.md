# Seafarer practice repo

A small repo for practicing GitHub with Claude Code. You never type git commands. You tell Claude what you want, and Claude does the git steps.

It holds two things.

## 1. The research board

One file per person in `cards/`, like `cards/bintulu-port-holdings.json`. Each card has the company, country, sector, stage (Idea, Researching, Group presentation or Decision), one key number, the source (document and page), and the owner's first name. A reviewer can flag a card as Wrong with the corrected value and page.

The board page is `docs/index.html`. It is rebuilt for you after every merge. To see it on your own computer, run `python tools/build.py` and open `docs/index.html`.

The three cards with owner "Example" are only samples. Their page references are placeholders.

## 2. The agent marketplace

Each folder in `plugins/` is a Claude Code plugin: a small package holding agents and skills. The list in `.claude-plugin/marketplace.json` is rebuilt for you, so you only add your own folder. `plugins/example-red-flags/` is a working sample.

To use it, start Claude Code and run:

    /plugin marketplace add CaravanAI/seafarer-practice
    /plugin install example-red-flags@seafarer-practice

## How your work gets in

1. Branch. Claude makes a branch with your name on it.
2. Commit. Claude saves your new card file or plugin folder.
3. Pull request. Claude opens a pull request so others can see it.
4. Review. Two automatic checks run, and a person reads it.
5. Merge. Once it passes, it is merged and the board updates.

The two automatic checks:

- **Card and plugin check**: every card has all its fields and a valid stage, and every plugin has a valid `plugin.json`.
- **No company files**: PDFs, Excel, Word, CSV and zip files are not allowed, and neither is a `companies/` folder.

## Rules

Public companies only. No holdings. No views: no buy, sell or hold opinions, and no price targets. Cards state what a document says and where.
