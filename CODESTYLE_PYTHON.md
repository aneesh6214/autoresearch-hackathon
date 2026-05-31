# Python Code Style

Prefer Python that is explicit, typed, easy to scan, and easy to change.

This guide is about day-to-day source code choices: types, names, functions,
modules, comments, imports, async code, tests, and common patterns. Product
behavior, runtime contracts, deployment, and app-specific policy belong in
separate docs.

## Defaults

### 1. Type Everything

Python is dynamic, but this codebase should not be untyped. Everything gets a
type: function parameters, return values, object shapes, class attributes,
callbacks, exported constants, and public module state. Avoid `Any`. If a
boundary genuinely receives unknown data, name that uncertainty and narrow it
before use.

**Bad**:

```python
def process(data):
    return data["key"]
```

**Good**:

```python
class Payload(TypedDict):
    key: str


def process_payload(payload: Payload) -> str:
    return payload["key"]
```

Use the narrowest useful shape: `TypedDict` for dict-shaped data, `Protocol`
for behavior, dataclasses or Pydantic models for domain records, and `TypeVar`
for real generic relationships.

Use `| None` for nullable values:

```python
def find_order(order_id: str) -> Order | None:
    return order_repository.get(order_id)
```

Do not hide uncertainty inside broad containers:

```python
class Config(TypedDict):
    api_url: str
    timeout_seconds: int
    is_debug_enabled: bool


def read_config(path: Path) -> Config:
    ...
```

If a boundary receives unknown JSON, make that explicit:

```python
JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def parse_json_body(raw_body: bytes) -> JsonValue:
    return json.loads(raw_body)
```

Model variants as variants instead of optional fields that only make sense in
some combinations.

```python
@dataclass(frozen=True)
class PendingOrder:
    status: Literal["pending"]


@dataclass(frozen=True)
class ShippedOrder:
    status: Literal["shipped"]
    tracking_number: str


Order = PendingOrder | ShippedOrder
```

### 2. Keep Complexity Visible

Use this as a quick check for code that needs another pass:

- Branching that is hard to scan
- Nested conditions that hide the happy path
- Repeated logic that should be extracted
- Magic numbers without names
- Comments explaining what obvious code already says
- Defensive checks without clear failure modes
- Abstractions used fewer than 3 times

Every constant should document why that value exists when the reason is not
obvious from the name.

```python
# External providers reject titles above this length.
MAX_TITLE_LENGTH = 300

title_text = title[:MAX_TITLE_LENGTH]
```

### 3. Comments And Docstrings

Comments and docstrings explain why code exists, what invariant it protects, or
what trade-off it encodes. They do not narrate mechanics.

```python
# Burst allowance: let the first requests in a window pass without delay.
if request_count < BURST_LIMIT:
    request_count += 1
    return
```

Bad comments restate the line below:

```python
# Increment the retry count.
retry_count += 1
```

A docstring that restates the function name is worse than no docstring.
`get_balance()` does not need `"""Get the balance."""`

Docstrings are for callers. Callers need behavior, constraints, and return
contracts; they do not need implementation details.

Write a docstring when:

- The function has non-obvious behavior, side effects, or fallback logic
- Parameters need explanation beyond their names and types
- The return shape is not obvious from the annotation
- The function is an exported API for other modules
- A test needs to explain why the scenario matters

Skip docstrings when the name and type signature already say everything.

Use this shape:

```python
def function_name(input_value: InputValue) -> OutputValue:
    """Brief, non-redundant explanation of the function's behavior.

    Optional caller-facing note for constraints, invariants, side effects, or
    surprising behavior that does not belong inside the function body.

    Args:
        input_value: Few-word description. Important caller note when applicable.

    Returns:
        Few-word return value. Important caller note when applicable.
    """
```

Rules:

