from __future__ import annotations

import copy
import json
import re
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODEL_DIR = Path(
    __file__
).resolve().parent / "working_models"

ALLOWED_STATUSES = {
    "proposed",
    "confirmed",
    "unresolved",
    "rejected",
    "superseded",
}

ALLOWED_OPERATIONS = {
    "add_class",
    "update_class",
    "remove_class",
    "add_generalization",
    "remove_generalization",
    "add_relation",
    "update_relation",
    "remove_relation",
    "record_decision",
    "resolve_decision",
}


class WorkingModelError(Exception):
    pass


class ModelNotFoundError(WorkingModelError):
    pass


class VersionConflictError(WorkingModelError):
    pass


class InvalidChangeError(WorkingModelError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "model"


def _model_path(model_id: str) -> Path:
    return MODEL_DIR / f"{model_id}.json"


def _history_path(model_id: str) -> Path:
    return MODEL_DIR / f"{model_id}.history.jsonl"


def _write_json_atomic(path: Path, value: dict) -> None:
    """
    Prevent a partially written model if the process stops
    during persistence.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")

    tmp.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tmp.replace(path)


def _append_history(
    model_id: str,
    event: dict,
) -> None:

    path = _history_path(model_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                event,
                ensure_ascii=False,
            )
            + "\n"
        )


def create_model(
    name: str,
    description: str | None = None,
) -> dict:

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_id = (
        f"{_slug(name)}-"
        f"{uuid.uuid4().hex[:8]}"
    )

    now = _utc_now()

    model = {
        "model_id": model_id,
        "name": name,
        "description": description,
        "version": 1,
        "status": "draft",
        "created_at": now,
        "updated_at": now,

        "classes": [],
        "relations": [],
        "generalizations": [],
        "decisions": [],
    }

    _write_json_atomic(
        _model_path(model_id),
        model,
    )

    _append_history(
        model_id,
        {
            "event": "model.created",
            "timestamp": now,
            "version": 1,
            "model": copy.deepcopy(model),
        },
    )

    return model


def get_model(model_id: str) -> dict:

    path = _model_path(model_id)

    if not path.exists():
        raise ModelNotFoundError(
            f"Working model not found: {model_id}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def _find_by_id(
    items: list[dict],
    element_id: str,
) -> dict | None:

    return next(
        (
            item
            for item in items
            if item.get("id") == element_id
        ),
        None,
    )


def _require_class(
    model: dict,
    class_id: str,
) -> dict:

    cls = _find_by_id(
        model["classes"],
        class_id,
    )

    if cls is None:
        raise InvalidChangeError(
            f"Unknown class: {class_id}"
        )

    return cls


def _assert_unique_id(
    model: dict,
    element_id: str,
) -> None:

    collections = (
        "classes",
        "relations",
        "generalizations",
    )

    for collection in collections:
        if _find_by_id(
            model[collection],
            element_id,
        ):
            raise InvalidChangeError(
                f"Element id already exists: "
                f"{element_id}"
            )


def _apply_add_class(
    model: dict,
    change: dict,
) -> None:

    element_id = change.get("id")
    name = change.get("name")

    if not element_id or not name:
        raise InvalidChangeError(
            "add_class requires id and name."
        )

    _assert_unique_id(
        model,
        element_id,
    )

    model["classes"].append({
        "id": element_id,
        "name": name,
        "stereotype": change.get(
            "stereotype"
        ),
        "status": change.get(
            "status",
            "proposed",
        ),
        "description": change.get(
            "description"
        ),
    })


def _apply_update_class(
    model: dict,
    change: dict,
) -> None:

    cls = _require_class(
        model,
        change.get("id"),
    )

    for field in (
        "name",
        "stereotype",
        "status",
        "description",
    ):
        if field in change:
            cls[field] = change[field]


def _apply_remove_class(
    model: dict,
    change: dict,
) -> None:

    class_id = change.get("id")

    _require_class(
        model,
        class_id,
    )

    model["classes"] = [
        cls
        for cls in model["classes"]
        if cls["id"] != class_id
    ]

    # Referential integrity.
    model["generalizations"] = [
        gen
        for gen in model["generalizations"]
        if gen.get("specific") != class_id
        and gen.get("general") != class_id
    ]

    model["relations"] = [
        rel
        for rel in model["relations"]
        if rel.get("source") != class_id
        and rel.get("target") != class_id
    ]


def _apply_add_generalization(
    model: dict,
    change: dict,
) -> None:

    element_id = change.get(
        "id",
        f"gen-{uuid.uuid4().hex[:8]}",
    )

    specific = change.get("specific")
    general = change.get("general")

    if not specific or not general:
        raise InvalidChangeError(
            "add_generalization requires "
            "specific and general."
        )

    if specific == general:
        raise InvalidChangeError(
            "A class cannot generalize itself."
        )

    _require_class(model, specific)
    _require_class(model, general)

    _assert_unique_id(
        model,
        element_id,
    )

    duplicate = any(
        g.get("specific") == specific
        and g.get("general") == general
        for g in model["generalizations"]
    )

    if duplicate:
        raise InvalidChangeError(
            "Generalization already exists."
        )

    model["generalizations"].append({
        "id": element_id,
        "specific": specific,
        "general": general,
        "status": change.get(
            "status",
            "proposed",
        ),
    })


def _apply_remove_generalization(
    model: dict,
    change: dict,
) -> None:

    element_id = change.get("id")

    if not _find_by_id(
        model["generalizations"],
        element_id,
    ):
        raise InvalidChangeError(
            f"Unknown generalization: "
            f"{element_id}"
        )

    model["generalizations"] = [
        g
        for g in model["generalizations"]
        if g["id"] != element_id
    ]


def _apply_add_relation(
    model: dict,
    change: dict,
) -> None:

    element_id = change.get("id")
    source = change.get("source")
    target = change.get("target")

    if not element_id:
        raise InvalidChangeError(
            "add_relation requires id."
        )

    if not source or not target:
        raise InvalidChangeError(
            "add_relation requires "
            "source and target."
        )

    _assert_unique_id(
        model,
        element_id,
    )

    _require_class(model, source)
    _require_class(model, target)

    model["relations"].append({
        "id": element_id,
        "name": change.get("name"),
        "stereotype": change.get(
            "stereotype"
        ),
        "source": source,
        "target": target,
        "status": change.get(
            "status",
            "proposed",
        ),
        "description": change.get(
            "description"
        ),
    })


def _apply_update_relation(
    model: dict,
    change: dict,
) -> None:

    relation = _find_by_id(
        model["relations"],
        change.get("id"),
    )

    if relation is None:
        raise InvalidChangeError(
            f"Unknown relation: "
            f"{change.get('id')}"
        )

    if "source" in change:
        _require_class(
            model,
            change["source"],
        )

    if "target" in change:
        _require_class(
            model,
            change["target"],
        )

    for field in (
        "name",
        "stereotype",
        "source",
        "target",
        "status",
        "description",
    ):
        if field in change:
            relation[field] = change[field]


def _apply_remove_relation(
    model: dict,
    change: dict,
) -> None:

    element_id = change.get("id")

    if not _find_by_id(
        model["relations"],
        element_id,
    ):
        raise InvalidChangeError(
            f"Unknown relation: {element_id}"
        )

    model["relations"] = [
        r
        for r in model["relations"]
        if r["id"] != element_id
    ]


def _apply_record_decision(
    model: dict,
    change: dict,
) -> None:

    decision_id = change.get(
        "decision_id",
        f"decision-{uuid.uuid4().hex[:8]}",
    )

    if any(
        d.get("decision_id") == decision_id
        for d in model["decisions"]
    ):
        raise InvalidChangeError(
            f"Decision already exists: "
            f"{decision_id}"
        )

    status = change.get(
        "status",
        "proposed",
    )

    if status not in ALLOWED_STATUSES:
        raise InvalidChangeError(
            f"Invalid decision status: {status}"
        )

    model["decisions"].append({
        "decision_id": decision_id,
        "subject": change.get("subject"),
        "property": change.get("property"),
        "value": change.get("value"),
        "status": status,
        "rationale": change.get(
            "rationale"
        ),
        "evidence": change.get(
            "evidence",
            [],
        ),
        "created_at": _utc_now(),
    })


def _apply_resolve_decision(
    model: dict,
    change: dict,
) -> None:

    decision_id = change.get(
        "decision_id"
    )

    decision = next(
        (
            d
            for d in model["decisions"]
            if d.get("decision_id")
            == decision_id
        ),
        None,
    )

    if decision is None:
        raise InvalidChangeError(
            f"Unknown decision: {decision_id}"
        )

    status = change.get("status")

    if status not in ALLOWED_STATUSES:
        raise InvalidChangeError(
            f"Invalid decision status: {status}"
        )

    decision["status"] = status
    decision["resolved_at"] = _utc_now()

    if "rationale" in change:
        decision["rationale"] = (
            change["rationale"]
        )

    if "evidence" in change:
        decision["evidence"] = (
            change["evidence"]
        )


HANDLERS = {
    "add_class": _apply_add_class,
    "update_class": _apply_update_class,
    "remove_class": _apply_remove_class,

    "add_generalization":
        _apply_add_generalization,

    "remove_generalization":
        _apply_remove_generalization,

    "add_relation": _apply_add_relation,
    "update_relation":
        _apply_update_relation,
    "remove_relation":
        _apply_remove_relation,

    "record_decision":
        _apply_record_decision,

    "resolve_decision":
        _apply_resolve_decision,
}


def apply_changes(
    model_id: str,
    expected_version: int,
    changes: list[dict],
    reason: str | None = None,
) -> dict:

    current = get_model(model_id)

    if current["version"] != expected_version:
        raise VersionConflictError(
            f"Version conflict: expected "
            f"{expected_version}, current "
            f"{current['version']}."
        )

    if not changes:
        raise InvalidChangeError(
            "At least one change is required."
        )

    # Transactional in memory:
    # if one operation fails, nothing is persisted.
    updated = copy.deepcopy(current)

    for change in changes:

        operation = change.get("op")

        if operation not in ALLOWED_OPERATIONS:
            raise InvalidChangeError(
                f"Unsupported operation: "
                f"{operation}"
            )

        HANDLERS[operation](
            updated,
            change,
        )

    old_version = current["version"]

    updated["version"] = old_version + 1
    updated["updated_at"] = _utc_now()

    _write_json_atomic(
        _model_path(model_id),
        updated,
    )

    _append_history(
        model_id,
        {
            "event": "model.updated",
            "timestamp": updated["updated_at"],
            "from_version": old_version,
            "to_version": updated["version"],
            "reason": reason,
            "changes": copy.deepcopy(changes),
        },
    )

    return updated


def get_history(
    model_id: str,
    limit: int = 50,
) -> list[dict]:

    # Also verifies existence.
    get_model(model_id)

    path = _history_path(model_id)

    if not path.exists():
        return []

    events = [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    return events[-limit:]