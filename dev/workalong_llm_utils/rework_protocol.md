This is a protocol for refactoring / reworking code components with claude-code or other
ai tools.
The main goal of this protocol is to ensure the codebase doesn't bloat and grow riddled
with duplicated code during AI refactoring / reworks.

# Pre-rework

- Commit. Make sure everything is committed
    - Optional: Create a new branch for the rework
- Optional: Check tests, if present.

# Simple protocol:

If the task is clear, go directly to coding phase

# Complex protocol:

If there's a complex task - first, read spec.md or ask user for a list of requirements

- After that, evaluate the current solution on the match with specs
    - Which additional featuers were implemented that are not present in the spec
        - What is the likely reason were they added
        -
    - Which components / features explicitly listed in the spec are missing
        - How difficult it is to add this
    - write to workalong.md
    - proceed to coding

## Coding:

- Before coding, lay out a plan to the user in clear terms.
    - Which components / features will be added
    - Which modified
    - Which moved / removed
    - Make an explicit enumeration for user to specify which steps are approved and
      which are declined
    - Each item should be formulated in as simple terms as possible, 1 line maximum per
      item, not longer than a few words
- Always remove duplicate code or alternative / previous implementations of the same
  feature
    - After making a change, call git diff and make sure file is in a desired target
      state and the changes you planned are correctly reflected
- proceed with implementing each item one by one and track progress with checkboxes in
  workalong.md
    - [x] item 1 - keep to original item descriptions, DO NOT ADD SUB-ITEMS. List which
      files were affected for this feature.

AI Issue resolution

1) Failed deletions
   Sometimes AI applier fails to delete code according to instructions
   This results in really confusing situations with duplicate functions / methods
   present in multiple places across the codebase
   To mitigate that

- Check file diff after each modifications and make sure it reflects the changes you've
  made

