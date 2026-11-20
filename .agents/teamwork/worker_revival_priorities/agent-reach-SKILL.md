---
name: agent-reach
description: "Multi-platform live data reach and intelligence extraction (X/Twitter, Reddit, YouTube, GitHub, RSS) without official API fees or keys using Agent-Reach CLI."
---

# Agent-Reach: Zero-API Multi-Platform Intelligence

Gives agents live web access across platforms without API fees using lightweight scrapers, cookies, and search pathways.

## Installation & Setup
```bash
git clone https://github.com/Panniantong/Agent-Reach.git
cd Agent-Reach
pip install -r requirements.txt
python -m agent_reach doctor
```

## Supported Platforms
- **Twitter / X**: Thread reading, user tweets, keyword search.
- **Reddit**: Subreddit monitoring, post comments, sentiment extraction.
- **YouTube**: Video transcripts, video metadata, comment threads.
- **GitHub**: Repositories, issues, releases, diffs.
- **Web Reader (Jina)**: Deep article extraction.
- **RSS**: Feed parsing and live headline tracking.

## Usage Commands
```bash
python -m agent_reach run twitter search --query "<keyword>"
python -m agent_reach run reddit get-post --url "<post-url>"
python -m agent_reach run youtube transcript --video-id "<id>"
python -m agent_reach doctor
```
