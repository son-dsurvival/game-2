# Temporary Session Memory

This file contains current-session state only. It is readable working memory and is not permanent canon until an approved Admin Editor operation promotes selected facts.

## Current Session Position

day:
phase:

## Game Cache

### Durable Facts

- fact:
  status:
  source turn:

### Active Threads

- thread:
  status:
  next question:
  source turn:

### Pending Commitments

- commitment:
  owner:
  due:
  source turn:

### Unresolved Questions

- question:
  source turn:

### Expiring Facts

- fact:
  expires:
  source turn:

## Active Background Directives

### {directive id}
actor:
task:
location:
constraints:
started:
expires:
status:
last processed tick:
assigned by:

## Session Resource Ledger

- current MP =
- money =

## Session Modifier Ledger

- {modifier name}: {description}

## Pending Branch Registry Updates

### {branch name}
status:
specialist:
template:
activation tags:
reason:

## Pending Session Canon

<!-- recorder:{turn id} -->
### Recorded Turn — {turn id}
day:
phase:
promotion_status: pending
summary:
commit_id:
parent_commit:

### State Updates
- {state name} = {value}

### Resource Commit
- {resource}: before {before}; delta {delta}; after {after}; status {status}

### New Modifiers
- {modifier name}: {description}

### Branch Registry Updates
- {branch}: status {status}; specialist {specialist}; template {template}; activation tags {activation tags}; reason {reason}

### Target Updates
- file:
- section:
- summary:
- pending content:

<!-- /recorder:{turn id} -->
