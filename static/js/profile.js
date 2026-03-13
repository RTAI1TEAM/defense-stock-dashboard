document.addEventListener("DOMContentLoaded", function () {
    const deleteForm = document.getElementById("deleteForm");
    const toggleDeleteBtn = document.getElementById("toggleDeleteBtn");

    if (deleteForm && toggleDeleteBtn) {
        toggleDeleteBtn.addEventListener("click", function () {
            const isHidden =
                deleteForm.style.display === "none" || deleteForm.style.display === "";

            deleteForm.style.display = isHidden ? "block" : "none";
        });

        const hasDeleteError = deleteForm.dataset.hasDeleteError === "true";
        if (hasDeleteError) {
            deleteForm.style.display = "block";
        }
    }

    const avatarModal = document.getElementById("avatarModal");
    const openAvatarModal = document.getElementById("openAvatarModal");
    const closeAvatarModal = document.getElementById("closeAvatarModal");
    const profileAvatar = document.getElementById("profileAvatar");
    const avatarOptions = document.querySelectorAll(".avatar-option");

    function openModal() {
        if (avatarModal) {
            avatarModal.classList.add("show");
            document.body.style.overflow = "hidden";
        }
    }

    function closeModal() {
        if (avatarModal) {
            avatarModal.classList.remove("show");
            document.body.style.overflow = "";
        }
    }

    if (openAvatarModal) {
        openAvatarModal.addEventListener("click", openModal);
    }

    if (closeAvatarModal) {
        closeAvatarModal.addEventListener("click", closeModal);
    }

    if (avatarModal) {
        avatarModal.addEventListener("click", function (e) {
            if (e.target === avatarModal) {
                closeModal();
            }
        });
    }

    avatarOptions.forEach(function (btn) {
        btn.addEventListener("click", function () {
            const selectedAvatar = btn.dataset.avatar;

            avatarOptions.forEach(function (item) {
                item.classList.remove("selected");
            });
            btn.classList.add("selected");

            fetch("/profile/change_avatar", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    avatar: selectedAvatar
                })
            })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("아바타 저장 실패");
                }
                return response.json();
            })
            .then(function (data) {
                if (data.status === "ok" && profileAvatar) {
                    profileAvatar.textContent = selectedAvatar;
                    
                    //프로필아바타 변경시 navbar 적용
                    const navbarAvatar = document.getElementById("navbarAvatar");
                    if (navbarAvatar) {
                    navbarAvatar.textContent = selectedAvatar;
        }

                    closeModal();
                }
            })

            .catch(function (error) {
                console.error(error);
                alert("아바타 저장 중 오류가 발생했습니다.");
            });
        });
    });
        // 비밀번호 변경 AJAX
    const changePasswordForm = document.getElementById("changePasswordForm");
    const passwordErrorBox = document.getElementById("passwordErrorBox");
    const passwordSuccessBox = document.getElementById("passwordSuccessBox");

    if (changePasswordForm) {
        changePasswordForm.addEventListener("submit", function (e) {
            e.preventDefault();

            if (passwordErrorBox) {
                passwordErrorBox.style.display = "none";
                passwordErrorBox.textContent = "";
            }

            if (passwordSuccessBox) {
                passwordSuccessBox.style.display = "none";
                passwordSuccessBox.textContent = "";
            }

            const formData = new FormData(changePasswordForm);

            fetch("/profile/change_password", {
                method: "POST",
                body: formData
            })
            .then(async function (response) {
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.message || "비밀번호 변경 실패");
                }

                return data;
            })
            .then(function (data) {
                if (data.status === "ok") {
                    if (passwordSuccessBox) {
                        passwordSuccessBox.textContent = data.message;
                        passwordSuccessBox.style.display = "block";
                    }

                    changePasswordForm.reset();

                    if (data.redirect_url) {
                        setTimeout(function () {
                            window.location.href = data.redirect_url;
                        }, 1000);
                    }
                }
            })
            .catch(function (error) {
                if (passwordErrorBox) {
                    passwordErrorBox.textContent = error.message;
                    passwordErrorBox.style.display = "block";
                }
            });
        });
    }
});
