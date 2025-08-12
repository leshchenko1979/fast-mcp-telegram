# Changelog

## [2025-08-12] - Search Interpretation Fix

### 🐛 Fixed
- **Search Query Interpretation Issue**: Language models were incorrectly using contact names as search queries in global search instead of targeting specific contacts

### ✨ Enhanced
- **Tool Documentation**: Significantly improved tool descriptions with:
  - Clear distinction between per-chat and global search modes
  - Usage examples with ❌/✅ indicators for common mistakes
  - Recommended and alternative workflows for contact-specific searches
  - Parameter relationship explanations
  - Updated descriptions reflecting new search_contacts functionality

- **Contact Resolution**: Added new tools to help language models:
  - `search_contacts()`: Resolve contact names to chat IDs using Telegram's native search
  - `get_contact_details()`: Get detailed contact information
  - Enhanced `get_dialogs()` documentation with workflow examples

### 📚 Added
- **Language Model Guidance**: Comprehensive documentation (`docs/language_model_guidance.md`) covering:
  - Correct usage patterns for different search scenarios
  - Common mistakes and how to avoid them
  - Tool usage workflows
  - Best practices for contact resolution
  - Testing examples to validate understanding

### 🔧 Technical Improvements
- **New Module**: `src/tools/contacts.py` for contact resolution functionality
- **Enhanced Server**: Added new MCP tools for contact management
- **Memory Bank**: Comprehensive project documentation for future reference
- **Code Cleanup**: Removed duplicate `find_contact` tool, eliminated code duplication
- **API Integration**: Implemented Telegram's native `contacts.SearchRequest` for better contact search

### 🎯 Impact
- **Expected Outcome**: Language models should now correctly distinguish between:
  - Contact-specific searches (using `chat_id` parameter)
  - Content-specific searches (using `query` parameter)
  - Hybrid searches (using both parameters)
- **Workflow**: Models should use `find_contact()` → `search_messages()` instead of incorrect global search with contact names

### 📋 Usage Examples
**Before (Incorrect)**:
```python
search_messages(query="John", chat_id=None)  # Searches for "John" in all chats
```

**After (Correct)**:
```python
contacts = search_contacts(query="John")
john_chat_id = contacts[0]['chat_id']
search_messages(chat_id=john_chat_id, query="")  # Gets messages from John's chat
```


