# Automated Supermarket Ordering

## Notion Data Source IDs

All databases live under [Automated Shopping](https://www.notion.so/Automated-Shopping-333768f38fe3803f8915d62bebcc4243).

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

## Household Profile

- 2 people, large portions (~1.5x recipe servings)
- Min 50g protein per serving; ~200g meat per serving if meat-based
- Allergies: nuts, coconut, poppy seeds (direct ingredients only; "may contain" is fine)
- Budget: ~£50/week, prefer value options
- Lunches: simple, quick, high protein
- Dinners: main planned meals

## Python Utilities

Run from project root: `python3 -m shopping.<module>`

- `src/shopping/models.py` — domain dataclasses
- `src/shopping/ingredients.py` — unit conversion, aggregation, parsing
- `src/shopping/pantry.py` — pantry deduction logic
- `src/shopping/meal_planning.py` — recipe selection scoring
- `src/shopping/shopping_list.py` — formatting, regular items check
