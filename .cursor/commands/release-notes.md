# Release Notes Generation

## Process for Creating Release Notes

When creating release notes, follow this systematic approach:

### 1. Identify Changes
- Use `git tag --sort=-version:refname | head -1` to find the latest tag
- **Note**: Typically you'll be preparing release notes before creating the new tag

### 2. Analyze Code Changes
- **Primary focus**: `git diff <previous-tag>..HEAD` - Examine actual code changes, not summaries
- **Final state**: `git show HEAD:<file>` - Shows final state of specific files
- **Also analyze summaries**: Use `git log --no-merges <previous-tag>..HEAD --pretty=full` to read commit subjects/bodies to understand intent and user-facing context
- **Cross-validate**: Treat commit summaries/messages as hints for categorization and wording, but always validate and correct against actual code changes
- **Describe final state**: Not the journey, but the end result

### 3. Categorize Changes
- **AI-driven categorization**: Let the AI analyze code changes and determine appropriate categories
- **Focus on impact**: Group changes by their functional impact

#### Prioritization
- Prefer user-facing changes first (features, UX, behavior changes)
- Then internal improvements (performance, stability, refactors)
- Then documentation or meta changes
- If there is sufficient user-facing content, omit secondary categories to keep the notes concise

### 4. Format Release Notes

Use this markdown template (paste as a markdown code block in chat):

```markdown
<main theme>

## <Category Name>
- **Brief description** - Detailed explanation of what was changed and why
- **Another change** - Impact and benefits

## <Another Category Name>
- **Additional changes** - Description of changes in this category

This release focuses on <main theme>.

**Full Changelog**: https://github.com/leshchenko1979/fast-mcp-telegram/compare/<previous-tag>...<current-tag>

**Note**: Replace `<current-tag>` with the new version tag once created
```

### 5. Quality Checks
- Verify all significant changes are mentioned
- Ensure categories accurately reflect the nature of changes made
- **Validate against code**: Ensure release note descriptions accurately reflect the actual code changes
- **Final state verification**: Confirm descriptions match the final state, not intermediate commits

### 6. Best Practices
- **No emojis** in release notes
- **Focus on impact** rather than implementation details
- **Code-first analysis**: Base descriptions on actual code changes, not commit messages
- **Final state focus**: Describe what the code does now, not the journey to get there
- **Provide as markdown block**: Output release notes as a markdown code block in chat for easy copy/paste, do NOT create files
- **Aggregate patch releases**: Do not publish separate notes for patches; include all patch changes since the last minor version in the next minor release notes
- **Omit file stats when not needed**: If primary (user-facing) content is sufficient, omit any “Files Changed” or file stats sections
- **Plain changelog URL**: Do not wrap the changelog URL in quotes or backticks; use a bare markdown link line like:
  - `**Full Changelog**: https://github.com/leshchenko1979/fast-mcp-telegram/compare/<previous-tag>...<current-tag>`

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

**Typical workflow**: Analyze changes → Prepare release notes → Quality checks → Update version → Create tag → Push → Create GitHub release → **Wait for user confirmation** → Send community message

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
