"""Pure, side-effect-free boolean rule evaluator.

The heart of the Rule Engine. Evaluates a nested condition tree ("definition")
against a flat `facts` dict, with no database access — all cross-entity values
are pre-resolved into `facts` by the caller (RuleService.build_facts). Keeping
this layer pure makes it deterministic, trivially unit-testable and safe to run
inside the workflow engine's hot path.

Definition grammar (JSON):

    node := group | condition
    group := {"type": "group", "logic": "and"|"or"|"not", "children": [node, ...]}
    condition := {
        "type": "condition",
        "field": "<fact key, dotted path allowed>",
        "op": "<operator>",
        "value": <static>,                # when value_type == "static" (default)
        "value_type": "static"|"field"|"variable",
        "value_field": "<other fact key>",# when value_type == "field"
        "variable": "<dynamic variable>"  # when value_type == "variable"
    }

Backward compatibility: a bare list of flat `{field, op, value}` dicts (the
legacy format) is accepted and evaluated as an AND group, so existing workflow
and lead-automation conditions keep working unchanged.
"""
from __future__ import annotations
import re
from datetime import datetime, date, time, timezone, timedelta
from decimal import Decimal

# ---- operator + logic catalogs (also surfaced to the UI via RuleService.catalog) ----
LOGIC_OPS = ("and", "or", "not")

COMPARISON_OPS = (
    "eq", "neq", "gt", "gte", "lt", "lte",
    "contains", "not_contains", "starts_with", "ends_with",
    "in", "not_in", "is_empty", "is_not_empty", "between", "regex",
)
DATE_OPS = ("date_before", "date_after", "date_on", "date_within_last_days",
            "date_older_than_days", "date_between")
TIME_OPS = ("time_before", "time_after", "time_between")
BOOL_OPS = ("is_true", "is_false")
ALL_OPS = COMPARISON_OPS + DATE_OPS + TIME_OPS + BOOL_OPS

# Dynamic variables resolved at evaluation time (value_type == "variable").
VARIABLES = (
    "today", "now", "yesterday", "tomorrow",
    "start_of_week", "start_of_month", "start_of_year",
    "current_user_id", "current_time",
)


def _now(ctx: dict | None) -> datetime:
    if ctx and ctx.get("now"):
        n = ctx["now"]
        return n if isinstance(n, datetime) else datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def resolve_variable(name: str, ctx: dict | None = None):
    """Resolve a dynamic variable name to a concrete value. Org-defined named
    variables (passed in ctx['user_vars']) take precedence over the built-ins."""
    user_vars = (ctx or {}).get("user_vars")
    if user_vars and name in user_vars:
        return user_vars[name]
    now = _now(ctx)
    today = now.date()
    if name == "today":
        return today.isoformat()
    if name == "now":
        return now.isoformat()
    if name == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    if name == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if name == "start_of_week":
        return (today - timedelta(days=today.weekday())).isoformat()
    if name == "start_of_month":
        return today.replace(day=1).isoformat()
    if name == "start_of_year":
        return today.replace(month=1, day=1).isoformat()
    if name == "current_time":
        return now.strftime("%H:%M")
    if name == "current_user_id":
        return str((ctx or {}).get("current_user_id")) if (ctx or {}).get("current_user_id") else None
    return None


def _coerce_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _to_date(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    # accept ISO date or datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _to_time(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, time):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s[:8] if len(s) >= 8 else s, fmt).time()
        except ValueError:
            continue
    # try ISO datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).time()
    except ValueError:
        return None


def _as_list(v):
    if isinstance(v, (list, tuple, set)):
        return list(v)
    if v is None:
        return []
    # comma-separated string → list
    return [p.strip() for p in str(v).split(",") if p.strip() != ""]


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) == 0
    return False


