import streamlit as st
import pandas as pd
import google.generativeai as genai
from pypdf import PdfReader
import re
import io
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Greek Curriculum Generator", layout="wide", page_icon="🇬🇷")

# 🛠️ MODEL CONFIGURATION
# Change this string to 'gemini-pro-latest', 'gemini-1.5-pro', or your specific access string.
MODEL_NAME = "gemini-pro-latest" 

# --- SESSION STATE SETUP ---
if 'locked_config' not in st.session_state: st.session_state['locked_config'] = None
if 'syllabus_df' not in st.session_state: st.session_state['syllabus_df'] = None
if 'generated_lessons' not in st.session_state: st.session_state['generated_lessons'] = {}
if 'analyzed_curriculum' not in st.session_state: st.session_state['analyzed_curriculum'] = {}

# --- HELPER FUNCTIONS ---

def get_model(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)

def extract_pdf_text(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def analyze_curriculum_llm(text, api_key):
    """Step 1: Extracts structured data from raw PDF text."""
    model = get_model(api_key)
    prompt = f"""
    ACT AS: Expert Pedagogical Analyst for Greek (Modersmål).
    TASK: Analyze the following Swedish curriculum text and extract 4 key data points.
    
    OUTPUT FORMAT: Return ONLY a valid Python Dictionary string (JSON-like) with these keys:
    {{
        "audience": "Target grade and student profile",
        "level": "Estimated CEFR level (e.g., A1, B2)",
        "grading": "Summary of Grade E criteria",
        "themes": "List of central themes (comma separated)"
    }}

    CURRICULUM TEXT:
    {text[:10000]} 
    """
    response = model.generate_content(prompt)
    # Clean up markdown if model returns ```json ... ```
    clean_text = response.text.replace("```json", "").replace("```python", "").replace("```", "")
    try:
        return eval(clean_text) # Safe enough for this specific constrained context
    except:
        return {"audience": "Error parsing", "level": "Error", "grading": "Error", "themes": "Error"}

def generate_skeleton_llm(config, api_key):
    """Step 2: Creates the 34-week plan based on the config."""
    model = get_model(api_key)
    prompt = f"""
    ACT AS: Curriculum Architect.
    CONTEXT: {config}
    TASK: Create a 34-week academic syllabus for this class.
    
    REQUIREMENTS:
    - Distribute the 'themes' logically across 34 weeks.
    - Include Grammar progression.
    - OUTPUT FORMAT: A raw text list with exactly 34 lines. Each line must be: "Theme | Grammar Focus"
    
    Example:
    Myths: Zeus | Noun Gender
    Geography: Athens | Adjectives
    ...
    """
    response = model.generate_content(prompt)
    return response.text.strip().split("\n")

def generate_lesson_material(prompt_payload, api_key):
    """Step 3: The Workbench generator."""
    model = get_model(api_key)
    response = model.generate_content(prompt_payload)
    return response.text

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔑 Engine Room")
    api_key = st.text_input("Gemini API Key", type="password")
    if not api_key:
        st.warning("Please enter API Key to proceed.")
    
    st.divider()
    st.caption(f"Using Model: {MODEL_NAME}")

# --- MAIN APP ---
st.title("🇬🇷 Greek Modersmål Generator (Live)")

# ==========================================
# STEP 1: CALIBRATION (LIVE)
# ==========================================
with st.expander("Step 1: Curriculum Calibration", expanded=not st.session_state['locked_config']):
    st.info("Upload the Skolverket PDF to extract the 'Curriculum DNA'.")
    
    uploaded_curriculum = st.file_uploader("Upload Syllabus (PDF)", type='pdf')
    
    if uploaded_curriculum and api_key and not st.session_state['analyzed_curriculum']:
        if st.button("Analyze Document"):
            with st.spinner("Reading PDF & Extracting Parameters..."):
                raw_text = extract_pdf_text(uploaded_curriculum)
                if raw_text:
                    analysis = analyze_curriculum_llm(raw_text, api_key)
                    st.session_state['analyzed_curriculum'] = analysis
                    st.rerun()

    # The Editable Form (Pre-filled by AI)
    if st.session_state['analyzed_curriculum']:
        st.success("Analysis Complete. Verify below:")
        with st.form("calibration_form"):
            data = st.session_state['analyzed_curriculum']
            c1, c2 = st.columns(2)
            with c1:
                audience = st.text_input("Target Audience", value=data.get('audience', ''))
                level = st.text_input("CEFR Level", value=data.get('level', ''))
            with c2:
                grading = st.text_area("Grade E Criteria", value=data.get('grading', ''))
                themes = st.text_area("Core Themes", value=data.get('themes', ''))
            
            if st.form_submit_button("✅ Lock Configuration"):
                st.session_state['locked_config'] = {
                    "audience": audience, "level": level, "grading": grading, "themes": themes
                }
                st.rerun()

# ==========================================
# STEP 2: SKELETON (LIVE)
# ==========================================
if st.session_state['locked_config']:
    st.markdown("---")
    st.header("Step 2: The Year Plan")
    
    # Generate Draft Button
    if st.session_state['syllabus_df'] is None:
        if st.button("Generate 34-Week Skeleton"):
            if not api_key:
                st.error("Need API Key")
            else:
                with st.spinner("Architecting the year..."):
                    lines = generate_skeleton_llm(st.session_state['locked_config'], api_key)
                    
                    # Parse the Pipe-separated lines
                    structured_data = []
                    for i, line in enumerate(lines):
                        if "|" in line:
                            parts = line.split("|")
                            theme = parts[0].strip()
                            grammar = parts[1].strip() if len(parts) > 1 else "Review"
                            structured_data.append({"Week": f"Week {i+1}", "Theme": theme, "Grammar Focus": grammar, "Status": "🔴"})
                    
                    # Fallback if AI fails format
                    if not structured_data:
                        structured_data = [{"Week": f"Week {i+1}", "Theme": "Topic", "Grammar Focus": "Grammar", "Status": "🔴"} for i in range(34)]

                    st.session_state['syllabus_df'] = pd.DataFrame(structured_data)
                    st.rerun()

    # The Editable Grid
    if st.session_state['syllabus_df'] is not None:
        edited_df = st.data_editor(
            st.session_state['syllabus_df'],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Week": st.column_config.TextColumn(disabled=False),
                "Theme": st.column_config.TextColumn("Topic"),
                "Status": st.column_config.TextColumn(disabled=True),
            }
        )
        st.session_state['syllabus_df'] = edited_df
        
        if st.button("Reset Syllabus"):
            st.session_state['syllabus_df'] = None
            st.rerun()

