document.addEventListener("DOMContentLoaded", function () {
    const tradeForm = document.getElementById("tradeForm");
    const strategyInput = document.getElementById("strategyInput");
    const strategySelector = document.getElementById("strategySelector");
    const tradeQuantity = document.getElementById("tradeQuantity");
    const tradeTypeInput = document.getElementById("tradeTypeInput");
    const balanceWarning = document.getElementById("balanceWarning");
    const totalAmount = document.getElementById("totalAmount");
    const currentBalanceEl = document.getElementById("current-balance");

    if (!tradeForm) return;

    const pricePerShare = parseInt(tradeForm.dataset.price || "0", 10);
    let currentBalance = parseInt(tradeForm.dataset.balance || "0", 10);
    const tradeUrl = tradeForm.dataset.tradeUrl;

    let maxQuantity = Math.floor(currentBalance / pricePerShare);

    if (strategyInput && strategySelector) {
        strategyInput.value = strategySelector.value;

        strategySelector.addEventListener("change", function () {
            strategyInput.value = this.value;
        });
    }

    if (tradeQuantity) {
        tradeQuantity.setAttribute("max", maxQuantity);
    }

    function updateTotal() {
        let quantity = parseInt(tradeQuantity.value, 10) || 1;

        if (quantity > maxQuantity) {
            quantity = maxQuantity;
            tradeQuantity.value = maxQuantity;
            balanceWarning.style.display = "block";
        } else {
            balanceWarning.style.display = "none";
        }

        if (quantity < 1) {
            quantity = 1;
            tradeQuantity.value = 1;
        }

        totalAmount.innerText = (pricePerShare * quantity).toLocaleString() + " 원";
    }

    if (tradeQuantity) {
        tradeQuantity.addEventListener("input", updateTotal);
    }

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

    updateTotal();
});