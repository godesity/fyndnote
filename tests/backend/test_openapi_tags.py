"""Every operation must be filed under exactly one declared tag.

An untagged route is invisible drift: Swagger UI hides it in an unlabelled
`default` section and Scalar buries it under "Other", where nobody notices a
newly added endpoint. Asset routes are excluded from the schema outright.
"""

from fyndnote.main import OPENAPI_TAGS, app

DECLARED = {t["name"] for t in OPENAPI_TAGS}
EXPECTED_COUNTS = {
    "Auth": 2,
    "SSO": 4,
    "Datasets": 8,
    "Templates": 4,
    "Projects": 5,
    "Rows & Annotations": 12,
    "Members": 4,
    "AI Prefill": 6,
}


def test_every_operation_has_exactly_one_declared_tag():
    spec = app.openapi()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            tags = op.get("tags") or []
            assert len(tags) == 1, f"{method.upper()} {path} tags={tags}"
            assert tags[0] in DECLARED, f"{method.upper()} {path} tags={tags}"


def test_sections_have_expected_sizes_and_no_stray_asset_routes():
    spec = app.openapi()
    counts: dict[str, int] = {}
    for ops in spec["paths"].values():
        for op in ops.values():
            counts[op["tags"][0]] = counts.get(op["tags"][0], 0) + 1
    assert counts == EXPECTED_COUNTS
    assert [t["name"] for t in spec["tags"]] == list(EXPECTED_COUNTS)
    assert "/favicon.svg" not in spec["paths"]
    assert "/icons.svg" not in spec["paths"]