- First paragraph is at most 2 sentences
- First paragraph does not merely restate the function name
- Notes are for caller-relevant behavior, not implementation details
- `Args` describe meaning or constraints, not the Python type
- `Returns` describes the returned value or guarantee, not the Python type
- Omit `Args` or `Returns` when the signature already makes them obvious

```python
def group_rows_by_invoice(rows: Sequence[LedgerRow]) -> dict[str, list[LedgerRow]]:
    """Groups ledger rows by invoice while preserving import order.

    Duplicate invoice ids are expected when a source file contains multiple
    line items for the same invoice.

    Args:
        rows: Ledger rows in source-file order.

    Returns:
        Rows keyed by invoice id, preserving source-file order within each group.
    """
    ...
```

General comment rules:

- Explain why, not what
- No commented-out code
- Test docstrings explain why the scenario matters

### 4. Use Names That Carry Meaning

A good name should remove the need for a comment.

- Functions, variables, and modules: `snake_case`
- Classes, exceptions, and type aliases: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: leading underscore, e.g. `_parse_row`
- Booleans: `is_`, `has_`, `should_`, or `can_`
- Collections: plural names
- Functions: verb-noun names

```python
orders = list_orders(user_id)
order = get_order(order_id)

is_active = order.status == OrderStatus.ACTIVE
has_write_access = permissions.can_write(user_id, order.project_id)
should_retry = retry_count < MAX_RETRY_COUNT
```

No abbreviations except universally understood ones:

- `id`
- `url`
- `db`
- `api`
- `http`
- `config`
- `auth`
- `env`

When in doubt, spell it out: `customer`, not `cust`; `transaction`, not `txn`;
`message`, not `msg`.

## Function Design

A function should do one job and have a name that makes that job obvious.

Prefer early returns. Avoid nesting by handling invalid or terminal cases
first.

```python
def get_invoice_total(invoice: Invoice | None) -> Decimal:
    if invoice is None:
        return Decimal("0")
    if invoice.status == InvoiceStatus.CANCELED:
        return Decimal("0")
    if not invoice.lines:
        return Decimal("0")

    return sum(line.amount for line in invoice.lines)
```

When a function has 3 or more parameters, break to one parameter per line:

```python
def create_order(
    customer_id: str,
    items: Sequence[OrderItem],
    currency: Currency,
    discount_code: str | None = None,
) -> Order:
    ...
```

Avoid mutable defaults:

```python
def collect_errors(errors: Sequence[str] | None = None) -> list[str]:
    return list(errors or [])
```

When optional parameters change behavior, make them keyword-only:

```python
def export_report(
    report: Report,
    *,
    include_archived: bool = False,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> bytes:
    ...
```

Prefer a few boring lines over a dense expression that has to be unpacked.

## Module And Package Structure

One module should have one clear purpose. Split a module when it stops being
easy to name. The file name should describe what the module does.

Avoid catch-all names like `utils.py`, `helpers.py`, `common.py`, and
`misc.py`. Prefer names that describe the job: `text_normalization.py`,
`retry_policy.py`, `invoice_totals.py`, `embedding_chunks.py`.

Rules:

- Keep parsing, validation, transformation, and side effects separate
- Keep side-effecting code at the boundary
- Avoid import-time side effects
- Avoid catch-all classes and catch-all modules
- Re-export intentionally in `__init__.py`, never as an accident

## Import Organization

Imports should be scannable before reading the body of the file.

Use groups, with one blank line between groups:

1. Standard library
2. Third-party packages
3. Local/project imports

Alphabetize within each group.

```python
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.models import Order
from app.results import Result
```

Rules:

- No wildcard imports
- No unused imports
- Prefer absolute project imports over fragile relative chains
- No import-time work that performs I/O
- No circular imports
- Re-export explicitly from `__init__.py` when a public surface is useful

## Error Handling

Catch the narrowest exception you can handle. If you cannot add context,
recover, or translate the error into something better, do not catch it.

