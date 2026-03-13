/**
 * news.js: 뉴스 목록 AJAX 렌더링 및 페이지네이션 제어
 */

// HTML의 hidden input이나 dataset에서 초기 검색어 설정을 읽어옴
const newsConfig = document.getElementById('newsConfig');
const INITIAL_QUERY = newsConfig.dataset.query;

/**
 * 1. 뉴스 목록을 DOM에 그리는 함수
 * @param {Array} newsItems - 서버로부터 받은 뉴스 객체 배열
 */
function renderNewsItems(newsItems) {
    const container = document.getElementById('newsList');
    container.innerHTML = ''; // 기존에 표시되던 뉴스 목록을 비움

    // 데이터가 없을 경우 안내 문구 표시
    if (newsItems.length === 0) {
        container.innerHTML = '<div class="text-center py-5"><p class="text-muted">검색 결과가 없습니다.</p></div>';
        return;
    }

    // 뉴스 배열을 순회하며 HTML 구조 생성 및 삽입
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
 * 2. 부트스트랩 스타일의 페이지네이션 버튼 업데이트
 * @param {Object} pagination - Flask 서버에서 계산해서 보내준 페이지 정보
 * @param {string} query - 현재 유지 중인 검색어
 */
function updatePaginationUI(pagination, query) {
    const paginationUl = document.getElementById('newsPagination');
    let html = '';

    // [이전] 버튼 생성: 1페이지인 경우 비활성화(disabled)
    const prevDisabled = pagination.current === 1 ? 'disabled' : '';
    html += `
        <li class="page-item ${prevDisabled}">
            <a class="page-link" href="#" onclick="fetchNewsPage(${pagination.current - 1}, '${query}'); return false;">&laquo;</a>
        </li>`;

    // 페이지 번호 루프: 서버에서 계산된 범위(pages)만큼 버튼 생성
    pagination.pages.forEach(p => {
        const activeClass = p === pagination.current ? 'active' : '';
        html += `
            <li class="page-item ${activeClass}">
                <a class="page-link" href="#" onclick="fetchNewsPage(${p}, '${query}'); return false;">${p}</a>
            </li>`;
    });

    // [다음] 버튼 생성: 마지막 페이지인 경우 비활성화(disabled)
    const nextDisabled = pagination.current === pagination.total_pages ? 'disabled' : '';
    html += `
        <li class="page-item ${nextDisabled}">
            <a class="page-link" href="#" onclick="fetchNewsPage(${pagination.current + 1}, '${query}'); return false;">&raquo;</a>
        </li>`;

    paginationUl.innerHTML = html;
}

/**
 * 3. 서버에 뉴스 데이터를 요청하는 핵심 AJAX 함수
 * @param {number} page - 요청할 페이지 번호
 * @param {string} query - 검색 키워드
 */
async function fetchNewsPage(page, query = '') {
    // 요청 URL 생성 (페이지와 인코딩된 검색어 포함)
    const url = `/news?page=${page}${query ? '&q=' + encodeURIComponent(query) : ''}`;
    
    try {
        // 비동기 fetch 호출
        const response = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' } // Flask 백엔드에서 AJAX 요청임을 식별하도록 헤더 추가
        });
        
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json(); // JSON 데이터 파싱

        // 1. 받아온 뉴스 목록으로 UI 갱신
        renderNewsItems(data.list_news);
        // 2. 페이지네이션 상태 갱신
        updatePaginationUI(data.pagination, data.current_query);

        // 3. 브라우저 주소창 업데이트: 페이지 새로고침 없이 URL만 변경 (뒤로가기/앞으로가기 지원)
        window.history.pushState({ page, query }, '', url);
        
        // 4. 사용자 편의를 위해 스크롤을 맨 위로 이동
        window.scrollTo({ top: 0, behavior: 'smooth' });

    } catch (error) {
        console.error('Fetch error:', error);
        alert('뉴스 데이터를 불러오는 중 오류가 발생했습니다.');
    }
}

/**
 * 4. 초기 로딩 시 실행되는 초기화 로직
 */
document.addEventListener('DOMContentLoaded', () => {
    // 서버가 HTML 렌더링 시 심어준 초기 페이지네이션 설정 데이터를 파싱
    const config = JSON.parse(newsConfig.dataset.pagination);
    updatePaginationUI(config, INITIAL_QUERY);

    // 검색창 엔터키 이벤트 바인딩
    const searchInput = document.getElementById("NewsSearch");
    if (searchInput) {
        searchInput.addEventListener("keypress", function (e) {
            if (e.key === "Enter") {
                e.preventDefault(); // 양식(form) 제출로 인한 페이지 새로고침 방지
                const query = e.target.value.trim();
                fetchNewsPage(1, query); // 검색 시 무조건 1페이지부터 결과 출력
            }
        });
    }
});