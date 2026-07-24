# Flight Disruption Agents — Ahmed Yakout

## My two parts: Reactive + Routing

---

## How to run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your API key (for Routing only — Reactive needs nothing)
Create a `.env` file in the project root:
```
OPENROUTER_API_KEY=your_key_here
```

---

## Part 1 — Reactive Agent (`reactive/`)

**No LLM. No API key needed. Zero AI.**

Pure `if/then` rules. The agent reads the case data (delay hours, membership, etc.) and applies fixed conditions.

```bash
cd reactive
python main.py
```

### What it does
| Condition | Action |
|---|---|
| Cancelled | Travel credit + rebooking |
| Has connection + delay ≥ 1h | Rebook on next flight |
| Delay > 6h | Hotel + rebooking |
| Delay 2–6h | Meal voucher (+ credit if gold/silver) |
| Delay < 2h | Apology only |

### Where it breaks
- A 1-hour delay with a gold member gets no compensation (rule doesn't check membership for short delays)
- Two conditions firing at once (e.g., cancelled AND missed connection) → only one rule fires
- Any case outside the hard-coded conditions → falls through silently

---

## Part 2 — Routing Agent (`routing/`)

**ONE LLM call to classify. Everything else is plain Python.**

The model reads the passenger case text and returns exactly one label. A fixed workflow function then handles that label — no more model calls.

```bash
cd routing
python main.py
```

### Categories the model chooses from
| Label | Meaning |
|---|---|
| `MINOR_DELAY` | < 2 hours, no connection risk |
| `MEDIUM_DELAY` | 2–6 hours, no connection risk |
| `MAJOR_DELAY` | > 6 hours, no connection risk |
| `MISSED_CONNECTION` | Passenger will miss connecting flight |
| `CANCELLATION` | Flight fully cancelled |
| `ESCALATE` | Complex / unclear → human agent |

### Why this is better than Reactive
- Understands natural language ("I want my money back" → `CANCELLATION` workflow)
- One call only → fast and cheap
- Easy to add a new category without rewriting all rules

### Where it still breaks
- Can't adjust based on tool results (e.g., if no flights are available, it can't try a different approach)
- A wrong classification causes one wrong workflow — but only one, not a cascade

---

## Comparison Table

| | Reactive | Routing |
|---|---|---|
| LLM calls | 0 | 1 |
| Tokens used | 0 | ~300–500 |
| Latency | < 1ms | < 1 sec |
| Handles natural language | ✗ | ✓ |
| Handles unseen phrasing | ✗ | ✓ |
| Adapts to tool results | ✗ | ✗ |
| Predictable behavior | ✓ | ✓ (after classification) |
| Easy to debug | ✓ | ✓ |
