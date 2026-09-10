import pytest

from supplyguard.services.analytics import answer_analytics


class Cursor:
    def __init__(self, rows): self.rows = rows
    def __aiter__(self): self.it = iter(self.rows); return self
    async def __anext__(self):
        try: return next(self.it)
        except StopIteration: raise StopAsyncIteration


class Records:
    def __init__(self): self.pipeline = None
    async def aggregate(self, pipeline):
        self.pipeline = pipeline
        return Cursor([{"_id": "CA", "value": 397}])


class DB:
    def __init__(self): self.records = Records()


@pytest.mark.asyncio
async def test_analytics_uses_allowlisted_pipeline():
    db = DB()
    answer, trace = await answer_analytics(db, "tenant-a", "Which state has most declarations?")
    assert "CA" in answer and trace[0]["tool"] == "mongodb_aggregate"
    assert db.records.pipeline[0]["$match"]["tenant_id"] == "tenant-a"
    assert db.records.pipeline[0]["$match"]["record_type"] == "fema_declaration"
    assert db.records.pipeline[1]["$group"]["_id"]["disaster_number"] == "$disasterNumber"
    assert db.records.pipeline[2]["$group"]["value"] == {"$sum": 1}
    assert trace[0]["measure"] == "distinct_disaster_numbers"


@pytest.mark.asyncio
async def test_analytics_applies_year_as_integer_filter():
    db = DB()
    await answer_analytics(db, "tenant-a", "Top incident types in 2025")
    assert db.records.pipeline[0]["$match"]["fyDeclared"] == 2025


@pytest.mark.asyncio
async def test_analytics_refuses_unrelated_question_without_database_call():
    db = DB()
    answer, trace = await answer_analytics(db, "tenant-a", "Who is Akshita Rastogi?")
    assert "outside" in answer
    assert trace[0]["status"] == "not_executed"
    assert db.records.pipeline is None
