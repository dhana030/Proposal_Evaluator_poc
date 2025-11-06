import streamlit as st
import pandas as pd
import requests

# FastAPI Endpoint (Assuming it's running locally on port 8000)
FASTAPI_URL = "http://localhost:8000/upload_and_evaluate/"

st.set_page_config(layout="wide", page_title="RFP Proposal Evaluator 🤖")

st.title("🤖 RFP Proposal Evaluation System")
st.markdown("Upload your RFP and two proposals to generate a side-by-side comparison score and reasoning using RAG and Kimi LLM.")

# --- File Upload Form ---
with st.form("upload_form", clear_on_submit=True):
    st.header("1. Upload Documents")
    
    rfp_file = st.file_uploader("Upload RFP PDF (with Arabic Rubric)", type="pdf", key="rfp")
    
    col1, col2 = st.columns(2)
    with col1:
        proposal1_file = st.file_uploader("Upload Proposal 1 PDF", type="pdf", key="prop1")
    with col2:
        proposal2_file = st.file_uploader("Upload Proposal 2 PDF", type="pdf", key="prop2")

    rfp_page_number = st.number_input(
        "RFP Rubric Page Number (0-indexed)", 
        min_value=0, 
        value=5, 
        step=1, 
        help="Enter the page number where the evaluation criteria/rubric is located in the RFP PDF."
    )

    submitted = st.form_submit_button("Start Evaluation 🚀")

if submitted:
    if not all([rfp_file, proposal1_file, proposal2_file]):
        st.error("Please upload all three required files (RFP, Proposal 1, Proposal 2).")
    else:
        st.info("Files uploaded successfully. Starting evaluation... this may take a few minutes for Jina embeddings and Kimi scoring.")
        
        # Prepare files for multipart upload
        files = {
            'rfp_file': (rfp_file.name, rfp_file.getvalue(), 'application/pdf'),
            'proposal1_file': (proposal1_file.name, proposal1_file.getvalue(), 'application/pdf'),
            'proposal2_file': (proposal2_file.name, proposal2_file.getvalue(), 'application/pdf'),
        }
        
        # Prepare form data
        data = {
            'rfp_page_number': rfp_page_number
        }
        
        # Send request to FastAPI backend
        try:
            with st.spinner("Processing... Chunking, Embedding, Storing in Zilliz, Retrieving, and Scoring with Kimi..."):
                response = requests.post(FASTAPI_URL, files=files, data=data, timeout=600) # 10 minute timeout
                
            if response.status_code == 200:
                result = response.json()
                st.success("Evaluation Complete! 🎉")
                
                # Display results table
                df_results = pd.DataFrame(result['results'])
                
                st.subheader("Final Proposal Comparison Scores and Reasons")
                st.dataframe(df_results, use_container_width=True)
                
                # Display a summary chart (optional)
                # score_cols = [col for col in df_results.columns if 'Score' in col]
                # if score_cols:
                #     summary_df = df_results[score_cols].apply(pd.to_numeric, errors='coerce').mean().sort_values(ascending=False)
                #     st.bar_chart(summary_df, use_container_width=True)
                
            else:
                st.error(f"Evaluation Failed (Status: {response.status_code}): {response.json().get('detail', 'Unknown error.')}")

        except requests.exceptions.RequestException as e:
            st.error(f"Could not connect to the FastAPI service. Ensure it is running: {e}")

# To run Streamlit: streamlit run streamlit_app.py