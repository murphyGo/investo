# Tech Debt Skill

Display technical debt dashboard and manage debt items.

## Arguments

- `$ARGUMENTS` - One of the following:
  - (empty) or `all` - Show full dashboard
  - `critical`, `high`, `medium`, `low` - Filter by priority
  - `category:<name>` - Filter by category (e.g., `category:security`)
  - `aged` - Show items exceeding escalation thresholds
  - `add` - Interactive: add new debt item
  - `promote DEBT-NNN` - Promote specific debt item to development plan
  - `promote auto` - Auto-select and promote based on escalation criteria
  - `resolve DEBT-NNN` - Mark debt item as resolved

## Objective

Provide a comprehensive view of technical debt and enable promotion of debt items to development tasks. Track, prioritize, and manage technical debt throughout the project lifecycle.

---

## Execution Steps

### Step 1: Locate TECH-DEBT File

1. **Search for TECH-DEBT.md**:
   - `docs/TECH-DEBT.md`
   - `TECH-DEBT.md`

2. **If not found**, create from template (see Template section below)

### Step 2: Parse Arguments

| Argument | Mode |
|----------|------|
| (empty), `all` | Dashboard mode |
| `critical`, `high`, `medium`, `low` | Filter mode |
| `category:<name>` | Filter mode |
| `aged` | Filter mode |
| `add` | Add mode |
| `promote DEBT-NNN` | Promote mode (specific) |
| `promote auto` | Promote mode (auto-select) |
| `resolve DEBT-NNN` | Resolve mode |

---

## Dashboard Mode

### Step 3: Load and Parse TECH-DEBT

1. **Read** TECH-DEBT.md
2. **Parse** all sections:
   - Summary table
   - Active items by priority
   - Resolved items

### Step 4: Calculate Statistics

For each active debt item, extract:
- DEBT ID, Title, Priority, Category
- Added date, Age (days)
- Location, Blocked by (if any)

### Step 5: Apply Filters (if filter mode)

| Filter | Behavior |
|--------|----------|
| `all` (default) | Show all active items |
| `critical` | Only Critical priority |
| `high` | Only High priority |
| `medium` | Only Medium priority |
| `low` | Only Low priority |
| `category:<name>` | Filter by category |
| `aged` | Items older than escalation threshold |

### Step 6: Generate Dashboard

```
## TECH-DEBT Dashboard

**Project**: {project-name}
**Generated**: YYYY-MM-DD HH:MM

---

### Health Status: 🟢 Good / 🟡 Warning / 🔴 Critical

[Explanation based on health indicators]

---

### Summary

| Priority | Count | Oldest | Avg Age |
|----------|-------|--------|---------|
| Critical | 0 | - | - |
| High | N | Xd | Yd |
| Medium | N | Xd | Yd |
| Low | N | Xd | Yd |
| **Total** | **N** | - | **Zd** |

---

### Escalation Alerts

| DEBT ID | Priority | Age | Threshold | Status |
|---------|----------|-----|-----------|--------|
| DEBT-001 | High | 16d | 14d | ⚠️ Promote recommended |

---

### Active Items by Priority

#### Critical Priority
_No critical items._

#### High Priority
| ID | Title | Category | Age | Location |
|----|-------|----------|-----|----------|
| DEBT-001 | [Title] | Performance | 16d | `src/db.py:45` |

#### Medium Priority
| ID | Title | Category | Age | Location |
|----|-------|----------|-----|----------|
| DEBT-002 | [Title] | Testing | 25d | `src/api.py:78` |

---

### Quick Actions

- Add new item: `/tech-debt add`
- Promote aged item: `/tech-debt promote DEBT-001`
- Auto-promote: `/tech-debt promote auto`
- View specific priority: `/tech-debt high`
- Resolve item: `/tech-debt resolve DEBT-001`
```

---

## Add Mode

### Step 3A: Gather Information

Prompt user for:

```
## Add Technical Debt Item

**Title**: [Brief description of the issue]
**Category**: [security/performance/reliability/testing/documentation/other]
**Priority**: [critical/high/medium/low]
**Location**: [file:line or component name]

**Description**:
[Detailed description of the technical debt]

**Impact**:
[What problems does this cause?]

**Remediation**:
[Steps to fix this issue]

**Estimated Effort**: [time estimate]
```

### Step 4A: Generate DEBT ID

1. Find highest existing DEBT-NNN in file
2. Increment to get new ID

### Step 5A: Add to TECH-DEBT.md

Insert new item in appropriate priority section:

```markdown
### DEBT-{NNN}: {Title}

**Category**: {category}
**Priority**: {priority}
**Added**: {YYYY-MM-DD}
**Location**: `{location}`

**Description**:
{description}

**Impact**:
{impact}

**Remediation**:
{remediation steps}

**Estimated Effort**: {effort}
```

