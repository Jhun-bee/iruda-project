# 이루다 (Iruda) - 자립청소년 AI 컨설팅 시스템

AI 기술과 따뜻한 마음이 만나 자립준비청년들의 체계적인 자립을 돕는 통합 지원 플랫폼입니다.

## 주요 기능

### ✨ 핵심 기능
- **개인화된 로드맵**: AI가 분석한 맞춤형 자립 계획 제공
- **지원정책 검색**: 의미적 검색으로 정확한 정책 매칭
- **Todo 관리 시스템**: 체계적인 할 일 관리 및 알림
- **AI 채팅**: OpenAI 기반 실시간 상담 및 지원
- **신청서 자동 생성**: AI로 맞춤형 정부 지원 신청서 작성

### 🔧 개선된 기능
- **연체 할일 자동 재계획**: 기한 넘긴 작업의 스마트한 재스케줄링
- **실시간 알림 시스템**: 마감일 임박 및 연체 알림
- **대화 히스토리**: 이전 상담 내용 저장 및 연속성 유지
- **진행률 추적**: 목표 달성률 시각화 및 통계

## 설치 및 실행 가이드

### 1. 시스템 요구사항
- Python 3.8 이상
- 최소 4GB RAM
- 1GB 이상의 저장공간

### 2. 환경 설정

```bash
# 1. 저장소 클론 또는 파일 다운로드
# 모든 파일을 동일한 디렉토리에 배치

# 2. 가상환경 생성 (권장)
python -m venv iruda_env

# 3. 가상환경 활성화
# Windows
iruda_env\Scripts\activate
# macOS/Linux  
source iruda_env/bin/activate

# 4. 필요 라이브러리 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 입력하세요:

```env
# 필수 설정
FLASK_SECRET_KEY=your-very-secure-secret-key-here
OPENAI_API_KEY=sk-your-openai-api-key-here

# 선택 설정
FLASK_ENV=development
FLASK_DEBUG=True
```

**OpenAI API 키 획득 방법:**
1. [OpenAI 웹사이트](https://platform.openai.com) 접속
2. 계정 생성 후 API Keys 메뉴로 이동  
3. 새 API 키 생성 및 복사
4. `.env` 파일의 `OPENAI_API_KEY`에 입력

### 4. 데이터베이스 및 초기 데이터

```bash
# 데이터베이스 초기화 (자동 실행됨)
python database/init_db.py
```

**정책 데이터 파일:**
- `정부정책_임시DB.xlsx` 파일이 루트 디렉토리에 있는지 확인
- 없다면 샘플 정책 데이터로 대체됩니다

### 5. 애플리케이션 실행

```bash
# 개발 서버 실행
python app.py
```

실행 후 브라우저에서 `http://localhost:5000` 접속

### 6. 테스트 계정

시스템에 기본 생성되는 테스트 계정:
- **이메일**: `test@iruda.com`
- **비밀번호**: `test123`

## 파일 구조

```
이루다/
├── app.py                 # 메인 Flask 애플리케이션
├── policy_matcher.py      # 개선된 정책 매칭 시스템
├── requirements.txt       # Python 패키지 의존성
├── .env                   # 환경 변수 (직접 생성)
├── 정부정책_임시DB.xlsx    # 정책 데이터베이스
├── database/
│   └── init_db.py         # 데이터베이스 초기화
├── templates/             # HTML 템플릿
│   ├── base.html
│   ├── dashboard.html     # 개선된 대시보드
│   ├── todos.html         # 할일 관리 페이지
│   ├── policies.html
│   ├── roadmap.html
│   ├── application_form.html
│   ├── register.html
│   ├── login.html
│   ├── home.html
│   └── mypage.html
└── static/                # CSS, JS, 이미지 파일들
```

## 주요 변경사항

### 🆕 새로운 기능
1. **Todo 관리 시스템**
   - 체계적인 할일 추적 및 관리
   - 우선순위, 카테고리, 상태별 필터링
   - 마감일 기반 자동 알림

2. **연체 관리**
   - 자동 연체 감지
   - AI 기반 일정 재계획
   - 맞춤형 경고 메시지

3. **개선된 AI 대화**
   - OpenAI GPT-3.5 완전 연동
   - 대화 히스토리 유지
   - 더 풍부하고 맥락적인 응답

4. **신청서 자동 생성**
   - AI 기반 맞춤형 신청서 작성
   - 필요 서류 자동 안내
   - 제출 방법 상세 가이드

### 🔧 개선사항
1. **데이터베이스 구조 개선**
   - Todo, 알림, 대화 히스토리 테이블 추가
   - 외래키 관계 최적화
   - 인덱스 및 트리거 추가

2. **사용자 경험 향상**
   - 실시간 알림 시스템
   - 진행률 시각화
   - 모바일 반응형 디자인

3. **성능 최적화**
   - 캐싱 메커니즘
   - 데이터베이스 쿼리 최적화
   - 백그라운드 작업 분리

