"""데이터베이스 연결 및 CRUD 작업 모듈"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from contextlib import contextmanager

# PostgreSQL, MySQL, SQLite 지원
try:
    import psycopg2
    from psycopg2.extras import execute_values
    from psycopg2.pool import SimpleConnectionPool
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

# SQLite는 Python 표준 라이브러리
import sqlite3
SQLITE_AVAILABLE = True

from config.settings import BASE_DIR

logger = logging.getLogger(__name__)


class DatabaseAdapter:
    """데이터베이스 연결 및 작업 어댑터"""
    
    def __init__(
        self,
        db_type: str = "postgresql",  # "postgresql", "mysql", or "sqlite"
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        connection_string: Optional[str] = None
    ):
        """
        초기화
        
        Args:
            db_type: 데이터베이스 타입 ("postgresql", "mysql", or "sqlite")
            host: 호스트 주소 (SQLite는 사용 안 함)
            port: 포트 번호 (SQLite는 사용 안 함)
            database: 데이터베이스 이름 (SQLite는 파일 경로)
            user: 사용자 이름 (SQLite는 사용 안 함)
            password: 비밀번호 (SQLite는 사용 안 함)
            connection_string: 전체 연결 문자열 (환경 변수에서 가져올 수 있음)
        """
        self.db_type = db_type.lower()
        
        if self.db_type == "sqlite":
            # SQLite는 파일 경로만 필요
            self.database = database or os.getenv("DB_NAME", str(BASE_DIR / "data" / "news.db"))
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self.database), exist_ok=True)
        else:
            self.host = host or os.getenv("DB_HOST", "localhost")
            self.port = port or int(os.getenv("DB_PORT", "5432" if self.db_type == "postgresql" else "3306"))
            self.database = database or os.getenv("DB_NAME", "news_db")
            self.user = user or os.getenv("DB_USER", "postgres" if self.db_type == "postgresql" else "root")
            self.password = password or os.getenv("DB_PASSWORD", "")
        
        self.connection_string = connection_string or os.getenv("DB_CONNECTION_STRING")
        
        self.connection = None
        self.cursor = None
        
        if self.db_type == "postgresql" and not POSTGRESQL_AVAILABLE:
            raise ImportError("psycopg2가 설치되지 않았습니다. pip install psycopg2-binary")
        if self.db_type == "mysql" and not MYSQL_AVAILABLE:
            raise ImportError("pymysql이 설치되지 않았습니다. pip install pymysql")
        if self.db_type == "sqlite" and not SQLITE_AVAILABLE:
            raise ImportError("sqlite3가 사용 불가능합니다 (Python 표준 라이브러리)")
    
    def connect(self) -> None:
        """데이터베이스에 연결"""
        try:
            if self.db_type == "sqlite":
                # SQLite 연결
                self.connection = sqlite3.connect(self.database)
                self.connection.row_factory = sqlite3.Row  # 딕셔너리처럼 접근 가능
                self.cursor = self.connection.cursor()
                logger.info(f"✅ SQLite 데이터베이스 연결 성공: {self.database}")
            elif self.connection_string:
                if self.db_type == "postgresql":
                    self.connection = psycopg2.connect(self.connection_string)
                else:
                    # MySQL connection string 형식: mysql://user:password@host:port/database
                    import urllib.parse
                    parsed = urllib.parse.urlparse(self.connection_string.replace("mysql://", ""))
                    self.connection = pymysql.connect(
                        host=parsed.hostname or self.host,
                        port=parsed.port or self.port,
                        user=parsed.username or self.user,
                        password=parsed.password or self.password,
                        database=parsed.path.lstrip("/") or self.database,
                        charset='utf8mb4'
                    )
                self.cursor = self.connection.cursor()
                logger.info(f"✅ {self.db_type.upper()} 데이터베이스 연결 성공: {self.database}")
            else:
                if self.db_type == "postgresql":
                    self.connection = psycopg2.connect(
                        host=self.host,
                        port=self.port,
                        database=self.database,
                        user=self.user,
                        password=self.password
                    )
                else:
                    self.connection = pymysql.connect(
                        host=self.host,
                        port=self.port,
                        user=self.user,
                        password=self.password,
                        database=self.database,
                        charset='utf8mb4'
                    )
                self.cursor = self.connection.cursor()
                logger.info(f"✅ {self.db_type.upper()} 데이터베이스 연결 성공: {self.database}")
            
        except Exception as e:
            logger.error(f"❌ 데이터베이스 연결 실패: {e}")
            raise
    
    def close(self) -> None:
        """연결 종료"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("데이터베이스 연결 종료")
    
    @contextmanager
    def transaction(self):
        """트랜잭션 컨텍스트 매니저"""
        try:
            yield self
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"트랜잭션 롤백: {e}")
            raise
    
    def execute(self, query: str, params: Optional[tuple] = None) -> None:
        """쿼리 실행"""
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
        except Exception as e:
            logger.error(f"쿼리 실행 실패: {query[:100]}... - {e}")
            raise
    
    def fetchall(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """쿼리 결과 전체 조회"""
        # SQLite는 플레이스홀더가 ?를 사용
        if self.db_type == "sqlite" and params and "%s" in query:
            query = query.replace("%s", "?")
        
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        
        rows = self.cursor.fetchall()
        # SQLite Row 객체를 튜플로 변환
        if self.db_type == "sqlite":
            return [tuple(row) for row in rows]
        return rows
    
    def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[tuple]:
        """쿼리 결과 단일 행 조회"""
        # SQLite는 플레이스홀더가 ?를 사용
        if self.db_type == "sqlite" and params and "%s" in query:
            query = query.replace("%s", "?")
        
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        
        row = self.cursor.fetchone()
        # SQLite Row 객체를 튜플로 변환
        if self.db_type == "sqlite" and row:
            return tuple(row)
        return row
    
    def create_tables(self) -> None:
        """테이블 생성 (raw_news, processed_news)"""
        if self.db_type == "postgresql":
            self._create_tables_postgresql()
        elif self.db_type == "mysql":
            self._create_tables_mysql()
        elif self.db_type == "sqlite":
            self._create_tables_sqlite()
        else:
            raise ValueError(f"지원하지 않는 DB 타입: {self.db_type}")
        
        logger.info("✅ 테이블 생성 완료")
    
    def reset_database(self) -> None:
        """데이터베이스 초기화 (모든 테이블 삭제 후 재생성)"""
        logger.warning("⚠️  모든 테이블을 삭제하고 재생성합니다.")
        
        try:
            # 테이블 순서 중요 (외래 키 제약 조건 때문)
            tables = ["processed_news", "raw_news"]
            
            for table in tables:
                logger.info(f"테이블 삭제: {table}")
                if self.db_type == "sqlite":
                    self.execute(f"DROP TABLE IF EXISTS {table}")
                    self.connection.commit()
                else:
                    self.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                    self.connection.commit()
            
            # 테이블 재생성
            self.create_tables()
            logger.info("✅ 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 데이터베이스 초기화 실패: {e}")
            raise
    
    def _create_tables_postgresql(self) -> None:
        """PostgreSQL 테이블 생성"""
        # raw_news 테이블
        self.execute("""
            CREATE TABLE IF NOT EXISTS raw_news (
                id BIGSERIAL PRIMARY KEY,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source VARCHAR(50),
                title TEXT,
                snippet TEXT,
                url TEXT UNIQUE,
                published TEXT,
                search_rank INT,
                raw_html_features JSONB,
                publisher VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # processed_news 테이블 (Lane 없음)
        self.execute("""
            CREATE TABLE IF NOT EXISTS processed_news (
                id BIGSERIAL PRIMARY KEY,
                ref_raw_id BIGINT REFERENCES raw_news(id),
                published_at TIMESTAMP,
                source_normalized VARCHAR(50),
                language CHAR(2),
                search_rank INT,
                is_kr BOOLEAN DEFAULT FALSE,
                is_re BOOLEAN DEFAULT FALSE,
                process_status VARCHAR(20) DEFAULT 'PHASE_1_DONE',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 인덱스 생성
        self.execute("CREATE INDEX IF NOT EXISTS idx_raw_news_url ON raw_news(url);")
        self.execute("CREATE INDEX IF NOT EXISTS idx_raw_news_source ON raw_news(source);")
        self.execute("CREATE INDEX IF NOT EXISTS idx_processed_news_ref_raw ON processed_news(ref_raw_id);")
        
        self.connection.commit()
    
    def _create_tables_mysql(self) -> None:
        """MySQL 테이블 생성"""
        # raw_news 테이블
        self.execute("""
            CREATE TABLE IF NOT EXISTS raw_news (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source VARCHAR(50),
                title TEXT,
                snippet TEXT,
                url TEXT,
                published TEXT,
                search_rank INT,
                raw_html_features JSON,
                publisher VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_url (url(255))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # processed_news 테이블
        self.execute("""
            CREATE TABLE IF NOT EXISTS processed_news (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ref_raw_id BIGINT,
                published_at TIMESTAMP,
                source_normalized VARCHAR(50),
                language CHAR(2),
                search_rank INT,
                is_kr BOOLEAN DEFAULT FALSE,
                is_re BOOLEAN DEFAULT FALSE,
                process_status VARCHAR(20) DEFAULT 'PHASE_1_DONE',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ref_raw_id) REFERENCES raw_news(id) ON DELETE CASCADE,
                INDEX idx_ref_raw (ref_raw_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        self.connection.commit()
    
    def _create_tables_sqlite(self) -> None:
        """SQLite 테이블 생성"""
        # raw_news 테이블
        self.execute("""
            CREATE TABLE IF NOT EXISTS raw_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source VARCHAR(50),
                title TEXT,
                snippet TEXT,
                url TEXT UNIQUE,
                published TEXT,
                search_rank INTEGER,
                raw_html_features TEXT,
                publisher TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # processed_news 테이블
        self.execute("""
            CREATE TABLE IF NOT EXISTS processed_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ref_raw_id INTEGER REFERENCES raw_news(id),
                published_at TIMESTAMP,
                source_normalized VARCHAR(50),
                language CHAR(2),
                search_rank INTEGER,
                is_kr INTEGER DEFAULT 0,
                is_re INTEGER DEFAULT 0,
                process_status VARCHAR(20) DEFAULT 'PHASE_1_DONE',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 인덱스 생성
        self.execute("CREATE INDEX IF NOT EXISTS idx_raw_news_url ON raw_news(url);")
        self.execute("CREATE INDEX IF NOT EXISTS idx_raw_news_source ON raw_news(source);")
        self.execute("CREATE INDEX IF NOT EXISTS idx_processed_news_ref_raw ON processed_news(ref_raw_id);")
        
        self.connection.commit()
    
    def insert_raw_news(self, articles: List[Dict[str, Any]], source: str) -> List[int]:
        """raw_news 테이블에 기사 삽입"""
        if not articles:
            return []
        
        inserted_ids = []
        title_conflict_count = 0
        
        for rank, article in enumerate(articles, start=1):
            try:
                url = article.get("url", "").strip()
                title = article.get("title", "").strip()
                snippet = article.get("summary", "") or article.get("snippet", "")
                publisher = article.get("source", "") or source
                
                if not url:
                    logger.warning(f"기사 삽입 건너뛰기: URL이 없음 (제목: {title[:50]})")
                    continue
                
                # URL 중복 시 제목 확인
                if self.db_type == "sqlite":
                    existing = self.fetchone(
                        "SELECT id, title FROM raw_news WHERE url = ? LIMIT 1;",
                        (url,)
                    )
                else:
                    existing = self.fetchone(
                        "SELECT id, title FROM raw_news WHERE url = %s LIMIT 1;",
                        (url,)
                    )
                
                if existing:
                    existing_id, existing_title = existing[0], existing[1]
                    if existing_title and existing_title.strip() != title:
                        title_conflict_count += 1
                        logger.warning(
                            f"⚠️ URL 중복 + 제목 불일치 감지 -> 기존 레코드 업데이트 (ID: {existing_id})"
                        )
                        # 기존 레코드 업데이트
                        if self.db_type == "postgresql":
                            self.cursor.execute(
                                "UPDATE raw_news SET title = %s, snippet = %s, published = %s, search_rank = %s, collected_at = %s WHERE id = %s;",
                                (title, snippet, article.get("published", ""), rank, datetime.utcnow(), existing_id)
                            )
                        elif self.db_type == "sqlite":
                            self.cursor.execute(
                                "UPDATE raw_news SET title = ?, snippet = ?, published = ?, search_rank = ?, collected_at = ? WHERE id = ?;",
                                (title, snippet, article.get("published", ""), rank, datetime.utcnow(), existing_id)
                            )
                        else:  # MySQL
                            self.cursor.execute(
                                "UPDATE raw_news SET title = %s, snippet = %s, published = %s, search_rank = %s, collected_at = %s WHERE id = %s;",
                                (title, snippet, article.get("published", ""), rank, datetime.utcnow(), existing_id)
                            )
                        inserted_ids.append(existing_id)
                        continue
                    else:
                        continue
                
                # 새로운 기사 삽입
                if self.db_type == "postgresql":
                    query = """
                        INSERT INTO raw_news (collected_at, source, title, snippet, url, published, search_rank, publisher)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                        RETURNING id;
                    """
                    params = (datetime.utcnow(), source, title, snippet, url, article.get("published", ""), rank, publisher)
                    self.cursor.execute(query, params)
                    result = self.cursor.fetchone()
                    if result:
                        inserted_ids.append(result[0])
                elif self.db_type == "sqlite":
                    query = """
                        INSERT OR IGNORE INTO raw_news (collected_at, source, title, snippet, url, published, search_rank, publisher)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """
                    params = (datetime.utcnow(), source, title, snippet, url, article.get("published", ""), rank, publisher)
                    self.cursor.execute(query, params)
                    if self.cursor.rowcount > 0:
                        inserted_ids.append(self.cursor.lastrowid)
                else:  # MySQL
                    query = """
                        INSERT INTO raw_news (collected_at, source, title, snippet, url, published, search_rank, publisher)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE id=id;
                    """
                    params = (datetime.utcnow(), source, title, snippet, url, article.get("published", ""), rank, publisher)
                    self.cursor.execute(query, params)
                    if self.cursor.rowcount > 0:
                        inserted_ids.append(self.cursor.lastrowid)
                
            except Exception as e:
                logger.warning(f"기사 삽입 실패 (URL: {article.get('url', 'N/A')[:50]}): {e}")
                continue
        
        self.connection.commit()
        if title_conflict_count > 0:
            logger.warning(f"⚠️ {source}: URL 중복 + 제목 불일치 {title_conflict_count}건 감지")
        
        logger.info(f"✅ {source}: {len(inserted_ids)}개 기사 raw_news에 저장")
        return inserted_ids
    
    def insert_processed_news(self, processed_articles: List[Dict[str, Any]]) -> int:
        """processed_news 테이블에 처리된 기사 삽입 (Lane 없음)"""
        if not processed_articles:
            return 0
        
        count = 0
        
        for article in processed_articles:
            try:
                if self.db_type == "sqlite":
                    query = """
                        INSERT INTO processed_news 
                        (ref_raw_id, published_at, source_normalized, language, search_rank, 
                         process_status)
                        VALUES (?, ?, ?, ?, ?, ?);
                    """
                else:
                    query = """
                        INSERT INTO processed_news 
                        (ref_raw_id, published_at, source_normalized, language, search_rank, 
                         process_status)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """
                
                params = (
                    article.get("ref_raw_id"),
                    article.get("published_at"),
                    article.get("source_normalized"),
                    article.get("language"),
                    article.get("search_rank"),
                    article.get("process_status", "PHASE_1_DONE")
                )
                self.cursor.execute(query, params)
                count += 1
            except Exception as e:
                logger.warning(f"처리된 기사 삽입 실패 (ref_raw_id: {article.get('ref_raw_id')}): {e}")
                continue
        
        self.connection.commit()
        logger.info(f"✅ {count}개 기사 processed_news에 저장")
        return count
    
    def get_raw_news_for_processing(self) -> List[Dict[str, Any]]:
        """Phase 1 처리 대상 raw_news 조회"""
        query = """
            SELECT r.id, r.collected_at, r.source, r.title, r.snippet, r.url, r.published, r.search_rank
            FROM raw_news r
            LEFT JOIN processed_news p ON r.id = p.ref_raw_id
            WHERE p.id IS NULL
            ORDER BY r.source, r.search_rank;
        """
        
        rows = self.fetchall(query)
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "collected_at": row[1],
                "source": row[2],
                "title": row[3],
                "snippet": row[4],
                "url": row[5],
                "published": row[6],
                "search_rank": row[7]
            })
        return result

    def ensure_llm_columns(self) -> None:
        """processed_news 테이블에 LLM 결과 컬럼이 없으면 추가"""
        columns = [
            ("llm_decision", "VARCHAR(10)"),
            ("llm_category", "VARCHAR(50)"),
            ("llm_reason", "TEXT")
        ]
        
        for col_name, col_type in columns:
            try:
                if self.db_type == "sqlite":
                    cursor = self.connection.cursor()
                    cursor.execute(f"PRAGMA table_info(processed_news)")
                    existing_cols = [row[1] for row in cursor.fetchall()]
                    
                    if col_name not in existing_cols:
                        logger.info(f"Adding column '{col_name}' to processed_news table...")
                        self.execute(f"ALTER TABLE processed_news ADD COLUMN {col_name} {col_type}")
                        
                elif self.db_type in ["postgresql", "mysql"]:
                    try:
                       self.execute(f"ALTER TABLE processed_news ADD COLUMN {col_name} {col_type}")
                       logger.info(f"Added column '{col_name}'")
                    except Exception as e:
                        logger.debug(f"Column '{col_name}' might already exist: {e}")
                        self.connection.rollback()
            except Exception as e:
                logger.error(f"Failed to add column {col_name}: {e}")
        
        self.connection.commit()

    def update_llm_results(self, results: List[Dict[str, Any]]) -> int:
        """LLM 분류 결과를 processed_news에 업데이트"""
        if not results:
            return 0
            
        count = 0
        try:
            data = [
                (r.get("decision"), r.get("category"), r.get("reason"), r.get("id"))
                for r in results
            ]
            
            if self.db_type == "sqlite":
                query = "UPDATE processed_news SET llm_decision=?, llm_category=?, llm_reason=?, process_status='PHASE_4_DONE' WHERE id=?"
            else:
                query = "UPDATE processed_news SET llm_decision=%s, llm_category=%s, llm_reason=%s, process_status='PHASE_4_DONE' WHERE id=%s"
                
            self.cursor.executemany(query, data)
            self.connection.commit()
            count = len(results)
            logger.info(f"✅ Updated LLM results for {count} articles")
            
        except Exception as e:
            logger.error(f"❌ Failed to batch update LLM results: {e}")
            self.connection.rollback()
            
        return count

    def ensure_publisher_column(self) -> None:
        """raw_news 테이블에 publisher 컬럼이 없으면 추가"""
        col_name = "publisher"
        col_type = "VARCHAR(100)" if self.db_type != "sqlite" else "TEXT"
        
        try:
            if self.db_type == "sqlite":
                cursor = self.connection.cursor()
                cursor.execute(f"PRAGMA table_info(raw_news)")
                existing_cols = [row[1] for row in cursor.fetchall()]
                
                if col_name not in existing_cols:
                    logger.info(f"Adding column '{col_name}' to raw_news table...")
                    self.execute(f"ALTER TABLE raw_news ADD COLUMN {col_name} {col_type}")
                    
            elif self.db_type in ["postgresql", "mysql"]:
                try:
                   self.execute(f"ALTER TABLE raw_news ADD COLUMN {col_name} {col_type}")
                   logger.info(f"Added column '{col_name}' to raw_news")
                except Exception as e:
                    logger.debug(f"Column '{col_name}' might already exist: {e}")
                    self.connection.rollback()

        except Exception as e:
            logger.error(f"Failed to add column {col_name} to raw_news: {e}")
        
        self.connection.commit()
