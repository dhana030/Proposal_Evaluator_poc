# Proposal Evaluator - Complete Flow Explanation

## Overview
This document explains how the proposal evaluation system works, addressing common misunderstandings.



## 📋 Complete Flow Breakdown

### **STEP 1: RFP Rubric Creation** 
*(File: `main.py` lines 29-56)*

#### 1a. Extract RFP Text from PDF
- **Location:** `main.py:32` → `utils.extract_text_from_pdf_page()`
- **What happens:**
  - Reads `data/rfp.pdf` 
  - Extracts text from a specific page (default: page 5)
  - Uses PyMuPDF (fitz) to extract raw text
- **Output:** Raw text string from the PDF page

#### 1b. Send RFP Text to Kimi for Rubric Generation
- **Location:** `main.py:39` → `kimi_client.extract_table_from_kimi()`
- **What happens:**
  - Takes the extracted RFP text
  - Sends it to Kimi AI model via Groq API
  - Kimi analyzes the Arabic text and generates a structured markdown table
  - The table contains:
    - Main Criterion
    - Weight %
    - Sub-Criterion  
    - Sub-Weight %
    - Expectation / Evaluation Rubric
- **Output:** Markdown table string with evaluation criteria

#### 1c. Save Rubric to File (for reference)
- **Location:** `main.py:46-48`
- **What happens:**
  - Saves the Kimi-generated markdown to `outputs/rfp_rubric_raw.md`
  - This is just for **review/debugging purposes**
  - The system does NOT read from this file during execution

#### 1d. Parse Rubric into DataFrame
- **Location:** `main.py:52` → `utils.extract_criteria_from_rubric()`
- **What happens:**
  - Parses the markdown table into a pandas DataFrame
  - Extracts columns: `Main_Criterion`, `Sub_Criterion`, `Rubric`
  - Each row represents one evaluation criterion
- **Output:** DataFrame with criteria rows (this drives the evaluation loop)

---

### **STEP 2: Proposal Ingestion** 
*(File: `main.py` lines 62-69)*

#### 2a. Initialize Milvus/Zilliz Collection
- **Location:** `main.py:63` → `proposal_ingestor.initialize_milvus()`
- **What happens:**
  - Connects to Zilliz Cloud (vector database)
  - Creates a collection named `proposal_chunks`
  - Sets up schema for storing: proposal_id, page_number, chunk_index, text_content, embedding

#### 2b. Ingest Each Proposal
- **Location:** `main.py:68-69` → `proposal_ingestor.ingest_proposal()`
- **What happens for each proposal PDF:**
  1. **Extract text** from all pages of the proposal PDF
  2. **Chunk the text** using `recursive_chunking()` (chunk_size=512, overlap=100)
  3. **Generate embeddings** using Jina Embeddings API for each chunk
  4. **Store in Milvus:**
     - Vector embeddings
     - Metadata (proposal_id, page_number, chunk_index, text_content)
- **Output:** All proposal chunks stored in vector database with embeddings

---

### **STEP 3: RAG-Based Evaluation Loop** 
*(File: `main.py` line 77 → `evaluator.run_evaluation_loop()`)*

This is the **core evaluation loop** that processes each criterion row.

#### For Each Criterion Row in the Rubric DataFrame:

##### 3a. Retrieve Relevant Context (RAG)
- **Location:** `evaluator.py:94` → `evaluator.retrieve_context()`
- **What happens:**
  1. **Embed the criterion:**
     - Takes: `"{criterion}. {rubric}"` (e.g., "Company Experience - KSA projects...")
     - Embeds it using Jina Embeddings API
  2. **Vector search in Milvus:**
     - Searches the entire collection using cosine similarity
     - Retrieves top K chunks (default: 5 chunks per proposal)
     - Searches across ALL proposals simultaneously
  3. **Aggregate context by proposal:**
     - Groups retrieved chunks by `proposal_id` (Prop_1, Prop_2)
     - Concatenates chunks for each proposal
     - Returns: `{"Prop_1": "chunk1\n---\nchunk2...", "Prop_2": "chunk3\n---\nchunk4..."}`
- **Output:** Relevant text context for each proposal related to the criterion

##### 3b. Send to Kimi for Scoring
- **Location:** `evaluator.py:101` → `kimi_client.score_proposals_with_rag()`
- **What happens:**
  1. Constructs a prompt with:
     - The evaluation criterion
     - The rubric/expectation
     - Retrieved context from Prop_1
     - Retrieved context from Prop_2
  2. Sends to Kimi AI model
  3. Kimi evaluates each proposal against the rubric
  4. Returns a markdown table with:
     - Proposal name
     - Score (0-5)
     - Reasoning (Arabic)
     - Reasoning (English)

##### 3c. Parse Scoring Results
- **Location:** `evaluator.py:121-167`
- **What happens:**
  1. Parses the markdown table returned by Kimi
  2. Extracts scores and reasoning for each proposal
  3. Appends to `final_evaluation_results` list
  4. Saves raw markdown to `outputs/kimi_scores/` for auditing

##### 3d. Persist Retrieved Evidence
- **Location:** `evaluator.py:92-138`
- **What happens:**
  1. For each criterion, the retrieved Milvus hits are grouped by proposal and ranked (top *k* per proposal after deduplication).
  2. Chunks are saved as JSON in `outputs/<timestamp>/references/NNN_<criterion>.json`. Each entry contains:
     - `proposal_id`
     - `page_number`
     - Exact chunk text used as evidence
  3. The path to the saved JSON is added to the per-proposal result as `References_File`.  
     *(Currently hidden in the UI but kept for future auditing or drill-down.)*

