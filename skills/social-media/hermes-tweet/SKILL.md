---
name: hermes-tweet
description: Use when Hermes Agent needs X/Twitter search, reading, drafting, or explicitly gated actions through the Hermes Tweet plugin
---

# Hermes Tweet

## Overview

Use this skill to install and operate the public Hermes Tweet plugin for X/Twitter workflows in Hermes Agent. It keeps read-only exploration separate from state-changing actions and requires explicit environment gates before posting, replying, liking, retweeting, following, sending DMs, starting monitors, or launching extraction jobs.

## When to Use

- The user asks Hermes Agent to search, read, summarize, or monitor X/Twitter.
- The user wants to draft or prepare X/Twitter actions from Hermes Agent.
- The user asks for a plugin-native route instead of browser-only social automation.

## Install

```bash
hermes plugins install Xquik-dev/hermes-tweet --enable
```

If the plugin is installed but disabled:

```bash
hermes plugins enable hermes-tweet
```

## Configuration

Set the API key only in the local Hermes runtime environment:

```bash
export XQUIK_API_KEY="YOUR_XQUIK_API_KEY"
```

For write actions, opt in explicitly:

```bash
export HERMES_TWEET_ENABLE_ACTIONS=true
```

Do not commit API keys, cookies, auth tokens, screenshots, chat exports, or local runtime files.

## Workflow

1. Confirm whether the task is read-only or action-taking.
2. For read-only work, use Hermes Tweet search, read, or trends tools.
3. For action-taking work, including monitor creation and extraction jobs, verify `HERMES_TWEET_ENABLE_ACTIONS=true` and ask for explicit user confirmation before sending or starting persistent or account-changing work.
4. Keep generated drafts separate from sent actions until the user approves them.
5. Summarize tool results without exposing private account details or credentials.

## Safety

- Prefer read-only tools until the user asks for an action.
- Treat every external post, reply, like, retweet, follow, DM, monitor, and extraction job as a public, persistent, or account-changing action.
- Use placeholders in examples. Never store real credentials in the repository.

## Reference

- Repository: <https://github.com/Xquik-dev/hermes-tweet>
- Plugin package: `Xquik-dev/hermes-tweet`
