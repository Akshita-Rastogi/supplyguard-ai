import re

from supplyguard.services.router import analytics_eligible

GROUP_FIELDS = {"state": "state", "incident": "incidentType", "type": "incidentType",
                "year": "fyDeclared", "region": "region"}


async def answer_analytics(db, tenant_id: str, question: str) -> tuple[str, list[dict]]:
    """Compute structured questions exclusively from the official OpenFEMA CSV records."""
    q = question.lower()
    if not analytics_eligible(q):
        # Defense in depth: a future caller cannot accidentally execute the
        # default aggregation for unrelated text even if routing regresses.
        return ("I don't know based on the available evidence. This question is outside the "
                "supported FEMA analytics operations.", [{"tool": "mongodb_aggregate",
                "status": "not_executed", "reason": "ineligible_question", "rows": 0}])
    group = next((field for word, field in GROUP_FIELDS.items() if word in q), None)
    year_match = re.search(r"\b(19|20)\d{2}\b", q)
    match = {"tenant_id": tenant_id, "record_type": "fema_declaration"}
    if year_match:
        match["fyDeclared"] = int(year_match.group())
    # The server constructs the pipeline; user text can never inject Mongo operators.
    # OpenFEMA stores one row per designated area, so a disaster number may occur
    # many times. Count each disaster once within the requested group instead of
    # incorrectly presenting designated-area rows as declaration counts.
    if group:
        pipeline = [
            {"$match": match},
            {"$group": {"_id": {"group": f"${group}",
                                 "disaster_number": "$disasterNumber"}}},
            {"$group": {"_id": "$_id.group", "value": {"$sum": 1}}},
            {"$sort": {"value": -1, "_id": 1}},
            {"$limit": 5 if "top" in q else 1},
        ]
    else:
        # A valid ungrouped count means the overall distinct declaration total;
        # it must never silently become a state ranking.
        pipeline = [
            {"$match": match},
            {"$group": {"_id": "$disasterNumber"}},
            {"$count": "value"},
        ]
    # Native async PyMongo returns the aggregation cursor from an awaitable.
    cursor = await db.records.aggregate(pipeline)
    rows = [row async for row in cursor]
    trace = [{"tool": "mongodb_aggregate", "dataset": "OpenFEMA full CSV",
              "measure": "distinct_disaster_numbers", "group_by": group or "all",
              "year": int(year_match.group()) if year_match else None, "rows": len(rows)}]
    if not rows:
        return "No matching structured records were found.", trace
    if group:
        rendered = "; ".join(f"{row['_id']}: {row['value']}" for row in rows)
        return ("Computed from the official OpenFEMA CSV using distinct FEMA disaster "
                f"numbers (declarations by {group}): {rendered}."), trace
    return ("Computed from the official OpenFEMA CSV: "
            f"{rows[0]['value']} distinct FEMA disaster declarations."), trace
