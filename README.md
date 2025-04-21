# JustFF Discord Bot

JustFF is a Discord bot that monitors voice and text chat for signs of player tilt. It uses speech recognition and sentiment analysis to track and display tilt levels for each user.

## Features

- Analyzes both voice and text chat using AI sentiment analysis and keyword detection
- Tracks and displays tilt scores and recent triggers
- Encourages positive communication for tilt decay (lets go!!)

## Commands

- `!join` — Bot joins your voice channel and starts monitoring
- `!leave` — Bot leaves the voice channel
- `!tilt [@user]` — Show tilt level for yourself or a mentioned user
- `!tilts` — Show tilt levels for all tracked users
- `!reset [@user]` — Reset tilt score for a user or everyone
- `!sensitivity [low|medium|high]` — Adjust tilt detection sensitivity
- `!analyze <text>` — Analyze a phrase for tilt (for testing)

## Requirements

- Python 3.10+
- FFmpeg installed and in your PATH
- See `requirements.txt` for Python dependencies

## Setup

1. Clone the repository.
2. Install dependencies
3. Create a `.env` file with your Discord bot token
4. Run the bot

## Notes

- The bot uses Whisper for speech-to-text and a local sentiment model for tilt detection.
- For best results, run on a machine with at least 2GB RAM.
- You can extend or customize tilt/positive keywords in `config.py`.

---