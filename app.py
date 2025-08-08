import gradio as gr
import fitz
import google.generativeai as genai
import json
import matplotlib.pyplot as plt
import time
import numpy as np
from urllib.parse import quote
import os # Make sure os is imported

# --- The rest of your functions remain the same ---
# (extract_text_from_pdf, analyze_with_gemini, etc.)
# ... (copy all your functions here) ...

def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file, limited to the first 5 pages."""
    if not pdf_file: return ""
    try:
        doc = fitz.open(pdf_file.name)
        text = "".join(page.get_text() for page_num, page in enumerate(doc) if page_num < 5)
        return text
    except Exception as e:
        return f"Error reading PDF: {e}"

def analyze_with_gemini(resume_text, jd_text):
    """
    Analyzes documents with a new prompt to generate tailored suggestions.
    """
    # IMPORTANT: Use os.environ.get() to read the key on Render
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return False, "Gemini API Key is not configured on the server."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = f"""
        You are an expert HR analyst and career coach. Your task is to analyze a resume and a job description.
        1.  From the job description, extract "jd_technical_skills" and "jd_soft_skills".
        2.  From the resume, extract "resume_technical_skills".
        3.  Based on the comparison, generate a list of 2-3 specific, actionable "suggestions" for improving the resume. These suggestions should be concise and tell the user *how* to integrate missing skills. For example: "Consider adding a project where you used Python and Pandas for data analysis to match the job's requirements."
        4.  IMPORTANT: Focus only on actual skills. Ignore vague phrases.
        5.  Return a single JSON object with four keys: "jd_technical_skills", "jd_soft_skills", "resume_technical_skills", and "suggestions".

        Resume Text:
        ---
        {resume_text}
        ---

        Job Description Text:
        ---
        {jd_text}
        ---

        Provide only the raw JSON object in your response.
        """

        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        parsed_json = json.loads(cleaned_response)

        jd_technical = set(skill.lower() for skill in parsed_json.get("jd_technical_skills", []))
        jd_soft = set(skill.lower() for skill in parsed_json.get("jd_soft_skills", []))
        resume_technical = set(skill.lower() for skill in parsed_json.get("resume_technical_skills", []))
        suggestions = parsed_json.get("suggestions", [])

        return True, (jd_technical, jd_soft, resume_technical, suggestions)

    except Exception as e:
        return False, f"Gemini API Error: {str(e)}. The model may have returned an unexpected format. Please try again."

def get_learning_resources(missing_skills):
    if not missing_skills: return ""
    links_md = "## 📚 Learning Resources\n\nHere are some links to help you get started on the missing technical skills:\n\n"
    for skill in sorted(list(missing_skills)):
        query = quote(f"{skill} tutorial for beginners")
        udemy_query = quote(skill)
        links_md += f"### {skill.title()}\n* [Search on YouTube](https://www.youtube.com/results?search_query={query})\n* [Search on Udemy](https://www.udemy.com/courses/search/?q={udemy_query})\n* [Search on Coursera](https://www.coursera.org/search?query={udemy_query})\n\n"
    return links_md

def create_donut_chart(matched_tech_count, missing_tech_count, soft_skill_count, score):
    if matched_tech_count == 0 and missing_tech_count == 0: return None
    outer_colors = ['#4CAF50', '#F44336', '#2196F3']; inner_colors = ['#4CAF50', '#F44336']
    outer_data = [matched_tech_count, missing_tech_count, soft_skill_count]
    outer_labels = [f'Matched\nTechnical', f'Missing\nTechnical', f'Soft\nSkills']
    inner_data = [matched_tech_count, missing_tech_count]
    fig, ax = plt.subplots(figsize=(8, 8)); fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    wedges, texts, autotexts = ax.pie(outer_data, radius=1, colors=outer_colors, wedgeprops=dict(width=0.3, edgecolor='w'), labels=outer_labels, autopct='%1.1f%%', pctdistance=0.85, labeldistance=1.05, textprops={'fontsize': 12, 'fontweight': 'bold'})
    plt.setp(autotexts, size=12, weight="bold", color="white"); plt.setp(texts, size=12, weight="bold", color="#333333")
    ax.pie(inner_data, radius=0.7, colors=inner_colors, wedgeprops=dict(width=0.3, edgecolor='w'))
    centre_circle = plt.Circle((0, 0), 0.4, fc='white'); fig.gca().add_artist(centre_circle)
    ax.text(0, 0, f'{score:.1f}%', ha='center', va='center', fontsize=40, fontweight='bold', color='#4CAF50')
    ax.text(0, -0.15, 'Technical Match', ha='center', va='center', fontsize=14, color='#555555')
    ax.set_title('Job Requirements Breakdown', fontsize=18, fontweight='bold', pad=20); ax.axis('equal')
    filepath = f"/tmp/skill_chart_{int(time.time())}.png"
    plt.savefig(filepath, bbox_inches='tight', pad_inches=0.1, transparent=True); plt.close(fig)
    return filepath

def analyze_documents(resume_pdf, jd_pdf, progress=gr.Progress()):
    if not resume_pdf or not jd_pdf: return None, "Please upload both your Resume and the Job Description."
    if not os.environ.get('GEMINI_API_KEY'): return None, "🔴 Gemini API Key is not configured on the server."
    progress(0, desc="Starting Analysis..."); progress(0.2, desc="Extracting text from PDFs...")
    resume_text = extract_text_from_pdf(resume_pdf); jd_text = extract_text_from_pdf(jd_pdf)
    progress(0.4, desc="Analyzing documents with Gemini AI...")
    success, data = analyze_with_gemini(resume_text, jd_text)
    if not success: return None, f"Analysis Failed: {data}"
    jd_technical, jd_soft, resume_technical, suggestions = data
    if not jd_technical: return None, "Analysis failed: Gemini could not identify any required technical skills in the Job Description."
    progress(0.7, desc="Calculating score and generating visuals...")
    matched_technical = resume_technical.intersection(jd_technical)
    missing_technical = jd_technical.difference(resume_technical)
    match_score = (len(matched_technical) / len(jd_technical)) * 100 if jd_technical else 0
    chart_path = create_donut_chart(len(matched_technical), len(missing_technical), len(jd_soft), match_score)
    progress(0.9, desc="Finding learning resources...")
    learning_links_md = get_learning_resources(missing_technical)
    result = f"# ⭐ Resume Analysis Report\n\nYour resume has a **{match_score:.1f}%** match with the job's **core technical requirements**.\n\n## 💡 AI-Powered Suggestions\n\n"
    if suggestions:
        for suggestion in suggestions: result += f"- {suggestion}\n"
    else: result += "No specific suggestions were generated. Your resume looks well-aligned!"
    result += f"\n\n---\n## ✅ Matched Technical Skills ({len(matched_technical)})\n"
    result += ", ".join(sorted([s.title() for s in matched_technical])) if matched_technical else "None"
    result += f"\n\n## ❌ Missing Technical Skills ({len(missing_technical)})\n"
    result += ", ".join(sorted([s.title() for s in missing_technical])) if missing_technical else "None! Great job."
    result += f"\n\n---\n### 💬 Required Soft Skills ({len(jd_soft)})\nWhile not part of the score, be prepared to discuss these:\n\n"
    result += ", ".join(sorted([s.title() for s in jd_soft])) if jd_soft else "None specified."
    result += f"\n\n---\n{learning_links_md}\n\n*Powered by Google Gemini. This is an automated guide.*"
    progress(1, desc="Done!")
    return chart_path, result

# --- GRADIO UI ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue", secondary_hue="light-blue"), css=".gradio-container {max-width: 1200px !important}") as iface:
    gr.Markdown("# 📄 Resume Analyzer AI with Google Gemini")
    gr.Markdown("...") # Your markdown description here

    with gr.Row():
        with gr.Column(scale=1, min_width=350):
            resume_file = gr.File(label="1. Upload Your Resume (PDF)")
            jd_file = gr.File(label="2. Upload Job Description (PDF)")
            analyze_btn = gr.Button("Analyze Resume", variant="primary")
            gr.Markdown("### Match Visualization")
            output_chart = gr.Image(label="Job Requirements Breakdown", show_label=False, interactive=False)
        with gr.Column(scale=2):
            output_report = gr.Markdown(label="Analysis Report")

    analyze_btn.click(
        fn=analyze_documents,
        inputs=[resume_file, jd_file],
        outputs=[output_chart, output_report],
        api_name="analyze"
    )

# IMPORTANT: This is the change for deployment
# It makes the app accessible on the network
iface.launch(server_name="0.0.0.0", server_port=7860)
