import sqlite3
import os

def init_database():
    """SQLite 데이터베이스 초기화"""
    
    # 데이터베이스 폴더가 없으면 생성
    os.makedirs('database', exist_ok=True)
    
    # 데이터베이스 연결
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    
    # 사용자 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 사용자 프로필 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            housing_status TEXT,
            income_level TEXT,
            education_level TEXT,
            employment_status TEXT,
            psychological_state INTEGER,
            support_needs TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # 로드맵 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roadmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            priority_areas TEXT,
            timeline TEXT,
            ai_recommendations TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # 정책 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            eligibility_criteria TEXT,
            application_url TEXT,
            contact_info TEXT,
            deadline DATE,
            budget_amount BIGINT,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 진행상황 추적 테이블 (누락된 테이블!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progress_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            roadmap_id INTEGER,
            task_name TEXT NOT NULL,
            task_category TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 3,
            due_date DATE,
            completion_date DATE,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (roadmap_id) REFERENCES roadmaps (id) ON DELETE CASCADE
        )
    ''')
    
    # 사용자 피드백 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            roadmap_id INTEGER,
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            feedback_text TEXT,
            improvement_suggestions TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (roadmap_id) REFERENCES roadmaps (id) ON DELETE CASCADE
        )
    ''')
    
    # 샘플 정책 데이터 삽입 (정부 정책 DB에서 가져온 실제 데이터)
    sample_policies = [
        ('생계급여(맞춤형 급여)', '중앙부처', '수급자에게 생계급여를 지급합니다', 
         '{"대상": "가구의 소득인정액이 생계급여 선정기준 이하", "기관": "보건복지부"}',
         'https://www.gov.kr/portal/service/serviceInfo/PTR000050463'),
        
        ('청년 주거급여', '중앙부처', '만 19~29세 청년을 대상으로 한 주거비 지원',
         '{"age_min": 19, "age_max": 29, "income_criteria": "중위소득 46% 이하"}',
         'https://www.gov.kr/portal/service/serviceInfo/PTR000050464'),
        
        ('청년 취업 성공패키지', '중앙부처', '저소득 청년층 취업지원 및 직업훈련 프로그램',
         '{"age_min": 18, "age_max": 34, "employment_status": "구직자"}',
         'https://www.work.go.kr/youngjob'),
        
        ('한국장학재단 국가장학금', '중앙부처', '대학생 학비 부담 완화를 위한 장학금 지원',
         '{"education_status": "재학생", "income_criteria": "중위소득 70% 이하"}',
         'https://www.kosaf.go.kr'),
        
        ('청년 심리상담 지원', '중앙부처', '청년층 정신건강 상담 및 치료비 지원',
         '{"age_min": 19, "age_max": 34}',
         'https://www.blutouch.net'),
    ]
    
    # 기존 정책이 없는 경우만 삽입
    cursor.execute('SELECT COUNT(*) FROM policies')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO policies 
            (name, category, description, eligibility_criteria, application_url)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_policies)
    
    # 인덱스 생성 (성능 최적화)
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_policies_category ON policies(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id ON roadmaps(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_progress_user_id ON progress_tracking(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_progress_status ON progress_tracking(status)')
    
    conn.commit()
    conn.close()
    
    print("✅ 데이터베이스가 성공적으로 초기화되었습니다!")
    print("📊 테이블 생성 완료: users, user_profiles, roadmaps, policies, progress_tracking, user_feedback")

if __name__ == '__main__':
    init_database()