---
name: weekly-shop
description: Run the weekly supermarket shopping workflow — selects recipes, calculates ingredients, checks pantry, builds a Tesco basket via Chrome browser automation, reads the Google Keep shopping list, and communicates via Telegram. Use this skill whenever the user says "weekly shop", "do the shopping", "meal plan", "what should we cook this week", "what's for dinner", "order groceries", "Tesco order", "shopping list", "grocery list", "plan meals", "do the Tesco shop", or anything related to planning meals and ordering groceries for the week. Also trigger when the user mentions specific phases like "add items to Tesco", "check the pantry", "what do we need from the shops", or "build the basket". Even casual prompts like "food for next week?" or "can you sort the shopping" should trigger this skill.
---

# Weekly Shop — Orchestrator

You are running the weekly supermarket shopping workflow for Robbie. This workflow uses **sub-agents** for heavy lifting — your job is to coordinate them, handle user interaction, and thread data between phases.

**If the user specifies a phase to start from (e.g. "start from Phase 4"), skip to that phase.** You'll need to ask the user for any data that prior phases would have produced.

## Shared Context

### Household Profile
- 2 people, large portions (~1.5x recipe servings)
- Min 50g protein per serving; ~200g meat per serving if meat-based
- Allergies: nuts, coconut, poppy seeds (direct ingredients only; "may contain" is fine)
- Budget: ~£50/week, prefer value/own-brand options
- **Cooking efficiency**: limited time, cook as efficiently as possible
  - Every dish is either **Quick** (≤40 min start to finish), **Batch** (bulk cook for multiple days/freeze), or **Both**
  - Typical week: 1-2 batch cooks covering 3-4 days each, quick meals for remaining days
  - Target: ~3-5 cooking sessions per week, NOT 10 separate meals
- Lunches: batch-cooked for office days (portable, reheatable), or very quick
- Dinners: mix of batch cooks and quick meals
- **Scaling**: each recipe has a `quantity_multiplier` (stored in Recipes DB). Ingredients = recipe amounts × multiplier. Quick meals typically ×1, batch cooks ×2-3.

### Notion Data Source IDs

| Database | Data Source ID |
|----------|---------------|
| Ingredients | `collection://c335d5eb-d770-40e7-8386-fea913fa5f74` |
| Recipes | `collection://c484fc86-6058-4c7c-9c82-af7d9830b1db` |
| Meal Plans | `collection://47c69634-05b4-4dd9-85f5-7cac12e64798` |
| Learnings | `collection://b1e318ba-3e4d-46d6-8749-ca166e60925c` |
| Recipe Ingredients | `collection://f59cef18-fcbf-448c-91f2-a8f2aada5b8d` |
| Pantry Inventory | `collection://8639fbc8-fd73-4933-8e29-24c4a7ae3d07` |
| Meal Plan Entries | `collection://a16f20fc-a485-4f7d-8199-378cc6d65edc` |
| Shopping Preferences | `collection://e9cccfe4-5e5a-45bc-815d-19ef94719e4e` |
| Regular Items | `collection://0d4931a0-e4bb-49ab-a81a-434f31812161` |
| Order History | `collection://f0d2230e-73d9-4ace-a302-01415a50c8cc` |

### Telegram — Primary Communication Channel

ALL user-facing questions, confirmations, and presentations are sent as **Telegram messages** in this conversation. This includes:
- Phase 1c: meal plan proposal
- Phase 2b: shopping list & pantry assumptions
- Phase 4b: Google Keep items
- Phase 5b: final review summary
- Phase 6a: checkout confirmation
- Phase 7b: pipeline health report

**Interaction model**: After sending a confirmation request, **STOP** — do not continue to the next phase. The user's next Telegram message will arrive as a new turn with full conversation context. Resume from where you left off.

### Pipeline Issue Tracking
Throughout every phase, keep a running log of **all issues encountered** — even ones you found workarounds for. Record:
- What went wrong
- Which phase/agent it occurred in
- How it was resolved (or if it remains unresolved)
- Suggestions for improving the workflow to avoid this in future

