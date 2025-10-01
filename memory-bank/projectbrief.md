
## Project Overview
fast-mcp-telegram is a production-ready Python-based MCP (Modular Control Platform) server that provides comprehensive Telegram integration capabilities. The project enables AI assistants and language models to interact with Telegram through a standardized interface, offering advanced search, messaging, contact management, and session persistence functionality.

## Core Requirements
1. **Telegram Integration**: Connect to Telegram via MTProto API using Telethon with robust session management
2. **Advanced Search**: Global and per-chat message search with multi-query support, filtering, and deduplication
3. **Comprehensive Messaging**: Send, edit, and read messages with formatting, replies, file sending (URLs/local), and phone number messaging
4. **Contact Management**: Search contacts, get detailed information, and manage contact relationships
5. **MCP Compliance**: Full MCP protocol implementation with HTTP transport and structured error handling
6. **Production Deployment**: Automated deployment with session persistence and cross-platform compatibility

## Key Goals
- **Production-Ready**: Enterprise-grade deployment with comprehensive session management
- **Advanced Search**: Multi-query parallel execution with intelligent deduplication
- **Robust Error Handling**: Unified structured error responses across all tools
- **Session Persistence**: Zero-downtime deployments with automatic session backup/restore
- **Cross-Platform**: Automatic handling of macOS resource forks and permission differences
- **Security-First**: Git-ignored session files with proper permission management

## Architecture Highlights
- **Session Management**: Streamlined session management using `~/.config/fast-mcp-telegram/` for cross-platform compatibility
- **Version Management**: Dynamic version reading from pyproject.toml with Python version compatibility
- **Deployment Automation**: Enhanced `deploy-mcp.sh` with backup/restore and cross-platform support
- **Error Resilience**: Structured error handling with request tracking and graceful degradation
- **LLM Optimization**: Concise tool descriptions and predictable API responses

## Production Features
- **Zero-Downtime Deployment**: Session files preserved across deployments
- **Automatic Permission Management**: Container user access automatically configured
- **Cross-Platform Compatibility**: Handles macOS, Linux, and Windows deployment scenarios
- **Health Monitoring**: Comprehensive container health checks and logging
- **Security Hardened**: Session files excluded from version control, proper file permissions
