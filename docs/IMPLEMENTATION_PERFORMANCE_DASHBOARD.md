# Performance Dashboard — Implementation Plan

## Overview

A new page (`/performance-dashboard`) that visualizes all saved performance test results as a scatter plot with:
- **X-axis**: Average response speed (seconds) — lower is better
- **Y-axis**: Accuracy % — higher is better
- **Color**: Model name
- **Border style**: Solid = sequential, Dashed = concurrent

## Dependency Order

```
Backend (DB query) → Backend API endpoint → Frontend types → Frontend API client →
Frontend chart component → Frontend page → Router → Header nav link
```

## Tasks

### Phase 1: Backend (Database & API)

#### 1.1 — Backend: Add aggregated stats endpoint
**File**: `app/routes/performance_testing.py`
**Dependencies**: None (modifies existing file)
**Description**: Add a new endpoint `GET /api/performance-testing/stats` that returns aggregated batch statistics grouped by batch_uuid. For each batch, compute:
- Average response speed from `response_received_time - request_sent_time`
- Accuracy % from `valid_response` column
- `batch_type` to differentiate sequential vs concurrent
- `model_name` and `friendly_name`

**Implementation**:
```python
@router.get("/api/performance-testing/stats")
async def api_get_performance_stats(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get aggregated performance stats per batch for dashboard visualization."""
    rows = (
        db.query(PerformanceTestResult)
        .order_by(PerformanceTestResult.batch_uuid, PerformanceTestResult.batch_type)
        .all()
    )
    # Group by batch_uuid and compute averages
    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        elapsed = (
            (r.response_received_time.timestamp() - r.request_sent_time.timestamp())
            if r.response_received_time and r.request_sent_time
            else 0
        )
        groups[r.batch_uuid].append({
            "elapsed": elapsed,
            "valid": r.valid_response,
            "batch_type": r.batch_type,
            "model_name": r.model_name,
            "friendly_name": r.friendly_name,
        })

    stats = []
    for batch_uuid, entries in groups.items():
        sequential_entries = [e for e in entries if e["batch_type"] == "sequential"]
        concurrent_entries = [e for e in entries if e["batch_type"] == "concurrent"]

        for label, elapses in [("sequential", sequential_entries), ("concurrent", concurrent_entries)]:
            if not elapses:
                continue
            avg_speed = sum(e["elapsed"] for e in elapses) / len(elapses)
            valid_count = sum(1 for e in elapses if e["valid"] is True)
            accuracy = valid_count / len(elapses) * 100 if elapses else 0
            stats.append({
                "batch_uuid": batch_uuid,
                "friendly_name": elapses[0]["friendly_name"],
                "model_name": elapses[0]["model_name"],
                "batch_type": label,
                "avg_speed_seconds": round(avg_speed, 3),
                "accuracy_pct": round(accuracy, 1),
                "total_requests": len(elapses),
            })
    return stats
```

---

### Phase 2: Frontend Types

#### 2.1 — Frontend: Add PerformanceStats type
**File**: `frontend/src/types/index.ts`
**Dependencies**: Phase 1 (backend endpoint exists)
**Description**: Add a new TypeScript interface for the stats response:
```typescript
export interface PerformanceStats {
  batch_uuid: string;
  friendly_name: string;
  model_name: string;
  batch_type: "sequential" | "concurrent";
  avg_speed_seconds: number;
  accuracy_pct: number;
  total_requests: number;
}
```

---

### Phase 3: Frontend API Client

#### 3.1 — Frontend: Add getPerformanceStats to api.ts
**File**: `frontend/src/services/api.ts`
**Dependencies**: Phase 2 (types defined)
**Description**: Add a new method to `performanceApi`:
```typescript
getPerformanceStats: () => request<PerformanceStats[]>('/api/performance-testing/stats'),
```

---

### Phase 4: Frontend Components

#### 4.1 — Frontend: Create PerformanceChart component
**File**: `frontend/src/components/ui/PerformanceChart.tsx` (NEW)
**Dependencies**: Phase 3 (API client ready)
**Reused Components**: `Card`, `Badge` from existing ui components
**Description**: A scatter plot component using Recharts.

