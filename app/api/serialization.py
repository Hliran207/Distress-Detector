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

    if "post_id" not in doc and "id" in doc:
        doc["post_id"] = doc.get("id")

    return doc