def _get_fact(facts: dict, field: str):
    """Read a fact by key. Supports dotted paths against nested dicts, but the
    fact map is normally pre-flattened (e.g. 'assigned_user.role') by the caller."""
    if field in facts:
        return facts[field]
    cur = facts
    for part in str(field).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _resolve_expected(cond: dict, facts: dict, ctx: dict | None):
    vt = cond.get("value_type") or "static"
    if vt == "field":
        return _get_fact(facts, cond.get("value_field"))
    if vt == "variable":
        return resolve_variable(cond.get("variable"), ctx)
    return cond.get("value")


def _eval_condition(cond: dict, facts: dict, ctx: dict | None) -> bool:
    field = cond.get("field")
    op = cond.get("op")
    actual = _get_fact(facts, field)
    expected = _resolve_expected(cond, facts, ctx)

    # existence / boolean operators first (don't need `expected`)
    if op == "is_empty":
        return _is_empty(actual)
    if op == "is_not_empty":
        return not _is_empty(actual)
    if op == "is_true":
        return actual is True or str(actual).lower() in ("true", "1", "yes")
    if op == "is_false":
        return actual is False or str(actual).lower() in ("false", "0", "no") or actual is None

    # numeric comparisons
    if op in ("gt", "gte", "lt", "lte"):
        a, e = _coerce_number(actual), _coerce_number(expected)
        if a is None or e is None:
            return False
        return {"gt": a > e, "gte": a >= e, "lt": a < e, "lte": a <= e}[op]

    if op == "eq":
        an, en = _coerce_number(actual), _coerce_number(expected)
        if an is not None and en is not None:
            return an == en
        return str(actual) == str(expected)
    if op == "neq":
        an, en = _coerce_number(actual), _coerce_number(expected)
        if an is not None and en is not None:
            return an != en
        return str(actual) != str(expected)

    if op == "contains":
        return actual is not None and expected is not None and str(expected).lower() in str(actual).lower()
    if op == "not_contains":
        return not (actual is not None and expected is not None and str(expected).lower() in str(actual).lower())
    if op == "starts_with":
        return actual is not None and expected is not None and str(actual).lower().startswith(str(expected).lower())
    if op == "ends_with":
        return actual is not None and expected is not None and str(actual).lower().endswith(str(expected).lower())

    if op == "in":
        opts = [str(x).lower() for x in _as_list(expected)]
        return actual is not None and str(actual).lower() in opts
    if op == "not_in":
        opts = [str(x).lower() for x in _as_list(expected)]
        return actual is None or str(actual).lower() not in opts

    if op == "between":
        bounds = _as_list(expected)
        if len(bounds) != 2:
            return False
        a, lo, hi = _coerce_number(actual), _coerce_number(bounds[0]), _coerce_number(bounds[1])
        if None in (a, lo, hi):
            return False
        return lo <= a <= hi

    if op == "regex":
        if actual is None or expected is None:
            return False
        try:
            return re.search(str(expected), str(actual)) is not None
        except re.error:
            return False

    # ---- date operators ----
    if op in DATE_OPS:
        ad = _to_date(actual)
        if ad is None:
            return False
        if op == "date_before":
            ed = _to_date(expected)
            return ed is not None and ad < ed
        if op == "date_after":
            ed = _to_date(expected)
            return ed is not None and ad > ed
        if op == "date_on":
            ed = _to_date(expected)
            return ed is not None and ad == ed
        if op == "date_within_last_days":
            n = _coerce_number(expected)
            if n is None:
                return False
            today = _now(ctx).date()
            return (today - timedelta(days=int(n))) <= ad <= today
        if op == "date_older_than_days":
            n = _coerce_number(expected)
            if n is None:
                return False
            today = _now(ctx).date()
            return ad < (today - timedelta(days=int(n)))
        if op == "date_between":
            bounds = _as_list(expected)
            if len(bounds) != 2:
                return False
            lo, hi = _to_date(bounds[0]), _to_date(bounds[1])
            return lo is not None and hi is not None and lo <= ad <= hi

    # ---- time operators ----
    if op in TIME_OPS:
        at = _to_time(actual)
        if at is None:
            return False
        if op == "time_before":
            et = _to_time(expected)
            return et is not None and at < et
        if op == "time_after":
            et = _to_time(expected)
            return et is not None and at > et
        if op == "time_between":
            bounds = _as_list(expected)
            if len(bounds) != 2:
                return False
            lo, hi = _to_time(bounds[0]), _to_time(bounds[1])
            if lo is None or hi is None:
                return False
            if lo <= hi:
                return lo <= at <= hi
            # overnight window (e.g. 22:00 → 06:00)
            return at >= lo or at <= hi

    return False


