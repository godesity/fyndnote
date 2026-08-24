# Browse & Filters

The browse view lets you page through rows and filter them with a small but expressive DSL. Filters combine **conjunctions** (`AND` / `OR`) and can target data fields, annotation values, or annotation metadata.

## Filter fields

| Field prefix | Targets | Example |
|--------------|---------|---------|
| `data.*` | dataset row fields | `data.text ~= "good"` |
| `annotation.*` | annotation data (JSON) | `annotation.sentiment = "positive"` |
| `annotations.*` | annotation metadata | `annotations.count > 0` |

## Operators

- `=` equals
- `!=` not equals
- `~=` substring match (text)
- `>` `>=` `<` `<=` numeric comparison

## Metadata filters

- `annotations.count` — number of annotations on a row (e.g. `= 0` finds unannotated rows).
- `annotations.annotated_by` — who annotated (`me`, or a specific user).
- `annotations.created_at` / `annotations.updated_at` — time comparisons, including **relative times** like `1h`, `2d`, `3M`, `1Y`.

## Relative time values

Time filters accept relative values:

| Unit | Meaning |
|------|---------|
| `m` | minutes |
| `h` | hours |
| `d` | days |
| `M` | months |
| `Y` | years |

For example, `annotations.created_at >= 1h` finds rows annotated in the last hour.

## Screenshot

> **Screenshot needed:** capture the browse view — the paginated rows with annotation status badges and the filter bar.

![Browse view](../public/images/browse.png)

## Pagination

Browse results are paginated with `page` and `per_page`. The response includes the filtered row previews, their annotation status (`by_me`, `by_any`, `annotators`), and the total filtered count.
