/**
 * 테이블 정렬 상태 기록 객체
 * 예: { 'tableId_0': true } (true는 오름차순, false는 내림차순)
 */
const sortOrders = {};

/**
 * 테이블의 특정 열을 기준으로 행을 정렬하는 함수
 * @param {string} tableId - 정렬할 테이블의 ID
 * @param {number} colIndex - 클릭한 헤더의 열 인덱스 (0부터 시작)
 */
function sortTable(tableId, colIndex) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const tbody = table.querySelector("tbody");
    // 1. tbody 안의 모든 행(tr)을 가져와 배열로 변환
    const rows = Array.from(tbody.querySelectorAll("tr"));

    // 2. 정렬 방향 결정 (기존 상태가 없으면 오름차순, 있으면 반전)
    const key = `${tableId}_${colIndex}`;
    const asc = sortOrders[key] === undefined ? true : !sortOrders[key];
    sortOrders[key] = asc;

    // 3. 데이터 비교 및 정렬 로직 시작
    rows.sort((a, b) => {
        // 비교할 셀의 텍스트 가져오기
        let x = a.cells[colIndex].innerText.trim();
        let y = b.cells[colIndex].innerText.trim();

        // 4. 숫자 데이터 전처리: 콤마(,), 단위(원, %) 등을 제거하고 숫자와 마침표만 남김
        let xVal = x.replace(/[^0-9.-]+/g, "");
        let yVal = y.replace(/[^0-9.-]+/g, "");

        // 5. 최종 비교값 결정: 숫자면 parseFloat로 변환, 숫자가 아니면 일반 문자열(소문자) 처리
        let xFinal = xVal !== "" && !isNaN(parseFloat(xVal)) ? parseFloat(xVal) : x.toLowerCase();
        let yFinal = yVal !== "" && !isNaN(parseFloat(yVal)) ? parseFloat(yVal) : y.toLowerCase();

        // 6. 실제 정렬 방향에 따른 비교 결과 반환
        if (xFinal < yFinal) return asc ? -1 : 1;
        if (xFinal > yFinal) return asc ? 1 : -1;
        return 0;
    });

    // 7. 정렬된 행들을 다시 tbody에 추가 (기존 순서가 덮어씌워짐)
    rows.forEach(row => tbody.appendChild(row));
    
    // 8. 정렬 후 순위(첫 번째 열) 업데이트
    updateRank(tableId);
}

/**
 * 테이블 정렬 후 첫 번째 열(No. 또는 순위)의 번호를 재지정하는 함수
 * @param {string} tableId - 대상 테이블의 ID
 */
function updateRank(tableId) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    rows.forEach((row, index) => {
        // 첫 번째 셀(Index 0)에 현재 행의 인덱스 + 1을 삽입
        row.cells[0].innerText = index + 1;
    });
}