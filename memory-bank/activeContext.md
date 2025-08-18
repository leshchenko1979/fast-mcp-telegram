# Active Context: tg_mcp

## Current Work Focus
**Primary**: All major features are complete and working. The system is production-ready with comprehensive documentation and testing.

**Current Status**: Monitoring system performance and gathering user feedback for potential future enhancements.

## Active Decisions and Considerations

### Documentation Maintenance
**Decision**: Keep documentation updated as new usage patterns emerge
**Rationale**: Language models may discover new edge cases or usage scenarios
**Impact**: Ensures continued accuracy of search and messaging functionality

### Future Enhancement Planning
**Consideration**: Monitor for additional user needs or Telegram API changes
**Approach**: Maintain current functionality while being ready for new requirements
**Priority**: Low - current system meets all defined requirements

## Important Patterns and Preferences

### Search Usage Patterns
1. **Contact-Specific Search**: Use `chat_id` parameter, `query` can be empty or specific
2. **Content Search**: Use global search with `query` parameter, no `chat_id`
3. **Hybrid Search**: Use both `chat_id` and `query` for targeted content search
4. **Exact Message Retrieval**: Use `read_messages(chat_id, message_ids)` when IDs are known

### Message Formatting Patterns
1. **Plain Text**: Default behavior (`parse_mode=None`) for maximum compatibility
2. **Markdown**: Use `parse_mode='md'` or `'markdown'` for rich text formatting
3. **HTML**: Use `parse_mode='html'` for HTML-based formatting

## Next Immediate Steps
1. **Monitor System Performance**: Track usage patterns and identify any issues
2. **Gather User Feedback**: Collect feedback on search accuracy and message formatting
3. **Documentation Updates**: Update docs if new usage patterns emerge
4. **Maintenance**: Keep dependencies updated and monitor for API changes
5. **Refactoring**: Maintain DRY utilities (`build_message_result`, `compute_entity_identifier`) across tools
