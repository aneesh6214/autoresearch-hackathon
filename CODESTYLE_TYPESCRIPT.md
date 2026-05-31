# TypeScript Code Style

Prefer TypeScript that is explicit, typed, easy to scan, and easy to change.

This guide is about day-to-day source code choices: types, names, functions,
modules, comments, imports, async code, tests, and common patterns. Product
behavior, runtime contracts, deployment, and app-specific policy belong in
separate docs.

## Defaults

### 1. Treat Types As Contracts

Use strict mode. Everything gets a type: function parameters, return values,
object shapes, component props, hook results, exported constants, callbacks,
and public module state. Avoid `any`, `as any`, and `@ts-ignore`. If a boundary
genuinely receives unknown data, call it `unknown` and narrow it before use.

**Bad**:

```typescript
function process(data: any) {
  return data.key
}
```

**Good**:

```typescript
interface Payload {
  key: string
}

function processPayload(payload: Payload): string {
  return payload.key
}
```

Use `interface` for object shapes. Use `type` for unions, intersections, and
literal sets.

```typescript
interface User {
  id: string
  name: string
}

type OrderStatus = "pending" | "paid" | "cancelled"
```

Props interfaces are always explicit. Never use `React.FC`.

```typescript
interface OrderCardProps {
  order: Order
  onSelect: (orderId: string) => void
}

function OrderCard({ order, onSelect }: OrderCardProps) {
  ...
}
```

Model variants as variants instead of optional fields that only make sense in
some combinations.

```typescript
type Order =
  | { status: "pending" }
  | { status: "shipped"; trackingNumber: string }
  | { status: "cancelled"; cancelReason: string }
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

```typescript
/** External providers reject titles above this length. */
const MAX_TITLE_LENGTH = 300

const titleText =
  title.length > MAX_TITLE_LENGTH ? title.slice(0, MAX_TITLE_LENGTH) : title
```

### 3. Comments And TSDoc

Comments and TSDoc explain why code exists, what invariant it protects, or what
trade-off it encodes. They do not narrate mechanics.

```typescript
// Burst allowance: let the first requests in a window pass without delay.
if (requestCount < BURST_LIMIT) {
  requestCount += 1
  return
}
```

Bad comments restate the line below:

```typescript
// Increment the retry count.
retryCount += 1
```

A TSDoc comment that restates the function name is worse than no comment.
`getBalance()` does not need `/** Get the balance. */`

TSDoc is for callers. Callers need behavior, constraints, and return contracts;
they do not need implementation details.

Write TSDoc when:

- The function has non-obvious behavior, side effects, or fallback logic
- Parameters need explanation beyond their names and types
- The return shape is not obvious from the annotation
- The function is an exported API for other modules
- A hook exposes a state/action contract worth explaining

Skip TSDoc when the name and type signature already say everything.

Use this shape:

```typescript
/**
 * Brief, non-redundant explanation of the function's behavior.
 *
 * Optional caller-facing note for constraints, invariants, side effects, or
 * surprising behavior that does not belong inside the function body.
 *
 * @param input Few-word description. Important caller note when applicable.
 * @returns Few-word return value. Important caller note when applicable.
 */
```

Rules:

- First paragraph is at most 2 sentences
- First paragraph does not merely restate the function name
- Notes are for caller-relevant behavior, not implementation details
- `@param` describes meaning or constraints, not the TypeScript type
- `@returns` describes the returned value or guarantee, not the TypeScript type
- Omit `@param` or `@returns` when the signature already makes them obvious

```typescript
/**
 * Groups ledger rows by invoice while preserving import order.
 *
 * Duplicate invoice ids are expected when a source file contains multiple line
 * items for the same invoice.
 *
 * @param rows Ledger rows in source-file order.
 * @returns Rows keyed by invoice id, preserving source-file order within each group.
 */
function groupRowsByInvoice(rows: LedgerRow[]): Map<string, LedgerRow[]> {
  ...
}
```

General comment rules:

- Explain why, not what
- No commented-out code
- Test names explain why the scenario matters

### 4. Use Names That Carry Meaning

A good name should remove the need for a comment.

- Functions and variables: `camelCase`
- Classes, interfaces, type aliases, and components: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Booleans: `is`, `has`, `should`, or `can`
- Collections: plural names
- Functions: verb-noun names

```typescript
const orders = listOrders(userId)
const order = getOrder(orderId)

const isActive = order.status === "active"
const hasWriteAccess = permissions.canWrite(userId, order.projectId)
const shouldRetry = retryCount < MAX_RETRY_COUNT
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

```typescript
function getInvoiceTotal(invoice: Invoice | null): number {
  if (!invoice) return 0
  if (invoice.status === "cancelled") return 0
  if (invoice.lines.length === 0) return 0

  return invoice.lines.reduce((sum, line) => sum + line.amount, 0)
}
```

When a function has 3 or more parameters, break to one parameter per line:

```typescript
function createOrder(
  customerId: string,
  items: OrderItem[],
  currency: Currency,
  discountCode: string | null = null,
): Order {
  ...
}
```

When optional parameters change behavior, prefer a named options object:

