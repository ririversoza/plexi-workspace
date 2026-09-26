# README audit notes (Mochi)

`mochi/README.md` is a corrected copy of the root `README.md` as of `baf0671`; it is the same in `a8723e2`.

## Changes

| Line | Before | After | Why |
|---|---|---|---|
| 7 | "Anything outside this **folder** is off limits." | "Anything outside this **repository** is off limits." | The same sentence opens with "inside this repository"; mixing "folder" and "repository" blurs the boundary the rule defines. |
| 18 | "colour-codes" | "color-codes" | The rest of the README uses US spelling ("cozy"); this was the only British spelling. |

## Checked, no change needed

- **Markdown:** all four tables have the same number of columns in the header, separator and body rows; every bold and italic marker is closed; the horizontal rule and `<sub>` footer render correctly.
- **Links:** the README has no links, so there are none to break.
- **Pronouns:** each agent has one set, used the same way in their table row and bullet. I can only check Mochi's (he/him) against a source, my own character sheet; it matches.
- **Emoji rows:** every table row has one leading emoji, and the team headings use distinct colors (🟠 🟢 🔵).
- **Column layout:** only the Staff table has a "Runs on" column. That's fine, because each team heading already names the tool its agents run on.
- **Haiku:** both Sora and Taro write haiku. That's a shared quirk, not a contradiction.

## Flagged for the manager (not changed)

- The README's workspace rule and "How work happens here" step 2 say agents may work anywhere in the repo. The new office rule limits each agent to its own `./<name>/` folder. The README should say so once that rule is final, but that's the manager's call, not an audit fix.
