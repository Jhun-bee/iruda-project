from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
from dotenv import load_dotenv
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
from datetime import datetime, timedelta
import openai
from openai import OpenAI

# Enhanced Policy Matcher 임포트
try:
    from policy_matcher import EnhancedPolicyMatcher
    ENHANCED_MATCHER_AVAILABLE = True
except ImportError as e:
    print(f"Enhanced Policy Matcher를 import할 수 없습니다: {e}")
    ENHANCED_MATCHER_AVAILABLE = False

# 환경변수 로드
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-this')

# Flask-Login 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# OpenAI 클라이언트 초기화
openai_client = None
if os.getenv('OPENAI_API_KEY'):
    try:
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        print("✅ OpenAI API 클라이언트 초기화 완료")
    except Exception as e:
        print(f"⚠️ OpenAI API 클라이언트 초기화 실패: {e}")
else:
    print("⚠️ OPENAI_API_KEY가 설정되지 않았습니다.")

# 전역 변수로 선언
enhanced_matcher = None

def initialize_enhanced_matcher():
    """앱 시작 시 정책 매칭 시스템 초기화"""
    global enhanced_matcher
    if not ENHANCED_MATCHER_AVAILABLE:
        print("Enhanced Policy Matcher 라이브러리를 사용할 수 없습니다.")
        return False
    try:
        enhanced_matcher = EnhancedPolicyMatcher()
        return True
    except Exception as e:
        print(f"Enhanced Policy Matcher 초기화 실패: {e}")
        return False

def get_user_profile(user_id):
    """사용자 프로필 정보 가져오기"""
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT housing_status, income_level, support_needs, age 
            FROM user_profiles up
            JOIN users u ON up.user_id = u.id
            WHERE user_id = ?
        ''', (user_id,))
        profile_data = cursor.fetchone()
        conn.close()
        
        if profile_data:
            return {
                'housing_status': profile_data[0],
                'income_level': profile_data[1], 
                'support_needs': json.loads(profile_data[2]) if profile_data[2] else [],
                'age': profile_data[3]
            }
        return None
    except Exception as e:
        print(f"사용자 프로필 조회 실패: {e}")
        return None

def apply_keyword_filter(policies, search_query):
    """기존 키워드 필터링 (fallback용)"""
    return [
        policy for policy in policies
        if (search_query.lower() in str(policy.get('서비스명', '')).lower() or
            search_query.lower() in str(policy.get('기관명', '')).lower() or
            search_query.lower() in str(policy.get('지원내용', '')).lower() or
            search_query.lower() in str(policy.get('지원대상', '')).lower())
    ]

def apply_category_filter(policies, category_filter):
    """기존 카테고리 필터링 (fallback용)"""
    return [
        policy for policy in policies
        if policy.get('구분', '') == category_filter
    ]

class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

# 정부 정책 데이터 로드 함수
def load_government_policies():
    try:
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        excel_path = os.path.join(current_dir, '정부정책_임시DB.xlsx')
        
        # Excel 파일에서 정책 데이터 읽기
        df = pd.read_excel(excel_path, sheet_name='중앙부처')
        policies = df.to_dict('records')
        
        # 지자체 데이터도 추가
        df_local = pd.read_excel(excel_path, sheet_name='지자체')
        policies.extend(df_local.to_dict('records'))
        
        # 민간 데이터도 추가
        df_private = pd.read_excel(excel_path, sheet_name='민간')
        policies.extend(df_private.to_dict('records'))
        
        return policies
    except Exception as e:
        print(f"정책 데이터 로드 실패: {e}")
        return []

# 홈페이지
@app.route('/')
def home():
    return render_template('home.html')

# 회원가입 페이지
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    # POST 요청 처리
    data = request.form
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    age = data.get('age', 20)  # 기본값 20
    
    # 프로필 정보
    housing_status = data.get('housing_status')
    income_level = data.get('income_level')
    support_needs = data.getlist('support_needs')
    
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 사용자 생성
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, age) 
            VALUES (?, ?, ?, ?)
        ''', (name, email, password_hash, age))
        
        user_id = cursor.lastrowid
        
        # 프로필 정보 저장
        cursor.execute('''
            INSERT INTO user_profiles 
            (user_id, housing_status, income_level, support_needs)
            VALUES (?, ?, ?, ?)
        ''', (user_id, housing_status, income_level, json.dumps(support_needs)))
        
        conn.commit()
        conn.close()
        
        flash('회원가입이 완료되었습니다!', 'success')
        return redirect(url_for('login'))
        
    except sqlite3.IntegrityError:
        flash('이미 존재하는 이메일입니다.', 'error')
        return render_template('register.html')