def _normalize(definition) -> dict:
    """Coerce any accepted shape into a single root group node.

    Accepts: a group node, a single condition node, a flat legacy list of
    conditions (→ AND group), or None/empty (→ always-true AND group)."""
    if not definition:
        return {"type": "group", "logic": "and", "children": []}
    if isinstance(definition, list):
        return {"type": "group", "logic": "and", "children": list(definition)}
    if isinstance(definition, dict):
        if definition.get("type") == "group" or "children" in definition:
            return definition
        # a bare condition dict
        return {"type": "group", "logic": "and", "children": [definition]}
    return {"type": "group", "logic": "and", "children": []}


def evaluate(definition, facts: dict, ctx: dict | None = None) -> bool:
    """Evaluate a rule definition tree against `facts`. Empty ⇒ True."""
    node = _normalize(definition)
    return _eval_node(node, facts or {}, ctx)


def _eval_node(node: dict, facts: dict, ctx: dict | None) -> bool:
    if not isinstance(node, dict):
        return False
    if node.get("type") == "group" or "children" in node:
        logic = (node.get("logic") or "and").lower()
        children = node.get("children") or []
        if not children:
            return True  # an empty group is vacuously true
        results = (_eval_node(c, facts, ctx) for c in children)
        if logic == "or":
            return any(results)
        if logic == "not":
            # NOT(children) == none of the children match (NOR); the common case
            # is a single child, which makes this a plain negation.
            return not any(_eval_node(c, facts, ctx) for c in children)
        return all(results)  # default AND
    # leaf condition
    return _eval_condition(node, facts, ctx)


def evaluate_trace(definition, facts: dict, ctx: dict | None = None) -> dict:
    """Like evaluate() but returns a structured trace for the rule tester:
    {matched, node: {..., matched, children/leaf}}."""
    node = _normalize(definition)
    tree = _trace_node(node, facts or {}, ctx)
    return {"matched": tree["matched"], "trace": tree}


def _trace_node(node: dict, facts: dict, ctx: dict | None) -> dict:
    if isinstance(node, dict) and (node.get("type") == "group" or "children" in node):
        logic = (node.get("logic") or "and").lower()
        kids = [_trace_node(c, facts, ctx) for c in (node.get("children") or [])]
        if not kids:
            matched = True
        elif logic == "or":
            matched = any(k["matched"] for k in kids)
        elif logic == "not":
            matched = not any(k["matched"] for k in kids)
        else:
            matched = all(k["matched"] for k in kids)
        return {"type": "group", "logic": logic, "matched": matched, "children": kids}
    matched = _eval_condition(node, facts, ctx)
    return {"type": "condition", "field": node.get("field"), "op": node.get("op"),
            "value": node.get("value"), "matched": matched}


def collect_fields(definition) -> set:
    """Every field/value_field referenced anywhere in the tree — lets the caller
    know which (possibly cross-entity) facts to resolve."""
    out: set = set()

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
            return
        if not isinstance(n, dict):
            return
        if n.get("type") == "group" or "children" in n:
            for c in (n.get("children") or []):
                walk(c)
            return
        if n.get("field"):
            out.add(n["field"])
        if n.get("value_type") == "field" and n.get("value_field"):
            out.add(n["value_field"])

    walk(_normalize(definition))
    return out
