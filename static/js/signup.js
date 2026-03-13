window.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form");
  if (!form) return; // 폼이 없으면 실행 중단

  // ──────────────────────────────────────────────
  // 회원가입 폼 유효성 검사 (submit 이벤트)
  // 인증번호 입력 단계에서는 검사 건너뜀
  // ──────────────────────────────────────────────
  form.addEventListener("submit", function (e) {
    const emailInput = document.querySelector('input[name="email"]');
    const passwordInput = document.querySelector('input[name="password"]');
    const password2Input = document.querySelector('input[name="password2"]'); // 비밀번호 확인
    const nicknameInput = document.querySelector('input[name="nickname"]');
    const codeInput = document.querySelector('input[name="code"]');           // 인증번호 입력창

    // 인증번호 입력 단계면 유효성 검사 건너뜀
    if (codeInput) {
      return;
    }

    // 각 입력값 추출 (없으면 빈 문자열)
    const email = emailInput ? emailInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value.trim() : "";
    const password2 = password2Input ? password2Input.value.trim() : "";
    const nickname = nicknameInput ? nicknameInput.value.trim() : "";

    // 필수 항목 전체 입력 여부 확인
    if (!email || !password || !password2 || !nickname) {
      e.preventDefault();
      alert("모든 항목을 입력해주세요!");
      return;
    }

    // 이메일 형식 확인 (@포함 여부)
    if (!email.includes("@")) {
      e.preventDefault();
      alert("이메일 형식이 올바르지 않아요!");
      return;
    }

    // 비밀번호 최소 길이 확인 (8자 이상)
    if (password.length < 8) {
      e.preventDefault();
      alert("비밀번호는 8자 이상이어야 해요!");
      return;
    }

    // 비밀번호 복잡도 확인 (영문 + 숫자 + 특수문자 모두 포함)
    const pwRule = /^(?=.*[a-zA-Z])(?=.*[0-9])(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;
    if (!pwRule.test(password)) {
      e.preventDefault();
      alert("비밀번호는 영문, 숫자, 특수문자를 모두 포함해야 해요!");
      return;
    }

    // 비밀번호 일치 여부 확인
    if (password !== password2) {
      e.preventDefault();
      alert("비밀번호가 일치하지 않아요!");
      return;
    }
  });
});