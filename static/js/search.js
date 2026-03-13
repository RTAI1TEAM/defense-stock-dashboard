// 네비게이션 바 종목 검색창에서 입력값에 따라 종목 목록을 필터링하는 스크립트
// 입력 시 검색 결과 표시, 바깥 클릭 시 결과창 닫기 처리
document.addEventListener("DOMContentLoaded", function(){
    const input = document.getElementById("navbarStockSearch");
    const results = document.getElementById("navbarStockResults");
    const items = document.querySelectorAll(".navbar-stock-item");
    const empty = document.getElementById("navbarEmpty");
    const newsItems = document.querySelectorAll(".news-item");


    if(input){    
        // 사용자가 검색창에 글자를 입력할 때마다 실행
        input.addEventListener("input", function(){
            const keyword = this.value.trim().toLowerCase();

            // 검색어가 없으면 결과창 숨김
            if(keyword === ""){
                results.style.display = "none";
                return;
            }
            // 검색어가 있으면 결과창 표시
            results.style.display = "block";
            let visible = 0;

            // 모든 종목 아이템 순회하면서 검색어 포함 여부 확인
            items.forEach(item => {
                const name = item.dataset.name;
                const ticker = item.dataset.ticker;
                // 종목명 혹은 티커에 검색어가 포함되면 표시
                if(name.includes(keyword) || ticker.includes(keyword)){
                    item.style.display = "block";
                    visible++;
                    } else {
                        item.style.display = "none";
                    }
            });

            // 결과가 -개면 "결과 없음" 문구 표시
            empty.style.display = visible === 0 ? "block" : "none";
        });

        document.addEventListener("click", function(e){
            // 클릭한 대상이 input이나 결과박스 내부가 아니면 결과창 닫기
            if(!input.contains(e.target) && !results.contains(e.target)){
                results.style.display = "none";
            }
        });
    } else return;
});

