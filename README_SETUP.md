# Social Media Agent - Setup Guide

This guide will help you set up and run the social media agent on your system.

## Prerequisites

- Python 3.9 or higher
- Twitter/X Developer Account with API access
- Google API key (for Gemini models) or OpenAI API key (for GPT models)

## Quick Setup

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

3. **Run setup validation:**
   ```bash
   python setup.py
   ```

4. **Test the agent:**
   ```bash
   python run_agent.py --validate
   ```

## Configuration

### Required Environment Variables

- `TWITTER_BEARER_TOKEN`: Your Twitter API bearer token
- `TWITTER_USER_ID`: Your Twitter user ID
- `GOOGLE_API_KEY`: Your Google API key (for Gemini models)
- `OPENAI_API_KEY`: Your OpenAI API key (for GPT models)

### Optional Configuration

- `MODEL_NAME`: Model to use (default: gemini-2.0-flash-exp)
- `SEARCH_TERMS`: Comma-separated search terms
- `MAX_TWEETS_PER_RUN`: Maximum tweets to process per run
- `MAX_LIKES_PER_DAY`: Daily like limit
- `MAX_REPLIES_PER_DAY`: Daily reply limit
- `SCHEDULE_HOURS`: Cron expression for scheduling (default: */3)

## Usage

### Run Once
```bash
python run_agent.py
```

### Run on Schedule
```bash
python run_agent.py --schedule
```

### Validate Setup
```bash
python run_agent.py --validate
```

## Getting Twitter API Credentials

1. Go to [Twitter Developer Portal](https://developer.x.com/)
2. Create a new app
3. Generate a bearer token
4. Get your user ID using the `/2/users/me` endpoint

## Getting Model API Keys

### Google Gemini
1. Go to [Google AI Studio](https://makersuite.google.com/)
2. Create an API key
3. Set `GOOGLE_API_KEY` in your .env file

### OpenAI
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an API key
3. Set `OPENAI_API_KEY` in your .env file

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure all dependencies are installed with `uv sync`
2. **API errors**: Check your API keys and rate limits
3. **Database errors**: Ensure the database path is writable
4. **Scheduling errors**: Check that APScheduler is installed

### Logs

Logs are written to:
- Console output
- `logs/agent.log` file

### Support

For issues and questions:
1. Check the logs for error messages
2. Validate your configuration with `--validate`
3. Review the README.md for detailed documentation
