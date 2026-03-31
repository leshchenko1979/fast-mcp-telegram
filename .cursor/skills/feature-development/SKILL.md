---
name: feature-development
description: Feature development workflow for Telegram MCP projects. Use when implementing new features including research, planning, implementation, testing, and documentation.
---

# Feature Development Workflow

## Process Overview

```
Research -> Plan -> Spike -> Implement -> Test -> Clean Up -> Push
```

---

## Phase 1: Research

**Goal**: Understand the problem space and existing code

1. **Explore codebase** with explore subagent:
   - Find relevant existing functions and patterns
   - Understand data structures and type definitions
   - Map relationships between components

2. **API Investigation**:
   - Use Context7 MCP for library documentation
   - Use WebSearch for Telegram API specs
   - Use telegram-dev MCP for live API probing
   - Verify actual return values and structures

3. **Edge Case Identification**:
   - Identify potential issues early
   - Note API limitations or quirks
   - Check for existing tests that may break

---

## Phase 2: Planning

**Goal**: Create a detailed, actionable plan

1. **Clarify Requirements**:
   - Ask user for specifics on behavior
   - Offer numbered options for implementation choices
   - Default to simplest approach

2. **Document Technical Findings**:
   - API behavior verified through research
   - Type structures and field access patterns
   - Known limitations and edge cases

3. **Create Plan** (use CreatePlan tool):
   - Numbered steps with specific file:line references
   - Code snippets for key changes
   - Mermaid diagrams for complex relationships
   - Complexity assessment table

---

## Phase 3: Spiking

**Goal**: Verify assumptions with live API tests

**Use telegram-dev MCP for live testing**:

1. **API Response Structure**:
   - Call methods directly and inspect raw responses
   - Verify type definitions (e.g., `TextWithEntities` vs plain string)
   - Check field names and access patterns

2. **Edge Cases**:
   - Test with edge cases (empty results, invalid inputs)
   - Verify error handling behavior
   - Confirm caching behavior if applicable

3. **Document Findings**:
   - Update plan with corrected assumptions
   - Note any API quirks or bugs
   - Identify potential issues before implementation

---

## Phase 4: Implementation

**Goal**: Execute the plan faithfully

1. **Follow Plan Steps** in order:
   - Make changes as specified in plan
   - Don't deviate without re-planning

2. **Track Progress**:
   - Use git status after each step
   - Verify expected changes

3. **Code Standards**:
   - No linter errors
   - No redundant comments
   - Follow existing patterns

---

## Phase 5: Testing

**Goal**: Verify implementation works correctly

1. **Live API Tests** (via telegram-dev MCP):
   - Test new parameters/behavior
   - Verify error handling
   - Check edge cases

2. **Unit Tests**:
   - Add new tests for new behavior
   - Update existing tests for changed behavior
   - Run full test suite

3. **Document Results**:
   - Note any issues found
   - Fix bugs discovered

---

## Phase 6: Clean Up

**Goal**: Ensure code quality and documentation

1. **Code Cleanup** (use code-cleanup-specialist subagent):
   - Run linter checks
   - Fix code quality issues
   - Verify tests pass

2. **Documentation Update**:
   - Update README.md with new features
   - Update docs/ folder
   - Use feature template:

   ```markdown
   ### [Feature Name]

   **Tool/Function**: [name]

   **Parameters**:
   - `[param]`: [type] - [description]

   **Values**:
   - [value 1]: [description]

   **Example**:
   ```[lang]
   [example code]
   ```
   ```

3. **Memory Bank Update**:
   - Update activeContext.md with current work
   - Update progress.md with completed features
   - Document key decisions

---

## Phase 7: Git Push

1. **Commit** with descriptive message:
   ```
   [type]: [brief description]

   [detailed changes if needed]
   ```

2. **Push** to remote

3. **Create PR** if needed

---

## Example: Adding Folder Filtering Feature

### Research
- Explored contacts.py for existing dialog iteration
- Used Context7 to verify iter_dialogs folder parameter
- Used WebSearch to find DialogFilter TL schema

### Spike
- Called GetDialogFiltersRequest via telegram-dev
- Discovered title is TextWithEntities object (not string)
- Discovered folder_id=0 shows as null on Dialog objects

### Plan
- Created step-by-step plan
- Documented TextWithEntities extraction
- Added note about folder_id=null behavior

### Implement
- Added get_available_folders() with caching
- Added _resolve_folder_id() helper
- Updated iter_dialogs calls with folder param

### Test
- Live tested folder="Бридж" - worked
- Live tested folder=1 - worked
- Fixed cache key bug (SQLiteSession issue)

### Clean Up
- Ran code-cleanup-specialist
- Updated README.md
- Updated docs/Tools-Reference.md
- Updated memory bank

### Push
- Committed with descriptive message
- Pushed to origin
