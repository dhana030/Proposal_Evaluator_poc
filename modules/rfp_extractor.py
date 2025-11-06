# import fitz  # PyMuPDF
# import os, json
# from groq import Client

# # --- Initialize Kimi client ---
# client = Client(api_key="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")

# # ---------- PDF TEXT EXTRACTION ----------
# def extract_text_from_pdf_page(pdf_path, page_number):
#     """Extracts text from a single page of a PDF file."""
#     try:
#         with fitz.open(pdf_path) as doc:
#             if page_number < 0 or page_number >= len(doc):
#                 print(f"❌ Error: Page number {page_number} is out of bounds. PDF has {len(doc)} pages.")
#                 return None
#             page = doc[page_number]
#             text = page.get_text("text")
#             return text.strip()
#     except Exception as e:
#         print(f"❌ Error extracting text from {pdf_path}: {e}")
#         return None


# # ---------- SEND TO KIMI MODEL ----------
# def extract_table_from_kimi(text):
#     """Sends extracted Arabic RFP text to Kimi model to generate an evaluation parameter table with a rubric."""
#     prompt = f"""
#     You are an AI proposal evaluator assistant.

#     From the following Arabic text (which may contain evaluation parameters or scoring criteria),
#     extract and structure the information into a **markdown table** with these columns:

#     - 'Main Criterion (with English translation in brackets)'
#     - 'Weight % (if mentioned)'
#     - 'Sub-Criterion (with English translation in brackets)'
#     - 'Sub-Weight % (if mentioned)'
#     - 'Expectation / Evaluation Rubric'

#     The 'Expectation / Evaluation Rubric' column must be generated **by you** based on the meaning of the parameters.
#     For each sub-criterion, define a **multi-level rubric** like this:

#     - **Excellent (Full Marks):** [Describe ideal submission]
#     - **Good (Partial Marks):** [Describe acceptable but incomplete submission]
#     - **Insufficient (Low/No Marks):** [Describe non-compliant submission]

#     Keep Arabic text with English translations in brackets.
#     Keep formatting clean and concise.

#     Arabic RFP content to analyze:
#     -------------------------------
#     {text}
#     -------------------------------
#     """

#     try:
#         completion = client.chat.completions.create(
#             model="moonshotai/kimi-k2-instruct-0905",
#             messages=[
#                 {"role": "system", "content": "You are a bilingual proposal evaluation expert skilled in Arabic-English analysis."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.2,
#         )

#         return completion.choices[0].message.content

#     except Exception as e:
#         print(f"❌ Kimi error during table extraction: {e}")
#         return None


# # ---------- MAIN EXECUTION ----------
# if __name__ == "__main__":
#     # 🔹 Step 1: Upload file (works in Colab or Jupyter)
#     try:
#         from google.colab import files
#         print("📂 Please upload your Arabic RFP PDF file...")
#         uploaded = files.upload()
#         pdf_path = list(uploaded.keys())[0]
#         print(f"✅ File uploaded: {pdf_path}")
#     except Exception:
#         # If not in Colab, ask user manually
#         pdf_path = input("Enter path to your Arabic RFP PDF file: ").strip()

#     # 🔹 Step 2: Ask for page number
#     try:
#         page_number = int(input("Enter the page number to extract (starting from 0): "))
#     except ValueError:
#         print("❌ Invalid page number.")
#         exit()

#     # 🔹 Step 3: Extract text from PDF page
#     extracted_text = extract_text_from_pdf_page(pdf_path, page_number)
#     if not extracted_text:
#         print("❌ No text extracted from PDF page.")
#         exit()

#     print("\n✅ Extracted text from page", page_number)
#     print("-" * 60)
#     print(extracted_text[:1000])  # show only first 1000 chars

#     # 🔹 Step 4: Send to Kimi for rubric generation
#     print("\n🔍 Sending to Kimi for rubric generation...")
#     result = extract_table_from_kimi(extracted_text)

#     if result:
#         print("\n✅ Kimi Evaluation Table & Rubric:\n")
#         print(result)
#     else:
#         print("❌ Failed to generate evaluation table from Kimi.")
