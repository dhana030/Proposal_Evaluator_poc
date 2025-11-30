import pandas as pd
import numpy as np
import os
from typing import Dict, List, Any
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

def retrieve_context(milvus_collection: Collection, criterion_text: str, k_chunks: int = 5) -> Dict[str, Any]:
    """
    Embeds the criterion and retrieves up to the top K relevant chunks per proposal.
    Returns both concatenated context strings and chunk metadata for references.
    """
    print(f"  - ⏳ Embedding criterion: '{criterion_text[:50]}...'")
    # 1. Embed the criterion
    try:
        embeddings = get_jina_embeddings([criterion_text], model="jina-embeddings-v2-base-en")
        query_vector = embeddings[0]
    except Exception as e:
        print(f"  - ❌ Jina embedding failed: {e}")
        return {
            "Prop_1": {"text": "", "chunks": []},
            "Prop_2": {"text": "", "chunks": []},
        }

    # 2. Search Milvus
    print(f"  - ⏳ Searching Milvus for relevant chunks...")
    search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    
    # Search the entire collection
    results = milvus_collection.search(
        data=[query_vector], 
        anns_field="embedding", 
        param=search_params, 
        # Retrieve more overall, then cap per proposal
        limit=max(k_chunks * 6, 10),
        output_fields=["proposal_id", "text_content", "page_number"]
    )

    # 3. Aggregate hits by proposal and retain distance to rank
    hits_by_proposal: Dict[str, List[Dict[str, Any]]] = {"Prop_1": [], "Prop_2": []}
    
    for hit in results[0]:
        proposal_id = hit.entity.get('proposal_id')
        text = hit.entity.get('text_content')
        page_number = hit.entity.get('page_number')
        distance = getattr(hit, "distance", None)  # for COSINE, lower is better
        
        if proposal_id in hits_by_proposal:
            hits_by_proposal[proposal_id].append({
                "proposal_id": proposal_id,
                "page_number": int(page_number) if page_number is not None else None,
                "text": text,
                "distance": float(distance) if distance is not None else None
            })
    
    # 4. For each proposal: sort by similarity, dedupe by text, cap at k_chunks
    final_context: Dict[str, Dict[str, Any]] = {}
    for p_id, items in hits_by_proposal.items():
        # Sort by distance (None last)
        items_sorted = sorted(
            items,
            key=lambda x: (x["distance"] is None, x["distance"] if x["distance"] is not None else 1e9)
        )
        seen_texts = set()
        topk: List[Dict[str, Any]] = []
        for it in items_sorted:
            txt = it.get("text", "")
            if txt in seen_texts:
                continue
            seen_texts.add(txt)
            # Drop distance from public references (keep if needed for debugging)
            topk.append({k: v for k, v in it.items() if k != "distance"})
            if len(topk) >= k_chunks:
                break
        final_context[p_id] = {
            "text": "\n---\n".join([c["text"] for c in topk]),
            "chunks": topk
        }
    print(f"  - ✅ Retrieved context from Prop_1 and Prop_2.")
    return final_context

def run_evaluation_loop(rubric_df: pd.DataFrame, num_proposals: int, output_dir: str = "outputs") -> pd.DataFrame:
    """
    Iterates through each criterion, retrieves context, and scores proposals.
    
    Args:
        rubric_df: DataFrame with evaluation criteria
        num_proposals: Number of proposals being evaluated
        output_dir: Directory to save output files (default: "outputs")
    """
    milvus_collection = get_milvus_collection()
    if milvus_collection is None:
        return pd.DataFrame()

    final_evaluation_results = []
    # Ensure output dir for Kimi scoring artifacts (within the timestamped folder)
    artifacts_dir = os.path.join(output_dir, "kimi_scores")
    os.makedirs(artifacts_dir, exist_ok=True)

    for index, row in rubric_df.iterrows():
        criterion = f"{row['Main_Criterion']} - {row['Sub_Criterion']}"
        rubric = row['Rubric']
        
        print(f"\n--- 🎯 Evaluating Criterion: {criterion} ---")
        
        # 1. Retrieval (RAG)
        context = retrieve_context(milvus_collection, criterion_text=f"{criterion}. {rubric}")
        
        context_p1_text = context.get('Prop_1', {}).get('text', "No relevant content found.")
        context_p2_text = context.get('Prop_2', {}).get('text', "No relevant content found.")

        # Save references (retrieved chunk metadata) for this criterion
        references_dir = os.path.join(output_dir, "references")
        os.makedirs(references_dir, exist_ok=True)
        safe_name = f"{index:03d}_" + "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in criterion)[:120]
        references_path = os.path.join(references_dir, f"{safe_name}.json")
        try:
            import json
            with open(references_path, "w", encoding="utf-8") as rf:
                json.dump({
                    "criterion": criterion,
                    "rubric": rubric,
                    "Prop_1": context.get('Prop_1', {}).get('chunks', []),
                    "Prop_2": context.get('Prop_2', {}).get('chunks', [])
                }, rf, ensure_ascii=False, indent=2)
        except Exception as _:
            references_path = ""
        
        # 2. Generation (Kimi Scoring)
        print("  - ⏳ Sending context to Kimi for scoring...")
        scoring_table_markdown = score_proposals_with_rag(
            criterion=criterion,
            rubric=rubric,
            proposal_1_context=context_p1_text,
            proposal_2_context=context_p2_text,
            num_proposals=num_proposals
        )

        # 3. Parse Scoring Table
        if scoring_table_markdown:
            print("  - ✅ Kimi scoring complete. Parsing results...")
            # Save raw Kimi markdown for auditing
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
                        'Reasoning (English)': reason_en,
                        'References_File': references_path
                    })
            except Exception as e:
                print(f"  - ❌ Failed to parse Kimi scoring table: {e}")
                
        else:
            print("  - ❌ Kimi returned no scoring table.")

    return pd.DataFrame(final_evaluation_results)