import os
import fitz
from dotenv import load_dotenv
from typing import List, Dict
from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType
from .utils import recursive_chunking, CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_DIM, get_jina_embeddings

load_dotenv()

# Jina embeddings will be called via HTTP helper in utils

# Milvus/Zilliz Cloud Connection
COLLECTION_NAME = "proposal_chunks"

def initialize_milvus():
    """Connects to Milvus/Zilliz Cloud and ensures the collection exists."""
    print("⏳ Connecting to Zilliz Cloud...")
    try:
        connections.connect(
            alias="default",
            uri=os.getenv("ZILLIZ_ENDPOINT"),
            token=os.getenv("ZILLIZ_TOKEN"),
            secure=True 
        )
        print("✅ Zilliz Cloud connection established.")
        
        # Define Collection Schema
        fields = [
            FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="proposal_id", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="page_number", dtype=DataType.INT64),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="text_content", dtype=DataType.VARCHAR, max_length=65535), # Use a large max_length for text
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        ]
        schema = CollectionSchema(fields, description="Proposal chunks for RAG")
        
        if utility.has_collection(COLLECTION_NAME):
            utility.drop_collection(COLLECTION_NAME) # Clear existing data for a clean run
            print(f"⚠️ Dropped existing collection: {COLLECTION_NAME}")

        collection = Collection(name=COLLECTION_NAME, schema=schema)
        
        # Create an index on the vector field
        index_params = {
            "index_type": "IVF_FLAT", 
            "metric_type": "COSINE", 
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        
        print(f"✅ Collection '{COLLECTION_NAME}' created and loaded.")
        return collection
        
    except Exception as e:
        print(f"❌ Error connecting or setting up Milvus/Zilliz: {e}")
        return None

def ingest_proposal(proposal_path: str, proposal_id: str, milvus_collection: Collection):
    """
    Extracts text from PDF, chunks it, embeds it using Jina API, 
    and inserts the vectors and metadata into Milvus.
    """
    print(f"\n--- 📄 Starting ingestion for {proposal_id} ({proposal_path}) ---")
    all_chunks = []
    
    # 1. Extract Text
    try:
        with fitz.open(proposal_path) as doc:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text").strip()
                if not text:
                    continue
                
                # 2. Chunk Text
                chunks = recursive_chunking(text)
                
                for i, chunk_text in enumerate(chunks):
                    all_chunks.append({
                        "text": chunk_text,
                        "proposal_id": proposal_id,
                        "page_number": page_num,
                        "chunk_index": i
                    })
        print(f"✅ Extracted text and generated {len(all_chunks)} chunks.")
        
    except Exception as e:
        print(f"❌ Error during PDF extraction/chunking: {e}")
        return

    # 3. Embed Chunks using Jina API
    try:
        texts_to_embed = [item['text'] for item in all_chunks]
        print(f"⏳ Calling Jina API to embed {len(texts_to_embed)} chunks...")
        embeddings = get_jina_embeddings(texts_to_embed, model="jina-embeddings-v2-base-en")
        
        # 4. Prepare data for Milvus insertion
        entities = [
            [item['proposal_id'] for item in all_chunks], # proposal_id
            [item['page_number'] for item in all_chunks], # page_number
            [item['chunk_index'] for item in all_chunks], # chunk_index
            [item['text'] for item in all_chunks],        # text_content
            embeddings                                    # embedding
        ]
        
        # 5. Insert into Milvus
        result = milvus_collection.insert(entities)
        milvus_collection.flush()
        
        print(f"✅ Successfully inserted {len(result.primary_keys)} vectors into Milvus.")
        
    except Exception as e:
        print(f"❌ Error during Jina API call or Milvus insertion: {e}")