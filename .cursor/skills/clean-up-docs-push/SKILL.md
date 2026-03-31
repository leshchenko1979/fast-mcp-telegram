---
name: Clean Up Docs Push
description: Code cleanup, docs update, and git push workflow
disable-model-invocation: true
---

## Workflow

1. **Code Cleanup** (use `code-cleanup-specialist` subagent):
   - Run linter checks on modified files
   - Fix any code quality issues
   - Run test suite to verify everything passes

2. **Update Docs**:
   - Update `README.md` - add new features to Features table and update tool descriptions
   - Update `docs/` folder - check all relevant files and update with new features

3. **Git Push**:
   - Create descriptive commit
    - Push to remote