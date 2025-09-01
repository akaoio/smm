# SMM - Social Media Marketing and Management System

A comprehensive Python-based social media automation platform built on the Frappe framework. SMM enables automated content creation, scheduling, and multi-platform posting with AI-powered content generation.

## Features

### 🤖 AI-Powered Content Generation
- **OpenAI Integration**: GPT-4 for intelligent text generation
- **DALL-E 3**: Image creation and variations
- **Smart Content Mechanisms**: Rule-based content generation with customizable prompts
- **Multi-Source Aggregation**: Combine RSS feeds, prompts, and linked content

### 📱 Multi-Platform Support
- **X (Twitter)**: Full OAuth 1.0a/2.0 support, media uploads, threading
- **Telegram Bot**: Message and media group posting
- **Facebook**: Basic integration
- **Extensible**: Plugin architecture for additional platforms

### 📅 Advanced Scheduling
- **Activity Plans**: Convert high-level strategies into scheduled activities
- **Smart Scheduling**: Conflict resolution and dependency management
- **Time-Based Execution**: Automated content generation and posting
- **Agent Management**: Multiple account support per platform

### 📡 Feed Management
- **RSS Integration**: Automated feed parsing and content extraction
- **Virtual Feeds**: JSON-based content sources
- **Multi-URL Support**: Multiple sources per feed provider
- **Configurable Intervals**: Customizable fetch frequencies

## Installation

### Prerequisites
- Python 3.7+
- Frappe Framework
- Bench (Frappe development tool)

### Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd smm
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the app:
   ```bash
   bench get-app smm /path/to/smm
   bench --site [your-site] install-app smm
   ```

4. Run migrations:
   ```bash
   bench --site [your-site] migrate
   ```

## Configuration

### API Setup
Configure API credentials for each platform:

1. **OpenAI**: Add API token for content generation
2. **X/Twitter**: Set up both OAuth 1.0a (media) and 2.0 (posting) credentials
3. **Telegram**: Configure bot token
4. **Facebook**: Add app credentials

### Agent Configuration
1. Create Agent records for each social media account
2. Complete OAuth authorization flow
3. Configure agent groups for bulk operations

### Content Mechanisms
Define content generation rules:
- Text generation parameters (length, style)
- Image generation settings (size, style)
- Feed source combinations
- Custom prompt templates

## Usage

### Basic Workflow

1. **Setup Feed Providers**: Configure RSS feeds or virtual content sources
2. **Create Content Mechanisms**: Define AI generation rules
3. **Configure Agents**: Set up social media accounts with OAuth
4. **Create Activity Plans**: Schedule content generation and posting
5. **Monitor Activities**: Track execution and performance

### Manual Operations

#### Test Content Generation
```bash
bench --site [site] execute smm.libs.openai.generate_content --kwargs '{"name":"[mechanism_id]"}'
```

#### Test Social Media Posting
```bash
bench --site [site] execute smm.libs.activity.cast --kwargs '{"name":"[activity_id]"}'
```

#### Fetch Feeds
```bash
bench --site [site] execute smm.libs.feed.fetch --kwargs '{"name":"[provider_id]"}'
```

#### Refresh OAuth Tokens
```bash
bench --site [site] execute smm.libs.x.refresh_access_token --kwargs '{"name":"[agent_name]"}'
```

## Architecture

### Data Flow
```
Feed Providers → Feeds → Content Mechanisms → Content → Network Activities → Social Platforms
```

### Core Components

- **Activity Plans**: High-level scheduling strategies
- **Network Activities**: Individual scheduled posts with content
- **Content Mechanisms**: AI generation rule engines
- **Agents**: Social media account abstractions
- **Feed Providers**: Content source configurations

### Scheduled Tasks
The system runs automated tasks:
- Token refresh for all agents
- Feed fetching based on intervals
- Activity plan processing
- Content generation
- Activity casting (posting)

## API Integration

### OpenAI
- GPT-4 Turbo for text generation
- DALL-E 3 for image creation
- Function calling for structured output
- Automatic image format conversion

### X/Twitter
- Dual OAuth support (1.0a for media, 2.0 for posting)
- Chunked media upload for large files
- Thread management and reply handling
- Profile synchronization

### Telegram Bot
- Message posting with formatting
- Media group support for multiple images
- Bot token authentication

## Security

- OAuth token encryption via Frappe password fields
- State verification for authorization flows
- Secure file handling with randomized names
- API credential isolation per environment

## Development

### File Structure
- `smm/libs/`: Core business logic modules
- `smm/tasks/`: Background scheduled tasks  
- `smm/smm/doctype/`: Frappe doctype definitions
- `smm/templates/`: UI templates

### Testing
Use the debug commands in `DEBUG.txt` for manual testing of specific components.

## License

MIT License - see LICENSE file for details.

## Contributing

This project follows Frappe development conventions. Please ensure all changes are compatible with the Frappe framework and maintain backward compatibility.