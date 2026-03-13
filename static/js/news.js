/**
 * news.js: 뉴스 목록 AJAX 렌더링 및 페이지네이션 제어
 */

const newsConfig = document.getElementById('newsConfig');
const INITIAL_QUERY = newsConfig.dataset.query;

/**
 * 뉴스 목록을 DOM에 그리는 함수
 */
function renderNewsItems(newsItems) {
    const container = document.getElementById('newsList');
    container.innerHTML = ''; // 기존 목록 삭제

    if (newsItems.length === 0) {
        container.innerHTML = '<div class="text-center py-5"><p class="text-muted">검색 결과가 없습니다.</p></div>';
        return;
    }

    newsItems.forEach(news => {
        const itemHtml = `
            <div class="news-item">
                <a href="${news.source_url}" target="_blank" class="text-decoration-none text-dark">
                    <div class="card mb-3 shadow-sm border-0" style="border-radius: 12px; overflow: hidden;">
                        <div class="row g-0 align-items-center">
                            <div class="col-auto">
                                <img src="${news.image_url || '/static/images/news_default.jpg'}" 
                                     style="width: 280px; height: 160px; object-fit: cover; flex-shrink: 0;"
                                     onerror="this.onerror=null;this.src='/static/images/news_default.jpg';">
                            </div>
                            <div class="col">
                                <div class="card-body">
                                    <h5 class="card-title fw-bold">${news.title_clean}</h5>
                                    <p class="card-text text-truncate" style="max-width: 600px;">${news.description_clean}</p>
                                    <p class="card-text">
                                        <small class="text-muted">${news.source_name} | ${news.pubDate_raw}</small>
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </a>
            </div>`;
        container.insertAdjacentHTML('beforeend', itemHtml);
    });
}

/**
 * 부트스트랩 스타일의 페이지네이션 버튼 업데이트
 */
function updatePaginationUI(pagination, query) {
    const paginationUl = document.getElementById('newsPagination');
    let html = '';

    // 이전 버튼
    const prevDisabled = pagination.current === 1 ? 'disabled' : '';
    html += `
        <li class="page-item ${prevDisabled}">
            <a class="page-link" href="#" onclick="fetchNewsPage(${pagination.current - 1}, '${query}'); return false;">&laquo;</a>
        </li>`;

    // 페이지 번호 버튼 (팀원 4번 알고리즘 적용)
    pagination.pages.forEach(p => {
        const activeClass = p === pagination.current ? 'active' : '';
        html += `
            <li class="page-item ${activeClass}">
                <a class="page-link" href="#" onclick="fetchNewsPage(${p}, '${query}'); return false;">${p}</a>
            </li>`;
    });

    // 다음 버튼
    const nextDisabled = pagination.current === pagination.total_pages ? 'disabled' : '';
    html += `
        <li class="page-item ${nextDisabled}">
            <a class="page-link" href="#" onclick="fetchNewsPage(${pagination.current + 1}, '${query}'); return false;">&raquo;</a>
        </li>`;

    paginationUl.innerHTML = html;
}

/**
 * 서버에 뉴스 데이터를 요청하는 핵심 AJAX 함수
 */
async function fetchNewsPage(page, query = '') {
    const url = `/news?page=${page}${query ? '&q=' + encodeURIComponent(query) : ''}`;
    
    try {
        const response = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' } // Flask에서 AJAX 요청임을 인식하게 함
        });
        
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();

        // UI 업데이트
        renderNewsItems(data.list_news);
        updatePaginationUI(data.pagination, data.current_query);

        // 브라우저 URL 업데이트 (뒤로가기 지원)
        window.history.pushState({ page, query }, '', url);
        
        // 페이지 상단으로 부드럽게 이동
        window.scrollTo({ top: 0, behavior: 'smooth' });

    } catch (error) {
        console.error('Fetch error:', error);
    }
}

/**
 * 초기 로딩 시 실행
 */
document.addEventListener('DOMContentLoaded', () => {
    const config = JSON.parse(newsConfig.dataset.pagination);
    updatePaginationUI(config, INITIAL_QUERY);
});