# ==========================================
# STEP 3: WORKBENCH (LIVE)
# ==========================================
if st.session_state['syllabus_df'] is not None and not st.session_state['syllabus_df'].empty:
    st.markdown("---")
    st.header("Step 3: The Workbench")
    
    # Select Week
    week_options = st.session_state['syllabus_df']['Week'].tolist()
    week_to_edit = st.selectbox("Select Week to Design:", week_options)
    
    # Get Data
    row = st.session_state['syllabus_df'].loc[st.session_state['syllabus_df']['Week'] == week_to_edit].iloc[0]
    
    st.markdown(f"#### 🛠️ Designing: {row['Theme']}")
    
    with st.form(key=f"wb_{week_to_edit}"):
        c1, c2 = st.columns(2)
        with c1:
            custom_topic = st.text_input("Topic", value=row['Theme'])
            custom_grammar = st.text_input("Grammar", value=row['Grammar Focus'])
            accessibility = st.checkbox("♿ Adapt for Learning Difficulties")
        with c2:
            teacher_notes = st.text_area("Teacher Instructions")
        
        st.markdown("---")
        st.subheader("📚 Source Material")
        uploaded_context = st.file_uploader("Upload Text/PDF Context", accept_multiple_files=True)
        
        generate_btn = st.form_submit_button("⚡ Generate Lesson Materials")

    if generate_btn and api_key:
        # Process Uploads
        source_text = ""
        if uploaded_context:
            for f in uploaded_context:
                # Handle PDF vs Text
                if f.type == "application/pdf":
                    source_text += f"\nSOURCE ({f.name}):\n{extract_pdf_text(f)}\n"
                else:
                    source_text += f"\nSOURCE ({f.name}):\n{f.getvalue().decode('utf-8')}\n"

        # Build Prompt
        instruction_mode = "INSTRUCTIONS: Use SOURCE MATERIAL strictly." if source_text else "INSTRUCTIONS: Write creative Greek text."
        access_mode = "CONSTRAINT: Dyslexia-friendly, simple sentences." if accessibility else ""
        
        full_prompt = f"""
        CONTEXT: {st.session_state['locked_config']}
        WEEK: {week_to_edit} | TOPIC: {custom_topic} | GRAMMAR: {custom_grammar}
        TEACHER NOTES: {teacher_notes}
        ACCESSIBILITY: {access_mode}
        {instruction_mode}
        
        SOURCE MATERIAL:
        {source_text[:20000]} 

        OUTPUT: Generte XML with <TEACHER>, <STUDENT_TEXT> (in Greek), <STUDENT_EXERCISES> (in Greek).
        """
        
        with st.spinner("Calling Gemini..."):
            output = generate_lesson_material(full_prompt, api_key)
            st.session_state['generated_lessons'][week_to_edit] = output
            
            # Update Status
            idx = st.session_state['syllabus_df'].index[st.session_state['syllabus_df']['Week'] == week_to_edit][0]
            st.session_state['syllabus_df'].at[idx, 'Status'] = "🟢"
            st.rerun()

    # Preview
    if week_to_edit in st.session_state['generated_lessons']:
        st.divider()
        raw = st.session_state['generated_lessons'][week_to_edit]
        
        # Robust Parsing
        try:
            t_guide = re.search(r'<TEACHER>(.*?)</TEACHER>', raw, re.DOTALL).group(1).strip()
        except: t_guide = "Error parsing Teacher Guide"
        
        try:
            s_text = re.search(r'<STUDENT_TEXT>(.*?)</STUDENT_TEXT>', raw, re.DOTALL).group(1).strip()
        except: s_text = "Error parsing Student Text"
        
        try:
            exercises = re.search(r'<STUDENT_EXERCISES>(.*?)</STUDENT_EXERCISES>', raw, re.DOTALL).group(1).strip()
        except: exercises = "Error parsing Exercises"

        t1, t2, t3 = st.tabs(["Teacher Guide", "Greek Text", "Exercises"])
        with t1: st.text_area("Guide", t_guide, height=300, key=f"t_{week_to_edit}")
        with t2: st.text_area("Text", s_text, height=300, key=f"s_{week_to_edit}")
        with t3: st.text_area("Exercises", exercises, height=300, key=f"e_{week_to_edit}")