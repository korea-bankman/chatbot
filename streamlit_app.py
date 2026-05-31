import streamlit as st
import google.generativeai as genai
import pdfplumber
import os

# 웹페이지 기본 설정 (브라우저 탭 제목 및 아이콘)
st.set_page_config(page_title="수혈 가이드라인 챗봇", page_icon="🩸", layout="centered")

# 1. 웹사이트 제목 및 설명 설정
st.title("🩸 수혈 가이드라인 챗봇")
st.write("혈액은행_병리맨")

# 2. 스트림릿 금고(Secrets)에서 구글 API 키 가져오기
if "GOOGLE_API_KEY" not in st.secrets:
    st.info("오른쪽 아래 'Manage app' -> 'Settings' -> 'Secrets'에 GOOGLE_API_KEY를 입력해 주세요.", icon="🔑")
    st.stop()

# 구글 제미나이 설정
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# [자동화] 폴더 내의 PDF 파일 자동으로 찾아내기
pdf_file = None
for file in os.listdir("."):
    if file.lower().endswith(".pdf"):
        pdf_file = file
        break

if not pdf_file:
    st.error("저장소에서 PDF 파일을 찾을 수 없습니다. 수혈 가이드라인 PDF 파일을 깃허브에 업로드해 주세요!")
    st.stop()

# 💡 긴 문서를 쪼개는 함수
def chunk_text(text, chunk_size=1200, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

# 3. PDF를 읽고 조각내어 저장하는 함수 (pdfplumber 적용으로 깨진 PDF도 안정적으로 추출)
@st.cache_data
def prepare_knowledge_base(file_path):
    with st.spinner("📚 가이드라인 문서를 고속 분석하고 있습니다. 잠시만 기다려 주세요..."):
        text = ""
        # 강력한 pdfplumber 엔진으로 파일 열기
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:  # 글자가 정상적으로 추출된 경우만 합치기
                    text += page_text + "\n"
        
        # 텍스트 조각내기
        return chunk_text(text)

# 지식 베이스 로드
chunks = prepare_knowledge_base(pdf_file)

# 4. 대화 기록 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 내용을 화면에 그려주기
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 질문 입력창
if prompt := st.chat_input("수혈 지침에 대해 질문해 주세요! (예: 신선동결혈장 투여 기준)"):
    # 1) 유저 입력창에 표시 및 저장
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) 관련 답변 찾기 및 생성 프로세스
    with st.chat_message("assistant"):
        try:
            # 외부 API 없이 내 서버에서 즉시 핵심 단어를 매칭하는 시스템
            query_words = [word.lower() for word in prompt.split() if len(word) > 1]
            
            scored_chunks = []
            for chunk in chunks:
                score = 0
                chunk_lower = chunk.lower()
                for word in query_words:
                    if word in chunk_lower:
                        score += chunk_lower.count(word)
                scored_chunks.append((score, chunk))
            
            # 단어 매칭 점수가 가장 높은 상위 4개 조각을 선택
            scored_chunks.sort(key=lambda x: x[0], reverse=True)
            relevant_contexts = [item[1] for item in scored_chunks[:4]]
            context_text = "\n\n---\n\n".join(relevant_contexts)
            
            # 메인 답변을 생성할 최신 제미나이 모델 호출
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            # AI에게 내리는 가이드라인 명령어
            full_prompt = (
                f"당신은 병원 수혈 지침 전문 챗봇입니다. 아래 제공된 [참고 지침]의 핵심 내용을 기반으로 사용자의 질문에 답변하세요.\n"
                f"사용자가 신뢰할 수 있도록 관련된 구체적인 수치, 적응증, 주의사항 등을 절대로 생략하지 말고 '매우 자세하고 친절하게' 풀어서 설명해 주세요.\n"
                f"가독성을 위해 줄바꿈과 불릿 기호(* 등)를 적극적으로 활용하여 구조적으로 답변하세요.\n"
                f"만약 제공된 지침 내용만으로 절대 답변할 수 없는 질문이라면, 지침서에서 해당 내용을 찾을 수 없다고 정중히 안내하세요.\n\n"
                f"[참고 지침 내용]\n{context_text}\n\n"
                f"질문: {prompt}"
            )
            
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            
            # AI 답변 기록 저장
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error(f"답변을 생성하는 중에 문제가 발생했습니다: {e}")