## 사용법

### 1. 회원가입 및 프로필 설정
- 개인 정보 및 지원 필요 영역 입력
- 맞춤형 추천을 위한 기본 데이터 제공

### 2. 로드맵 생성
- AI가 개인 상황 분석
- 단계별 자립 계획 수립
- Todo 항목으로 자동 변환 가능

### 3. 할일 관리
- 생성된 계획을 체계적으로 실행
- 진행 상황 실시간 추적
- 마감일 임박 시 자동 알림

### 4. 정책 검색 및 신청
- 의미적 검색으로 정확한 정책 찾기
- AI 기반 신청서 자동 생성
- 필요 서류 및 제출 방법 안내

### 5. AI 상담
- 실시간 채팅으로 궁금증 해결
- 이전 대화 내용 기반 연속 상담
- 페이지 이동 제안으로 편의성 증대

## 문제 해결

### OpenAI API 연결 실패
```python
# .env 파일에서 API 키 확인
OPENAI_API_KEY=sk-your-actual-key-here
```

### 데이터베이스 오류
```bash
# 데이터베이스 재초기화
rm database/iruda.db
python database/init_db.py
```

### 정책 데이터 로드 실패
- `정부정책_임시DB.xlsx` 파일 경로 확인
- 파일 권한 설정 확인
- Excel 파일 형식 및 시트명 확인

### 포트 충돌
```python
# app.py 마지막 줄에서 포트 변경
app.run(debug=True, host='0.0.0.0', port=5001)
```

## 확장 계획

### 단기 (1-3개월)
- [ ] 이메일 알림 시스템
- [ ] 모바일 앱 개발
- [ ] 다국어 지원

### 중기 (3-6개월)
- [ ] 음성 인터페이스
- [ ] 금융 교육 모듈
- [ ] 민간 기업 연계 프로그램
- [ ] 위기 대응 모드

### 장기 (6-12개월)
- [ ] 다채널 접근성 확대 (키오스크)
- [ ] 빅데이터 분석 리포트
- [ ] 타 지역 확산
- [ ] 성과 측정 시스템

## 기술 스택

### Backend
- **Flask**: Python 웹 프레임워크
- **SQLite**: 경량 데이터베이스 (PostgreSQL로 확장 가능)
- **OpenAI GPT-3.5**: 대화형 AI 및 텍스트 생성

### Frontend  
- **Tailwind CSS**: 반응형 UI 디자인
- **Vanilla JavaScript**: 동적 상호작용
- **HTML5**: 시맨틱 마크업

### AI/ML
- **Sentence Transformers**: 의미적 검색
- **scikit-learn**: 머신러닝 유틸리티
- **KLUE RoBERTa**: 한국어 자연어 처리

## 보안 고려사항

### 데이터 보호
- 개인정보는 암호화하여 저장
- 세션 기반 인증 시스템
- SQL 인젝션 방지를 위한 파라미터화 쿼리

### API 보안
- OpenAI API 키 환경 변수로 관리  
- HTTPS 사용 권장 (프로덕션)
- 요청 제한(Rate Limiting) 구현

### 사용자 개인정보
- 최소한의 필요 정보만 수집
- 사용자 동의 기반 데이터 처리
- 데이터 삭제 요청 대응

## 라이선스

이 프로젝트는 교육 및 사회적 목적을 위한 오픈소스 프로젝트입니다.

## 기여하기

### 버그 리포트
- 문제 상황 상세 설명
- 재현 가능한 단계 제공
- 환경 정보 (OS, Python 버전 등)

### 기능 제안
- 사용자 관점에서의 필요성 설명
- 구체적인 구현 아이디어
- 기대 효과 및 영향

### 코드 기여
- 코드 스타일 가이드 준수
- 충분한 테스트 포함
- 문서화 업데이트

## 연락처 및 지원

**개발팀**: STC (세이브 더 칠드런)
- 배정윤, 김준희, 이상엽, 이상진

**문의사항**:
- 기술적 문제: GitHub Issues
- 일반 문의: 프로젝트 담당자 연락

---

## 빠른 시작 체크리스트

- [ ] Python 3.8+ 설치 확인
- [ ] 모든 파일을 동일 폴더에 배치
- [ ] `pip install -r requirements.txt` 실행
- [ ] `.env` 파일 생성 및 OpenAI API 키 입력
- [ ] `python app.py` 실행
- [ ] 브라우저에서 `localhost:5000` 접속
- [ ] 테스트 계정으로 로그인: `test@iruda.com` / `test123`

**시스템이 정상 작동하면 자립준비청년들을 위한 든든한 AI 파트너 '이루다'를 만나보실 수 있습니다!**

## 추가 참고자료

- [Flask 공식 문서](https://flask.palletsprojects.com/)
- [OpenAI API 가이드](https://platform.openai.com/docs)
- [Tailwind CSS 문서](https://tailwindcss.com/docs)
- [SQLite 튜토리얼](https://www.sqlite.org/docs.html)