# 로그인 페이지
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name, password_hash FROM users WHERE email = ?', (email,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data and check_password_hash(user_data[3], password):
        user = User(user_data[0], user_data[1], user_data[2])
        login_user(user)
        return redirect(url_for('dashboard'))
    else:
        flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
        return render_template('login.html')

# 개선된 OpenAI API 호출 함수
def call_openai_api(message, conversation_history=None):
    """OpenAI API를 호출하여 응답을 받아옵니다."""
    global openai_client
    
    if not openai_client:
        return generate_mock_response(message)
    
    try:
        # 시스템 메시지 설정
        system_message = {
            "role": "system", 
            "content": f"""당신은 자립준비청년을 위한 AI 상담사 '이루다'입니다. 
            친근하고 따뜻하며 실용적인 조언을 제공합니다.
            
            주요 역할:
            1. 자립준비청년의 고민과 질문에 공감하며 답변
            2. 정부 지원정책과 제도에 대한 정보 제공
            3. 개인별 맞춤 로드맵 및 계획 수립 지원
            4. 주거, 경제, 교육, 취업, 심리 지원 관련 안내
            
            말투: 친근하면서도 전문적, 격려하고 지지하는 톤
            길이: 3-5문장으로 간결하게, 필요시 구체적인 행동방안 제시"""
        }
        
        # 대화 히스토리 구성
        messages = [system_message]
        if conversation_history:
            messages.extend(conversation_history[-10:])  # 최근 10개 메시지만 유지
        
        messages.append({"role": "user", "content": message})
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"OpenAI API 호출 실패: {e}")
        return generate_mock_response(message)

# 채팅 API (개선된 버전)
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        # OpenAI API 호출
        ai_response = call_openai_api(message, conversation_history)
        suggestion = check_for_page_suggestion(message)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'suggestion': suggestion
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_mock_response(message):
    """OpenAI 대신 사용할 임시 응답 생성기 (개선된 버전)"""
    message_lower = message.lower()
    
    # 키워드 기반 응답 패턴
    responses = {
        'roadmap|로드맵|계획': f"안녕하세요 {current_user.name}님! 맞춤형 자립 로드맵을 만들어드릴게요. 현재 상황과 목표를 바탕으로 단계별 계획을 수립해보겠습니다. 로드맵 페이지에서 더 자세한 계획을 확인하실 수 있어요!",
        
        'policy|정책|지원|급여|수당': "다양한 정부 지원정책이 준비되어 있어요! 주거급여, 생계급여, 취업지원 프로그램 등이 있습니다. 어떤 분야의 지원을 원하시는지 알려주시면 더 구체적으로 안내해드릴게요.",
        
        'todo|할일|체크|관리': "할 일 관리는 자립에서 정말 중요해요! 로드맵에서 생성된 계획들을 체계적인 할 일로 변환해서 단계별로 실행할 수 있도록 도와드릴게요. 기한도 설정하고 알림도 받을 수 있답니다.",
        
        'housing|주거|원룸|임대': "주거 안정이 자립의 첫 걸음이죠! 주거급여 신청, LH 청년전세임대, 청년 월세 한시 특별지원 등 다양한 주거 지원정책이 있어요. 현재 상황에 맞는 정책을 찾아보실까요?",
        
        'job|취업|일자리|구직': "취업 준비 함께 해봐요! 청년내일채움공제, 국민취업지원제도, 청년 디지털 일자리 등 다양한 프로그램이 있습니다. 이력서 작성부터 면접 준비까지 단계별로 도와드릴 수 있어요.",
        
        'money|돈|경제|생계|소득': "경제적 자립이 걱정되시는군요. 생계급여, 근로장려금, 청년 소득지원 등의 제도가 있어요. 가계부 작성 방법이나 저축 계획도 함께 세워보시면 좋을 것 같아요!",
        
        'hello|안녕|처음': f"안녕하세요 {current_user.name}님! 저는 여러분의 자립을 돕는 AI 상담사 이루다예요. 로드맵 설계, 정책 안내, 일상 고민까지 무엇이든 편하게 말씀해주세요. 오늘은 어떤 도움이 필요하신가요?",
        
        'help|도움|뭘할수있': "제가 도울 수 있는 일들이 정말 많아요! 📋 개인 맞춤 로드맵 작성, 💰 지원정책 찾기, ✅ 할 일 관리, 📞 상담 및 정보 제공, 📝 신청서 작성 도움 등이 있어요. 어떤 것부터 시작해볼까요?"
    }
    
    # 패턴 매칭으로 응답 생성
    for pattern, response in responses.items():
        if re.search(pattern, message_lower):
            return response
    
    # 기본 응답
    return f"{current_user.name}님, 좋은 질문이네요! 더 구체적으로 알려주시면 맞춤형 조언을 드릴 수 있어요. 예를 들어 '주거 지원이 필요해', '취업 준비를 하고 싶어', '로드맵을 만들고 싶어' 같이 말씀해주시면 더 정확한 도움을 드릴 수 있습니다."

