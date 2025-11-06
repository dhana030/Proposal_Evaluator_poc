import os
import fitz 
import pandas as pd
from dotenv import load_dotenv

# Import modules
from modules.proposal_ingestor import initialize_milvus, ingest_proposal
from modules.kimi_client import extract_table_from_kimi
from modules.evaluator import run_evaluation_loop
from modules.utils import extract_text_from_pdf_page, extract_criteria_from_rubric 

load_dotenv()

# --- Configuration ---
RFP_PATH = "data/rfp.pdf"
PROPOSALS_PATHS = {
    "Prop_1": "data/proposal1.pdf",
    "Prop_2": "data/proposal2.pdf"
}
RFP_PAGE_NUMBER = 5 # Default page number
OUTPUT_DIR = "outputs"

def main(rfp_path: str = RFP_PATH, proposals_paths: dict = PROPOSALS_PATHS, rfp_page_number: int = RFP_PAGE_NUMBER):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # --------------------------------
    # 1. RFP Rubric Creation (Your existing, slightly refactored logic)
    # --------------------------------
    print("\n\n--- Step 1: RFP Rubric Creation ---")
    
    # 1a. Extract text from RFP page
    rfp_text = extract_text_from_pdf_page(rfp_path, rfp_page_number)
    if not rfp_text:
        print("🔴 ERROR: Failed to extract RFP text. Exiting.")
        return

    # 1b. Send to Kimi for rubric generation
    print("🔍 Sending RFP text to Kimi to generate the Evaluation Rubric...")
    rubric_markdown = extract_table_from_kimi(rfp_text)
    
    if not rubric_markdown:
        print("🔴 ERROR: Kimi failed to generate the evaluation rubric. Exiting.")
        return

    # Save the raw rubric for review/debugging
    rubric_file_path = os.path.join(OUTPUT_DIR, "rfp_rubric_raw.md")
    with open(rubric_file_path, "w", encoding="utf-8") as f:
        f.write(rubric_markdown)
    print(f"✅ Kimi Rubric saved to: {rubric_file_path}")

    # 1c. Parse the markdown table into a DataFrame for the evaluation loop
    rubric_df = extract_criteria_from_rubric(rubric_markdown)
    if rubric_df.empty:
        print("🔴 ERROR: Failed to parse the rubric into a DataFrame. Exiting.")
        return
    print(f"✅ Parsed {len(rubric_df)} sub-criteria for evaluation.")


    # --------------------------------
    # 2. Proposal Ingestion (Chunk, Embed, Store)
    # --------------------------------
    print("\n\n--- Step 2: Proposal Ingestion into Zilliz Cloud ---")
    milvus_collection = initialize_milvus()
    if milvus_collection is None:
        print("🔴 ERROR: Milvus initialization failed. Cannot ingest.")
        return

    for prop_id, prop_path in proposals_paths.items():
        ingest_proposal(prop_path, prop_id, milvus_collection)

    
    # --------------------------------
    # 3. RAG-Based Evaluation Loop
    # --------------------------------
    print("\n\n--- Step 3: Running RAG Evaluation Loop ---")
    
    final_scores_df = run_evaluation_loop(rubric_df, num_proposals=len(proposals_paths))
    
    if final_scores_df.empty:
        print("🔴 WARNING: No final scores were generated.")
        return
    
    # --------------------------------
    # 4. Final Output and Presentation
    # --------------------------------
    print("\n\n--- Step 4: Final Output ---")
    
    # Pivot the table for the final user-facing format (robust to missing columns)
    value_candidates = ['Score (0-5)', 'Reasoning (Arabic)', 'Reasoning (English)']
    value_columns = [c for c in value_candidates if c in final_scores_df.columns]
    if not value_columns:
        print("🔴 WARNING: No scoring/reasoning columns found. Returning raw results.")
        pivot_df = final_scores_df.copy()
    else:
        try:
            pivot_df = final_scores_df.pivot_table(
                index=['Main_Criterion', 'Sub_Criterion'],
                columns='Proposal',
                values=value_columns,
                aggfunc='first'
            )
            # Flatten the column index
            pivot_df.columns = [f'{col[0]} - {col[1]}' for col in pivot_df.columns]
            
            # Reorder columns for better presentation (Score then Reasoning for each proposal)
            desired_cols = []
            for prop_id in proposals_paths.keys():
                desired_cols.append(f'Score (0-5) - {prop_id}')
                if 'Reasoning (Arabic)' in value_columns:
                    desired_cols.append(f'Reasoning (Arabic) - {prop_id}')
                if 'Reasoning (English)' in value_columns:
                    desired_cols.append(f'Reasoning (English) - {prop_id}')
            existing_cols = [c for c in desired_cols if c in pivot_df.columns]
            if not existing_cols:
                print("🔴 WARNING: No expected pivot columns found. Returning all available columns.")
                pivot_df = pivot_df.reset_index()
            else:
                pivot_df = pivot_df[existing_cols].reset_index()
        except Exception as e:
            print(f"🔴 WARNING: Pivot failed: {e}. Returning raw results.")
            pivot_df = final_scores_df.copy()
    
    
    # Save a uniquely named file per run
    output_path = os.path.join(OUTPUT_DIR, f"evaluation_results_page_{rfp_page_number}.xlsx")
    pivot_df.to_excel(output_path, index=False)
    
    print(f"🎉 SUCCESS! Final evaluation results saved to: {output_path}")
    return pivot_df, output_path

if __name__ == "__main__":
    # Ensure placeholder data files exist for the demo to run without error
    for f in [RFP_PATH] + list(PROPOSALS_PATHS.values()):
        if not os.path.exists(f):
             print(f"⚠️ Placeholder file not found: {f}. Please create/upload it.")
             # Create dummy files for structure check
             os.makedirs(os.path.dirname(f), exist_ok=True)
             with open(f, 'w') as temp_f:
                 temp_f.write("Dummy content for file: " + os.path.basename(f))
    
    main()