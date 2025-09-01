# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SMM is a Social Media Marketing and Management system built on the Frappe framework. It automates social media content creation, scheduling, and posting across multiple platforms (X/Twitter, Facebook, Telegram) with AI-powered content generation using OpenAI.

## Development Commands

### Testing and Debugging
```bash
# Test content generation mechanisms
bench --site [site_name] execute smm.libs.openai.generate_content --kwargs '{"name":"[mechanism_id]"}'

# Test activity casting (posting to social media)
bench --site [site_name] execute smm.libs.activity.cast --kwargs '{"name":"[activity_id]"}'

# Test feed fetching
bench --site [site_name] execute smm.libs.feed.fetch --kwargs '{"name":"[feed_provider_id]"}'

# Refresh OAuth tokens
bench --site [site_name] execute smm.libs.x.refresh_access_token --kwargs '{"name":"[agent_name]"}'
```

### Frappe Development
```bash
# Install app in development mode
bench --site [site_name] install-app smm

# Migrate database after doctype changes
bench --site [site_name] migrate

# Build assets
bench build

# Start development server
bench start
```

## Architecture Overview

### Core Data Model
The system revolves around these key relationships:
- **Network Activity Plan** → **Network Activity** → **Content** → **Agent** → **Social Platform**
- **Feed Provider** → **Feed** → **Content Generation**
- **API** → **Agent** (stores OAuth credentials per platform)

### Scheduling System (`smm/libs/activity.py`)
The `ActivityPlan` class orchestrates content scheduling:
1. **Plan Processing**: Converts high-level plans into specific activities
2. **Activity Generation**: Creates time-based activities with agent assignments  
3. **Content Generation**: Triggers AI content creation
4. **Activity Casting**: Posts content to social platforms

### Multi-Platform Integration (`smm/libs/`)
Each platform has dedicated modules:
- **x.py**: X/Twitter with OAuth 1.0a/2.0, media upload via chunked API
- **openai.py**: GPT-4 text generation, DALL-E 3 image generation with function calling
- **telegrambot.py**: Telegram Bot API integration
- **agent.py**: Unified platform abstraction layer

### Content Generation Pipeline
1. **Feed Aggregation**: RSS feeds + virtual feeds (JSON arrays)
2. **AI Processing**: OpenAI function calling with structured prompts
3. **Media Handling**: Image generation, variation, format conversion to PNG
4. **Multi-Source Input**: Combines feeds, prompts, and linked activities

### Key Design Patterns
- **Provider Pattern**: Unified interface for different social platforms via `agent.call()`
- **Transform System**: Dynamic field resolution using `{"var": ["context", "key"]}` syntax
- **Scheduled Tasks**: Frappe scheduler events for automated operations
- **State Management**: Activity lifecycle (Pending → Success/Failed)

### OAuth Flow Architecture
Complex multi-version OAuth support:
- OAuth 1.0a for X media uploads (required for large files)
- OAuth 2.0 for modern API access
- State management via Frappe cache
- Automatic token refresh with fallback mechanisms

### File Structure Notes
- `smm/smm/doctype/*/`: Frappe doctype definitions (JSON + Python + JS)
- `smm/libs/`: Core business logic modules
- `smm/tasks/`: Scheduled background tasks
- Each doctype follows Frappe conventions: `.json` (fields), `.py` (controller), `.js` (client-side)

## Important Implementation Details

### OAuth Token Management
The system supports dual OAuth versions per agent. X/Twitter requires OAuth 1.0a for media uploads but uses OAuth 2.0 for posting. Store tokens in Agent doctype password fields.

### Content Mechanism System
Content generation uses a sophisticated rule engine where mechanisms define:
- Text generation parameters (length, style)
- Image generation settings (size, style, variations)  
- Feed source combinations
- Prompt templates

### Activity Dependencies
Network Activities can reference other activities for threading (replies, quotes). The system prevents duplicate activities and manages scheduling conflicts through complex datetime logic.

### Media Pipeline
Images are automatically converted to PNG format and stored in Frappe's file system under `Home/SMM/` folder with randomized filenames for security.