import os
import sys
import uuid
import time
from typing import List, Dict, Any
from pathlib import Path

# Import new API clients
from openai import OpenAI
from pinecone import Pinecone
import boto3
from PyPDF2 import PdfReader

# Add the root directory to the path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config import Config

class DocumentIngestion:
    def __init__(self):
        """Initialize all API clients"""
        # Skip OpenAI client initialization due to proxy issues
        # Will use direct HTTP requests instead
        print("⚠️  Using direct OpenAI API calls to avoid proxy issues")
        
        self.pinecone_client = Pinecone(api_key=Config.PINECONE_API_KEY)
        self.s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
        self.index = self.pinecone_client.Index(Config.PINECONE_INDEX_NAME)
        
        print("✅ All clients initialized successfully")

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                text += f"\n--- Page {page_num + 1} ---\n{page_text}"
            return text.strip()
        except Exception as e:
            print(f"❌ Error extracting text from {file_path}: {e}")
            return ""

    def chunk_text(self, text: str, max_chunk_size: int = None, overlap: int = None) -> List[str]:
        """Split text into overlapping chunks"""
        max_size = max_chunk_size or Config.MAX_CHUNK_SIZE
        overlap_size = overlap or Config.CHUNK_OVERLAP
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary if possible
            if end < len(text) and '.' in chunk[-100:]:
                last_period = chunk.rfind('.')
                if last_period > len(chunk) - 200:  # Don't break too early
                    chunk = chunk[:last_period + 1]
                    end = start + len(chunk)
            
            chunks.append(chunk.strip())
            start = end - overlap_size
            
        return [chunk for chunk in chunks if chunk.strip()]

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks using direct API calls"""
        import requests
        
        embeddings = []
        
        print(f"🔄 Generating embeddings for {len(texts)} chunks...")
        
        for i, text in enumerate(texts):
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
                        "input": text
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    embedding = data['data'][0]['embedding']
                    embeddings.append(embedding)
                else:
                    print(f"❌ API error for chunk {i}: {response.status_code}")
                    embeddings.append([0.0] * Config.PINECONE_DIMENSION)
                
                if (i + 1) % 10 == 0:
                    print(f"   Generated {i + 1}/{len(texts)} embeddings")
                    
            except Exception as e:
                print(f"❌ Error generating embedding for chunk {i}: {e}")
                embeddings.append([0.0] * Config.PINECONE_DIMENSION)
                
        return embeddings

    def upsert_to_pinecone(self, chunks: List[str], embeddings: List[List[float]], 
                          metadata: Dict[str, Any]) -> bool:
        """Upload embeddings to Pinecone"""
        try:
            vectors = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_id = f"{metadata.get('filename', 'doc')}_{i}_{uuid.uuid4().hex[:8]}"
                
                vector_metadata = {
                    **metadata,
                    'chunk_index': i,
                    'text': chunk[:1000],  # Limit metadata size
                    'chunk_id': vector_id
                }
                
                vectors.append({
                    'id': vector_id,
                    'values': embedding,
                    'metadata': vector_metadata
                })
            
            # Upsert in batches of 100
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch)
                print(f"   Upserted batch {i//batch_size + 1}/{(len(vectors)-1)//batch_size + 1}")
                time.sleep(0.1)  # Rate limiting
            
            print(f"✅ Successfully upserted {len(vectors)} vectors to Pinecone")
            return True
            
        except Exception as e:
            print(f"❌ Error upserting to Pinecone: {e}")
            return False

    def process_local_file(self, file_path: str) -> bool:
        """Process a single local file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return False
            
        print(f"🔄 Processing: {file_path.name}")
        
        # Extract text based on file type
        if file_path.suffix.lower() == '.pdf':
            text = self.extract_text_from_pdf(str(file_path))
        elif file_path.suffix.lower() in {'.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', 
                                          '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', 
                                          '.go', '.rs', '.swift', '.kt', '.scala', '.json', 
                                          '.yaml', '.yml', '.xml', '.toml', '.sql', '.sh', 
                                          '.bat', '.dockerfile', '.gitignore', '.env', '.rst'}:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        text = f.read()
                except Exception as e:
                    print(f"❌ Error reading {file_path.name}: {e}")
                    return False
        else:
            print(f"❌ Unsupported file type: {file_path.suffix}")
            return False
            
        if not text.strip():
            print(f"❌ No text extracted from {file_path.name}")
            return False
            
        # Process the document
        chunks = self.chunk_text(text)
        embeddings = self.generate_embeddings(chunks)
        
        metadata = {
            'filename': file_path.name,
            'file_path': str(file_path),
            'file_size': file_path.stat().st_size,
            'total_chunks': len(chunks),
            'processed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        success = self.upsert_to_pinecone(chunks, embeddings, metadata)
        
        if success:
            print(f"✅ Successfully processed {file_path.name} ({len(chunks)} chunks)")
        
        return success

    def process_s3_files(self, prefix: str = "") -> bool:
        """Process all files in S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=Config.S3_BUCKET,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                print(f"❌ No files found in S3 bucket with prefix '{prefix}'")
                return False
                
            files = response['Contents']
            print(f"📁 Found {len(files)} files in S3")
            
            success_count = 0
            for file_obj in files:
                key = file_obj['Key']
                
                # Skip directories
                if key.endswith('/'):
                    continue
                    
                # Download and process file
                local_path = f"/tmp/{os.path.basename(key)}"
                
                try:
                    self.s3_client.download_file(Config.S3_BUCKET, key, local_path)
                    
                    if self.process_local_file(local_path):
                        success_count += 1
                        
                    # Clean up
                    os.remove(local_path)
                    
                except Exception as e:
                    print(f"❌ Error processing S3 file {key}: {e}")
                    
            print(f"✅ Successfully processed {success_count}/{len(files)} files from S3")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Error accessing S3: {e}")
            return False

    def get_index_stats(self):
        """Display current index statistics"""
        try:
            stats = self.index.describe_index_stats()
            print("\n📊 Index Statistics:")
            print(f"   Total vectors: {stats.get('total_vector_count', 0)}")
            print(f"   Index fullness: {stats.get('index_fullness', 0):.2%}")
            print(f"   Dimension: {stats.get('dimension', 0)}")
            
            namespaces = stats.get('namespaces', {})
            if namespaces:
                print("   Namespaces:")
                for ns, ns_stats in namespaces.items():
                    print(f"     {ns}: {ns_stats.get('vector_count', 0)} vectors")
                    
        except Exception as e:
            print(f"❌ Error getting index stats: {e}")

def main():
    """Main ingestion function"""
    print("🚀 Starting DevRAG-Lite Document Ingestion")
    print("=" * 50)
    
    # Validate configuration
    if not Config.validate():
        print("❌ Configuration validation failed!")
        print("Please check your environment variables:")
        print("   - OPENAI_API_KEY")
        print("   - PINECONE_API_KEY")
        return False
    
    # Initialize ingestion system
    ingestion = DocumentIngestion()
    
    # Show current index stats
    ingestion.get_index_stats()
    
    # Ask user what to ingest
    print("\n📋 Ingestion Options:")
    print("1. Process local files (provide file paths)")
    print("2. Process all files from S3 bucket")
    print("3. Process specific S3 prefix")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        while True:
            file_path = input("\nEnter file path (or 'done' to finish): ").strip()
            if file_path.lower() == 'done':
                break
            if file_path:
                ingestion.process_local_file(file_path)
                
    elif choice == "2":
        ingestion.process_s3_files()
        
    elif choice == "3":
        prefix = input("Enter S3 prefix: ").strip()
        ingestion.process_s3_files(prefix)
        
    else:
        print("❌ Invalid choice")
        return False
    
    # Show final stats
    print("\n" + "=" * 50)
    ingestion.get_index_stats()
    print("✅ Ingestion complete!")
    
    return True

if __name__ == "__main__":
    main()