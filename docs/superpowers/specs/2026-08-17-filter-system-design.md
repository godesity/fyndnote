# Filter System for Browse View

## Overview

Add a powerful filter system to the Browse Data view that allows users to filter rows by dataset fields, annotation labels, annotation metadata, and row index — all through a single tokenized input with autocomplete.

## Filter Syntax

### Paths

| Path | Source | Example |
|------|--------|---------|
| `data.<field>` | Dataset row field | `data.text ~= "urgent"` |
| `annotation.<field>` | Annotation label data (from template) | `annotation.sentiment = "positive"` |
| `annotations.count` | Number of annotations on row | `annotations.count >= 1` |
| `annotations.annotated_by` | User who annotated the row | `annotations.annotated_by = "john"` |
| `row_index` | Row number (0-based) | `row_index >= 50` |

### Operators

| Operator | Meaning | Applies to |
|----------|---------|------------|
| `=` | Equals | All types |
| `!=` | Not equals | All types |
| `~=` | Contains (string contains) | Strings, complex values (JSON.stringify match) |
| `>` | Greater than | Numbers |
| `>=` | Greater than or equal | Numbers |
| `<` | Less than | Numbers |
| `<=` | Less than or equal | Numbers |

### Conjunctions

- Multiple expressions are joined by `AND` or `OR`
- Default conjunction is `AND`
- Conjunction can be toggled by clicking the label
- All expressions at the same level — no nested grouping

### Examples

```
annotation.sentiment ~= "pos"
annotations.count >= 1 AND data.text ~= "urgent"
data.score > 0.8 OR annotations.annotated_by = "me"
row_index >= 100 AND row_index <= 200
```

## Frontend — FilterBar Component

### Tokenized Input

The filter input is a single text field that tokenizes typed content into styled pills:

- **Field token** (purple bg, `#ede9fe`): Autocompleted field path — left-rounded corner
- **Operator token** (blue bg, `#dbeafe`): Auto-detected when operator chars typed — no corner radius
- **Value token** (yellow bg, `#fef3c7`): Auto-closed on second quote — right-rounded corner
- **Conjunction token** (gray bg, `#f3f4f6`): Click to toggle AND/OR

An expression group (field + operator + value) renders as a seamless pill with no internal padding between tokens.

### Internal State Format

The FilterBar maintains state as a single array that doubles as the API payload — no separate serialization:

```typescript
interface FilterExpression {
  field: string;        // e.g. "data.text", "annotation.sentiment", "annotations.count"
  operator: string;     // =, !=, ~=, >, >=, <, <=
  value: string;        // the raw value (quotes stripped for strings)
  conjunction: 'AND' | 'OR';  // how this joins with the previous expression
}
```

This is the same format sent to the backend — no transformation needed.

### Autocomplete

When typing, show a dropdown of matching paths (merged from all sources):

- `data.*` fields from the dataset schema (fetched once on mount via project metadata)
- `annotation.*` fields extracted from the template source (via regex on widget `name` props)
- `annotations.count`, `annotations.annotated_by`, `row_index` (always available)

These are separate sources for autocomplete but produce identical `FilterExpression` output.

Pressing `Tab` accepts the highlighted suggestion as a field token.

### Empty-State Suggestions

When the input is focused and empty, show suggested filters:

- `annotations.count = 0` (unannotated)
- `annotations.count > 0` (any annotation)
- `annotations.annotated_by = "me"` (annotated by current user)

This replaces the old status dropdown (All / Annotated by me / Unannotated).

### Behavior

| Action | Result |
|--------|--------|
| Type partial path | Autocomplete dropdown shows matching fields |
| Tab | Accept current autocomplete as field token |
| Type operator (`=`, `!=`, `~=`, `>`, `>=`, `<`, `<=`) | Auto-detected as operator token |
| Type `"` | Auto-close on second `"`, create value token |
| Enter | Finalize expression group as a filter |
| Click AND/OR | Toggle conjunction type |
| Backspace on empty cursor | Remove previous token |
| ✕ on token | Remove individual token |
| Click `+ Add filter` | Focus input for new expression |

### Props

```
interface FilterBarProps {
  projectId: string;
  userId: string;
  datasetSchema: { name: string; type: string }[];
  annotationFields: { name: string; type: string }[];
  onFilterChange: (filter: FilterExpression[]) => void;
}
```

## Backend — Filter Application

### API Change

Replace the existing `GET` browse endpoint with a `POST`:

```
POST /api/v1/projects/{pid}/rows

Body:
{
  "user_id": "alice",
  "page": 1,
  "filter": [
    {"field": "annotation.sentiment", "operator": "~=", "value": "pos", "conjunction": "AND"},
    {"field": "annotations.count", "operator": ">=", "value": "1", "conjunction": "AND"}
  ]
}
```

- `page` is 1-based, defaults to 1
- `filter` is optional — omit or pass `[]` for all rows (unfiltered)
- `conjunction` on the first filter expression is ignored (treated as AND)

The existing `status` parameter is removed.

### Filter Pipeline

Apply filters in this order (cheapest first):

1. **Row index filters** (`row_index`): Pure computation on the index list — O(n), trivially fast
2. **Annotation metadata filters** (`annotations.count`, `annotations.annotated_by`): SQL query on annotations table. For `annotations.count`, use `SELECT row_index FROM annotations WHERE project_id = ? GROUP BY row_index HAVING COUNT(*) ...`. For `annotations.annotated_by`, use direct equality.
3. **Annotation data filters** (`annotation.*`): Query SQLite for annotations matching current row indices. Use `json_extract(data, '$.<field>')` to extract the specific field without loading the full JSON into Python:

   ```sql
   SELECT row_index FROM annotations
   WHERE project_id = ?
     AND json_extract(data, '$.<field>') LIKE '%<pattern>%'
   ```
   
   For non-contains operators (`=`, `>`, etc.), use `json_extract` with the appropriate comparison. This is efficient because the filter runs after cheaper passes have narrowed the index set.

### Data Field Filtering (Arrow)

Dataset `data.*` fields are backed by Apache Arrow typed columns (`ChunkedArray`). Filter dispatch by column type:

| Column type | `~=` (contains) | Other operators |
|-------------|-----------------|-----------------|
| `pa.string()` | `pc.match_substring(col, pattern)` | `pc.equal`, `pc.greater`, etc. |
| `pa.int*`, `pa.float*` | Cast to string first via `pc.cast(col, pa.string())` then `pc.match_substring` | `pc.equal`, `pc.greater`, etc. |
| `pa.struct(...)` | `pc.match_substring(pc.cast(col, pa.string()), pattern)` — casts struct to string representation like `{k1: v1, k2: v2}` | Python-level: `col.to_pylist()` → compare each dict |
| Other types | Fallback: `col.to_pylist()` → JSON-serialize per element → Python-level comparison | Fallback |

No manual serialization needed for the common cases — Arrow compute handles it natively.

### Filter Applier

```python
def apply_filters(indices, filter_exprs, ds, annotations, user_id):
    for expr in filter_exprs:
        if expr.field == "row_index":
            indices = apply_row_index_filter(indices, expr)
        elif expr.field.startswith("annotations."):
            indices = apply_annotation_meta_filter(indices, expr)
        elif expr.field.startswith("annotation."):
            indices = apply_annotation_data_filter(indices, expr, annotations)
        elif expr.field.startswith("data."):
            indices = apply_data_field_filter(indices, expr, ds)
    return indices
```

### Annotation Schema Discovery

Extract annotation field names from the template source using regex:

```python
WIDGET_RE = re.compile(
    r'<(SelectField|TextField|CheckboxGroup|RatingField|NERField|BBoxField)'
    r'\s[^>]*?name="([^"]+)"'
)
```

Extract these on project load and return them alongside the project metadata so the frontend can populate autocomplete.

## Files to Change

### Backend
- `backend/routers/projects.py` — Change browse endpoint from GET to POST, add Pydantic body schema, remove `status` param
- `backend/services/annotation_service.py` — Add filter application logic to `browse_rows` (row_index → SQL → annotation data → Arrow scan)
- `backend/schemas.py` — Add request/response schemas for POST body; add annotation field list to project response

### Frontend
- `frontend/src/components/FilterBar.tsx` — New component: tokenized input with autocomplete
- `frontend/src/views/BrowseView.tsx` — Replace status dropdown with FilterBar, pass filter array to POST body
- `frontend/src/api/client.ts` — Change `browseRows` from GET to POST, send `{user_id, page, filter}` in body
- `frontend/src/components/RowGrid.tsx` — Add count indicator ("42 results")

## Future Considerations

- Nested AND/OR grouping (parentheses) if needed
- Date-based filters for `annotations.created_at`
- Saved filter presets per project
