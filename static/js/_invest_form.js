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

    if (!tradeForm) return; // 거래 폼이 없으면 스크립트 중단

    // form의 data-* 속성에서 값 읽기
    const pricePerShare = parseInt(tradeForm.dataset.price || "0", 10);
    let currentBalance = parseInt(tradeForm.dataset.balance || "0", 10);
    const tradeUrl = tradeForm.dataset.tradeUrl;

    // 현재 잔액 기준 최대 매수 가능 수량 계산
    let maxQuantity = Math.floor(currentBalance / pricePerShare);


 /* ══════════════════════════════════════════════════════════════════
       전략 선택값 동기화
       - select에서 고른 전략값을 hidden input에 반영
       - 서버 전송 시 선택한 전략이 함께 전달되도록 처리
    ══════════════════════════════════════════════════════════════════ */
    if (strategyInput && strategySelector) {
        // 처음 로딩될 때 선택된 전략 값을 입력 필드에 넣어줍니다.
        strategyInput.value = strategySelector.value;
        // 사용자가 드롭다운을 바꿀 때마다 hidden 필드 값을 갱신합니다.
        strategySelector.addEventListener("change", function () {
            strategyInput.value = this.value;
        });
    }
    // 수량 input의 최대값 설정
    if (tradeQuantity) {
        tradeQuantity.setAttribute("max", maxQuantity);
    }

 /* ══════════════════════════════════════════════════════════════════
       총 거래금액 계산 및 수량 검증
    ══════════════════════════════════════════════════════════════════ */
    function updateTotal() {
        let quantity = parseInt(tradeQuantity.value, 10) || 1;

        // 최대 매수 가능 수량 초과 시 자동 보정 + 경고 표시
        if (quantity > maxQuantity) {
            quantity = maxQuantity;
            tradeQuantity.value = maxQuantity;
            balanceWarning.style.display = "block"; // "잔액 부족" 경고 표시
        } else {
            balanceWarning.style.display = "none";
        }

        // 최소 수량은 1로 고정
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

    /* ══════════════════════════════════════════════════════════════════
      거래 요청 처리
    ══════════════════════════════════════════════════════════════════ */
    window.handleTrade = function (type) {
        // 매수 버튼 클릭 시 전달받은 'buy' 타입을 입력창에 세팅합니다.
        tradeTypeInput.value = type;

        // 폼에 적힌 수량, 전략 등의 정보를 보따리(FormData)에 담습니다.
        const formData = new FormData(tradeForm);

        fetch(tradeUrl, {
            method: "POST",
            body: formData
        })
        .then(response => response.json()) // 서버의 응답을 JSON 형식으로 해석합니다.
        .then(data => {
            if (data.success) {
                alert(data.message);

                // 매수 후 잔액이 줄었으므로, 서버에서 받은 새 잔액으로 화면 갱신
                if (data.new_balance) {
                    const newBalanceNum = parseInt(String(data.new_balance).replace(/,/g, ""), 10);

                    if (!isNaN(newBalanceNum)) {
                        currentBalance = newBalanceNum;
                        maxQuantity = Math.floor(currentBalance / pricePerShare);

                        if (currentBalanceEl) {
                            currentBalanceEl.innerText = Number(currentBalance).toLocaleString();
                        }

                        tradeQuantity.setAttribute("max", maxQuantity);
                    }
                }

                tradeQuantity.value = 1;
                totalAmount.innerText = pricePerShare.toLocaleString() + " 원";
                balanceWarning.style.display = "none";
            } else {
                alert("매수 실패: " + data.message);
            }
        })
        .catch(error => {
            console.error("Error:", error);
            alert("통신 오류가 발생했습니다.");
        });
    };

//초기 화면값 세팅
    updateTotal();
});