```python
try:
    result = risky_operation()
except SpecificError as exc:
    logger.error("operation failed", exc_info=True)
    raise OperationFailed("Cannot complete operation.") from exc
```

Rules:

- Never use bare `except`
- Never silently swallow exceptions
- Preserve the original exception with `raise ... from exc`
- Re-raise unknown errors
- Do not expose stack traces, credentials, file paths, or raw dependency errors
- Do not catch `Exception` unless you are at a process, task, or request boundary

## Preferred Patterns

Use object-oriented, functional, and imperative code where each fits. The
default is the smallest shape that keeps the behavior obvious.

Use compact literals when values are simple and fit comfortably on one line.
Use multi-line literals when values are complex, documented, or easier to scan
vertically.

### Prefer Data-Driven Logic

Replace repetitive branches with data.

```python
STATUS_COLORS: dict[OrderStatus, str] = {
    OrderStatus.PENDING: "yellow",
    OrderStatus.PROCESSING: "blue",
    OrderStatus.SHIPPED: "purple",
}

color = STATUS_COLORS[status]
```

Apply this to status mappings, provider selection, retry schedules, state
transitions, feature flags, validation rules, and pricing tables.

### Normalize At Boundaries

Convert messy external data into clean internal types as soon as it enters the
system. The rest of the code should work with the common format.

```python
def parse_order_payload(payload: Mapping[str, JsonValue]) -> OrderInput:
    ...
```

Once `OrderInput` exists, downstream code should not keep checking raw dict
keys or provider-specific aliases.

### Avoid One-Off Branches

When an edge case can be handled by the same expression as the normal case,
prefer that over a separate branch.

```python
ItemT = TypeVar("ItemT")


def insert_item(items: Sequence[ItemT], item: ItemT, position: int) -> list[ItemT]:
    return [*items[:position], item, *items[position:]]
```

Empty slices already handle the first and last positions.

## Async And Concurrency

Never block the event loop.

Rules:

- Use `asyncio.TaskGroup` for structured concurrency
- Do not create fire-and-forget tasks
- Keep state consistent across cancellation points
- Run CPU-bound work in a process pool or dedicated worker
- Run blocking I/O in a thread pool when an async API is unavailable
- Put timeouts around external calls
- Catch the narrowest error you can handle, then re-raise unknown errors

```python
async def fetch_all(client: httpx.AsyncClient, urls: Sequence[str]) -> list[bytes]:
    results: list[bytes] = []

    async with asyncio.TaskGroup() as task_group:
        tasks = [task_group.create_task(fetch_url(client, url)) for url in urls]

    for task in tasks:
        results.append(task.result())

    return results
```

## Testing Style

Tests should explain behavior, not implementation trivia.

Rules:

- Test names describe the scenario and expected behavior
- Test docstrings explain why the scenario matters
- Use clear arrange/act/assert structure
- Assert on meaningful outcomes, not incidental internals
- Keep fixtures explicit and local unless reuse is real
- Avoid sleeps, randomness, and external services in unit tests
- Use factories/builders when setup noise hides the behavior under test

```python
def test_empty_input_produces_empty_output() -> None:
    """Empty input should be accepted by callers that stream partial batches."""
    assert chunk_items([]) == []
```

## Verification Checklist

Before finishing Python code, confirm:

- Every parameter and return value is typed
- Object shapes, class attributes, callbacks, and public state are typed
- No avoidable `Any`
- Names follow Python conventions
- Booleans use `is_`, `has_`, `should_`, or `can_`
- Nesting stays shallow enough that the main path is obvious
- Magic numbers are named constants
- Imports are grouped, alphabetized, and explicit
- No wildcard imports
- No import-time side effects
- No bare `except`
- No silent error swallowing
- Repetitive branching is data-driven
- Edge-case branches are only present when they add clarity
- Async code does not block the event loop
- Tests assert behavior and explain non-obvious scenarios

Optimize for the next reader. Leave code you can return to without rebuilding
the whole context from scratch.
