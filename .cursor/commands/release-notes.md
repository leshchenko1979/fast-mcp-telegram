# Release Notes Generation

## Process for Creating Release Notes

When creating release notes, follow this systematic approach:

### 1. Identify Changes
- Use `git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+\.0$' | head -1` to find the latest major version tag (X.Y.0 format)
- Check for any commits since the last tag: `git log --oneline <last-major-tag>..HEAD`
- **Include all changes**: Analyze both local commits and any remote changes since the last major version
- **Note**: Typically you'll be preparing release notes before creating the new tag

### 2. Analyze Code Changes
- **Primary focus**: `git diff <previous-major-tag>..HEAD` - Examine user-facing code changes only
- **User-facing filter**: Look for new features, bug fixes, and behavior changes that affect end users
- **Skip internal changes**: Ignore refactoring, code cleanup, documentation, and architecture changes unless they're the only changes
- **Final state**: `git show HEAD:<file>` - Shows final user-visible functionality
- **Also analyze summaries**: Use `git log --onelines <previous-major-tag>..HEAD` to identify user-facing commits
- **Cross-validate**: Treat commit messages as hints, but validate against actual user-visible functionality
- **Describe user value**: Focus on what users can now do, not implementation details

### 3. Categorize Changes
- **AI-driven categorization**: Let the AI analyze code changes and determine appropriate categories
- **Focus on impact**: Group changes by their functional impact

#### Prioritization
- **PRIMARY FOCUS**: Added and fixed user-facing features only (new functionality, bug fixes, behavior changes)
- **SECONDARY**: Internal improvements only if there are no user-facing features to highlight
- **OMIT**: Refactoring, code quality improvements, documentation changes, and meta changes unless they're the only changes
- **CONCISE**: If there are user-facing features, omit all internal improvements to keep notes focused on value

### 4. Format Release Notes

Use this markdown template (paste as a markdown code block in chat):

```markdown
<Main user-facing features or key improvements - NO VERSION NUMBERS>

## New Features
- **Feature name** - What users can now do that they couldn't before
- **Another feature** - User-visible capability or improvement

## Fixes
- **Issue resolved** - What was broken and how it's now fixed
- **Another fix** - User-visible problem that was solved

This release <briefly describe the primary user-facing value proposition>.

**Full Changelog**: https://github.com/leshchenko1979/fast-mcp-telegram/compare/<previous-major-tag>...<current-tag>
```
**Note**: Replace `<current-tag>` with the new version tag once created. Only include internal improvements if there are no user-facing features to highlight. DO NOT include version numbers in the release title.

### 5. Quality Checks
- Verify all significant changes are mentioned
- Ensure categories accurately reflect the nature of changes made
- **Validate against code**: Ensure release note descriptions accurately reflect the actual code changes
- **Final state verification**: Confirm descriptions match the final state, not intermediate commits

### 6. Best Practices
- **No emojis** in release notes
- **User-facing focus**: Prioritize what users can now do or what problems are now solved
- **Omit internal changes**: Don't mention refactoring, code cleanup, or internal improvements unless they're the only changes
- **Impact over implementation**: Describe user-visible benefits, not how the code was changed
- **Code-first analysis**: Base descriptions on actual user-facing code changes, not commit messages
- **Final state focus**: Describe what users can now accomplish, not the development journey
- **Provide as markdown block**: Output release notes as a markdown code block in chat for easy copy/paste, do NOT create files
- **Aggregate major releases**: Include all changes since the last major version (X.Y.0)
- **Include recent commits**: Always analyze commits since the last tag, even if not yet tagged
- **Omit file stats**: Never include "Files Changed" or technical implementation details
- **Plain changelog URL**: Do not wrap the changelog URL in quotes or backticks; use a bare markdown link line like:
  - `**Full Changelog**: https://github.com/leshchenko1979/fast-mcp-telegram/compare/<previous-major-tag>...<current-tag>`

### 7. Version Bump Process
- **First**: Update version in `src/_version.py` (single source of truth for version management)
- **Then**: Create git tag: `git tag <version>` (no "v" prefix)
- **Next**: Push tag: `git push origin <version>`
- **Then**: Create GitHub release with generated notes
- **Wait for confirmation**: Do not proceed until user confirms GitHub release is published
- **Finally**: Send community announcement to Telegram group (only after user confirmation)

**Important**:
- Release notes are for GitHub releases only - do NOT commit release notes files to git repository
- Version is managed in `src/_version.py` with dynamic reading in `pyproject.toml` - only update the `_version.py` file
- There are no release files in this repository. Do not add any `RELEASE_NOTES*` or similar files to git.
- Tags are plain semantic versions without a leading "v" (example: `0.3.0`).

**Typical workflow**: Identify last major version → Analyze all changes since → Focus on user-facing features → Prepare release notes → Quality checks → Update version → Create tag → Push → Create GitHub release → **Wait for user confirmation** → Send community message

### 8. Community Announcement Process
- **Prerequisite**: Only proceed after user confirms GitHub release is published
- **Target**: Send message to `@mcp_telegram` community group
- **Language**: Russian (primary community language)
- **Content**: Include version number, header and key features
- **Format**: Use Markdown formatting with emojis for better readability
- **Structure**:
  - Version header with date
  - Categorized feature highlights with checkmarks
  - GitHub link to the release
- **Timing**: Send only after user confirms GitHub release is published
