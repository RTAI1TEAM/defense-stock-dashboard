from flask import Blueprint, render_template, request, jsonify  # jsonify 추가
from database import get_conn
news_bp = Blueprint('news', __name__)

PER_PAGE = 10

def get_news_from_db(keyword=None, page=1, per_page=PER_PAGE):
    conn = get_conn()
    offset = (page - 1) * per_page
    try:
        with conn.cursor() as cursor:
            if keyword:
                like_keyword = f"%{keyword}%"
                count_sql = """
                    SELECT COUNT(*) as total FROM news
                    WHERE title LIKE %s OR summary LIKE %s OR source LIKE %s
                """
                cursor.execute(count_sql, (like_keyword, like_keyword, like_keyword))
                total_count = cursor.fetchone()["total"]
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
                cursor.execute("SELECT COUNT(*) as total FROM news")
                total_count = cursor.fetchone()["total"]
                sql = """
                    SELECT id, title, summary, source, source_url,
                           thumbnail_url, published_at, view_count
                    FROM news
                    ORDER BY published_at DESC, id DESC
                    LIMIT %s OFFSET %s
                """
                cursor.execute(sql, (per_page, offset))

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
        conn.close()


def get_pagination(page, total_count, per_page=PER_PAGE, window=2):
    total_pages = max(1, -(-total_count // per_page))
    # 페이지 수 버튼 항상 5개 고정
    if total_pages <= 5:
        start = 1
        end = total_pages
    elif page <= 3:
        start = 1
        end = 5
    elif page >= total_pages - 2:
        start = total_pages - 4
        end = total_pages
    else:
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
    search_query = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", 1, type=int))

    all_news, total_count = get_news_from_db(
        keyword=search_query if search_query else None,
        page=page
    )

    # AJAX 요청인지 확인 (헤더 또는 파라미터로 구분)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if page == 1:
        top3_news = all_news[:3]
        list_news = all_news[3:]
    else:
        top3_news = []
        list_news = all_news

    pagination = get_pagination(page, total_count)

    # AJAX 요청일 경우 뉴스 데이터와 페이지 정보만 JSON으로 반환
    if is_ajax:
        return jsonify({
            "list_news": list_news,
            "pagination": pagination,
            "current_query": search_query
        })

    # 일반 접속 시 기존대로 페이지 렌더링
    return render_template(
        "news.html",
        top3_news=top3_news,
        list_news=list_news,
        total_count=total_count,
        current_query=search_query,
        pagination=pagination,
    )