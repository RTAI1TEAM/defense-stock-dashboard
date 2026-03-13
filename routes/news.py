from flask import Blueprint, render_template, request, jsonify
from database import get_conn

# 뉴스 관련 기능을 담당하는 Blueprint 생성
news_bp = Blueprint('news', __name__)

# 한 페이지당 보여줄 뉴스 개수 설정
PER_PAGE = 13

def get_news_from_db(keyword=None, page=1, per_page=PER_PAGE):
    """
    데이터베이스에서 뉴스 목록을 가져오는 함수
    :param keyword: 검색어 (제목, 요약, 출처에서 검색)
    :param page: 현재 페이지 번호
    :param per_page: 페이지당 아이템 수
    :return: (뉴스 목록 리스트, 전체 뉴스 개수)
    """
    conn = get_conn()
    offset = (page - 1) * per_page  # SQL 시작 지점 계산
    
    try:
        with conn.cursor() as cursor:
            if keyword:
                # 검색어가 있을 경우: LIKE 연산자를 사용한 필터링 조회
                like_keyword = f"%{keyword}%"
                
                # 1. 검색 조건에 맞는 전체 개수 파악 (페이징 계산용)
                count_sql = """
                    SELECT COUNT(*) as total FROM news
                    WHERE title LIKE %s OR summary LIKE %s OR source LIKE %s
                """
                cursor.execute(count_sql, (like_keyword, like_keyword, like_keyword))
                total_count = cursor.fetchone()["total"]
                
                # 2. 검색 조건에 맞는 실제 데이터 조회 (최신순 정렬 및 페이징)
                sql = """
                    SELECT id, title, summary, source, source_url,
                           thumbnail_url, published_at, view_count
                    FROM news
                    WHERE title LIKE %s OR summary LIKE %s OR source LIKE %s
                    ORDER BY published_at DESC, id DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (like_keyword, like_keyword, like_keyword, per_page, offset))
            else:
                # 검색어가 없을 경우: 전체 뉴스 조회
                # 1. 전체 개수 파악
                cursor.execute("SELECT COUNT(*) as total FROM news")
                total_count = cursor.fetchone()["total"]
                
                # 2. 전체 데이터 조회 (최신순 정렬 및 페이징)
                sql = """
                    SELECT id, title, summary, source, source_url,
                           thumbnail_url, published_at, view_count
                    FROM news
                    ORDER BY published_at DESC, id DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (per_page, offset))

            # 조회된 데이터 가공 (템플릿에서 사용하기 편하도록 키 이름 매핑 및 날짜 포맷팅)
            rows = cursor.fetchall()
            for row in rows:
                row["title_clean"] = row["title"] or ""
                row["description_clean"] = row["summary"] or ""
                row["image_url"] = row["thumbnail_url"]
                row["source_name"] = row["source"] or ""
                row["pubDate_raw"] = (
                    row["published_at"].strftime("%Y-%m-%d %H:%M")
                    if row["published_at"] else ""
                )
            return rows, total_count 
    finally:
        # DB 연결 종료 (Context Manager를 사용하더라도 conn.close()는 명시적으로 처리)
        conn.close()


def get_pagination(page, total_count, per_page=PER_PAGE):
    """
    페이지네이션 버튼 로직 계산 함수 (현재 페이지를 기준으로 앞뒤 버튼 생성)
    :param page: 현재 페이지
    :param total_count: 전체 아이템 개수
    :param per_page: 페이지당 개수
    :return: 페이지네이션 정보 딕셔너리
    """
    # 전체 페이지 수 계산 (올림 처리)
    total_pages = max(1, -(-total_count // per_page)) 
    
    # 하단 페이지 번호 버튼 생성 로직 (항상 5개 고정)
    if total_pages <= 5:
        # 전체 페이지가 5개 이하이면 1부터 끝까지 표시
        start = 1
        end = total_pages
    elif page <= 3:
        # 현재 페이지가 앞쪽이면 1~5 표시
        start = 1
        end = 5
    elif page >= total_pages - 2:
        # 현재 페이지가 뒤쪽이면 마지막 5개 페이지 표시
        start = total_pages - 4
        end = total_pages
    else:
        # 현재 페이지가 중간이면 앞뒤로 2개씩 표시
        start = page - 2
        end = page + 2

    return {
        "current": page,
        "total_pages": total_pages,
        "pages": list(range(start, end + 1)),
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


@news_bp.route("/news")
def show_news():
    """
    뉴스 목록 페이지 접속 핸들러
    """
    # URL 파라미터로부터 검색어(q)와 페이지 번호(page)를 가져옴
    search_query = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", 1, type=int))
    
    # DB에서 데이터 조회
    all_news, total_count = get_news_from_db(
        keyword=search_query if search_query else None,
        page=page
    )

    # 요청이 AJAX(비동기)인지 확인 (Header의 X-Requested-With 확인)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # 화면 구성을 위한 데이터 분리: 상단 Top3 뉴스와 나머지 리스트 뉴스
    top3_news = all_news[:3]
    list_news = all_news[3:]

    # 페이지네이션 정보 계산
    pagination = get_pagination(page, total_count)

    # AJAX 요청일 경우 (예: 페이지 번호 클릭 시 전체 리프레시 없이 뉴스 목록만 교체)
    if is_ajax:
        return jsonify({
            "list_news": list_news,
            "pagination": pagination,
            "current_query": search_query
        })

    # 브라우저 직접 접속(일반 요청) 시 기존 HTML 템플릿 반환
    return render_template(
        "news.html",
        top3_news=top3_news,
        list_news=list_news,
        total_count=total_count,
        current_query=search_query,
        pagination=pagination,
    )