**Features**:
- Scatter plot with speed (x) and accuracy (y)
- Color-coded by model name
- Border style: solid = sequential, dashed = concurrent
- Batch enable/disable toggles
- Legend with model colors
- Hover tooltip with batch details

**Implementation approach**:
- Use `recharts` ScatterChart + Scatter component
- Map model names to a color palette
- Use `strokeDasharray` to differentiate sequential (solid) vs concurrent (dashed)
- Include a checkbox list below the chart for enabling/disabling batches
- Reuse `Card` component as wrapper

**API usage**:
```typescript
import { performanceApi } from '../../services/api';

interface PerformanceChartProps {
  data: PerformanceStats[];
  enabledBatches: Set<string>;
  onToggleBatch: (batchUuid: string) => void;
}
```

---

#### 4.2 — Frontend: Export PerformanceChart from ui index
**File**: `frontend/src/components/ui/index.ts`
**Dependencies**: Phase 4.1 (PerformanceChart created)
**Description**: Add export line:
```typescript
export { default as PerformanceChart } from "./PerformanceChart";
```

---

#### 4.3 — Frontend: Create PerformanceDashboard page
**File**: `frontend/src/pages/PerformanceDashboard.tsx` (NEW)
**Dependencies**: Phase 4.1 (chart component), Phase 3 (API client)
**Reused Components**: `PageHeader`, `Card`, `StatusBanner` from existing ui components
**Description**: Main page component that:
1. Fetches stats on mount using `performanceApi.getPerformanceStats()`
2. Displays the `PerformanceChart` component
3. Shows loading/error states using existing `StatusBanner`
4. Provides controls to select/deselect all batches

