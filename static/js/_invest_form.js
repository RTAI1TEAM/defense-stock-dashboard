document.addEventListener("DOMContentLoaded", function () {
    const tradeForm = document.getElementById("tradeForm");
    const strategyInput = document.getElementById("strategyInput");
    const strategySelector = document.getElementById("strategySelector");
    const tradeQuantity = document.getElementById("tradeQuantity");
    const tradeTypeInput = document.getElementById("tradeTypeInput");
    const balanceWarning = document.getElementById("balanceWarning");
    const totalAmount = document.getElementById("totalAmount");
    const currentBalanceEl = document.getElementById("current-balance");

    if (!tradeForm) return;   // 거래 폼이 없으면 스크립트 중단

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
        strategyInput.value = strategySelector.value;

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
            balanceWarning.style.display = "block";
        } else {
            balanceWarning.style.display = "none";
        }
        // 최소 수량은 1로 고정
        if (quantity < 1) {
            quantity = 1;
            tradeQuantity.value = 1;
        }

        totalAmount.innerText = (pricePerShare * quantity).toLocaleString() + " 원";
    }

    if (tradeQuantity) {
        tradeQuantity.addEventListener("input", updateTotal);
    }

       /* ══════════════════════════════════════════════════════════════════
       거래 요청 처리
       ══════════════════════════════════════════════════════════════════ */
    window.handleTrade = function (type) {
        tradeTypeInput.value = type;

        const formData = new FormData(tradeForm);

        fetch(tradeUrl, {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);

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
                alert("거래 실패: " + data.message);
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