#!/usr/bin/env python3
"""
DevRAG-Lite Setup Verification Script
Verifies all components are properly configured and working
"""

import os
import sys
import traceback
from config import Config

def check_environment_variables():
    """Check if all required environment variables are set"""
    print("=== Environment Variables ===")
    
    required_vars = {
        'OPENAI_API_KEY': Config.OPENAI_API_KEY,
        'PINECONE_API_KEY': Config.PINECONE_API_KEY
    }
    
    all_good = True
    for var_name, var_value in required_vars.items():
        if var_value:
            print(f"✅ {var_name}: Set")
        else:
            print(f"❌ {var_name}: Missing")
            all_good = False
    
    return all_good

def check_pinecone_connection():
    """Verify Pinecone connection and index status"""
    print("\n=== Pinecone Connection ===")
    
    try:
        from pinecone import Pinecone
        
        # Initialize Pinecone with new API
        pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        print("✅ Connected to Pinecone")
        
        # List indexes
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]
        print(f"📋 Available indexes: {index_names}")
        
        # Check our specific index
        if Config.PINECONE_INDEX_NAME in index_names:
            print(f"✅ Index '{Config.PINECONE_INDEX_NAME}' exists")
            
            # Get index stats
            index = pc.Index(Config.PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()
            print(f"📊 Index stats: {stats}")
            
            vector_count = stats.get('total_vector_count', 0)
            if vector_count > 0:
                print(f"✅ Index contains {vector_count} vectors (documents ingested)")
            else:
                print("⚠️  Index is empty (no documents ingested yet)")
                
        else:
            print(f"❌ Index '{Config.PINECONE_INDEX_NAME}' not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Pinecone error: {e}")
        traceback.print_exc()
        return False

def check_openai_connection():
    """Verify OpenAI API connection"""
    print("\n=== OpenAI Connection ===")
    
    try:
        from openai import OpenAI
        
        # Initialize OpenAI client with minimal config
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        
        # Test with a simple embedding
        response = client.embeddings.create(
            model=Config.EMBEDDING_MODEL,
            input="test connection"
        )
        
        print("✅ OpenAI API connection successful")
        print(f"✅ Embedding model '{Config.EMBEDDING_MODEL}' working")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        # Try alternative approach
        try:
            import openai
            openai.api_key = Config.OPENAI_API_KEY
            print("✅ OpenAI API key set (legacy mode)")
            return True
        except:
            return False

def check_aws_connection():
    """Verify AWS S3 connection"""
    print("\n=== AWS S3 Connection ===")
    
    try:
        import boto3
        
        # Create S3 client
        s3 = boto3.client('s3', region_name=Config.AWS_REGION)
        
        # Test bucket access
        try:
            s3.head_bucket(Bucket=Config.S3_BUCKET)
            print(f"✅ S3 bucket '{Config.S3_BUCKET}' accessible")
            
            # List objects in bucket
            response = s3.list_objects_v2(Bucket=Config.S3_BUCKET, MaxKeys=5)
            object_count = response.get('KeyCount', 0)
            print(f"📁 Bucket contains {object_count} objects")
            
        except Exception as bucket_error:
            print(f"⚠️  S3 bucket error: {bucket_error}")
            
        return True
        
    except Exception as e:
        print(f"❌ AWS error: {e}")
        return False

def check_project_files():
    """Check if all required project files exist"""
    print("\n=== Project Files ===")
    
    required_files = [
        'config.py',
        'src/ingestion/ingest.py',
        'create_index_final.py',
        'infrastructure/aws/cloudformation.yaml',
        'infrastructure/aws/s3-only.yaml'
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} missing")
            all_exist = False
    
    return all_exist

def main():
    """Run all verification checks"""
    print("🔍 DevRAG-Lite Setup Verification")
    print("=" * 40)
    
    checks = [
        ("Environment Variables", check_environment_variables),
        ("Project Files", check_project_files),
        ("Pinecone Connection", check_pinecone_connection),
        ("OpenAI Connection", check_openai_connection),
        ("AWS S3 Connection", check_aws_connection),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} failed: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("📋 VERIFICATION SUMMARY")
    print("=" * 40)
    
    all_passed = True
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All checks passed! Your DevRAG-Lite setup is ready.")
        print("\n💡 Next steps:")
        print("   - Run ingestion if index is empty: python src/ingestion/ingest.py")
        print("   - Build query interface for RAG responses")
    else:
        print("\n⚠️  Some checks failed. Please fix issues before proceeding.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)