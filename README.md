# DevRAG-Lite - Developer-Focused RAG System

Production-ready RAG (Retrieval-Augmented Generation) system for querying developer documentation, code repositories, and technical content. Built entirely on free-tier cloud services.

## Features

- **Semantic Search**: Vector-based code and documentation search using Pinecone
- **LLM Integration**: GPT-3.5-turbo for intelligent answer generation
- **Code Analysis**: Automatic extraction of functions, classes, and imports from Python/JS
- **Multi-Format Support**: Process 20+ file types (.py, .js, .md, .yaml, .json, etc.)
- **CLI Interface**: Unified command-line tool with 6 commands
- **GitHub Integration**: Direct repository scraping with rate limiting
- **Free Tier**: Runs on OpenAI, Pinecone, and AWS S3 free tiers

## Current Status

- ✅ 800 vectors indexed (FastAPI, React, Python repositories)
- ✅ Full end-to-end RAG pipeline operational
- ✅ CLI interface with query, chat, search, stats commands
- ✅ Code analysis for Python and JavaScript files

## Quick Start

### Prerequisites

1. Set environment variables:
```bash
export OPENAI_API_KEY="your-openai-key"
export PINECONE_API_KEY="your-pinecone-key"
export AWS_ACCESS_KEY_ID="your-aws-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Usage

#### Check System Status
```bash
python devrag_cli.py stats
```

#### Ask Questions (RAG)
```bash
# One-shot query
python devrag_cli.py query "How do I create a FastAPI endpoint?"

# Interactive chat session
python devrag_cli.py chat
```

#### Search Only (No LLM)
```bash
python devrag_cli.py search "React hooks" --top-k 5
```

#### Ingest Documents
```bash
# Bulk ingest all scraped repositories
python devrag_cli.py ingest --bulk

# Interactive single file ingestion
python devrag_cli.py ingest
```

## CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `query` | Ask a question (one-shot) | `devrag_cli.py query "What is FastAPI?"` |
| `chat` | Start interactive session | `devrag_cli.py chat` |
| `search` | Vector search only (no LLM) | `devrag_cli.py search "async await"` |
| `stats` | Show system statistics | `devrag_cli.py stats` |
| `ingest` | Ingest documents | `devrag_cli.py ingest --bulk` |
| `scrape` | Scrape GitHub repository | `devrag_cli.py scrape owner/repo` |

## Architecture

```
DevRAG-Lite Pipeline:
┌─────────────────┐
│ GitHub Scraper  │  Fetch repos with API metadata
└────────┬────────┘
         │
┌────────▼────────┐
│ Code Analyzer   │  Extract functions, classes, imports
└────────┬────────┘
         │
┌────────▼────────┐
│ Text Chunker    │  Smart chunking with boundaries
└────────┬────────┘
         │
┌────────▼────────┐
│ OpenAI Embeddings│ Generate vectors (1536-dim)
└────────┬────────┘
         │
┌────────▼────────┐
│ Pinecone Index  │  Store vectors with metadata
└─────────────────┘

Query Flow:
User Question → Embedding → Vector Search → Context Assembly → GPT-3.5 → Answer
```

## Technology Stack

- **Vector Database**: Pinecone (serverless, free tier)
- **Embeddings**: OpenAI text-embedding-3-small (1536-dim)
- **LLM**: OpenAI GPT-3.5-turbo
- **Storage**: AWS S3 (optional)
- **Code Analysis**: Python AST, Regex patterns
- **Language**: Python 3.x

## Project Structure

```
devrag-lite/
├── devrag_cli.py              # Unified CLI interface
├── bulk_ingest.py             # Bulk repository ingestion
├── config.py                  # Configuration management
├── verify_setup.py            # System health checks
├── create_index_final.py      # Pinecone index creation
├── src/
│   ├── ingestion/
│   │   ├── ingest.py         # Document ingestion pipeline
│   │   ├── github_scraper.py # GitHub API integration
│   │   └── config.py         # Ingestion config
│   ├── processing/
│   │   └── code_analyzer.py  # Code structure extraction
│   └── query/
│       ├── search.py         # Semantic search engine
│       └── rag.py            # RAG engine (search + LLM)
├── infrastructure/
│   └── aws/                  # CloudFormation templates
└── scraped_repos/            # Downloaded repository files
```

## Example Queries

The system can answer questions like:

- "How do I create a FastAPI endpoint?"
- "Show me React hook examples"
- "What's the Python async/await syntax?"
- "How to handle authentication in FastAPI?"
- "Find error handling patterns"

## Development

### Verify Setup
```bash
python verify_setup.py
```

### Create Pinecone Index
```bash
python create_index_final.py
```

### Scrape Repositories
```bash
python src/ingestion/github_scraper.py
```

### Run Bulk Ingestion
```bash
python bulk_ingest.py
```

## Configuration

Key settings in `config.py`:

- `OPENAI_MODEL`: GPT-3.5-turbo
- `EMBEDDING_MODEL`: text-embedding-3-small
- `PINECONE_INDEX_NAME`: devrag-index
- `MAX_CHUNK_SIZE`: 1000 characters
- `CHUNK_OVERLAP`: 200 characters

## Limitations

- Free tier limits: Pinecone (100K vectors), OpenAI (rate limits)
- GitHub API rate limits: 60 requests/hour (unauthenticated)
- Code analysis: Python and JavaScript only
- LLM context window: 4096 tokens

## Future Enhancements

- [ ] Web UI interface
- [ ] VS Code extension
- [ ] Slack bot integration
- [ ] Support for more languages (Go, Rust, Java)
- [ ] Conversation history tracking
- [ ] Custom embedding models
- [ ] Multi-repository search filters

## Documentation

See [PROGRESS.md](PROGRESS.md) for detailed project history and implementation notes.

## License

MIT

## Contributing

This is a demonstration project. Feel free to fork and adapt for your needs.

---

**Built with free-tier services**: OpenAI + Pinecone + AWS S3 + Python