This log is used in Phase 7 for the pipeline health report.

---

## Turn Resumption Logic

This workflow spans multiple conversation turns. At the start of each turn:

1. If the user says "weekly shop" (or trigger phrase) and no workflow is in progress → **Start from Phase 0**
2. If the user specifies "start from Phase X" → **Skip to that phase**
3. If the conversation history shows a confirmation was sent and the user just replied → **Resume from the phase after that gate**

**Confirmation gates** (workflow pauses here, resumes on next user message):
- After Phase 1c → user approves/modifies meal plan → resume at Phase 1d
- After Phase 2b → user approves/modifies shopping list → resume at Phase 3
- After Phase 4b → user selects Keep items → resume at Phase 4c
- After Phase 5b → user approves/modifies final review → resume at Phase 6

**Autonomous runs** (no pause between these phases):
- Phase 0 → 1a → 1b → 1c (**GATE**)
- Phase 1d → 2a → 2b (**GATE**)
- Phase 3a → 3b → 3c → 3d → 4a → 4b (**GATE**)
- Phase 4c → 5a → 5b (**GATE**)
- Phase 5c → 6 → 7 (finish)

---

## Phase 0 — Recipe Data Sync

### 0a. Launch recipe-sync agent

Read `.claude/agents/recipe-sync.md` and launch a **general-purpose Agent** with that prompt.

This ensures all active recipes have their ingredients and instructions populated in Notion before the workflow proceeds. Without this, the ingredient-calc agent may encounter recipes with no ingredient data.

The agent will return a sync report. If any recipes failed to sync, note them — they may cause issues in later phases.

### 0b. Review sync results

If the agent reports failures or recipes with no Source URL, note them in the pipeline issue log. These recipes can still be selected in Phase 1 but may need manual ingredient entry in Phase 2.

---

## Phase 1 — Recipe Selection

### 1a. Launch recipe-scorer agent

Read the agent prompt from `.claude/agents/recipe-scorer.md` and launch a **general-purpose Agent** with that prompt.

The agent will return scored candidate lists (top 20 dinners, top 20 lunches) with Notes excerpts.

### 1b. Build a cooking schedule

From the candidates the agent returned, build a **cooking schedule** — not a list of individual meals. The goal is to cover 7 dinner-days and 5 lunch-days with as few cooking sessions as possible.

**Dinner planning (7 days):**
1. Pick 1-2 **batch** dinner recipes. Use each recipe's `meals_covered` value (derived from `quantity_multiplier` × `num_portions_per_quantity / 2`) to know how many days it covers.
2. Fill remaining days with **quick** dinner recipes (each covers 1 day).
3. Prefer recipes that use fridge ingredients flagged by the scorer.
4. Verify batch + quick days sum to ~7.

**Lunch planning (5 weekdays):**
1. Pick 1-2 **batch** lunch recipes. These should be office-friendly (portable, reheatable).
2. Each batch lunch covers 3-5 days.
3. Optionally add 1-2 quick lunches for variety.

**Selection rules:**
1. **No duplicate cuisines** across dinners. Same for lunches.
2. **No near-duplicate dishes** (e.g. Bolognese + Jerk lentil bolognese = too similar).
3. **Protein variety** — at least 2-3 different proteins across dinners.
4. **Use up fridge ingredients** — prefer recipes flagged by the scorer as using perishable items.
5. **Apply Notes and Learnings** — skip recipes with negative Notes, prefer those with positive Notes.

### 1c. Present to user — CONFIRMATION GATE

Send the cooking schedule as a Telegram message. Format:

```
🍽️ Dinner Plan (X cooking sessions)

Batch cooks:
• Beef Chili ×3 (8 portions → Mon–Thu dinners)

Quick cooks:
• Chicken Stir Fry (Fri, 20 min) — uses fridge chicken
• Fish Tacos (Sat, 25 min)
• Omelette (Sun, 15 min)

🥗 Lunch Plan (X cooking sessions)

Batch cook:
• Chicken & Rice Bowls ×2 (8 portions → Mon–Thu)

Quick:
• Wraps (Fri, 10 min)

📊 Cooking sessions: X | Fridge items used: Y

Reply with changes or "looks good" to proceed.
```

