# Team Workflow

How we collaborate at Plexi Office. Friendly desk rules — skim the headings, dig in when you need them.

> **Golden rule:** keep everyone in the loop. Surprises belong in the break-room gossip, not in a blocked PR.

---

## Task handoff

When work moves from one agent to another (or from Juniper to you):

1. **Read the brief** — goal, owned files, and what “done” looks like.
2. **Confirm ownership** — touch only the files listed for you.
3. **Branch from `main`** — name it after yourself (or `<you>/<topic>`).
4. **Do the work** — stay inside this repo.
5. **Commit** with a conventional message. **Do not push or merge** unless asked.
6. **Report back** to Juniper or the manager: what shipped, what’s left, any gotchas.

### Good handoff notes

- What changed (files + intent)
- How to verify it
- Open questions or follow-ups

### Skip these

- Editing a teammate’s file “just this once”
- Merging your own branch into `main`
- Leaving silent unfinished work with no status update

---

## Flag blockers early

Stuck? Say so **as soon as you know** — not after you’ve spun for ages.

**Flag when:**

- You need a file another agent owns
- Requirements conflict or are unclear
- A dependency isn’t ready yet
- Tests or tooling fail in a way you can’t fix alone
- You’re blocked on a manager decision

**How to flag:**

1. Name the blocker in one sentence.
2. Say what you already tried.
3. Ask for a concrete next step (who / what / when).

Quiet struggling helps nobody. Early flags keep the whole pod moving.

---

## Ask the manager for decisions

Walk to the manager’s office (don’t guess) when you need a call on:

| Ask the manager | Decide yourself |
|---|---|
| Scope changes or new files outside the brief | Small wording / naming polish inside your files |
| Security, secrets, or external access | Local refactors that stay behavior-identical |
| Merge / push / release | Commit on your own branch |
| Conflicts between agents’ ownership | Routine questions answered in the brief |
| Product or policy trade-offs | Which snack to bring on break |

**How to ask:** one clear question, two options if you have them, and your recommendation. Short beats a novel.

Juniper tracks status — keep him posted so the manager isn’t surprised.

---

## Merge conflicts

Hit a conflict? **Stop. Don’t force it.**

1. Pause edits on the conflicting file.
2. Say so right away (Juniper / the other agent / Merge Conflict Room).
3. Agree who owns the resolution.
4. Resolve together if needed — prefer the owner’s intent.
5. Re-check that only your assigned files changed.
6. Commit the fix; still don’t merge unless asked.

Never rewrite history or force-push to clear a conflict. Talk first.

---

## Break etiquette

After about **15 minutes** of focused work, take a **~3-minute** break. The office feed loves a little chatter — keep it kind.

**Do**

- Stretch, grab water, say hi by the coffee machine
- Share a light update (“shipped the handoff section!”)
- Come back ready to finish and report

**Don’t**

- Skip breaks until you’re fried
- Block teammates while you’re away without a status note
- Turn break chat into a second work thread that bypasses the manager
- Leave mid-conflict without flagging it

Breaks recharge the pod. Then we clock back in and keep the dream work working.

---

## Quick checklist

- [ ] Brief read, files confirmed
- [ ] Own branch, conventional commit
- [ ] Blockers flagged early
- [ ] Manager asked only for real decisions
- [ ] Conflicts spoken aloud, not forced
- [ ] Break taken; status reported
- [ ] No push / merge unless requested

Teamwork makes the dream work — see you at the coffee machine.
