window.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    const emailInput = document.querySelector('input[name="email"]');
    const passwordInput = document.querySelector('input[name="password"]');
    const password2Input = document.querySelector('input[name="password2"]');
    const nicknameInput = document.querySelector('input[name="nickname"]');
    const codeInput = document.querySelector('input[name="code"]');

    // 인증번호 입력 단계면 기존 회원가입 검사는 건너뜀
    if (codeInput) {
      return;
    }

    const email = emailInput ? emailInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value.trim() : "";
    const password2 = password2Input ? password2Input.value.trim() : "";
    const nickname = nicknameInput ? nicknameInput.value.trim() : "";

    if (!email || !password || !password2 || !nickname) {
      e.preventDefault();
      alert("모든 항목을 입력해주세요!");
      return;
    }

    if (!email.includes("@")) {
      e.preventDefault();
      alert("이메일 형식이 올바르지 않아요!");
      return;
    }

    if (password.length < 8) {
      e.preventDefault();
      alert("비밀번호는 8자 이상이어야 해요!");
      return;
    }

    const pwRule = /^(?=.*[a-zA-Z])(?=.*[0-9])(?=.*[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]).{8,}$/;
    if (!pwRule.test(password)) {
      e.preventDefault();
      alert("비밀번호는 영문, 숫자, 특수문자를 모두 포함해야 해요!");
      return;
    }

    if (password !== password2) {
      e.preventDefault();
      alert("비밀번호가 일치하지 않아요!");
      return;
    }
  });
});