**Layout**:
```
┌─────────────────────────────────────────┐
│  PageHeader "Performance Dashboard"     │
├─────────────────────────────────────────┤
│  [StatusBanner if loading/error]        │
├─────────────────────────────────────────┤
│  ┌─ PerformanceChart ─────────────────┐ │
│  │  [Scatter plot with Recharts]     │ │
│  │  [Batch toggles below chart]      │ │
│  └───────────────────────────────────┘ │
├─────────────────────────────────────────┤
│  ┌─ Stats Table ─────────────────────┐ │
│  │  [Optional: table with all data]  │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

### Phase 5: Routing & Navigation

#### 5.1 — Frontend: Add route in App.tsx
**File**: `frontend/src/App.tsx`
**Dependencies**: Phase 4.3 (PerformanceDashboard page exists)
**Description**: Import and add route:
```typescript
import PerformanceDashboard from './pages/PerformanceDashboard';
// ... in Routes:
<Route path="/performance-dashboard" element={<PerformanceDashboard />} />
```

#### 5.2 — Frontend: Add nav link in Header.tsx
**File**: `frontend/src/components/Header.tsx`
**Dependencies**: Phase 5.1 (route exists)
**Description**: Add nav link to existing links array:
```typescript
{ path: '/performance-dashboard', label: 'Performance Dashboard' }
```

---

### Phase 6: Package Installation

#### 6.1 — Install recharts
**Command**: `cd frontend && npm install recharts`
**Dependencies**: None
**Description**: Install the Recharts library. This uses npm internally and does not manually edit package.json.

---

## Execution Order Summary

| Order | Task | Depends On |
|-------|------|------------|
| 1 | 1.1 Backend stats endpoint | — |
| 2 | 2.1 Frontend types | 1.1 |
| 3 | 3.1 Frontend API client | 2.1 |
| 4 | 4.1 PerformanceChart component | 3.1 |
| 5 | 4.2 Export from ui/index | 4.1 |
| 6 | 4.3 PerformanceDashboard page | 3.1, 4.1 |
| 7 | 5.1 Add route in App.tsx | 4.3 |
| 8 | 5.2 Add nav link in Header.tsx | 5.1 |
| 9 | 6.1 Install recharts | Can be done in parallel with 1-8 |

**Note**: Task 6.1 (npm install) can be started first since it has no dependencies and other tasks can be written in parallel.

## Reused Components

| Component | Source | Used In |
|-----------|--------|---------|
| `Card` | `components/ui/Card.tsx` | PerformanceChart wrapper, PerformanceDashboard |
| `Badge` | `components/ui/Badge.tsx` | PerformanceChart labels (batch type, model) |
| `PageHeader` | `components/ui/PageHeader.tsx` | PerformanceDashboard page |
| `StatusBanner` | `components/ui/StatusBanner.tsx` | PerformanceDashboard loading/error states |
| `performanceApi` | `services/api.ts` | All frontend data fetching |
| `TestResult` type | `types/index.ts` | Data reference patterns |
| Tailwind classes | Existing project config | All components |

## Differences from Original Spec

The following items deviate from the original implementation plan. All other tasks (1.1–6.1) were implemented as specified.

### 1.1 — Backend: Datetime parsing improvement
**Original**: Used `.timestamp()` on datetime objects
**Actual**: Changed to `datetime.fromisoformat()` for robust string timestamp parsing from the database

### 4.1 — PerformanceChart: Enhanced beyond original spec
**Original spec**:
- Color-coded by model name
- Use `strokeDasharray` to differentiate sequential vs concurrent
- Include a checkbox list below the chart for enabling/disabling batches

**Actual implementation**:
- **Color by batch UUID** (not model name) using deterministic HSL rainbow via `hashString()` + `getBatchColor()`
- **Scatter shape differs by batch type**: sequential = solid circle, concurrent = filled circle + dashed outline circle group (not `strokeDasharray` on the XAxis)
- **Interactive `BatchLegend` component** replaces checkbox list — click legend items to show/hide batches
- **Custom tooltip** with friendly_name, model, speed (2 decimal places), accuracy, requests count, and batch type Badge
- **X-axis clamped** to [0, 200] range via computed `clampedSpeed` field
- **Reference line** at Y=100% (dashed)
- **Props are optional**: `visibleBatches` and `onToggleBatch` default to undefined (backward compatible)
- **`isAnimationActive={false}`** to disable animation

**New helper functions added**:
```typescript
function hashString(str: string): number     // deterministic string → int hash
function getBatchColor(batchUuid: string, totalBatches: number): string  // HSL rainbow
```

### 4.3 — PerformanceDashboard: Enhanced beyond original spec
**Original spec**:
- Fetches stats, displays chart, shows loading/error states, provides select/deselect controls

**Actual implementation** (all above plus):
- **Multi-column sort** on stats table: Shift+click column headers to add sort keys; click again cycles asc → desc → clear
- **Batch search filter** input: filters batches by name or UUID before rendering checkboxes
- **Three action buttons**: "Select All", "Deselect All", "Clear Sort" (conditional)
- **Full sortable stats table** with columns: Friendly Name, Model, Batch Type (colored Badge), Avg Speed (font-mono, 3 decimals), Accuracy (font-mono), Requests
- **Visual toggle states**: checked = `bg-primary-50` with border, unchecked = `opacity-50`
- **Empty state card** when no test data exists

**Actual Layout**:
```
┌───────────────────────────────────────────────────┐
│  Performance Dashboard          [Select All]      │
│                                 [Deselect All]    │
│                                 [Clear Sort] (cond.)│
├───────────────────────────────────────────────────┤
│  ┌─ PerformanceChart ───────────────────────────┐ │
│  │  [Scatter plot with Recharts]               │ │
│  │  [Interactive Batch Legend below chart]     │ │
│  └─────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────┤
│  ┌─ Batch Controls ─────────────────────────────┐ │
│  │  [Search: "Search batches by name or ID..."] │ │
│  │  [Checkbox grid with visual states]          │ │
│  └─────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────┤
│  ┌─ Detailed Statistics ────────────────────────┐ │
│  │  [Multi-sortable table]                      │ │
│  └─────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────┘
```

### 5.2 — Header nav label
**Original**: `{ path: '/performance-dashboard', label: 'Performance Dashboard' }`
**Actual**: `{ path: '/performance-dashboard', label: 'Dashboard' }`