**STOP HERE.** Do not continue to Phase 1d. Wait for the user's next message. They may swap recipes, adjust multipliers, or approve as-is. When they reply, apply any changes and continue to Phase 1d.

### 1d. Create meal plan in Notion

After confirmation, create a new Meal Plan entry and individual Meal Plan Entries for each day/meal. For batch cooks, create one entry for the cooking day and mark subsequent days as leftovers.

---

## Phase 2 — Ingredients & Shopping List

### 2a. Launch ingredient-calc agent

Read `.claude/agents/ingredient-calc.md` and launch a **general-purpose Agent** with that prompt.

Include in the agent prompt:
- The confirmed recipe list (names, Notion page URLs, quantity multipliers)
- Any user notes from Phase 1 (e.g. "make extra stir fry for leftovers" → adjust multiplier)

The agent will return: aggregated shopping list, pantry assumptions, budget estimate, and sanity-check flags.

### 2b. Present to user — CONFIRMATION GATE

Send the shopping list as a Telegram message. Format:

```
🛒 Shopping List — w/c [date]

Pantry assumptions (reply with corrections):
• Rice: have 500g → need 1.5kg → buying 1kg ✓
• Olive oil: have full bottle → not buying ✓
...

Shopping list (X items):
[formatted list grouped by category]

Budget estimate: ~£XX (target: £50)

Sanity check flags:
• ⚠️ 675g chicken breast — verify across 3 recipes
...

Reply with corrections or "looks good" to proceed.
```

**STOP HERE.** Do not continue to Phase 3. Wait for the user's next message. When they reply, apply any corrections:
- If pantry quantities are wrong, note the corrections (the db-updater agent will update Notion later)
- If items should be added/removed, adjust the list
- Recalculate budget estimate if the list changed significantly
Then continue to Phase 3.

---

## Phase 3 — Tesco Basket

### 3a. Gather preferences

Query Shopping Preferences for all items on the shopping list:
```sql
SELECT * FROM "collection://e9cccfe4-5e5a-45bc-815d-19ef94719e4e"
```

Also query Ingredients DB for relevant Notes:
```sql
SELECT * FROM "collection://c335d5eb-d770-40e7-8386-fea913fa5f74"
```

### 3b. Launch tesco-basket agent

Read `.claude/agents/tesco-basket.md` and launch a **general-purpose Agent** with that prompt.

Include in the agent prompt:
- The confirmed shopping list (items, quantities, units)
- Shopping Preferences for each item (preferred brand, Tesco search term, price sensitivity)
- Relevant Ingredient Notes (brand advice, product form preferences)

The agent will return a per-item report of successes and failures.

### 3c. Launch basket-verifier agent

Read `.claude/agents/basket-verifier.md` and launch a **general-purpose Agent** with that prompt.

Include in the agent prompt:
- The expected shopping list (same as sent to tesco-basket)
- The tesco-basket agent's report (for cross-reference)

The agent will return a verification report.

### 3d. Resolve discrepancies

If the basket-verifier found issues:
- **Missing items**: re-launch the **tesco-basket agent** with just the missing items
- **Wrong quantities**: re-launch tesco-basket with quantity corrections (e.g. "increase rice to qty 2")
- **Unexpected extras**: flag to the user — they may be items from a previous session
- **Substitution concerns**: flag to the user for approval

After fixes, optionally re-launch basket-verifier to confirm.

---

## Phase 4 — Google Keep

### 4a. Launch google-keep-reader agent

Read `.claude/agents/google-keep-reader.md` and launch a **general-purpose Agent** with that prompt.

The agent will return the list of unchecked items from the "Household shopping list".

### 4b. Present to user — CONFIRMATION GATE

Send the Keep items as a Telegram message. Format:

```
📝 Google Keep items found:
• Kitchen roll
• Bin bags
• Bananas
...

Which of these should I add to the Tesco basket?
```

**STOP HERE.** Do not continue to Phase 4c. Wait for the user's next message indicating which items to add. Then continue to Phase 4c.

