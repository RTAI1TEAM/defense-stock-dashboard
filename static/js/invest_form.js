function submitTrade() {
    const form = document.getElementById('tradeForm');
    const formData = new FormData(form);

    // fetch를 통해 백엔드에 '몰래' 데이터를 보냅니다.

    fetch("/invest/execute", {
        method: "POST",
        body: formData
    })
    .then(response => response.json()) // 여기서 JSON 데이터를 파싱합니다.
    .then(data => {
        if (data.success) {
            // 성공 시 알림창을 띄우고 창을 닫습니다.
            alert(data.message);
            
            // 3. 페이지 새로고침 없이 UI 업데이트 (옵션)
            // 예: document.getElementById('user-balance').innerText = data.new_balance.toLocaleString() + '원';
            
            goBack(); // 분석 카드로 돌아가는 함수 실행
        } else {
            alert("거래 실패: " + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("통신 오류가 발생했습니다.");
    });

    // fetch("{{ url_for('stock_detail.execute_trade') }}", {
    //     method: "POST",
    //     body: formData
    // })
    // .then(response => response.json()) // 여기서 JSON 데이터를 파싱합니다.
    // .then(data => {
    //     if (data.success) {
    //         // 성공 시 알림창을 띄우고 창을 닫습니다.
    //         alert(data.message);
            
    //         // 3. 페이지 새로고침 없이 UI 업데이트 (옵션)
    //         // 예: document.getElementById('user-balance').innerText = data.new_balance.toLocaleString() + '원';
            
    //         goBack(); // 분석 카드로 돌아가는 함수 실행
    //     } else {
    //         alert("거래 실패: " + data.message);
    //     }
    // })
    // .catch(error => {
    //     console.error('Error:', error);
    //     alert("통신 오류가 발생했습니다.");
    // });
// }