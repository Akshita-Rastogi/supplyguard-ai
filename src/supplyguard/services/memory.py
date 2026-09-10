from datetime import UTC, datetime

from pymongo.errors import PyMongoError


def is_follow_up(question: str) -> bool:
    """Conservatively decide whether earlier turns are needed to resolve this question."""
    normalized = question.lower().strip()
    markers = ("what about", "how about", "and ", "also ", "that ", "those ",
               "it ", "them ", "same ", "previous ", "earlier ")
    return len(normalized.split()) <= 12 and any(
        normalized.startswith(marker) or f" {marker}" in normalized for marker in markers
    )


async def load_recent_turns(db, tenant_id: str, conversation_id: str | None,
                            limit: int) -> list[dict]:
    """Load bounded, tenant-scoped history; memory failure must not block an answer."""
    if not conversation_id:
        return []
    try:
        cursor = db.conversation_turns.find(
            {"tenant_id": tenant_id, "conversation_id": conversation_id},
            {"_id": 0, "question": 1, "answer": 1},
        ).sort("created_at", -1).limit(limit)
        turns = await cursor.to_list(length=limit)
        return list(reversed(turns))
    except PyMongoError:
        return []


def build_context(question: str, turns: list[dict], max_chars: int) -> str:
    """Create a small transcript for follow-ups without allowing unbounded prompt growth."""
    if not turns:
        return question
    lines = ["Previous conversation (context only, not factual evidence):"]
    for turn in turns:
        lines.extend((f"User: {turn['question']}", f"Assistant: {turn['answer']}"))
    lines.extend(("Current user question:", question))
    rendered = "\n".join(lines)
    if len(rendered) <= max_chars:
        return rendered
    # Preserve the current question and the most recent end of the transcript.
    prefix = "[Older conversation truncated]\n"
    suffix = rendered[-max(0, max_chars - len(prefix)):]
    return f"{prefix}{suffix}"[:max_chars]


async def store_turn(db, tenant_id: str, conversation_id: str | None, request_id: str,
                     question: str, answer: str) -> bool:
    """Persist one session turn, degrading safely when memory storage is unavailable."""
    if not conversation_id:
        return False
    try:
        await db.conversation_turns.insert_one({
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "request_id": request_id,
            "question": question,
            "answer": answer,
            "created_at": datetime.now(UTC),
        })
        return True
    except PyMongoError:
        return False
