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
        df, output_path = main(
            rfp_path=rfp_path,
            proposals_paths=proposals_paths,
            rfp_page_number=rfp_page_number
        )

        if df is None or df.empty:
            raise HTTPException(status_code=500, detail="Evaluation pipeline produced no results.")

        # Convert DataFrame to JSON for API response
        return JSONResponse(content={
            "status": "success",
            "output_path": output_path,
            "results": df.to_dict(orient="records")
        })

    except Exception as e:
        # Clean up files in case of error (optional but recommended)
        # os.remove(rfp_path)
        # os.remove(proposal1_path)
        # os.remove(proposal2_path)
        raise HTTPException(status_code=500, detail=f"An error occurred during evaluation: {str(e)}")

# To run FastAPI: uvicorn fast_api_app:app --reload