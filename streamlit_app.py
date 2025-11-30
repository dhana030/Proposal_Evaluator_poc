import streamlit as st
import pandas as pd
import requests
import sys
import traceback
import json
import os

# FastAPI Endpoint (Assuming it's running locally on port 8000)
FASTAPI_URL = "http://localhost:8000/upload_and_evaluate/"

# Set page config at the very top (before any other Streamlit commands)
st.set_page_config(
    layout="wide", 
    page_title="RFP Proposal Evaluator",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
    <style>
        /* Main background */
        .stApp {
            background-color: #FFFFFF;
        }
        
        /* Primary button styling */
        .stButton > button {
            background-color: #1971E5;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1.5rem;
            font-weight: 500;
            transition: background-color 0.3s;
        }
        
        .stButton > button:hover {
            background-color: #1559C7;
        }
        
        /* Secondary button styling */
        button[kind="secondary"] {
            background-color: white;
            color: #1971E5;
            border: 1px solid #1971E5;
        }
        
        button[kind="secondary"]:hover {
            background-color: #F0F7FF;
        }
        
        /* Container backgrounds */
        .stContainer {
            background-color: white;
            padding: 1.5rem;
            border-radius: 8px;
            margin: 1rem 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Headers */
        h1 {
            color: #1a1a1a;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        h2 {
            color: #2a2a2a;
            font-weight: 600;
            margin-top: 2rem;
            margin-bottom: 1rem;
        }
        
        h3 {
            color: #3a3a3a;
            font-weight: 600;
        }
        
        /* File uploader styling */
        .uploadedFile {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 0.75rem;
        }
        
        /* Info boxes */
        .stInfo {
            background-color: #E8F4FD;
            border-left: 4px solid #1971E5;
            padding: 1rem;
            border-radius: 4px;
        }
        
        /* Success messages */
        .stSuccess {
            background-color: #E8F5E9;
            border-left: 4px solid #4CAF50;
            padding: 1rem;
            border-radius: 4px;
        }
        
        /* Error messages */
        .stError {
            background-color: #FFEBEE;
            border-left: 4px solid #F44336;
            padding: 1rem;
            border-radius: 4px;
        }
        
        /* Warning messages */
        .stWarning {
            background-color: #FFF3E0;
            border-left: 4px solid #FF9800;
            padding: 1rem;
            border-radius: 4px;
        }
        
        /* Dataframe styling */
        .dataframe {
            background-color: white;
            border-radius: 6px;
        }
        
        /* Checkbox styling */
        .stCheckbox > label {
            font-weight: 500;
            color: #2a2a2a;
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            background-color: #F5F5F5;
            border-radius: 4px;
            font-weight: 500;
        }
        
        /* Text input styling */
        .stNumberInput > div > div > input {
            background-color: white;
        }
        
        /* Progress bar */
        .stProgress > div > div > div {
            background-color: #1971E5;
        }
        
        /* Spinner text */
        .stSpinner > div {
            color: #1971E5;
        }
        
        /* Remove Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Initialize session state for file handling
if 'files_uploaded' not in st.session_state:
    st.session_state.files_uploaded = False
if 'rfp_file' not in st.session_state:
    st.session_state.rfp_file = None
if 'proposal1_file' not in st.session_state:
    st.session_state.proposal1_file = None
if 'proposal2_file' not in st.session_state:
    st.session_state.proposal2_file = None
if 'stored_result' not in st.session_state:
    st.session_state.stored_result = None
if 'stored_df_results' not in st.session_state:
    st.session_state.stored_df_results = None
if 'stored_raw_results' not in st.session_state:
    st.session_state.stored_raw_results = []

st.title("RFP Proposal Evaluation System")
#st.markdown("Upload your RFP and two proposals to get score and reasoning")
st.markdown("---")

# --- File Upload Section (Outside form to avoid JS module issues) ---
st.header("Upload Documents")

rfp_file = st.file_uploader(
    "Upload RFP PDF", 
    type=["pdf"], 
    key="rfp_uploader",
    help="Upload the RFP document containing evaluation criteria"
)

col1, col2 = st.columns(2)
with col1:
    proposal1_file = st.file_uploader(
        "Upload Proposal 1 PDF", 
        type=["pdf"], 
        key="prop1_uploader",
        help="Upload the first proposal PDF"
    )
with col2:
    proposal2_file = st.file_uploader(
        "Upload Proposal 2 PDF", 
        type=["pdf"], 
        key="prop2_uploader",
        help="Upload the second proposal PDF"
    )

rfp_page_number = st.number_input(
    "Enter RFP Page Number for evaluation criteria", 
    min_value=0, 
    value=5, 
    step=1, 
    help="Enter the page number where the evaluation criteria/rubric is located in the RFP PDF."
)

# Store files in session state
if rfp_file is not None:
    st.session_state.rfp_file = rfp_file
if proposal1_file is not None:
    st.session_state.proposal1_file = proposal1_file
if proposal2_file is not None:
    st.session_state.proposal2_file = proposal2_file

# Evaluation button (centered, medium width)
left_col, mid_col, right_col = st.columns([3, 2, 3])
with mid_col:
    submitted = st.button("Start Evaluation", type="primary")

# Handle evaluation submission
if submitted:
    # Use files from current upload or session state
    current_rfp = rfp_file if rfp_file is not None else st.session_state.get('rfp_file')
    current_prop1 = proposal1_file if proposal1_file is not None else st.session_state.get('proposal1_file')
    current_prop2 = proposal2_file if proposal2_file is not None else st.session_state.get('proposal2_file')
    
    if not all([current_rfp, current_prop1, current_prop2]):
        st.error("Please upload all three required files (RFP, Proposal 1, Proposal 2).")
        st.info("Tip: Make sure all file uploaders show a file name before clicking 'Start Evaluation'.")
    else:
        try:
            st.info("Files uploaded successfully. Starting evaluation... this may take a few minutes for Jina embeddings and Kimi scoring.")
            
            # Reset file pointers to beginning
            if hasattr(current_rfp, 'seek'):
                current_rfp.seek(0)
            if hasattr(current_prop1, 'seek'):
                current_prop1.seek(0)
            if hasattr(current_prop2, 'seek'):
                current_prop2.seek(0)
            
            # Prepare files for multipart upload
            files = {
                'rfp_file': (current_rfp.name, current_rfp.getvalue(), 'application/pdf'),
                'proposal1_file': (current_prop1.name, current_prop1.getvalue(), 'application/pdf'),
                'proposal2_file': (current_prop2.name, current_prop2.getvalue(), 'application/pdf'),
            }
            
            # Prepare form data
            data = {
                'rfp_page_number': int(rfp_page_number)
            }
            
            # Send request to FastAPI backend
            with st.spinner("Processing... Chunking, Embedding, Storing in Zilliz, Retrieving, and Scoring with Kimi..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    status_text.text("Connecting to FastAPI backend...")
                    progress_bar.progress(10)
                    
                    response = requests.post(
                        FASTAPI_URL, 
                        files=files, 
                        data=data, 
                        timeout=600,  # 10 minute timeout
                        stream=False
                    )
                    
                    progress_bar.progress(50)
                    status_text.text("Processing response...")
                    
                    if response.status_code == 200:
                        result = response.json()
                        progress_bar.progress(100)
                        status_text.text("Complete!")
                        
                        st.success("Evaluation Complete!")
                        
                        # Display output directory info if available
                        if 'output_directory' in result:
                            st.info(f"Results saved to: `{result['output_directory']}`")
                        
                        # Display results table
                        if 'results' in result and result['results']:
                            df_results = pd.DataFrame(result['results'])

                            # Persist in session_state to survive reruns
                            st.session_state.stored_result = result
                            st.session_state.stored_df_results = df_results
                            st.session_state.stored_raw_results = result.get('raw_results', [])
                            
                            st.markdown("### Evaluation Results")
                            st.dataframe(df_results, use_container_width=True, height=400)

                            # COMMENTED OUT: Reference Documents section - Uncomment if client wants to show reference chunks
                            # Use raw_results array (long-form) for references, which contains References_File paths
                            # raw_results = result.get('raw_results', [])
                            # if raw_results:
                            #     st.markdown("### Reference Documents")
                            #     st.caption("Toggle to view the exact retrieved proposal snippets and page numbers used for scoring.")
                            #
                            #     for ridx, r in enumerate(raw_results):
                            #         main_crit = r.get('Main_Criterion', '')
                            #         sub_crit = r.get('Sub_Criterion', '')
                            #         proposal = r.get('Proposal', '')
                            #         references_file = r.get('References_File', '')
                            #
                            #         with st.container():
                            #             st.markdown(f"**Criterion:** {main_crit} — {sub_crit}  \n**Proposal:** {proposal}")
                            #             toggle_key = f"refs_toggle_{ridx}_{proposal}"
                            #             show_refs = st.checkbox("Show References", key=toggle_key, value=False, disabled=not bool(references_file))
                            #             if show_refs:
                            #                 if not references_file or not os.path.exists(references_file):
                            #                     st.warning("Reference file not found on server.")
                            #                 else:
                            #                     try:
                            #                         with open(references_file, "r", encoding="utf-8") as rf:
                            #                             refs = json.load(rf)
                            #
                            #                         for prop_key in ['Prop_1', 'Prop_2']:
                            #                             chunks = refs.get(prop_key, [])
                            #                             if not chunks:
                            #                                 continue
                            #                             with st.expander(f"{prop_key} - {len(chunks)} reference chunk(s)"):
                            #                                 for i, ch in enumerate(chunks, start=1):
                            #                                     page_num = ch.get("page_number", "N/A")
                            #                                     text = ch.get("text", "")
                            #                                     st.markdown(f"**Page:** {page_num}")
                            #                                     st.text_area(f"Snippet {i}", value=text, height=150, key=f"{toggle_key}_{prop_key}_{i}", label_visibility="collapsed")
                            #                     except Exception as e:
                            #                         st.error(f"Failed to load references: {e}")
                            
                            # Download button for results
                            csv = df_results.to_csv(index=False)
                            st.download_button(
                                label="Download Results as CSV",
                                data=csv,
                                file_name="evaluation_results.csv",
                                mime="text/csv"
                            )
                            
                            # COMMENTED OUT: Average Scores Comparison chart - Uncomment if client wants to show score comparison graph
                            # Display a summary chart if scores are available
                            # score_cols = [col for col in df_results.columns if 'Score' in col]
                            # if score_cols:
                            #     try:
                            #         # Extract numeric scores
                            #         score_data = {}
                            #         for col in score_cols:
                            #             score_data[col] = pd.to_numeric(df_results[col], errors='coerce')
                            #         
                            #         if score_data:
                            #             summary_df = pd.DataFrame(score_data).mean().sort_values(ascending=False)
                            #             st.markdown("### Average Scores Comparison")
                            #             st.bar_chart(summary_df)
                            #     except Exception as chart_error:
                            #         st.warning(f"Could not generate chart: {chart_error}")
                        else:
                            st.warning("No results found in response.")
                    
                    else:
                        progress_bar.progress(100)
                        error_detail = "Unknown error"
                        try:
                            error_response = response.json()
                            error_detail = error_response.get('detail', str(response.text))
                        except:
                            error_detail = response.text[:500] if response.text else "No error details available"
                        
                        st.error(f"Evaluation Failed (Status: {response.status_code})")
                        st.error(f"Error details: {error_detail}")
                        st.info("Make sure the FastAPI server is running on port 8000")
                
                except requests.exceptions.Timeout:
                    st.error("Request timed out. The evaluation is taking longer than expected.")
                    st.info("Try reducing the RFP page number or check if the FastAPI server is still running.")
                
                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to the FastAPI service.")
                    st.info("Please ensure the FastAPI server is running:")
                    st.code("uvicorn fast_api_app:app --reload", language="bash")
                
                except requests.exceptions.RequestException as e:
                    st.error(f"Request failed: {str(e)}")
                    st.info("Check the FastAPI server logs for more details.")
                
                finally:
                    progress_bar.empty()
                    status_text.empty()
        
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            st.exception(e)
            st.info("Please check the browser console and Streamlit logs for more details.")
            
            # Show traceback in expander for debugging
            with st.expander("Show detailed error traceback"):
                st.code(traceback.format_exc(), language="python")

# Render persisted results if available (prevents disappearing on rerun)
# if st.session_state.stored_result and isinstance(st.session_state.stored_df_results, pd.DataFrame):
#     result = st.session_state.stored_result
#     df_results = st.session_state.stored_df_results
#     raw_results = st.session_state.stored_raw_results or []

#     st.header("2. Results")

#     if 'output_directory' in result:
#         st.info(f"📁 Results saved to: `{result['output_directory']}`")

#     if not df_results.empty:
#         st.subheader("Final Proposal Comparison Scores and Reasons")
#         st.dataframe(df_results, use_container_width=True, height=400)

#         csv = df_results.to_csv(index=False)
#         st.download_button(
#             label="📥 Download Results as CSV",
#             data=csv,
#             file_name="evaluation_results.csv",
#             mime="text/csv"
#         )

#         score_cols = [col for col in df_results.columns if 'Score' in col]
#         if score_cols:
#             try:
#                 score_data = {col: pd.to_numeric(df_results[col], errors='coerce') for col in score_cols}
#                 if score_data:
#                     summary_df = pd.DataFrame(score_data).mean().sort_values(ascending=False)
#                     st.subheader("Average Scores Comparison")
#                     st.bar_chart(summary_df)
#             except Exception as chart_error:
#                 st.warning(f"Could not generate chart: {chart_error}")

#     if raw_results:
#         st.subheader("References (on-demand)")
#         st.caption("Toggle to view the exact retrieved proposal snippets and page numbers used for scoring.")

#         for ridx, r in enumerate(raw_results):
#             main_crit = r.get('Main_Criterion', '')
#             sub_crit = r.get('Sub_Criterion', '')
#             proposal = r.get('Proposal', '')
#             references_file = r.get('References_File', '')

#             with st.container():
#                 st.markdown(f"- Criterion: {main_crit} — {sub_crit}  \n- Proposal: {proposal}")
#                 toggle_key = f"persist_refs_toggle_{ridx}_{proposal}"
#                 show_refs = st.checkbox("Show references", key=toggle_key, value=False, disabled=not bool(references_file))
#                 if show_refs:
#                     if not references_file or not os.path.exists(references_file):
#                         st.warning("Reference file not found on server.")
#                     else:
#                         try:
#                             with open(references_file, "r", encoding="utf-8") as rf:
#                                 refs = json.load(rf)

#                             for prop_key in ['Prop_1', 'Prop_2']:
#                                 chunks = refs.get(prop_key, [])
#                                 if not chunks:
#                                     continue
#                                 with st.expander(f"{prop_key} — {len(chunks)} reference chunk(s)"):
#                                     for i, ch in enumerate(chunks, start=1):
#                                         page_num = ch.get("page_number", "N/A")
#                                         text = ch.get("text", "")
#                                         st.markdown(f"Page: {page_num}")
#                                         st.text_area(f"Snippet {i}", value=text, height=150, key=f"{toggle_key}_{prop_key}_{i}")
#                         except Exception as e:
#                             st.error(f"Failed to load references: {e}")

# To run Streamlit: streamlit run streamlit_app.py