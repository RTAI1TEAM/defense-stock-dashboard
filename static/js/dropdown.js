document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("stockSearchInput");         // 검색 입력창
    const items = document.querySelectorAll(".stock-item");            // 전체 종목 목록 아이템
    const emptyMessage = document.getElementById("stockEmptyMessage"); // 검색 결과 없을 때 표시할 메시지

    // 입력창이 없으면 실행 중단
    if (!input) return;

    // ──────────────────────────────────────────────
    // 종목 검색 필터링 (input 이벤트)
    // 종목명 또는 티커가 키워드와 일치하는 항목만 표시
    // ──────────────────────────────────────────────
    input.addEventListener("input", function () {
        const keyword = this.value.trim().toLowerCase(); // 입력값 소문자 변환
        let visibleCount = 0; // 검색 결과 개수 카운트

        items.forEach(item => {
            const name = item.dataset.name || "";     // 종목명
            const ticker = item.dataset.ticker || ""; // 티커

            // 종목명 또는 티커가 키워드를 포함하는지 확인
            const matched = name.includes(keyword) || ticker.includes(keyword);

            if (matched) {
                item.style.display = "block"; // 일치하면 표시
                visibleCount++;
            } else {
                item.style.display = "none";  // 불일치하면 숨김
            }
        });

        // 검색 결과가 없을 때 안내 메시지 표시
        emptyMessage.style.display = visibleCount === 0 ? "block" : "none";
    });

    // ──────────────────────────────────────────────
    // 드롭다운 열릴 때 검색창 자동 포커스
    // ──────────────────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="dropdown"]').forEach(btn => {
        btn.addEventListener("shown.bs.dropdown", function () {
            setTimeout(() => input.focus(), 100); // 드롭다운 애니메이션 후 포커스
        });
    });
});