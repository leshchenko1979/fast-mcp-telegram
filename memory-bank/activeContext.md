# Active Context: tg_mcp

## Current Work Focus
**Primary Issue**: Language models are incorrectly interpreting search requests when users ask to find information from specific contacts. Instead of using the contact name to identify a specific chat (via `chat_id`), models are using the name as a search query in global search.

## Recent Changes
- Created comprehensive memory bank documentation
- Identified the core search interpretation problem
- Analyzed current search functionality in `src/tools/search.py`
- Documented the dual search mode architecture (global vs per-chat)
- Enhanced `search_messages` tool documentation with clear usage guidance
- Improved `get_dialogs` tool documentation with workflow examples
- Created new `search_contacts` tool using Telegram's native contacts.SearchRequest
- Removed old `find_contact` tool to eliminate duplication
- Fixed global search text extraction issue
- Added comprehensive language model guidance documentation

## Next Steps
1. **✅ Test the Enhanced Documentation**: Verified that the improved tool descriptions resolve the search interpretation issue
2. **✅ Validate New Tools**: Tested the `search_contacts` tool with language models - works perfectly
3. **✅ Monitor Usage Patterns**: Language models now correctly use the contact resolution workflow
4. **✅ Gather Feedback**: New documentation and tools are effective and working as expected
5. **🔄 Production Ready**: All improvements are implemented and tested successfully

## Active Decisions and Considerations

### Search Mode Clarification
**Decision**: Need to make the distinction between search modes explicit in documentation
**Rationale**: Current documentation doesn't clearly explain when to use `chat_id` vs global search
**Impact**: Will help language models make correct parameter choices

### Contact Name Resolution
**Decision**: Implemented `search_contacts` tool using Telegram's native contacts.SearchRequest
**Rationale**: Provides powerful contact search through contacts and global Telegram users
**Implementation**: Created `src/tools/contacts.py` with native Telegram search functionality
**Benefits**: More accurate contact resolution, supports username/phone search, eliminates duplication

### Documentation Strategy
**Approach**: Enhanced tool descriptions with:
- Clear usage scenarios and examples
- Parameter relationship explanations
- Common mistake examples with ❌/✅ indicators
- Best practices for different search types
- Recommended and alternative workflows for contact resolution
- Comprehensive language model guidance document
- Updated tool descriptions reflecting new search_contacts functionality

## Important Patterns and Preferences

### Search Usage Patterns
1. **Contact-Specific Search**: Use `chat_id` parameter, `query` can be empty or specific
2. **Content Search**: Use global search with `query` parameter, no `chat_id`
3. **Hybrid Search**: Use both `chat_id` and `query` for targeted content search

### Language Model Guidance
- **Explicit Instructions**: Always specify when to use each parameter
- **Example-Driven**: Provide concrete examples for each scenario
- **Error Prevention**: Highlight common mistakes and how to avoid them

## Learnings and Project Insights

### Current Search Behavior
- **Global Search**: Searches across all chats for the query term
- **Per-Chat Search**: Searches within a specific chat (identified by chat_id)
- **Query Interpretation**: Global search treats the query as content to find, not as a contact identifier

### Language Model Behavior
- **Assumption Pattern**: Models assume contact names should be search queries
- **Context Confusion**: Models don't distinguish between "find messages from X" vs "find messages about X"
- **Parameter Ambiguity**: The relationship between `query` and `chat_id` is not clear enough

### Technical Architecture Insights
- **Dual Mode Design**: The system correctly supports both search modes
- **Parameter Validation**: Current validation prevents invalid combinations
- **Documentation Gap**: The main issue is in tool documentation, not implementation

## Immediate Action Items
1. **✅ Enhanced search_messages tool description** with clear parameter explanations and examples
2. **✅ Added usage examples** for different search scenarios with ❌/✅ indicators
3. **✅ Created comprehensive documentation** explaining contact targeting vs content searching
4. **✅ Implemented search_contacts tool** using Telegram's native contacts.SearchRequest
5. **✅ Removed duplicate tools** and cleaned up codebase
6. **✅ Fixed global search text extraction** issue
7. **✅ Tested all improvements** - working perfectly
8. **✅ Updated tool descriptions** with recommended and alternative workflows