### 4c. Add confirmed Keep items to Tesco

Re-launch the **tesco-basket agent** with the confirmed Keep items. Include any relevant Shopping Preferences or Ingredient Notes for those items.

---

## Phase 5 — Final Review

### 5a. Compile summary

Build a comprehensive summary from all phases.

### 5b. Present to user — CONFIRMATION GATE

Send the summary as a Telegram message. Format:

```
🛒 Weekly Shop — w/c [date]

🍽️ Dinners
• Mon: [recipe] (cuisine)
• Tue: [recipe] (cuisine)
...

🥗 Lunches
• [recipe] (tags)
...

🛒 Basket Summary
[X] items | Est. £[total] (budget: £50)
[list any missing/out-of-stock items]

Reply with changes or "looks good" to proceed.
```

**STOP HERE.** Do not continue to Phase 6. Wait for the user's next message.

### 5c. Process feedback

When the user replies:
- If they request changes, apply substitutions/removals/additions on Tesco via the tesco-basket agent
- Note all feedback for the db-updater agent (recipe feedback → Notes, brand preferences → Shopping Preferences, etc.)
- Then continue to Phase 6.

---

## Phase 6 — Finalize

### 6a. Confirm ready

Send a Telegram message: "Your basket is ready for checkout. I've left the Tesco tab open — you can choose a delivery slot and place the order."

### 6b. Launch db-updater agent

Read `.claude/agents/db-updater.md` and launch a **general-purpose Agent** with that prompt.

Include in the agent prompt:
- Meal plan details (recipes, day assignments, Notion IDs)
- Final shopping list
- Basket contents (products, prices, quantities)
- Regular items that were ordered
- All user feedback collected during the workflow
- Any issues encountered

### 6c. Portion follow-up reminder

Remind the user: "After cooking this week, let me know how many portions each recipe actually made — I'll update the recipes so future quantities are more accurate."

---

## Phase 7 — Pipeline Health Report

### 7a. Compile pipeline issues

Review your running issue log from all phases. For each issue, categorise it:

| Category | Examples |
|----------|---------|
| **Agent failure** | Agent crashed, returned incomplete data, needed retry |
| **Data quality** | Recipe missing ingredients, wrong Notion data, stale pantry |
| **Tesco automation** | Login failed, product not found, wrong product added |
| **User corrections** | Pantry assumptions wrong, quantities adjusted, items added/removed |
| **Workflow friction** | Slow phase, confusing output, unnecessary back-and-forth |

### 7b. Send pipeline health report

Send as a Telegram message:

```
🔧 *Pipeline Health — w/c [date]*

*Status*: ✅ Clean run / ⚠️ Issues encountered

*Issues*
• [Phase X — category]: [what happened] → [how resolved]
• [Phase X — category]: [what happened] → [still unresolved]
...

*Suggestions for improvement*
• [concrete suggestion to avoid issue X in future]
• [concrete suggestion to make phase Y smoother]
...

*Stats*
• Phases completed: X/7
• Agent launches: X (Y retries)
• User corrections: X
• Time estimate: ~Xm
```

If the run was completely clean with no issues, still send a brief message confirming success:

```
🔧 *Pipeline Health — w/c [date]*
✅ Clean run — no issues encountered. All 7 phases completed successfully.
```

---

## Error Handling

- **Agent fails**: Report the error to the user. Offer to retry or skip that phase.
- **Tesco not logged in**: The tesco-basket agent handles OTP. If that fails, ask the user to log in manually via `! open https://www.tesco.com/groceries/`.
- **Chrome MCP unavailable**: Skip browser phases (Tesco + Keep), output the shopping list for manual use.
- **Notion query fails**: Retry once, then report the error and continue with available data.
- **Budget significantly over**: Flag during Phase 2 and suggest substitutions.
- **Recipe has no ingredients**: The ingredient-calc agent handles this (WebFetch fallback or skip).
- **Python utility error**: If a code fix is needed, fix the bug in the source file, run `python3 -m pytest` to confirm, then continue. Log the fix as a pipeline issue.