---

## Promote Mode

### Step 3P: Select Promotion Candidate

#### If `promote DEBT-NNN`:
1. Find the specified debt item
2. Validate it exists and is active
3. Proceed to Step 4P

#### If `promote auto`:
1. Apply escalation criteria:
   - Critical priority → Always promote
   - High priority + age > 14 days → Promote
   - Medium priority + age > 21 days → Consider
   - 3+ items in same category → Promote oldest

2. Rank candidates by urgency
3. Present list for user choice:
   ```
   ## Auto-Promote Candidates

   | # | DEBT ID | Priority | Age | Reason |
   |---|---------|----------|-----|--------|
   | 1 | DEBT-001 | High | 16d | Exceeds 14d threshold |
   | 2 | DEBT-002 | Medium | 25d | Exceeds 21d threshold |

   Select item to promote (1-N) or 'cancel':
   ```

### Step 4P: Generate Development Task

Transform debt into development plan format:

```markdown
### X.Y - Address DEBT-{NNN}: {Title}

**Source**: TECH-DEBT promotion
**Original Priority**: {priority}

- [ ] {Remediation step 1}
- [ ] {Remediation step 2}
- [ ] Add/update tests
- [ ] Mark DEBT-{NNN} resolved
```

### Step 5P: Present Proposal

```
## Debt Promotion Proposal

### Source Item

**DEBT ID**: DEBT-NNN
**Title**: {title}
**Priority**: {priority} | **Age**: {X days}
**Category**: {category}

**Description**:
{description}

### Proposed Development Task

**Target**: Add to current unit's stage plan

{generated task markdown}

Add to development plan? (yes/no)
```

### Step 6P: Update Documents (on approval)

1. **Update current stage plan**:
   - Add new step to the active per-stage plan file in `aidlc-docs/construction/plans/`
   - Include `[DEBT-NNN]` reference
   - Log in `aidlc-docs/audit.md`

2. **Update TECH-DEBT.md**:
   - Add note: "Promoted to development plan on YYYY-MM-DD"
   - Keep item active until resolved

---

## Resolve Mode

### Step 3R: Find and Validate Item

1. Find DEBT-NNN in active items
2. Confirm with user:
   ```
   Resolving DEBT-{NNN}: {title}

   Please confirm:
   - [ ] Issue has been fixed
   - [ ] Tests added/updated
   - [ ] No regression introduced

   Mark as resolved? (yes/no)
   ```

### Step 4R: Move to Resolved

1. Remove from active section
2. Add to Resolved Items section:
   ```markdown
   ### DEBT-{NNN}: {title} ✅
   **Resolved**: YYYY-MM-DD
   **Resolution**: {brief description of fix}
   ```

---

## Escalation Criteria

| Priority | Age Threshold | Action |
|----------|---------------|--------|
| Critical | 0 days | Auto-promote |
| High | 14 days | Recommend promote |
| Medium | 21 days | Suggest promote |
| Low | 30 days | Consider promote |

### Additional Triggers

| Condition | Action |
|-----------|--------|
| Blocks current work | Immediate promote |
| 3+ items same category | Promote oldest |
| Security-related | Escalate priority |

---

## Health Indicators

| Indicator | 🟢 Good | 🟡 Warning | 🔴 Critical |
|-----------|---------|------------|-------------|
| Total Count | < 5 | 5-10 | > 10 |
| Critical Items | 0 | 1 | > 1 |
| High Items > 14d | 0 | 1-2 | > 2 |
| Avg Age | < 7d | 7-14d | > 14d |

---

## TECH-DEBT.md Template

```markdown
# Technical Debt Registry

## Summary

| Priority | Count | Oldest |
|----------|-------|--------|
| Critical | 0 | - |
| High | 0 | - |
| Medium | 0 | - |
| Low | 0 | - |

---

## Active Items

### Critical Priority

_No critical items._

### High Priority

_No high priority items._

### Medium Priority

_No medium priority items._

### Low Priority

_No low priority items._

---

## Resolved Items

_No resolved items yet._
```

---

## Example Invocations

Full dashboard:
```
/tech-debt
```

Filter by priority:
```
/tech-debt high
/tech-debt critical
```

Filter by category:
```
/tech-debt category:security
```

Show aged items:
```
/tech-debt aged
```

Add new item:
```
/tech-debt add
```

Promote specific item:
```
/tech-debt promote DEBT-001
```

Auto-select and promote:
```
/tech-debt promote auto
```

Resolve item:
```
/tech-debt resolve DEBT-001
```
