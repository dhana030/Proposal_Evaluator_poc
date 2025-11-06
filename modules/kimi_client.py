import os
from groq import Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Kimi client (using Groq SDK for Moonshot/Kimi model)
client = Client(api_key=os.getenv("KIMI_API_KEY"))
KIMI_MODEL = "moonshotai/kimi-k2-instruct-0905"

def extract_table_from_kimi(text: str) -> str:
    """
    Generates an evaluation parameter table/rubric from the RFP text.
    
    """
    prompt = f"""
    You are an AI proposal evaluator assistant.

    From the following Arabic text (which may contain evaluation parameters or scoring criteria),
    extract and structure the information into a **markdown table** with these columns:

    - 'Main Criterion (with English translation in brackets)'
    - 'Weight % (if mentioned)'
    - 'Sub-Criterion (with English translation in brackets)'
    - 'Sub-Weight % (if mentioned)'
    - 'Expectation / Evaluation Rubric'

    The 'Expectation / Evaluation Rubric' column must be generated **by you** based on the meaning of the parameters.
    For each sub-criterion, define a **multi-level rubric** like this:

    - **Excellent (Full Marks):** [Describe ideal submission]
    - **Good (Partial Marks):** [Describe acceptable but incomplete submission]
    - **Insufficient (Low/No Marks):** [Describe non-compliant submission]

    Keep Arabic text with English translations in brackets.
    Keep formatting clean and concise.

    Arabic RFP content to analyze:
    -------------------------------
    {text}
    -------------------------------
    """

    try:
        completion = client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[
                {"role": "system", "content": "You are a bilingual proposal evaluation expert skilled in Arabic-English analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        return completion.choices[0].message.content

    except Exception as e:
        print(f"❌ Kimi error during table extraction: {e}")
        return None

def score_proposals_with_rag(
    criterion: str, 
    rubric: str, 
    proposal_1_context: str, 
    proposal_2_context: str, 
    num_proposals: int
) -> str:
    """
    Uses the Kimi model to compare proposals against a rubric and provide a score/reason.
    """
    
    # Construct proposal context strings dynamically
    proposal_contexts = {
        1: f"**PROPOSAL 1 CONTEXT:**\n{proposal_1_context}",
        2: f"**PROPOSAL 2 CONTEXT:**\n{proposal_2_context}"
    }

    # Generate an evaluation prompt
    prompt = f"""
    You are a proposal scoring expert. Your task is to evaluate {num_proposals} proposals based on a specific criterion and rubric.

    **Evaluation Criterion:** {criterion}

    **Required Rubric/Expectation:**
    {rubric}

    **--- Proposal Contexts ---**
    {proposal_contexts[1]}
    
    ---
    {proposal_contexts[2]}
    **--- End of Contexts ---**

    Analyze the provided context from Proposal 1 and Proposal 2 against the Required Rubric. 
    
    Generate your output as a single, clean **markdown table** with exactly these columns:
    
    1. **Proposal** (e.g., Proposal 1, Proposal 2)
    2. **Score (0-5)** (A numerical score from 0 to 5, where 5 is Excellent and 0 is Insufficient)
    3. **Reasoning (Arabic)** (A detailed justification in **Arabic**)
    4. **Reasoning (English)** (The same justification in clear English)
    
    Do NOT include any text, headers, or explanations outside the markdown table. The table is the only output.
    """

    try:
        completion = client.chat.completions.create(
            model=KIMI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert bilingual analyst who compares and scores documents against a formal rubric."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1 # Low temperature for factual scoring
        )

        return completion.choices[0].message.content
        
    except Exception as e:
        print(f"❌ Kimi scoring error: {e}")
        return None