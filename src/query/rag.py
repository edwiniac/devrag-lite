"""
RAG (Retrieval-Augmented Generation) System for DevRAG
Combines semantic search with LLM completion for developer queries
"""
import os
import sys
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add the root directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.query.search import SemanticSearch, ContextAssembler, SearchResult
from config import Config


@dataclass
class RAGResponse:
    """Response from RAG system"""
    answer: str
    sources: List[SearchResult]
    context_used: str
    query: str
    tokens_used: Optional[int] = None


class RAGEngine:
    """Complete RAG engine combining search and generation"""

    def __init__(
        self,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_k_results: int = 5
    ):
        """
        Initialize RAG engine

        Args:
            model: OpenAI model to use (default: gpt-3.5-turbo)
            temperature: Response creativity (0-1)
            max_tokens: Maximum response length
            top_k_results: Number of search results to use
        """
        self.model = model or Config.OPENAI_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_k_results = top_k_results

        self.search_engine = SemanticSearch()
        self.context_assembler = ContextAssembler(max_context_length=3000)

        print(f"✅ RAG Engine initialized (model: {self.model})")

    def generate_completion(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate LLM completion with context

        Args:
            query: User question
            context: Retrieved context from vector search
            system_prompt: Optional custom system prompt

        Returns:
            Dict with 'answer' and metadata
        """
        if system_prompt is None:
            system_prompt = """You are DevRAG, an expert developer assistant with access to a knowledge base of code repositories, documentation, and technical content.

Your role:
- Answer developer questions using the provided context
- Cite specific files and repositories when referencing code
- Provide code examples when relevant
- Explain technical concepts clearly
- If the context doesn't contain the answer, say so honestly

Format your responses with:
- Clear explanations
- Code snippets in markdown (```language```)
- References to source files
- Step-by-step instructions when appropriate"""

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""Context from knowledge base:

{context}

---

User Question: {query}

Please answer the question using the context provided above. If you reference specific code or information, cite the source file."""}
        ]

        try:
            # Use direct HTTP request to avoid proxy issues
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'answer': data['choices'][0]['message']['content'],
                    'tokens_used': data['usage']['total_tokens'],
                    'model': data['model']
                }
            else:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"❌ Error generating completion: {e}")
            raise

    def query(
        self,
        question: str,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_context: bool = False
    ) -> RAGResponse:
        """
        Perform complete RAG query: search + retrieve + generate

        Args:
            question: User's natural language question
            filter_dict: Optional metadata filters
            include_context: Include raw context in response

        Returns:
            RAGResponse with answer and sources
        """
        print(f"\n🔍 Processing RAG query: '{question}'")

        # 1. Semantic search
        print("   📚 Searching knowledge base...")
        search_results = self.search_engine.search(
            query=question,
            top_k=self.top_k_results,
            filter_dict=filter_dict
        )

        if not search_results:
            return RAGResponse(
                answer="I couldn't find any relevant information in the knowledge base to answer your question.",
                sources=[],
                context_used="",
                query=question
            )

        print(f"   ✅ Found {len(search_results)} relevant sources")

        # 2. Assemble context
        print("   📝 Assembling context...")
        context = self.context_assembler.assemble_context(
            search_results,
            include_metadata=True,
            deduplicate=True
        )

        # 3. Generate answer
        print("   🤖 Generating answer...")
        completion = self.generate_completion(question, context)

        print(f"   ✅ Answer generated ({completion.get('tokens_used', 0)} tokens)")

        return RAGResponse(
            answer=completion['answer'],
            sources=search_results,
            context_used=context if include_context else "",
            query=question,
            tokens_used=completion.get('tokens_used')
        )

    def query_with_conversation(
        self,
        question: str,
        conversation_history: List[Dict[str, str]],
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> RAGResponse:
        """
        RAG query with conversation context

        Args:
            question: Current question
            conversation_history: Previous Q&A pairs
            filter_dict: Optional filters

        Returns:
            RAGResponse
        """
        # Combine current question with conversation context
        full_query = question
        if conversation_history:
            context_summary = "\n".join([
                f"Previous Q: {item['question']}\nPrevious A: {item['answer'][:200]}..."
                for item in conversation_history[-2:]  # Last 2 exchanges
            ])
            full_query = f"Conversation context:\n{context_summary}\n\nCurrent question: {question}"

        return self.query(full_query, filter_dict=filter_dict)

    def query_code_specific(
        self,
        question: str,
        language: Optional[str] = None,
        repository: Optional[str] = None
    ) -> RAGResponse:
        """
        Query specific to code/language/repository

        Args:
            question: User question
            language: Programming language filter
            repository: Repository name filter

        Returns:
            RAGResponse
        """
        filter_dict = {}

        if language:
            filter_dict['analysis_language'] = language
            print(f"   🔧 Filtering by language: {language}")

        if repository:
            filter_dict['repo_name'] = repository
            print(f"   📦 Filtering by repository: {repository}")

        return self.query(question, filter_dict=filter_dict)

    def interactive_session(self):
        """Start an interactive RAG session"""
        print("\n" + "="*60)
        print("🤖 DevRAG Interactive Assistant")
        print("="*60)
        print("\nAsk me anything about the indexed repositories!")
        print("Commands:")
        print("  - Type your question to get an answer")
        print("  - 'context' - Show sources for last query")
        print("  - 'stats' - Show system statistics")
        print("  - 'quit' - Exit")
        print("="*60)

        conversation_history = []
        last_response = None

        while True:
            try:
                user_input = input("\n💬 You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!")
                    break

                if user_input.lower() == 'context':
                    if last_response and last_response.sources:
                        print("\n📚 Sources from last query:")
                        for i, source in enumerate(last_response.sources, 1):
                            print(f"\n{i}. {source}")
                            print(f"   Preview: {source.content[:150]}...")
                    else:
                        print("No previous query.")
                    continue

                if user_input.lower() == 'stats':
                    stats = self.search_engine.get_index_stats()
                    print("\n📊 System Statistics:")
                    print(f"   Indexed vectors: {stats.get('total_vectors', 0)}")
                    print(f"   Dimension: {stats.get('dimension', 0)}")
                    continue

                # Process RAG query
                response = self.query(user_input)
                last_response = response

                # Display answer
                print(f"\n🤖 DevRAG: {response.answer}")

                # Show sources summary
                if response.sources:
                    print(f"\n📚 Sources ({len(response.sources)}):")
                    for i, source in enumerate(response.sources[:3], 1):
                        repo = source.metadata.get('repo_full_name', 'Unknown')
                        filename = source.metadata.get('filename', 'Unknown')
                        print(f"   {i}. {repo}/{filename} (relevance: {source.score:.3f})")

                if response.tokens_used:
                    print(f"\n💡 Tokens used: {response.tokens_used}")

                # Save to conversation history
                conversation_history.append({
                    'question': user_input,
                    'answer': response.answer
                })

            except KeyboardInterrupt:
                print("\n\n👋 Session interrupted")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                continue

        print("\nSession ended.")


def main():
    """Test RAG engine"""
    print("🚀 DevRAG Engine - Testing Mode")
    print("="*60)

    # Check if index has data
    search = SemanticSearch()
    stats = search.get_index_stats()

    if stats.get('total_vectors', 0) == 0:
        print("\n⚠️  Index is empty! Run bulk_ingest.py first.")
        return 1

    print(f"\n✅ Index ready with {stats['total_vectors']} vectors")

    # Initialize RAG engine
    rag = RAGEngine(
        temperature=0.7,
        max_tokens=1000,
        top_k_results=5
    )

    # Test queries
    test_queries = [
        "How do I create a FastAPI endpoint?",
        "Explain React hooks",
        "How to use async/await in Python?"
    ]

    print("\n📝 Running test queries...\n")

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Q: {query}")
        print('='*60)

        try:
            response = rag.query(query)
            print(f"\nA: {response.answer[:500]}...")
            print(f"\nSources: {len(response.sources)}")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Start interactive session
    print("\n" + "="*60)
    user_choice = input("\nStart interactive session? (y/n): ").strip().lower()

    if user_choice == 'y':
        rag.interactive_session()

    return 0


if __name__ == "__main__":
    sys.exit(main())
