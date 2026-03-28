from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from hemis_formatter import PROFILE_LABELS, format_uploaded_bytes, preview_text


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"
PROFILE_OPTIONS = ["auto", "sequential", "legacy", "jismoniy_uz", "jismoniy_ru"]
ENCODING_OPTIONS = ["auto", "cp1254", "cp1251", "utf-8", "cp1252", "latin1"]


st.set_page_config(
    page_title="HEMIS Formatter",
    page_icon="H",
    layout="wide",
)


st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(255, 219, 172, 0.55), transparent 34%),
            linear-gradient(135deg, #f4efe6 0%, #dde7ef 100%);
    }
    .block-container {
        max-width: 1080px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .hero {
        padding: 1.6rem 1.8rem;
        border: 1px solid rgba(27, 52, 75, 0.16);
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.72);
        box-shadow: 0 20px 60px rgba(27, 52, 75, 0.08);
        margin-bottom: 1rem;
    }
    .hero h1 {
        margin: 0;
        color: #17324a;
        letter-spacing: 0.02em;
    }
    .hero p {
        margin: 0.6rem 0 0;
        color: #35536a;
        font-size: 1rem;
    }
    .mini-card {
        padding: 1rem 1.1rem;
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.78);
        border: 1px solid rgba(27, 52, 75, 0.12);
        margin-top: 0.5rem;
    }
    [data-testid="stFileUploaderDropzone"] {
        border: 2px dashed #264c63;
        border-radius: 22px;
        background: rgba(255, 255, 255, 0.78);
        padding: 1.6rem 1rem;
    }
    [data-testid="stFileUploaderDropzone"] * {
        color: #17324a;
    }
    div.stButton > button {
        border-radius: 14px;
        border: none;
        background: linear-gradient(135deg, #1c5d79 0%, #124559 100%);
        color: white;
        font-weight: 600;
        padding: 0.85rem 1.1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="hero">
        <h1>HEMIS Formatter</h1>
        <p>Word faylni yuklang, profilni tanlang va HEMIS formatdagi natijani bir klikda oling.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.markdown("### Sozlamalar")
    selected_profile = st.selectbox(
        "Parser profili",
        options=PROFILE_OPTIONS,
        format_func=lambda key: PROFILE_LABELS[key],
        index=0,
    )
    selected_encoding = st.selectbox("Encoding", options=ENCODING_OPTIONS, index=0)
    st.markdown(
        """
        `Auto` odatda yetarli.

        `Sequential`: XORIJIY TILLAR kabi ketma-ket savol/javob fayllari uchun.

        `Jismoniy UZ` va `Jismoniy RU`: maxsus buzilgan bloklar uchun.
        """
    )
    st.caption("Eslatma: `.doc` va `.docx` bilan ishlashi uchun kompyuterda Microsoft Word o'rnatilgan bo'lishi kerak.")


uploader_col, info_col = st.columns([1.5, 1])

with uploader_col:
    uploaded_file = st.file_uploader(
        "Word faylni shu yerga tashlang",
        type=["doc", "docx"],
        accept_multiple_files=False,
    )

with info_col:
    st.markdown('<div class="mini-card">', unsafe_allow_html=True)
    st.write("`Qo'llab-quvvatlanadi`")
    st.write("- `.doc`")
    st.write("- `.docx`")
    st.write("- Yuklash, generatsiya, preview, download")
    st.markdown("</div>", unsafe_allow_html=True)


if uploaded_file is not None:
    st.markdown(
        f"""
        <div class="mini-card">
            <strong>Fayl:</strong> {uploaded_file.name}<br>
            <strong>Hajm:</strong> {uploaded_file.size / 1024:.1f} KB
        </div>
        """,
        unsafe_allow_html=True,
    )


generate_clicked = st.button("Generatsiya qilish", type="primary", use_container_width=True, disabled=uploaded_file is None)

if generate_clicked and uploaded_file is not None:
    run_dir = GENERATED_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    with st.spinner("Fayl HEMIS formatga o'tkazilmoqda..."):
        result = format_uploaded_bytes(
            source_name=uploaded_file.name,
            content=uploaded_file.getvalue(),
            output_dir=run_dir,
            profile=selected_profile,
            encoding=selected_encoding,
        )

    st.session_state["conversion_result"] = {
        "source_name": result.source_name,
        "profile": result.profile,
        "encoding": result.encoding,
        "question_count": result.question_count,
        "hemis_text": result.hemis_text,
        "txt_name": result.txt_path.name,
        "docx_name": result.docx_path.name,
        "txt_path": str(result.txt_path),
        "docx_path": str(result.docx_path),
        "txt_bytes": result.txt_path.read_bytes(),
        "docx_bytes": result.docx_path.read_bytes(),
    }


if "conversion_result" in st.session_state:
    data = st.session_state["conversion_result"]
    st.success("Generatsiya tugadi.")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Savollar soni", data["question_count"])
    metric_col2.metric("Tanlangan profil", PROFILE_LABELS[data["profile"]])
    metric_col3.metric("Encoding", data["encoding"])

    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        "DOCX yuklab olish",
        data=data["docx_bytes"],
        file_name=data["docx_name"],
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    download_col2.download_button(
        "TXT yuklab olish",
        data=data["txt_bytes"],
        file_name=data["txt_name"],
        mime="text/plain",
        use_container_width=True,
    )

    st.markdown(
        f"""
        <div class="mini-card">
            <strong>Saqlangan DOCX:</strong> {data["docx_path"]}<br>
            <strong>Saqlangan TXT:</strong> {data["txt_path"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Preview", expanded=True):
        st.code(preview_text(data["hemis_text"], question_limit=6), language="text")