```typescript
interface ExportReportOptions {
  includeArchived?: boolean
  maxRows?: number
}

function exportReport(
  report: Report,
  options: ExportReportOptions = {},
): Uint8Array {
  ...
}
```

Prefer a few boring lines over a dense expression that has to be unpacked.

## Module And File Structure

One module should have one clear purpose. Split a module when it stops being
easy to name. The file name should describe what the module does.

Avoid catch-all names like `utils.ts`, `helpers.ts`, `common.ts`, and
`misc.ts`. Prefer names that describe the job: `date-ranges.ts`,
`retry-policy.ts`, `invoice-totals.ts`, `embedding-chunks.ts`.

Frontend pages should decompose into the pieces that carry different
responsibilities:

- `types.ts` for shared local types
- `constants.ts` for named policy and display constants
- `use-*.ts` for stateful logic
- focused components for repeated UI pieces

Rules:

- Keep parsing, validation, transformation, and side effects separate
- Keep side-effecting code at the boundary
- Avoid import-time side effects
- Avoid catch-all components and catch-all modules
- Re-export intentionally in `index.ts`, never as an accident

## Import Organization

Imports should be scannable before reading the body of the file.

Use groups, with one blank line between groups:

1. Node built-ins
2. React and framework imports
3. Third-party packages
4. Local/project imports
5. Relative imports

Alphabetize within each group.

```typescript
import { readFile } from "node:fs/promises"

import { useCallback, useState } from "react"

import { clsx } from "clsx"

import { useOrders } from "@/hooks/use-orders"
import type { Order } from "@/types/order"

import { OrderCard } from "./order-card"
```

Rules:

- No wildcard imports
- No unused imports
- Prefer named imports
- Prefer absolute project imports over fragile relative chains
- Keep type-only imports marked with `import type`
- Re-export explicitly from `index.ts` when a public surface is useful

## Preferred Patterns

Use object-oriented, functional, and imperative code where each fits. The
default is the smallest shape that keeps the behavior obvious.

Use compact literals when values are simple and fit comfortably on one line.
Use multi-line literals when values are complex, documented, or easier to scan
vertically.

### Prefer Data-Driven Logic

Replace repetitive branches with data.

```typescript
const DATE_RANGE_LABELS: Record<DateRange, string> = {
  "7d": "7 Days",
  "30d": "30 Days",
  all: "All Time",
  custom: "Custom",
}

const label = DATE_RANGE_LABELS[range]
```

Apply this to status mappings, provider selection, retry schedules, state
transitions, feature flags, validation rules, and pricing tables.

### Normalize At Boundaries

Convert messy external data into clean internal types as soon as it enters the
system. The rest of the code should work with the common format.

```typescript
function parseOrderPayload(payload: unknown): OrderInput {
  ...
}
```

Once `OrderInput` exists, downstream code should not keep checking raw object
keys or provider-specific aliases.

### Avoid One-Off Branches

When an edge case can be handled by the same expression as the normal case,
prefer that over a separate branch.

```typescript
function insert<T>(items: T[], item: T, position: number): T[] {
  return [...items.slice(0, position), item, ...items.slice(position)]
}
```

`slice(0, 0)` and `slice(length)` already produce empty arrays. The edge cases
fall out naturally.

## Async And Promises

Never block the event loop.

Rules:

- Use `Promise.all` for structured concurrency
- Do not create fire-and-forget promises
- Keep state consistent across `await` points
- Run CPU-bound work in a worker when it can block the event loop
- Use async APIs instead of synchronous I/O in request paths
- Catch the narrowest error you can handle, then rethrow unknown errors

```typescript
async function loadOrderPage(orderId: string): Promise<OrderPageData> {
  const [order, items] = await Promise.all([
    fetchOrder(orderId),
    fetchOrderItems(orderId),
  ])

  return { order, items }
}
```

## Testing Style

Tests should explain behavior, not implementation trivia.

Rules:

- Test names describe the scenario and expected behavior
- Use clear arrange/act/assert structure
- Assert on meaningful outcomes, not incidental internals
- Keep fixtures explicit and local unless reuse is real
- Avoid sleeps, randomness, and external services in unit tests
- Use factories/builders when setup noise hides the behavior under test
- Shared utilities and hooks with non-trivial logic need unit tests

```typescript
it("must produce empty output for empty input, never throw", () => {
  expect(chunkItems([])).toEqual([])
})
```

## Verification Checklist

Before finishing TypeScript code, confirm:

- Every parameter and return value is typed
- No avoidable `any`, `as any`, or unexplained `@ts-ignore`
- Object shapes use `interface`; unions and intersections use `type`
- Props interfaces are explicit; no `React.FC`
- Names follow TypeScript conventions
- Booleans use `is`, `has`, `should`, or `can`
- Nesting stays shallow enough that the main path is obvious
- Magic numbers are named constants
- Imports are grouped, alphabetized, explicit, and type-only where appropriate
- No wildcard imports
- No import-time side effects
- Repetitive branching is data-driven
- Edge-case branches are only present when they add clarity
- Async code does not block the event loop
- Promises are awaited or returned
- Tests assert behavior and explain non-obvious scenarios

Optimize for the next reader. Leave code you can return to without rebuilding
the whole context from scratch.
