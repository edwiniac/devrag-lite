#!/usr/bin/env python3
"""
Bulk ingestion script to index all scraped repositories
Processes all files in scraped_repos/ directory with enhanced metadata
"""
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Add the root directory to the path
sys.path.append(os.path.dirname(__file__))

from src.ingestion.ingest import DocumentIngestion
from src.processing.code_analyzer import CodeAnalyzer


class BulkIngestion:
    def __init__(self):
        """Initialize bulk ingestion with document processor and code analyzer"""
        self.doc_ingestion = DocumentIngestion()
        self.code_analyzer = CodeAnalyzer()
        self.stats = {
            "total_files": 0,
            "processed": 0,
            "failed": 0,
            "total_chunks": 0,
            "skipped": 0
        }

    def load_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Load metadata JSON for a file if it exists"""
        metadata_path = Path(str(file_path) + ".meta.json")

        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load metadata for {file_path.name}: {e}")
                return {}
        return {}

    def process_file_with_analysis(self, file_path: Path, github_metadata: Dict[str, Any]) -> bool:
        """Process a file with code analysis and enhanced metadata"""
        try:
            print(f"\n🔄 Processing: {file_path.name}")

            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e:
                    print(f"❌ Failed to read {file_path.name}: {e}")
                    return False

            if not content.strip():
                print(f"⚠️  Empty file, skipping: {file_path.name}")
                self.stats["skipped"] += 1
                return False

            # Perform code analysis for supported file types
            code_analysis = None
            file_extension = file_path.suffix.lower()

            if file_extension in ['.py', '.js', '.ts', '.jsx', '.tsx']:
                print(f"   🔍 Analyzing code structure...")
                code_analysis = self.code_analyzer.analyze_file(str(file_path), content)

                if code_analysis:
                    print(f"   Found: {len(code_analysis.get('functions', []))} functions, "
                          f"{len(code_analysis.get('classes', []))} classes, "
                          f"{len(code_analysis.get('imports', []))} imports")

            # Chunk the content
            chunks = self.doc_ingestion.chunk_text(content)
            print(f"   📄 Created {len(chunks)} chunks")

            # Generate embeddings
            embeddings = self.doc_ingestion.generate_embeddings(chunks)

            # Build comprehensive metadata
            base_metadata = {
                'filename': file_path.name,
                'file_path': str(file_path),
                'file_extension': file_extension,
                'file_size': file_path.stat().st_size,
                'total_chunks': len(chunks),
                'source': 'github_scraper'
            }

            # Sanitize GitHub metadata for Pinecone (only primitives allowed)
            sanitized_github_metadata = {}
            for key, value in github_metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    sanitized_github_metadata[key] = value
                elif isinstance(value, list) and all(isinstance(x, str) for x in value):
                    sanitized_github_metadata[key] = value
                elif isinstance(value, dict):
                    # Convert dict to JSON string
                    sanitized_github_metadata[key + '_json'] = json.dumps(value)
                elif isinstance(value, list):
                    # Convert complex list to JSON string
                    sanitized_github_metadata[key + '_json'] = json.dumps(value)
                else:
                    # Convert other types to string
                    sanitized_github_metadata[key] = str(value)

            # Merge with sanitized GitHub metadata
            metadata = {**base_metadata, **sanitized_github_metadata}

            # Add code analysis if available (flattened for Pinecone)
            if code_analysis:
                metadata['analysis_language'] = code_analysis.get('language', 'unknown')
                metadata['analysis_function_count'] = len(code_analysis.get('functions', []))
                metadata['analysis_class_count'] = len(code_analysis.get('classes', []))
                metadata['analysis_import_count'] = len(code_analysis.get('imports', []))
                metadata['analysis_complexity_score'] = code_analysis.get('complexity_score', 0)

                # Store function and class names as list of strings
                function_names = [f['name'] for f in code_analysis.get('functions', [])[:10]]
                class_names = [c['name'] for c in code_analysis.get('classes', [])[:10]]

                if function_names:
                    metadata['analysis_functions'] = function_names
                if class_names:
                    metadata['analysis_classes'] = class_names

            # Upsert to Pinecone
            success = self.doc_ingestion.upsert_to_pinecone(chunks, embeddings, metadata)

            if success:
                print(f"   ✅ Successfully indexed {file_path.name}")
                self.stats["processed"] += 1
                self.stats["total_chunks"] += len(chunks)
                return True
            else:
                print(f"   ❌ Failed to index {file_path.name}")
                self.stats["failed"] += 1
                return False

        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
            self.stats["failed"] += 1
            return False

    def process_repository(self, repo_dir: Path) -> Dict[str, int]:
        """Process all files in a repository directory"""
        print(f"\n{'='*60}")
        print(f"📁 Processing repository: {repo_dir.name}")
        print(f"{'='*60}")

        # Get all files (excluding .meta.json files)
        all_files = [f for f in repo_dir.iterdir()
                     if f.is_file() and not f.name.endswith('.meta.json')]

        print(f"Found {len(all_files)} files to process")

        repo_stats = {"total": len(all_files), "success": 0, "failed": 0}

        for file_path in all_files:
            self.stats["total_files"] += 1

            # Load GitHub metadata
            github_metadata = self.load_metadata(file_path)

            # Process the file
            success = self.process_file_with_analysis(file_path, github_metadata)

            if success:
                repo_stats["success"] += 1
            else:
                repo_stats["failed"] += 1

        return repo_stats

    def run_bulk_ingestion(self, scraped_repos_dir: str = "scraped_repos"):
        """Run bulk ingestion on all repositories"""
        print("🚀 DevRAG Bulk Ingestion Starting")
        print("="*60)

        scraped_path = Path(scraped_repos_dir)

        if not scraped_path.exists():
            print(f"❌ Directory not found: {scraped_repos_dir}")
            return False

        # Get all repository directories
        repo_dirs = [d for d in scraped_path.iterdir() if d.is_dir()]

        if not repo_dirs:
            print(f"❌ No repository directories found in {scraped_repos_dir}")
            return False

        print(f"📦 Found {len(repo_dirs)} repositories to process:")
        for repo_dir in repo_dirs:
            print(f"   - {repo_dir.name}")

        # Show initial index stats
        print("\n📊 Initial Index Status:")
        self.doc_ingestion.get_index_stats()

        # Process each repository
        for repo_dir in repo_dirs:
            repo_stats = self.process_repository(repo_dir)
            print(f"\n📈 {repo_dir.name} Summary:")
            print(f"   Total: {repo_stats['total']}")
            print(f"   Success: {repo_stats['success']}")
            print(f"   Failed: {repo_stats['failed']}")

        # Show final statistics
        print("\n" + "="*60)
        print("🎉 BULK INGESTION COMPLETE")
        print("="*60)
        print(f"📊 Final Statistics:")
        print(f"   Total files: {self.stats['total_files']}")
        print(f"   Successfully processed: {self.stats['processed']}")
        print(f"   Failed: {self.stats['failed']}")
        print(f"   Skipped (empty): {self.stats['skipped']}")
        print(f"   Total chunks created: {self.stats['total_chunks']}")
        print(f"   Success rate: {self.stats['processed']/max(self.stats['total_files'],1)*100:.1f}%")

        # Show final index stats
        print("\n📊 Final Index Status:")
        self.doc_ingestion.get_index_stats()

        return True


def main():
    """Main entry point for bulk ingestion"""
    import argparse

    parser = argparse.ArgumentParser(description="Bulk ingest scraped repositories into Pinecone")
    parser.add_argument(
        "--dir",
        default="scraped_repos",
        help="Directory containing scraped repositories (default: scraped_repos)"
    )
    parser.add_argument(
        "--repo",
        help="Process only a specific repository (folder name)"
    )

    args = parser.parse_args()

    bulk = BulkIngestion()

    if args.repo:
        # Process single repository
        repo_path = Path(args.dir) / args.repo
        if not repo_path.exists():
            print(f"❌ Repository not found: {repo_path}")
            return 1

        bulk.process_repository(repo_path)
    else:
        # Process all repositories
        bulk.run_bulk_ingestion(args.dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
