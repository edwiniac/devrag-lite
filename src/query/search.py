"""
Semantic Search and Query System for DevRAG
Handles vector search, context retrieval, and result ranking
"""
import os
import sys
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add the root directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from pinecone import Pinecone
from config import Config


@dataclass
class SearchResult:
    """Represents a single search result"""
    content: str
    score: float
    metadata: Dict[str, Any]
    chunk_id: str

    def __str__(self):
        repo = self.metadata.get('repo_full_name', 'Unknown')
        filename = self.metadata.get('filename', 'Unknown')
        return f"[{self.score:.3f}] {repo}/{filename}"


class SemanticSearch:
    """Semantic search engine using Pinecone vector database"""

    def __init__(self):
        """Initialize search with Pinecone and OpenAI"""
        self.pinecone_client = Pinecone(api_key=Config.PINECONE_API_KEY)
        self.index = self.pinecone_client.Index(Config.PINECONE_INDEX_NAME)
        print("✅ Search engine initialized")

    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding vector for search query"""
        try:
            # Use direct HTTP request to avoid proxy issues
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": Config.EMBEDDING_MODEL,
                    "input": query
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                embedding = data['data'][0]['embedding']
                return embedding
            else:
                raise Exception(f"OpenAI API error: {response.status_code}")

        except Exception as e:
            print(f"❌ Error generating query embedding: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[SearchResult]:
        """
        Perform semantic search on the vector database

        Args:
            query: Natural language search query
            top_k: Number of results to return
            filter_dict: Optional metadata filters (e.g., {'repo_name': 'fastapi'})
            include_metadata: Whether to include full metadata

        Returns:
            List of SearchResult objects sorted by relevance
        """
        try:
            # Generate query embedding
            print(f"🔍 Searching for: '{query}'")
            query_embedding = self.generate_query_embedding(query)

            # Perform vector search
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                filter=filter_dict,
                include_metadata=include_metadata
            )

            # Parse results
            search_results = []
            for match in results.get('matches', []):
                result = SearchResult(
                    content=match['metadata'].get('text', ''),
                    score=match['score'],
                    metadata=match.get('metadata', {}),
                    chunk_id=match['id']
                )
                search_results.append(result)

            print(f"✅ Found {len(search_results)} results")
            return search_results

        except Exception as e:
            print(f"❌ Search error: {e}")
            return []

    def search_by_repository(
        self,
        query: str,
        repo_name: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """Search within a specific repository"""
        filter_dict = {"repo_name": repo_name}
        return self.search(query, top_k=top_k, filter_dict=filter_dict)

    def search_by_language(
        self,
        query: str,
        language: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """Search for code in a specific programming language"""
        filter_dict = {"analysis_language": language}
        return self.search(query, top_k=top_k, filter_dict=filter_dict)

    def search_by_file_type(
        self,
        query: str,
        file_extension: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """Search within specific file types"""
        if not file_extension.startswith('.'):
            file_extension = f'.{file_extension}'
        filter_dict = {"file_extension": file_extension}
        return self.search(query, top_k=top_k, filter_dict=filter_dict)

    def get_index_stats(self) -> Dict[str, Any]:
        """Get current index statistics"""
        try:
            stats = self.index.describe_index_stats()
            return {
                'total_vectors': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', 0),
                'index_fullness': stats.get('index_fullness', 0)
            }
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {}


class ContextAssembler:
    """Assembles context from search results for RAG"""

    def __init__(self, max_context_length: int = 4000):
        """
        Initialize context assembler

        Args:
            max_context_length: Maximum characters in assembled context
        """
        self.max_context_length = max_context_length

    def assemble_context(
        self,
        results: List[SearchResult],
        include_metadata: bool = True,
        deduplicate: bool = True
    ) -> str:
        """
        Assemble search results into a coherent context string

        Args:
            results: List of search results
            include_metadata: Include file/repo information
            deduplicate: Remove duplicate content

        Returns:
            Assembled context string
        """
        if not results:
            return ""

        context_parts = []
        total_length = 0
        seen_content = set() if deduplicate else None

        for i, result in enumerate(results, 1):
            # Skip duplicates
            if deduplicate and result.content in seen_content:
                continue

            # Build context entry
            if include_metadata:
                repo = result.metadata.get('repo_full_name', 'Unknown')
                filename = result.metadata.get('filename', 'Unknown')
                file_path = result.metadata.get('file_path', '')

                header = f"\n{'='*60}\n"
                header += f"SOURCE {i}: {repo}/{filename}\n"
                header += f"Relevance: {result.score:.3f}\n"

                # Add code analysis info if available
                if result.metadata.get('analysis_language'):
                    header += f"Language: {result.metadata['analysis_language']}\n"
                if result.metadata.get('analysis_functions'):
                    funcs = ', '.join(result.metadata['analysis_functions'][:3])
                    header += f"Functions: {funcs}\n"
                if result.metadata.get('analysis_classes'):
                    classes = ', '.join(result.metadata['analysis_classes'][:3])
                    header += f"Classes: {classes}\n"

                header += f"{'='*60}\n"

                context_entry = f"{header}{result.content}\n"
            else:
                context_entry = f"\n{result.content}\n"

            # Check length constraints
            if total_length + len(context_entry) > self.max_context_length:
                break

            context_parts.append(context_entry)
            total_length += len(context_entry)

            if deduplicate:
                seen_content.add(result.content)

        return "\n".join(context_parts)

    def rank_results_by_diversity(
        self,
        results: List[SearchResult],
        diversity_weight: float = 0.3
    ) -> List[SearchResult]:
        """
        Re-rank results to balance relevance and diversity

        Args:
            results: Original search results
            diversity_weight: Weight for diversity (0-1), higher = more diverse

        Returns:
            Re-ranked results
        """
        if len(results) <= 1:
            return results

        ranked = [results[0]]  # Start with top result
        remaining = results[1:]

        while remaining:
            best_score = -1
            best_idx = 0

            for idx, candidate in enumerate(remaining):
                # Calculate diversity score (different repos/files)
                diversity_score = 0
                for selected in ranked:
                    if candidate.metadata.get('repo_name') != selected.metadata.get('repo_name'):
                        diversity_score += 0.5
                    if candidate.metadata.get('filename') != selected.metadata.get('filename'):
                        diversity_score += 0.5

                # Combine relevance and diversity
                combined_score = (
                    (1 - diversity_weight) * candidate.score +
                    diversity_weight * diversity_score
                )

                if combined_score > best_score:
                    best_score = combined_score
                    best_idx = idx

            ranked.append(remaining.pop(best_idx))

        return ranked


def main():
    """Interactive search test interface"""
    print("🔍 DevRAG Semantic Search")
    print("="*50)

    search = SemanticSearch()

    # Show stats
    stats = search.get_index_stats()
    print(f"\n📊 Index Statistics:")
    print(f"   Total vectors: {stats.get('total_vectors', 0)}")
    print(f"   Dimension: {stats.get('dimension', 0)}")

    if stats.get('total_vectors', 0) == 0:
        print("\n⚠️  Index is empty. Run bulk_ingest.py first!")
        return

    # Interactive search
    print("\n💡 Try queries like:")
    print("   - 'How to create a FastAPI endpoint'")
    print("   - 'React component lifecycle'")
    print("   - 'Python async/await examples'")
    print("\nType 'quit' to exit\n")

    assembler = ContextAssembler(max_context_length=2000)

    while True:
        try:
            query = input("\n🔍 Enter search query: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                break

            if not query:
                continue

            # Perform search
            results = search.search(query, top_k=5)

            if not results:
                print("❌ No results found")
                continue

            # Display results
            print(f"\n{'='*60}")
            print(f"SEARCH RESULTS ({len(results)} found)")
            print('='*60)

            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result}")
                print(f"   Content preview: {result.content[:150]}...")

            # Assemble context
            print(f"\n{'='*60}")
            print("ASSEMBLED CONTEXT FOR RAG")
            print('='*60)
            context = assembler.assemble_context(results[:3], include_metadata=True)
            print(context[:1000] + "..." if len(context) > 1000 else context)

        except KeyboardInterrupt:
            print("\n👋 Search interrupted")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n👋 Search interface closed")


if __name__ == "__main__":
    main()
