from flask import Blueprint, render_template, request
from database import get_conn

news_bp = Blueprint('news', __name__)


def get_news_from_db(keyword=None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            if keyword:
                sql = """
                SELECT
                    id,
                    title,
                    summary,
                    source,
                    source_url,
                    thumbnail_url,
                    published_at,
                    view_count
                FROM news
                WHERE title LIKE %s
                   OR summary LIKE %s
                   OR source LIKE %s
                ORDER BY published_at DESC, id DESC
                LIMIT 13
                """
                like_keyword = f"%{keyword}%"
                cursor.execute(sql, (like_keyword, like_keyword, like_keyword))
            else:
                sql = """
                SELECT
                    id,
                    title,
                    summary,
                    source,
                    source_url,
                    thumbnail_url,
                    published_at,
                    view_count
                FROM news
                ORDER BY published_at DESC, id DESC
                LIMIT 13
                """
                cursor.execute(sql)

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

            return rows
    finally:
        conn.close()


@news_bp.route("/")
@news_bp.route("/news")
def show_news():
    search_query = request.args.get("q", "").strip()
    all_news = get_news_from_db(search_query if search_query else None)

    top3_news = all_news[:3]
    list_news = all_news[3:13]

    return render_template(
        "news.html",
        top3_news=top3_news,
        list_news=list_news,
        total_count=len(all_news),
        current_query=search_query
    )