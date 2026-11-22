# Real Backend Lead Resolver Herb Test

This run used the configured provider and the real `BackendLeadResolver`.
No herbs-per-phase value was supplied by the test.

## Player Authorization

> You decide

## Backend Plan

Renn is assigned to collect medicinal herbs in the north grove.

## Backend Lead Resolver Result

- **Status:** `resolved`
- **Outcome:** {'summary': 'Renn safely gathers a modest sustainable harvest of medicinal herbs.', 'quantity': {'resource': 'medicinal herbs', 'amount': 3, 'unit': 'units'}, 'risk_result': 'No encounter, injury, or complication occurred.', 'time_result': 'One phase elapsed.', 'return_constraint': 'The standing three-phase return constraint remains active.'}
- **Resource changes:**

```json
[
  {
    "resource": "medicinal herbs",
    "before": null,
    "delta": 3,
    "after": null,
    "unit": "units",
    "reason": "Current medicinal herb total was not supplied; reconcile this +3 delta against the Ledger Resources current value."
  }
]
```

## Assumption Record

```json
null
```

The quantity in this file is the resolver's decision, not a test constant.
