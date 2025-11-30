import os
import uvicorn
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from main import main, RFP_PATH, PROPOSALS_PATHS
from typing import Dict

# Define the root directory for file storage
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI()

@app.post("/upload_and_evaluate/")
async def upload_and_evaluate(
    rfp_file: UploadFile = File(...),
    proposal1_file: UploadFile = File(...),
    proposal2_file: UploadFile = File(...),
    rfp_page_number: int = Form(...)
):
    """Handles file uploads and triggers the main evaluation pipeline."""
    try:
        # Save uploaded files
        rfp_path = os.path.join(DATA_DIR, "rfp.pdf")
        proposal1_path = os.path.join(DATA_DIR, "proposal1.pdf")
        proposal2_path = os.path.join(DATA_DIR, "proposal2.pdf")

        # Build paths dict for this request
        proposals_paths = {
            "Prop_1": proposal1_path,
            "Prop_2": proposal2_path
        }
        
        # Write files to disk
        for file, path in [(rfp_file, rfp_path), (proposal1_file, proposal1_path), (proposal2_file, proposal2_path)]:
            content = await file.read()
            with open(path, "wb") as f:
                f.write(content)
        
        # Run the full evaluation pipeline with request-specific params
        result = main(
            rfp_path=rfp_path,
            proposals_paths=proposals_paths,
            rfp_page_number=rfp_page_number
        )

        if result is None:
            raise HTTPException(status_code=500, detail="Evaluation pipeline failed or returned no results.")
        
        df, output_path = result
        if df is None or df.empty:
            raise HTTPException(status_code=500, detail="Evaluation pipeline produced no results.")

        # Extract output directory from output_path
        output_dir = os.path.dirname(output_path)

        # Attempt to load raw_results.json for UI references
        raw_results_path = os.path.join(output_dir, "raw_results.json")
        raw_results = []
        try:
            if os.path.exists(raw_results_path):
                import json as _json
                with open(raw_results_path, "r", encoding="utf-8") as jf:
                    raw_results = _json.load(jf)
        except Exception as _:
            raw_results = []

        # Convert DataFrame to JSON for API response
        return JSONResponse(content={
            "status": "success",
            "output_directory": output_dir,
            "output_path": output_path,
            "results": df.to_dict(orient="records"),
            "raw_results": raw_results
        })

    except Exception as e:
        # Clean up files in case of error (optional but recommended)
        # os.remove(rfp_path)
        # os.remove(proposal1_path)
        # os.remove(proposal2_path)
        raise HTTPException(status_code=500, detail=f"An error occurred during evaluation: {str(e)}")

# To run FastAPI: uvicorn fast_api_app:app --reload