def check_for_page_suggestion(message):
    """메시지를 분석해서 페이지 이동 제안"""
    message_lower = message.lower()
    
    suggestions = [
        (['roadmap', '로드맵', '계획'], '/roadmap', '로드맵 페이지에서 체계적인 자립 계획을 세워보시겠어요?'),
        (['policy', '정책', '지원', '급여'], '/policies', '지원정책 페이지에서 맞춤 정책을 찾아보시겠어요?'),
        (['todo', '할일', '체크'], '/todos', '할 일 관리 페이지에서 진행상황을 체크해보시겠어요?')
    ]
    
    for keywords, url, message in suggestions:
        if any(keyword in message_lower for keyword in keywords):
            return {
                'type': 'redirect',
                'url': url,
                'message': message
            }
    return None

# 대시보드 (개선된 버전)
@app.route('/dashboard')
@login_required
def dashboard():
    # 사용자 로드맵 조회
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, description, priority_areas, timeline 
        FROM roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
    ''', (current_user.id,))
    roadmap_data = cursor.fetchone()
    conn.close()
    
    roadmap = None
    if roadmap_data:
        roadmap = {
            'title': roadmap_data[0],
            'description': roadmap_data[1],
            'priority_areas': json.loads(roadmap_data[2]) if roadmap_data[2] else [],
            'timeline': json.loads(roadmap_data[3]) if roadmap_data[3] else {}
        }
    
    return render_template('dashboard.html', roadmap=roadmap)

# 대시보드 통계 API
@app.route('/dashboard-stats')
@login_required
def dashboard_stats():
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 활성 할일 개수
        cursor.execute('''
            SELECT COUNT(*) FROM todos 
            WHERE user_id = ? AND status IN ('pending', 'in_progress')
        ''', (current_user.id,))
        active_tasks = cursor.fetchone()[0]
        
        # 완료된 할일 개수
        cursor.execute('''
            SELECT COUNT(*) FROM todos 
            WHERE user_id = ? AND status = 'completed'
        ''', (current_user.id,))
        completed_tasks = cursor.fetchone()[0]
        
        # 오늘 기한인 할일
        cursor.execute('''
            SELECT COUNT(*) FROM todos 
            WHERE user_id = ? AND DATE(due_date) = DATE('now') AND status != 'completed'
        ''', (current_user.id,))
        due_today = cursor.fetchone()[0]
        
        # 연체된 할일
        cursor.execute('''
            SELECT COUNT(*) FROM todos 
            WHERE user_id = ? AND DATE(due_date) < DATE('now') AND status != 'completed'
        ''', (current_user.id,))
        overdue_tasks = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'active_tasks': active_tasks,
            'completed_tasks': completed_tasks,
            'due_today': due_today,
            'overdue_tasks': overdue_tasks,
            'recommended_policies': 3  # 임시값
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# AI 로드맵 생성 (기존 함수 개선)
@app.route('/generate-roadmap', methods=['POST'])
@login_required
def generate_roadmap():
    try:
        # 사용자 프로필 정보 가져오기
        user_profile = get_user_profile(current_user.id)
        
        if not user_profile:
            return jsonify({'success': False, 'error': '프로필 정보가 없습니다.'})
        
        # OpenAI를 통한 로드맵 생성 (또는 템플릿 사용)
        roadmap = generate_personalized_roadmap(user_profile)
        
        # 로드맵을 데이터베이스에 저장
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO roadmaps (user_id, title, description, priority_areas, timeline)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            current_user.id,
            roadmap['title'],
            roadmap['description'],
            json.dumps(roadmap['priority_areas']),
            json.dumps(roadmap['timeline'])
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'roadmap': roadmap})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_personalized_roadmap(user_profile):
    """사용자 프로필을 바탕으로 개인화된 로드맵 생성"""
    # 기본 템플릿 (추후 OpenAI로 개선)
    support_needs = user_profile.get('support_needs', [])
    
    priority_areas = []
    timeline = {}
    
    if '주거지원' in support_needs:
        priority_areas.append('주거 안정')
        timeline['1개월'] = timeline.get('1개월', []) + ['주거급여 신청', '임대주택 정보 조회']
        timeline['3개월'] = timeline.get('3개월', []) + ['안정적 주거지 확보']
    
    if '취업지원' in support_needs:
        priority_areas.append('경제적 자립')
        timeline['1개월'] = timeline.get('1개월', []) + ['이력서 작성', '취업지원 프로그램 신청']
        timeline['3개월'] = timeline.get('3개월', []) + ['안정적 일자리 확보']
    
    if '심리지원' in support_needs:
        priority_areas.append('심리적 안정')
        timeline['1개월'] = timeline.get('1개월', []) + ['상담센터 연결', '멘토 매칭']
        
    return {
        "title": f"{current_user.name}님의 맞춤형 자립 로드맵",
        "description": "체계적인 자립을 위한 단계별 계획입니다.",
        "priority_areas": priority_areas or ["주거 안정", "경제적 자립", "사회적 네트워크 구축"],
        "timeline": timeline or {
            "1개월": ["자립지원센터 상담", "긴급 지원제도 확인"],
            "3개월": ["안정적 소득원 확보", "주거 독립 준비"],
            "6개월": ["비상자금 마련", "사회보험 가입"]
        }
    }

# 로드맵 페이지
@app.route('/roadmap')
@login_required
def roadmap():
    # 사용자 로드맵 조회
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, description, priority_areas, timeline 
        FROM roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
    ''', (current_user.id,))
    roadmap_data = cursor.fetchone()
    
    roadmap = None
    progress_percentage = 0
    roadmap_id = None
    
    if roadmap_data:
        roadmap_id = roadmap_data[0]
        roadmap = {
            'id': roadmap_id,
            'title': roadmap_data[1],
            'description': roadmap_data[2],
            'priority_areas': json.loads(roadmap_data[3]) if roadmap_data[3] else [],
            'timeline': json.loads(roadmap_data[4]) if roadmap_data[4] else {}
        }
        
        # 진행률 계산 (todos 테이블 기반)
        cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM todos WHERE user_id = ? AND roadmap_id = ?
        ''', (current_user.id, roadmap_id))
        progress_data = cursor.fetchone()
        if progress_data[0] > 0:
            progress_percentage = int((progress_data[1] / progress_data[0]) * 100)
    
    conn.close()
    return render_template('roadmap.html', roadmap=roadmap, progress_percentage=progress_percentage)

# 로드맵 상세 계획 생성 API (수정된 버전)
@app.route('/roadmap/detail-plan', methods=['POST'])
@login_required
def roadmap_detail_plan():
    try:
        data = request.json
        period = data.get('period')
        goals = data.get('goals', [])
        
        if not goals:
            return jsonify({'success': False, 'error': '목표가 없습니다.'})
        
        # 상세 계획 생성
        if openai_client:
            detail_plan = generate_ai_detail_plan(period, goals)
        else:
            detail_plan = generate_detail_plan(period, goals)
        
        return jsonify({
            'success': True,
            'detail_plan': detail_plan
        })
        
    except Exception as e:
        print(f"상세 계획 생성 오류: {e}")
        return jsonify({'success': False, 'error': str(e)})

def generate_ai_detail_plan(period, goals):
    """OpenAI를 사용한 상세 계획 생성"""
    try:
        goals_text = ', '.join(goals)
        prompt = f"""
        다음 {period} 목표들에 대한 구체적이고 실행 가능한 상세 계획을 작성해주세요:
        목표: {goals_text}
        
        각 목표마다 다음 형식으로 작성해주세요:
        1. 제목: [목표명] - 세부 계획
        2. 구체적인 실행 단계 5개 (각각 실행 가능한 액션 아이템)
        3. 예상 소요시간
        4. 우선순위 (high/medium/low)
        
        자립준비청년의 관점에서 현실적이고 도움이 되는 계획으로 작성해주세요.
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 자립준비청년을 위한 실무 전문가입니다. 구체적이고 실행 가능한 계획을 수립해주세요."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        ai_response = response.choices[0].message.content
        
        # AI 응답을 구조화된 형태로 파싱
        return parse_ai_detail_plan(ai_response, goals)
        
    except Exception as e:
        print(f"AI 상세 계획 생성 실패: {e}")
        return generate_detail_plan(period, goals)

def generate_detail_plan(period, goals):
    """상세 계획 생성 함수 (OpenAI 대신 임시 구현)"""
    detail_plan = []
    
    for i, goal in enumerate(goals):
        if '주거' in goal:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    "주거급여 신청 자격 요건 확인하기",
                    "필요 서류 준비 (소득증명서, 임대차계약서)",
                    "관할 주민센터에서 신청 접수하기",
                    "심사 결과 확인 및 후속 조치",
                    "월별 주거비 관리 시스템 구축하기"
                ],
                'estimated_time': '2-3주',
                'priority': 'high'
            })
        elif '취업' in goal or '구직' in goal:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    "이력서 및 자기소개서 작성하기",
                    "취업지원 프로그램 신청하기",
                    "직업훈련 과정 알아보기",
                    "구인구직 사이트 활용법 익히기",
                    "면접 준비 및 연습하기"
                ],
                'estimated_time': '3-4주',
                'priority': 'high'
            })
        elif '생활비' in goal or '경제' in goal:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    "월별 수입/지출 현황 파악하기",
                    "생계급여 지원 신청하기",
                    "가계부 작성 습관 만들기",
                    "비상자금 적립 계획 세우기",
                    "금융 교육 프로그램 수강하기"
                ],
                'estimated_time': '1-2주',
                'priority': 'medium'
            })
        else:
            detail_plan.append({
                'title': f"{goal} - 세부 계획",
                'tasks': [
                    f"{goal} 관련 정보 수집하기",
                    "전문가 상담 받기",
                    "단계별 실행 계획 수립하기",
                    "필요한 지원 프로그램 찾기",
                    "정기적인 점검 및 조정하기"
                ],
                'estimated_time': '2주',
                'priority': 'medium'
            })
    
    return detail_plan

# Todo 변환 API (개선된 버전)
@app.route('/roadmap/convert-to-todos', methods=['POST'])
@login_required
def convert_to_todos():
    try:
        data = request.json
        period = data.get('period')
        goals = data.get('goals')
        detail_plan = data.get('detail_plan', [])
        
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 로드맵 ID 가져오기
        cursor.execute('''
            SELECT id FROM roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
        ''', (current_user.id,))
        roadmap_result = cursor.fetchone()
        roadmap_id = roadmap_result[0] if roadmap_result else None
        
        # 상세 계획이 있다면 각 태스크를 개별 Todo로 생성
        if detail_plan:
            for plan in detail_plan:
                for task in plan['tasks']:
                    # 기한 계산 (period에 따라)
                    due_date = calculate_due_date(period, plan.get('estimated_time', '1주'))
                    
                    cursor.execute('''
                        INSERT INTO todos 
                        (user_id, roadmap_id, title, description, due_date, priority, status, category)
                        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                    ''', (
                        current_user.id, 
                        roadmap_id, 
                        task, 
                        plan['title'],
                        due_date,
                        plan.get('priority', 'medium'),
                        period
                    ))
        else:
            # 기본 목표를 Todo로 변환
            for goal in goals:
                due_date = calculate_due_date(period)
                cursor.execute('''
                    INSERT INTO todos 
                    (user_id, roadmap_id, title, description, due_date, priority, status, category)
                    VALUES (?, ?, ?, ?, ?, 'medium', 'pending', ?)
                ''', (current_user.id, roadmap_id, goal, f"{period} 목표", due_date, period))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '할 일 목록으로 변환되었습니다!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def calculate_due_date(period, estimated_time=None):
    """기간과 예상시간을 바탕으로 마감일 계산"""
    from datetime import datetime, timedelta
    
    base_date = datetime.now()
    
    if period == '1개월':
        return (base_date + timedelta(days=30)).strftime('%Y-%m-%d')
    elif period == '3개월':
        return (base_date + timedelta(days=90)).strftime('%Y-%m-%d')
    elif period == '6개월':
        return (base_date + timedelta(days=180)).strftime('%Y-%m-%d')
    else:
        # 예상시간 기반 계산
        if estimated_time:
            if '주' in estimated_time:
                weeks = int(re.search(r'(\d+)', estimated_time).group(1))
                return (base_date + timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        return (base_date + timedelta(days=14)).strftime('%Y-%m-%d')  # 기본 2주

# Todo 관리 페이지
@app.route('/todos')
@login_required
def todos():
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    
    # 모든 todos 조회 (상태별로 정렬)
    cursor.execute('''
        SELECT id, title, description, due_date, priority, status, category, created_at,
               CASE 
                   WHEN status = 'completed' THEN 3
                   WHEN DATE(due_date) < DATE('now') THEN 1  
                   WHEN DATE(due_date) = DATE('now') THEN 2
                   ELSE 4
               END as sort_priority
        FROM todos 
        WHERE user_id = ? 
        ORDER BY sort_priority, due_date ASC
    ''', (current_user.id,))
    
    all_todos = cursor.fetchall()
    
    # 데이터 구조화
    todos = []
    for todo in all_todos:
        todos.append({
            'id': todo[0],
            'title': todo[1], 
            'description': todo[2],
            'due_date': todo[3],
            'priority': todo[4],
            'status': todo[5],
            'category': todo[6],
            'created_at': todo[7],
            'is_overdue': datetime.strptime(todo[3], '%Y-%m-%d').date() < datetime.now().date() if todo[5] != 'completed' else False,
            'is_due_today': datetime.strptime(todo[3], '%Y-%m-%d').date() == datetime.now().date() if todo[5] != 'completed' else False
        })
    
    conn.close()
    return render_template('todos.html', todos=todos)

# Todo 상태 업데이트 API
@app.route('/todos/<int:todo_id>/update-status', methods=['POST'])
@login_required
def update_todo_status(todo_id):
    try:
        data = request.json
        new_status = data.get('status')
        
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 완료 시간 업데이트
        completed_at = datetime.now().isoformat() if new_status == 'completed' else None
        
        cursor.execute('''
            UPDATE todos 
            SET status = ?, completed_at = ? 
            WHERE id = ? AND user_id = ?
        ''', (new_status, completed_at, todo_id, current_user.id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Todo 삭제 API
@app.route('/todos/<int:todo_id>/delete', methods=['DELETE'])
@login_required
def delete_todo(todo_id):
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM todos WHERE id = ? AND user_id = ?
        ''', (todo_id, current_user.id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Todo 수정 API
@app.route('/todos/<int:todo_id>/edit', methods=['POST'])
@login_required
def edit_todo(todo_id):
    try:
        data = request.json
        title = data.get('title')
        description = data.get('description') 
        due_date = data.get('due_date')
        priority = data.get('priority')
        
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE todos 
            SET title = ?, description = ?, due_date = ?, priority = ?
            WHERE id = ? AND user_id = ?
        ''', (title, description, due_date, priority, todo_id, current_user.id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 알림 확인 API
@app.route('/notifications')
@login_required
def get_notifications():
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 오늘 마감인 할일
        cursor.execute('''
            SELECT id, title, due_date FROM todos 
            WHERE user_id = ? AND DATE(due_date) = DATE('now') AND status != 'completed'
        ''', (current_user.id,))
        due_today = cursor.fetchall()
        
        # 연체된 할일
        cursor.execute('''
            SELECT id, title, due_date FROM todos 
            WHERE user_id = ? AND DATE(due_date) < DATE('now') AND status != 'completed'
        ''', (current_user.id,))
        overdue = cursor.fetchall()
        
        # 3일 내 마감인 할일
        cursor.execute('''
            SELECT id, title, due_date FROM todos 
            WHERE user_id = ? 
            AND DATE(due_date) BETWEEN DATE('now', '+1 day') AND DATE('now', '+3 days')
            AND status != 'completed'
        ''', (current_user.id,))
        upcoming = cursor.fetchall()
        
        conn.close()
        
        notifications = []
        
        for todo in overdue:
            notifications.append({
                'id': todo[0],
                'title': todo[1],
                'message': f'마감일이 지난 할일: {todo[1]}',
                'type': 'error',
                'due_date': todo[2]
            })
            
        for todo in due_today:
            notifications.append({
                'id': todo[0], 
                'title': todo[1],
                'message': f'오늘 마감: {todo[1]}',
                'type': 'warning',
                'due_date': todo[2]
            })
            
        for todo in upcoming:
            notifications.append({
                'id': todo[0],
                'title': todo[1], 
                'message': f'곧 마감: {todo[1]} ({todo[2]})',
                'type': 'info',
                'due_date': todo[2]
            })
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'counts': {
                'overdue': len(overdue),
                'due_today': len(due_today), 
                'upcoming': len(upcoming)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 연체 할일 재계획 API
@app.route('/todos/reschedule-overdue', methods=['POST'])
@login_required
def reschedule_overdue_todos():
    try:
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 연체된 할일들 조회
        cursor.execute('''
            SELECT id, title, description, category FROM todos 
            WHERE user_id = ? AND DATE(due_date) < DATE('now') AND status != 'completed'
        ''', (current_user.id,))
        overdue_todos = cursor.fetchall()
        
        if not overdue_todos:
            return jsonify({'success': True, 'message': '연체된 할일이 없습니다.'})
        
        # AI를 통한 재계획 생성 (또는 기본 로직)
        reschedule_plan = generate_reschedule_plan(overdue_todos)
        
        # 새로운 일정으로 업데이트
        for todo_id, new_due_date in reschedule_plan.items():
            cursor.execute('''
                UPDATE todos SET due_date = ? WHERE id = ? AND user_id = ?
            ''', (new_due_date, todo_id, current_user.id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'{len(reschedule_plan)}개의 할일이 재계획되었습니다.',
            'reschedule_plan': reschedule_plan
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def generate_reschedule_plan(overdue_todos):
    """연체된 할일들을 위한 재계획 생성"""
    reschedule_plan = {}
    base_date = datetime.now()
    
    for i, todo in enumerate(overdue_todos):
        # 우선순위와 카테고리를 고려한 재계획
        if '긴급' in todo[1] or '신청' in todo[1]:
            # 긴급한 일은 3일 내
            new_date = (base_date + timedelta(days=3)).strftime('%Y-%m-%d')
        elif '주거' in todo[2] or '생계' in todo[2]:
            # 생존과 관련된 일은 1주 내
            new_date = (base_date + timedelta(days=7)).strftime('%Y-%m-%d')
        else:
            # 일반적인 일은 2주 내
            new_date = (base_date + timedelta(days=14)).strftime('%Y-%m-%d')
        
        reschedule_plan[todo[0]] = new_date
    
    return reschedule_plan

# 정책 검색 페이지 (기존 유지하되 개선)
@app.route('/policies')
@login_required  
def policies():
    # 검색 파라미터 가져오기
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    recommended = request.args.get('recommended', False)
    
    # Enhanced Matcher가 사용 가능하고 의미있는 검색어가 있을 때
    if enhanced_matcher and search_query and len(search_query) > 2:
        try:
            user_profile = get_user_profile(current_user.id)
            filtered_policies = enhanced_matcher.semantic_search(
                query=search_query,
                user_profile=user_profile,
                top_k=20
            )
        except Exception as e:
            print(f"의미적 검색 실패, 기존 방식 사용: {e}")
            # 기존 방식으로 fallback
            all_policies = load_government_policies()
            filtered_policies = all_policies.copy()
            if search_query:
                filtered_policies = apply_keyword_filter(filtered_policies, search_query)
    else:
        # 기존 검색 방식 유지
        all_policies = load_government_policies()
        filtered_policies = all_policies.copy()
        
        if search_query:
            filtered_policies = apply_keyword_filter(filtered_policies, search_query)
        
        if category_filter:
            filtered_policies = apply_category_filter(filtered_policies, category_filter)
        
        if recommended:
            filtered_policies = get_recommended_policies(filtered_policies)
    
    return render_template('policies.html', policies=filtered_policies)

def get_recommended_policies(policies):
    """사용자 프로필 기반 정책 추천"""
    try:
        user_profile = get_user_profile(current_user.id)
        if not user_profile:
            return policies[:10]  # 프로필 없으면 상위 10개 반환
        
        support_needs = user_profile.get('support_needs', [])
        
        recommended = []
        for policy in policies:
            score = 0
            policy_text = (policy.get('서비스명', '') + ' ' + 
                          policy.get('지원내용', '') + ' ' + 
                          policy.get('지원대상', '')).lower()
            
            # 지원 요구사항 매칭
            for need in support_needs:
                if need == '주거지원' and ('주거' in policy_text or '임대' in policy_text):
                    score += 3
                elif need == '경제지원' and ('생계' in policy_text or '급여' in policy_text):
                    score += 3
                elif need == '취업지원' and ('취업' in policy_text or '일자리' in policy_text):
                    score += 3
                elif need == '교육지원' and ('교육' in policy_text or '학비' in policy_text):
                    score += 3
                elif need == '심리지원' and ('상담' in policy_text or '심리' in policy_text):
                    score += 2
            
            # 자립준비청년 대상 정책 우선
            if '자립' in policy_text or '청소년' in policy_text:
                score += 2
            
            if score > 0:
                recommended.append((policy, score))
        
        # 점수 순으로 정렬하고 상위 20개 반환
        recommended.sort(key=lambda x: x[1], reverse=True)
        return [policy for policy, score in recommended[:20]]
        
    except Exception as e:
        print(f"추천 정책 생성 오류: {e}")
        return policies[:10]

# 정책 추천 API
@app.route('/policies/recommend', methods=['POST'])
@login_required
def recommend_policies():
    try:
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# MyPage 라우트들 (기존 유지)
@app.route('/mypage')
@login_required
def mypage():
    # 사용자 정보와 프로필 가져오기
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, email, age FROM users WHERE id = ?', (current_user.id,))
    user_data = cursor.fetchone()
    
    cursor.execute('''
        SELECT housing_status, income_level, education_level, employment_status, support_needs
        FROM user_profiles WHERE user_id = ?
    ''', (current_user.id,))
    profile_data = cursor.fetchone()
    
    conn.close()
    
    user = {
        'id': user_data[0],
        'name': user_data[1], 
        'email': user_data[2],
        'age': user_data[3]
    }
    
    profile = {}
    if profile_data:
        profile = {
            'housing_status': profile_data[0],
            'income_level': profile_data[1],
            'education_level': profile_data[2],
            'employment_status': profile_data[3],
            'support_needs': json.loads(profile_data[4]) if profile_data[4] else []
        }
    
    return render_template('mypage.html', user=user, profile=profile)

@app.route('/mypage', methods=['POST'])
@login_required
def update_mypage():
    try:
        # 폼 데이터 가져오기
        name = request.form.get('name')
        email = request.form.get('email')
        age = request.form.get('age')
        
        # 프로필 정보
        housing_status = request.form.get('housing_status')
        income_level = request.form.get('income_level')
        support_needs = request.form.getlist('support_needs')
        
        # 비밀번호 변경 (선택사항)
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        conn = sqlite3.connect('database/iruda.db')
        cursor = conn.cursor()
        
        # 사용자 기본 정보 업데이트
        cursor.execute('''
            UPDATE users SET name = ?, email = ?, age = ? WHERE id = ?
        ''', (name, email, age, current_user.id))
        
        # 프로필 정보 업데이트
        cursor.execute('''
            UPDATE user_profiles 
            SET housing_status = ?, income_level = ?, support_needs = ?
            WHERE user_id = ?
        ''', (housing_status, income_level, json.dumps(support_needs), current_user.id))
        
        # 비밀번호 변경 처리
        if current_password and new_password:
            cursor.execute('SELECT password_hash FROM users WHERE id = ?', (current_user.id,))
            stored_hash = cursor.fetchone()[0]
            
            if check_password_hash(stored_hash, current_password):
                new_hash = generate_password_hash(new_password)
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                             (new_hash, current_user.id))
                flash('비밀번호가 변경되었습니다.', 'success')
            else:
                flash('현재 비밀번호가 올바르지 않습니다.', 'error')
                conn.close()
                return redirect(url_for('mypage'))
        
        conn.commit()
        conn.close()
        
        flash('정보가 성공적으로 업데이트되었습니다.', 'success')
        return redirect(url_for('mypage'))
        
    except Exception as e:
        flash(f'업데이트 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('mypage'))

@app.route('/mypage/roadmaps')
@login_required
def mypage_roadmaps():
    return render_template('mypage_roadmaps.html')

@app.route('/mypage/todos')
@login_required
def mypage_todos():
    return redirect(url_for('todos'))

# 신청양식 생성 페이지
@app.route('/application-form')
def application_form_page():
    policy_name = request.args.get('policy', '')
    return render_template('application_form.html', policy_name=policy_name)

# 로그아웃
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    # 데이터베이스 초기화
    from database.init_db import init_database
    init_database()
    
    # 개선된 정책 매칭 시스템 초기화
    print("이루다 시스템 초기화 중...")
    if initialize_enhanced_matcher():
        print("✅ Enhanced Policy Matcher 준비 완료!")
    else:
        print("⚠️ 기본 시스템으로 시작 (Enhanced Matcher 비활성)")
    
    # 앱 실행
    print("🚀 이루다 서비스 시작!")
    app.run(debug=True, host='0.0.0.0', port=5000)
