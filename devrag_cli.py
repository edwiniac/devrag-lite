#!/usr/bin/env python3
"""
DevRAG CLI - Unified Command Line Interface
Main entry point for all DevRAG operations
"""
import sys
import os
import argparse
from pathlib import Path

# Add the root directory to the path
sys.path.append(os.path.dirname(__file__))

from src.query.rag import RAGEngine
from src.query.search import SemanticSearch
from config import Config


def check_setup():
    """Verify system is ready"""
    if not Config.validate():
        print("❌ Configuration incomplete!")
        print("   Missing: OPENAI_API_KEY or PINECONE_API_KEY")
        print("   Set these in your environment variables")
        return False

    # Check if index has data
    try:
        search = SemanticSearch()
        stats = search.get_index_stats()

        if stats.get('total_vectors', 0) == 0:
            print("⚠️  Index is empty!")
            print("   Run: python bulk_ingest.py")
            return False

        print(f"✅ System ready ({stats['total_vectors']} vectors indexed)")
        return True

    except Exception as e:
        print(f"❌ System check failed: {e}")
        return False


def cmd_query(args):
    """Handle query command"""
    if not check_setup():
        return 1

    rag = RAGEngine(
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        top_k_results=args.top_k
    )

    try:
        response = rag.query(
            args.question,
            include_context=args.show_context
        )

        print("\n" + "="*60)
        print("ANSWER")
        print("="*60)
        print(response.answer)

        if response.sources:
            print("\n" + "="*60)
            print(f"SOURCES ({len(response.sources)})")
            print("="*60)
            for i, source in enumerate(response.sources, 1):
                repo = source.metadata.get('repo_full_name', 'Unknown')
                filename = source.metadata.get('filename', 'Unknown')
                print(f"\n{i}. {repo}/{filename}")
                print(f"   Relevance: {source.score:.3f}")
                print(f"   Preview: {source.content[:150]}...")

        if args.show_context and response.context_used:
            print("\n" + "="*60)
            print("RAW CONTEXT")
            print("="*60)
            print(response.context_used)

        if response.tokens_used:
            print(f"\n💡 Tokens used: {response.tokens_used}")

        return 0

    except Exception as e:
        print(f"❌ Query failed: {e}")
        return 1


def cmd_interactive(args):
    """Start interactive session"""
    if not check_setup():
        return 1

    rag = RAGEngine(
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        top_k_results=args.top_k
    )

    rag.interactive_session()
    return 0


def cmd_search(args):
    """Perform vector search only (no LLM)"""
    if not check_setup():
        return 1

    search = SemanticSearch()

    try:
        results = search.search(
            args.query,
            top_k=args.top_k
        )

        if not results:
            print("❌ No results found")
            return 1

        print(f"\n{'='*60}")
        print(f"SEARCH RESULTS ({len(results)} found)")
        print('='*60)

        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result}")
            repo = result.metadata.get('repo_full_name', 'Unknown')
            filename = result.metadata.get('filename', 'Unknown')
            print(f"   File: {repo}/{filename}")
            print(f"   Preview: {result.content[:200]}...")

            if args.verbose:
                print(f"   Full content:\n{result.content}\n")

        return 0

    except Exception as e:
        print(f"❌ Search failed: {e}")
        return 1


def cmd_stats(args):
    """Show system statistics"""
    print("📊 DevRAG System Statistics")
    print("="*60)

    try:
        # Configuration
        print("\n🔧 Configuration:")
        print(f"   OpenAI Model: {Config.OPENAI_MODEL}")
        print(f"   Embedding Model: {Config.EMBEDDING_MODEL}")
        print(f"   Pinecone Index: {Config.PINECONE_INDEX_NAME}")
        print(f"   S3 Bucket: {Config.S3_BUCKET}")

        # Index stats
        search = SemanticSearch()
        stats = search.get_index_stats()

        print("\n📈 Vector Database:")
        print(f"   Total vectors: {stats.get('total_vectors', 0)}")
        print(f"   Dimension: {stats.get('dimension', 0)}")
        print(f"   Index fullness: {stats.get('index_fullness', 0):.2%}")

        # Scraped data
        scraped_path = Path("scraped_repos")
        if scraped_path.exists():
            repos = [d for d in scraped_path.iterdir() if d.is_dir()]
            total_files = sum(len([f for f in repo.iterdir() if f.is_file() and not f.name.endswith('.meta.json')])
                            for repo in repos)

            print("\n📁 Scraped Repositories:")
            print(f"   Repositories: {len(repos)}")
            print(f"   Total files: {total_files}")

            for repo in repos:
                files = [f for f in repo.iterdir() if f.is_file() and not f.name.endswith('.meta.json')]
                print(f"      - {repo.name}: {len(files)} files")

        return 0

    except Exception as e:
        print(f"❌ Failed to get stats: {e}")
        return 1


def cmd_ingest(args):
    """Run ingestion"""
    print("🚀 Starting ingestion...")

    if args.bulk:
        # Bulk ingest all scraped repos
        os.system("python bulk_ingest.py")
    else:
        # Interactive single file ingestion
        os.system("python src/ingestion/ingest.py")

    return 0


def cmd_scrape(args):
    """Scrape GitHub repository"""
    print(f"🐙 Scraping repository: {args.repo}")

    # Run scraper
    os.system(f"python src/ingestion/github_scraper.py")

    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="DevRAG - Developer-focused RAG System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive session (recommended)
  python devrag_cli.py chat

  # Quick query
  python devrag_cli.py query "How do I create a FastAPI endpoint?"

  # Search without LLM
  python devrag_cli.py search "React hooks"

  # Show statistics
  python devrag_cli.py stats

  # Ingest data
  python devrag_cli.py ingest --bulk

For more information: https://github.com/yourusername/devrag-lite
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Query command
    query_parser = subparsers.add_parser('query', help='Ask a question (one-shot)')
    query_parser.add_argument('question', help='Your question')
    query_parser.add_argument('--temperature', type=float, default=0.7,
                             help='Response creativity (0-1)')
    query_parser.add_argument('--max-tokens', type=int, default=1000,
                             help='Maximum response length')
    query_parser.add_argument('--top-k', type=int, default=5,
                             help='Number of sources to retrieve')
    query_parser.add_argument('--show-context', action='store_true',
                             help='Show raw context used')
    query_parser.set_defaults(func=cmd_query)

    # Interactive chat
    chat_parser = subparsers.add_parser('chat', help='Start interactive session')
    chat_parser.add_argument('--temperature', type=float, default=0.7)
    chat_parser.add_argument('--max-tokens', type=int, default=1000)
    chat_parser.add_argument('--top-k', type=int, default=5)
    chat_parser.set_defaults(func=cmd_interactive)

    # Search command
    search_parser = subparsers.add_parser('search', help='Vector search only (no LLM)')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--top-k', type=int, default=5)
    search_parser.add_argument('--verbose', action='store_true',
                              help='Show full content')
    search_parser.set_defaults(func=cmd_search)

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show system statistics')
    stats_parser.set_defaults(func=cmd_stats)

    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest documents')
    ingest_parser.add_argument('--bulk', action='store_true',
                              help='Bulk ingest all scraped repos')
    ingest_parser.set_defaults(func=cmd_ingest)

    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Scrape GitHub repo')
    scrape_parser.add_argument('repo', help='Repository (owner/name)')
    scrape_parser.set_defaults(func=cmd_scrape)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print("\n💡 Tip: Start with 'python devrag_cli.py chat' for interactive mode")
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