##### 3e. Repeat for Next Criterion
- The loop continues for all rows in the rubric DataFrame
- Each criterion is evaluated independently

---

### **STEP 4: Final Output**
*(File: `main.py` lines 86-129)*

- Converts results to a pivot table format
- Saves to Excel file: `outputs/evaluation_results_page_{page_number}.xlsx`
- Saves raw results (including `References_File`) to:
  - `outputs/<timestamp>/raw_results.csv`
  - `outputs/<timestamp>/raw_results.json`

---

## 🔄 Summary Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: RFP Rubric Creation                                 │
├─────────────────────────────────────────────────────────────┤
│ 1. Read PDF: data/rfp.pdf (page 5)                         │
│    ↓                                                         │
│ 2. Extract text from PDF page                               │
│    ↓                                                         │
│ 3. Send text to Kimi → Generate rubric table                │
│    ↓                                                         │
│ 4. Save to: outputs/rfp_rubric_raw.md (for reference only)  │
│    ↓                                                         │
│ 5. Parse table → DataFrame (rubric_df)                      │
│    Each row = one evaluation criterion                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Proposal Ingestion                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. Initialize Milvus/Zilliz collection                      │
│    ↓                                                         │
│ 2. For each proposal PDF:                                   │
│    - Extract text from all pages                            │
│    - Chunk text (512 chars, 100 overlap)                    │
│    - Generate embeddings (Jina API)                         │
│    - Store in Milvus with metadata                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Evaluation Loop (for EACH criterion row)            │
├─────────────────────────────────────────────────────────────┤
│ For each row in rubric_df:                                  │
│                                                              │
│  ┌──────────────────────────────────────────────┐          │
│  │ 3a. RAG Retrieval                            │          │
│  │ - Embed criterion + rubric                   │          │
│  │ - Vector search in Milvus                    │          │
│  │ - Get top K chunks from Prop_1 and Prop_2    │          │
│  │ - Return context for each proposal           │          │
│  └──────────────────────────────────────────────┘          │
│              ↓                                               │
│  ┌──────────────────────────────────────────────┐          │
│  │ 3b. Kimi Scoring                             │          │
│  │ - Send criterion, rubric, and contexts       │          │
│  │ - Kimi evaluates each proposal               │          │
│  │ - Returns scores (0-5) and reasoning         │          │
│  └──────────────────────────────────────────────┘          │
│              ↓                                               │
│  ┌──────────────────────────────────────────────┐          │
│  │ 3c. Parse Results                            │          │
│  │ - Extract scores and reasoning               │          │
│  │ - Add to final_evaluation_results            │          │
│  └──────────────────────────────────────────────┘          │
│                                                              │
│ Repeat for next criterion...                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Final Output                                        │
├─────────────────────────────────────────────────────────────┤
│ - Pivot results table                                       │
│ - Save to Excel: evaluation_results_page_5.xlsx            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Points to Remember

1. **RFP text source:** Comes directly from `data/rfp.pdf`, NOT from `rfp_rubric_raw.md`
2. **rfp_rubric_raw.md:** This is an OUTPUT file saved for reference/debugging
3. **Rubric DataFrame:** Drives the evaluation loop - each row = one criterion to evaluate
4. **RAG retrieval:** For each criterion, the system searches for relevant chunks in ALL proposals
5. **Proposal chunks:** Stored in Milvus with embeddings, retrieved using vector similarity search
6. **Scoring:** Kimi evaluates retrieved context against the rubric for each proposal
7. **Loop structure:** The rubric DataFrame is iterated row-by-row, not the proposal chunks

---

## 📁 File Roles

- **`main.py`**: Orchestrates the entire flow
- **`modules/kimi_client.py`**: 
  - `extract_table_from_kimi()`: Generates rubric from RFP text
  - `score_proposals_with_rag()`: Scores proposals against rubric
- **`modules/utils.py`**: 
  - `extract_text_from_pdf_page()`: Extracts text from PDF
  - `extract_criteria_from_rubric()`: Parses markdown table to DataFrame
- **`modules/proposal_ingestor.py`**: Chunks and embeds proposals, stores in Milvus
- **`modules/evaluator.py`**: 
  - `retrieve_context()`: RAG retrieval using vector search
  - `run_evaluation_loop()`: Main evaluation loop
- **`outputs/rfp_rubric_raw.md`**: Output file (reference only, not read during execution)

---

## 🔍 How the Table is Looped

The **rubric DataFrame** (created from Kimi's markdown table) is what gets looped:

```python
# In evaluator.py, line 87
for index, row in rubric_df.iterrows():
    criterion = f"{row['Main_Criterion']} - {row['Sub_Criterion']}"
    rubric = row['Rubric']
    
    # For THIS criterion, retrieve relevant chunks from proposals
    context = retrieve_context(milvus_collection, criterion_text=f"{criterion}. {rubric}")
    
    # Send contexts to Kimi for scoring
    scoring_table_markdown = score_proposals_with_rag(...)
```

**NOT** the proposal chunks - those are retrieved dynamically based on the criterion being evaluated.

