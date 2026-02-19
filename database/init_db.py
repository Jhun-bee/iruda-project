import sqlite3
import os
from datetime import datetime

def init_database():
    """이루다 데이터베이스 초기화"""
    
    # database 디렉토리가 없으면 생성
    os.makedirs('database', exist_ok=True)
    
    conn = sqlite3.connect('database/iruda.db')
    cursor = conn.cursor()
    
    try:
        # 1. 사용자 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                age INTEGER DEFAULT 20,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. 사용자 프로필 테이블 (개선)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                housing_status TEXT,
                income_level TEXT,
                education_level TEXT DEFAULT '',
                employment_status TEXT DEFAULT '',
                support_needs TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # 3. 로드맵 테이블 (개선)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS roadmaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                priority_areas TEXT DEFAULT '[]',
                timeline TEXT DEFAULT '{}',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # 4. 새로운 Todos 테이블 (핵심 기능)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                roadmap_id INTEGER,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                due_date DATE NOT NULL,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                category TEXT DEFAULT '',
                completed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (roadmap_id) REFERENCES roadmaps (id) ON DELETE SET NULL
            )
        ''')
        
        # 5. 알림 테이블 (새로 추가)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                todo_id INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT DEFAULT 'info',
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (todo_id) REFERENCES todos (id) ON DELETE CASCADE
            )
        ''')
        
        # 6. 기존 progress_tracking 테이블 (호환성 유지)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS progress_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                roadmap_id INTEGER,
                task_name TEXT NOT NULL,
                task_category TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 3,
                completed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (roadmap_id) REFERENCES roadmaps (id) ON DELETE SET NULL
            )
        ''')
        
        # 7. 대화 히스토리 테이블 (새로 추가)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # 8. 정책 북마크 테이블 (새로 추가)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS policy_bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                policy_name TEXT NOT NULL,
                policy_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # 인덱스 생성 (성능 향상)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id ON roadmaps(user_id)')
        
        # 트리거 생성 (updated_at 자동 업데이트)
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_todos_timestamp 
            AFTER UPDATE ON todos
            FOR EACH ROW
            BEGIN
                UPDATE todos SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        ''')
        
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS update_user_profiles_timestamp
            AFTER UPDATE ON user_profiles
            FOR EACH ROW  
            BEGIN
                UPDATE user_profiles SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        ''')
        
        # 기본 데이터 삽입 (개발용)
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            print("샘플 데이터 생성 중...")
            
            # 샘플 사용자
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash('test123')
            
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, age) 
                VALUES ('테스트 사용자', 'test@iruda.com', ?, 22)
            ''', (password_hash,))
            
            user_id = cursor.lastrowid
            
            # 샘플 프로필
            cursor.execute('''
                INSERT INTO user_profiles 
                (user_id, housing_status, income_level, support_needs)
                VALUES (?, '자립준비청소년', '50만원 이하', '["주거지원", "경제지원", "취업지원"]')
            ''', (user_id,))
            
            # 샘플 로드맵
            import json
            sample_roadmap = {
                "1개월": ["주거급여 신청", "취업지원 프로그램 등록", "생계급여 확인"],
                "3개월": ["안정적 일자리 확보", "독립 주거 준비", "사회보험 가입"], 
                "6개월": ["비상자금 마련", "자립 네트워크 구축", "장기 계획 수립"]
            }
            
            cursor.execute('''
                INSERT INTO roadmaps 
                (user_id, title, description, priority_areas, timeline)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id,
                "테스트 사용자님의 자립 로드맵",
                "단계적 자립을 위한 맞춤형 계획",
                json.dumps(["주거 안정", "경제적 자립", "사회적 네트워크"]),
                json.dumps(sample_roadmap)
            ))
            
            roadmap_id = cursor.lastrowid
            
            # 샘플 Todos 생성
            from datetime import datetime, timedelta
            base_date = datetime.now()
            
            sample_todos = [
                {
                    'title': '주거급여 신청서 작성',
                    'description': '관할 주민센터에서 주거급여 신청서 제출',
                    'due_date': (base_date + timedelta(days=7)).strftime('%Y-%m-%d'),
                    'priority': 'high',
                    'category': '1개월'
                },
                {
                    'title': '취업지원센터 방문 상담',
                    'description': '지역 취업지원센터에서 맞춤형 취업 상담 받기',
                    'due_date': (base_date + timedelta(days=10)).strftime('%Y-%m-%d'),
                    'priority': 'high',
                    'category': '1개월'
                },
                {
                    'title': '이력서 및 자기소개서 작성',
                    'description': '표준 이력서 양식으로 작성 및 검토',
                    'due_date': (base_date + timedelta(days=14)).strftime('%Y-%m-%d'),
                    'priority': 'medium',
                    'category': '1개월'
                },
                {
                    'title': '생계급여 수급 자격 확인',
                    'description': '국민기초생활보장 수급 자격 요건 확인 및 신청',
                    'due_date': (base_date + timedelta(days=5)).strftime('%Y-%m-%d'),
                    'priority': 'high',
                    'category': '1개월'
                }
            ]
            
            for todo in sample_todos:
                cursor.execute('''
                    INSERT INTO todos 
                    (user_id, roadmap_id, title, description, due_date, priority, status, category)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                ''', (
                    user_id, roadmap_id, todo['title'], todo['description'],
                    todo['due_date'], todo['priority'], todo['category']
                ))
        
        conn.commit()
        print("✅ 데이터베이스 초기화 완료!")
        
        # 테이블 생성 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"생성된 테이블: {[table[0] for table in tables]}")
        
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    init_database()