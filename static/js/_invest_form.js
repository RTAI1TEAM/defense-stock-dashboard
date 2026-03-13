document.addEventListener("DOMContentLoaded", function () {
    // --- 1. DOM 요소 선택 및 초기 데이터 설정 ---
    // 자바스크립트가 조작할 HTML의 "부품"들을 변수에 담아 준비합니다.
    const tradeForm = document.getElementById("tradeForm");
    const strategyInput = document.getElementById("strategyInput");
    const strategySelector = document.getElementById("strategySelector");
    const tradeQuantity = document.getElementById("tradeQuantity");
    const tradeTypeInput = document.getElementById("tradeTypeInput");
    const balanceWarning = document.getElementById("balanceWarning");
    const totalAmount = document.getElementById("totalAmount");
    const currentBalanceEl = document.getElementById("current-balance");

    // 필수 요소인 폼(Form)이 없으면 오류 방지를 위해 실행을 중단합니다.
    if (!tradeForm) return;

    // dataset: HTML 태그(data-price 등)에 심어둔 서버 데이터를 가져와 숫자로 변환합니다.
    const pricePerShare = parseInt(tradeForm.dataset.price || "0", 10);
    let currentBalance = parseInt(tradeForm.dataset.balance || "0", 10);
    const tradeUrl = tradeForm.dataset.tradeUrl;

    // [계산] 현재 잔액으로 살 수 있는 최대 수량을 미리 구해둡니다.
    let maxQuantity = Math.floor(currentBalance / pricePerShare);

    // --- 2. 전략 선택 및 입력 필드 동기화 ---
    if (strategyInput && strategySelector) {
        // 처음 로딩될 때 선택된 전략 값을 입력 필드에 넣어줍니다.
        strategyInput.value = strategySelector.value;
        // 사용자가 드롭다운을 바꿀 때마다 hidden 필드 값을 갱신합니다.
        strategySelector.addEventListener("change", function () {
            strategyInput.value = this.value;
        });
    }

    // 입력창에 '최대 수량' 제한을 겁니다.
    if (tradeQuantity) {
        tradeQuantity.setAttribute("max", maxQuantity);
    }

    // --- 3. 실시간 금액 계산 및 유효성 검사 함수 ---
    function updateTotal() {
        let quantity = parseInt(tradeQuantity.value, 10) || 1;

        // 잔액보다 더 많이 사려고 할 때의 처리
        if (quantity > maxQuantity) {
            quantity = maxQuantity;
            tradeQuantity.value = maxQuantity;
            balanceWarning.style.display = "block"; // "잔액 부족" 경고 표시
        } else {
            balanceWarning.style.display = "none";
        }

        // 최소 1개는 사야 하므로 1 미만 방지
        if (quantity < 1) {
            quantity = 1;
            tradeQuantity.value = 1;
        }

        // [화면 업데이트] "단가 * 수량"을 천 단위 콤마 형식으로 보여줍니다.
        totalAmount.innerText = (pricePerShare * quantity).toLocaleString() + " 원";
    }

    // 사용자가 수량을 타이핑할 때마다 위 함수를 실행합니다.
    if (tradeQuantity) {
        tradeQuantity.addEventListener("input", updateTotal);
    }

    // --- 4. 거래 실행 함수 (전역 window 객체 할당) ---
    /**
     * [알아두기] 왜 window.handleTrade인가요?
     * 이 스크립트 파일 안에서만 function을 만들면 HTML 버튼의 onclick="handleTrade()"가 찾지 못할 수 있습니다.
     * 'window'는 브라우저의 최상위 대장입니다. 여기에 등록하면 HTML 버튼 어디서든 이 함수를 부를 수 있습니다.
     */
    window.handleTrade = function (type) {
        // 매수 버튼 클릭 시 전달받은 'buy' 타입을 입력창에 세팅합니다.
        tradeTypeInput.value = type;

        // 폼에 적힌 수량, 전략 등의 정보를 보따리(FormData)에 담습니다.
        const formData = new FormData(tradeForm);

        /**
         * [비동기 통신: Fetch]
         * 페이지 새로고침 없이 서버와 몰래 통신하여 결과를 받아옵니다.
         */
        fetch(tradeUrl, {
            method: "POST",
            body: formData
        })
        .then(response => response.json()) // 서버의 응답을 JSON 형식으로 해석합니다.
        .then(data => {
            if (data.success) {
                // 매수 성공 시 서버가 보내준 축하(?) 메시지를 띄웁니다.
                alert(data.message);

                // 매수 후 잔액이 줄었으므로, 서버에서 받은 새 잔액으로 화면을 갱신합니다.
                if (data.new_balance) {
                    // 콤마가 포함된 문자열일 경우를 대비해 숫자로 정제합니다.
                    const newBalanceNum = parseInt(String(data.new_balance).replace(/,/g, ""), 10);

                    if (!isNaN(newBalanceNum)) {
                        currentBalance = newBalanceNum;
                        // 돈이 줄었으니 이제 살 수 있는 최대 수량도 다시 계산합니다.
                        maxQuantity = Math.floor(currentBalance / pricePerShare);

                        // 화면상의 잔액 글자를 새 숫자로 바꿉니다.
                        if (currentBalanceEl) {
                            currentBalanceEl.innerText = Number(currentBalance).toLocaleString();
                        }

                        // 수량 입력창의 max 값도 새롭게 제한합니다.
                        tradeQuantity.setAttribute("max", maxQuantity);
                    }
                }

                // 다음 거래를 위해 수량을 1로 초기화합니다.
                tradeQuantity.value = 1;
                totalAmount.innerText = pricePerShare.toLocaleString() + " 원";
                balanceWarning.style.display = "none";
            } else {
                // 서버에서 "돈이 모자라요" 등의 이유로 거절했을 때
                alert("매수 실패: " + data.message);
            }
        })
        .catch(error => {
            // 인터넷 끊김 등 통신 자체가 실패했을 때
            console.error("Error:", error);
            alert("통신 오류가 발생했습니다.");
        });
    };

    // 페이지가 처음 열릴 때 합계 금액을 한 번 계산해 둡니다.
    updateTotal();
});