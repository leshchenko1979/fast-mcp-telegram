# Project Brief: tg_mcp

## Project Overview
tg_mcp is a Python-based MCP (Modular Control Platform) server that provides comprehensive Telegram integration capabilities. The project enables AI assistants and language models to interact with Telegram through a standardized interface, offering search, messaging, analytics, and data export functionality.

## Core Requirements
1. **Telegram Integration**: Connect to Telegram via MTProto API using Telethon
2. **Search Functionality**: Global and per-chat message search with filtering capabilities
3. **Messaging**: Send messages to chats with reply functionality
4. **Analytics**: Generate statistics and insights from chat data
5. **Data Export**: Export chat data in various formats
6. **MCP Compliance**: Follow MCP protocol standards for tool integration

## Key Goals
- Provide reliable Telegram access for AI assistants
- Enable efficient message search and retrieval
- Support comprehensive chat management and analytics
- Maintain clean separation between global and targeted search operations
- Ensure proper documentation for language model usage

## Current Challenge
**Search Query Interpretation Issue**: Language models are incorrectly using contact names as search queries in global search, causing the system to search for the name within message content rather than targeting the specific contact's chat.

## Technical Constraints
- Must work with existing Telegram API limitations
- Need to handle both global and per-chat search scenarios
- Must provide clear documentation for AI model usage patterns
- Should maintain backward compatibility with existing implementations


