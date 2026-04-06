from typing import Any


def serialize_mongo_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Convert MongoDB documents to JSON-safe dicts.
    - ObjectId -> str (on `_id`)
    - Normalize body field: prefer `body`, fallback to `selftext`
    - Normalize post id field: prefer `post_id`, fallback to `id`
    """
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])

    if "body" not in doc and "selftext" in doc:
        doc["body"] = doc.get("selftext")

    if "post_id" not in doc or doc.get("post_id") in (None, ""):
        if doc.get("id") not in (None, ""):
            doc["post_id"] = doc.get("id")
        elif doc.get("reddit_id") not in (None, ""):
            doc["post_id"] = str(doc.get("reddit_id"))

    if doc.get("post_id") is not None:
        doc["post_id"] = str(doc["post_id"])

    return doc

