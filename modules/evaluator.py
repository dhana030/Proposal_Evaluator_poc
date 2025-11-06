import pandas as pd
import numpy as np
import os
from typing import Dict
from pymilvus import Collection, connections
from dotenv import load_dotenv

from .kimi_client import score_proposals_with_rag
from .utils import EMBEDDING_DIM

load_dotenv()

from .utils import get_jina_embeddings

# Milvus/Zilliz Cloud Connection
COLLECTION_NAME = "proposal_chunks"

def get_milvus_collection() -> Collection:
    """Connects and returns the loaded Milvus collection."""
    try:
        connections.connect(alias="default", uri=os.getenv("ZILLIZ_ENDPOINT"), token=os.getenv("ZILLIZ_TOKEN"), secure=True)
        collection = Collection(COLLECTION_NAME)
        collection.load()
        return collection
    except Exception as e:
        print(f"❌ Failed to connect to or load Milvus collection: {e}")
        return None

def retrieve_context(milvus_collection: Collection, criterion_text: str, k_chunks: int = 5) -> Dict[str, str]:
    """
    Embeds the criterion and retrieves the top K relevant chunks from ALL proposals.
    """
    print(f"  - ⏳ Embedding criterion: '{criterion_text[:50]}...'")
    # 1. Embed the criterion
    try:
        embeddings = get_jina_embeddings([criterion_text], model="jina-embeddings-v2-base-en")
        query_vector = embeddings[0]
    except Exception as e:
        print(f"  - ❌ Jina embedding failed: {e}")
        return {"Prop_1": "", "Prop_2": ""}

    # 2. Search Milvus
    print(f"  - ⏳ Searching Milvus for relevant chunks...")
    search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    
    # Search the entire collection
    results = milvus_collection.search(
        data=[query_vector], 
        anns_field="embedding", 
        param=search_params, 
        limit=k_chunks * 2, # Retrieve more to ensure we get chunks from both
        output_fields=["proposal_id", "text_content", "page_number"]
    )

    # 3. Aggregate context by proposal
    context_map = {"Prop_1": [], "Prop_2": []}
    
    for hit in results[0]:
        proposal_id = hit.entity.get('proposal_id')
        text = hit.entity.get('text_content')
        
        if proposal_id in context_map:
            # Add to the context list for the relevant proposal
            context_map[proposal_id].append(text)
    
    # 4. Concatenate and return the unique context for each proposal
    final_context = {
        p_id: "\n---\n".join(list(dict.fromkeys(chunks)))
        for p_id, chunks in context_map.items()
    }
    print(f"  - ✅ Retrieved context from Prop_1 and Prop_2.")
    return final_context

def run_evaluation_loop(rubric_df: pd.DataFrame, num_proposals: int) -> pd.DataFrame:
    """
    Iterates through each criterion, retrieves context, and scores proposals.
    """
    milvus_collection = get_milvus_collection()
    if milvus_collection is None:
        return pd.DataFrame()

    final_evaluation_results = []
    # Ensure output dir for Kimi scoring artifacts
    artifacts_dir = os.path.join("outputs", "kimi_scores")
    os.makedirs(artifacts_dir, exist_ok=True)

    for index, row in rubric_df.iterrows():
        criterion = f"{row['Main_Criterion']} - {row['Sub_Criterion']}"
        rubric = row['Rubric']
        
        print(f"\n--- 🎯 Evaluating Criterion: {criterion} ---")
        
        # 1. Retrieval (RAG)
        context = retrieve_context(milvus_collection, criterion_text=f"{criterion}. {rubric}")
        
        context_p1 = context.get('Prop_1', "No relevant content found.")
        context_p2 = context.get('Prop_2', "No relevant content found.")
        
        # 2. Generation (Kimi Scoring)
        print("  - ⏳ Sending context to Kimi for scoring...")
        scoring_table_markdown = score_proposals_with_rag(
            criterion=criterion,
            rubric=rubric,
            proposal_1_context=context_p1,
            proposal_2_context=context_p2,
            num_proposals=num_proposals
        )

        # 3. Parse Scoring Table
        if scoring_table_markdown:
            print("  - ✅ Kimi scoring complete. Parsing results...")
            # Save raw Kimi markdown for auditing
            safe_name = f"{index:03d}_" + "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in criterion)[:120]
            try:
                with open(os.path.join(artifacts_dir, f"{safe_name}.md"), "w", encoding="utf-8") as f:
                    f.write(scoring_table_markdown)
            except Exception as _:
                pass
            
            # Robust parsing of the returned markdown table
            try:
                lines = [ln for ln in scoring_table_markdown.strip().split('\n') if ln.strip()]
                # Find header and separator lines dynamically
                header_idx = next((i for i, ln in enumerate(lines) if ln.strip().startswith('|')), None)
                sep_idx = None
                if header_idx is not None:
                    for j in range(header_idx + 1, min(header_idx + 4, len(lines))):
                        if set(lines[j].replace('|','').strip()) <= set('-: '):
                            sep_idx = j
                            break
                if header_idx is None or sep_idx is None:
                    raise ValueError("Markdown table header/separator not found")

                data_started = False
                for ln in lines[sep_idx + 1:]:
                    if not ln.strip().startswith('|'):
                        if data_started:
                            break
                        else:
                            continue
                    data_started = True
                    cells = [p.strip() for p in ln.split('|') if p.strip()]
                    if len(cells) < 3:
                        continue
                    if len(cells) >= 4:
                        proposal_name, score, reason_ar, reason_en = cells[0], cells[1], cells[2], cells[3]
                    else:
                        proposal_name, score, reason_ar = cells[0], cells[1], cells[2]
                        reason_en = ""

                    # Normalize proposal names to match PROPOSALS_PATHS keys for pivot step
                    name_lower = proposal_name.lower()
                    if 'prop_1' in name_lower or 'proposal 1' in name_lower or 'proposal1' in name_lower:
                        normalized_proposal = 'Prop_1'
                    elif 'prop_2' in name_lower or 'proposal 2' in name_lower or 'proposal2' in name_lower:
                        normalized_proposal = 'Prop_2'
                    else:
                        normalized_proposal = proposal_name

                    final_evaluation_results.append({
                        'Main_Criterion': row['Main_Criterion'],
                        'Sub_Criterion': row['Sub_Criterion'],
                        'Proposal': normalized_proposal,
                        'Score (0-5)': score,
                        'Reasoning (Arabic)': reason_ar,
                        'Reasoning (English)': reason_en
                    })
            except Exception as e:
                print(f"  - ❌ Failed to parse Kimi scoring table: {e}")
                
        else:
            print("  - ❌ Kimi returned no scoring table.")

    return pd.DataFrame(final_evaluation_results)