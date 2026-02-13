/**
 * 인증 관련 기능 (로그인/회원가입)
 */

const API_BASE_URL = "http://localhost:8000";

// 유효성 검사 규칙
const validators = {
    id: (val) => /^[a-zA-Z0-9]{4,}$/.test(val),
    pw: (val) => val.length >= 8,
    name: (val) => /^[가-힣]{2,}$/.test(val),
    phone: (val) => /^010-\d{4}-\d{4}$/.test(val),
    email: (val) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)
};

function toggleError(inputId, isValid, errorMessage = "") {
    /* 에러 메시지 표시/숨김 */
    const input = document.getElementById(inputId);
    let errorTag = input.nextElementSibling;
    
    while(errorTag && !errorTag.classList.contains("error-message")) {
        errorTag = errorTag.nextElementSibling;
    }

    if (!input) return;

    if (isValid) {
        input.classList.remove("input-error");
        if(errorTag) {
            errorTag.style.display = "none";
            errorTag.classList.remove("show");
        }
    } else {
        input.classList.add("input-error");
        if(errorTag) {
            errorTag.textContent = errorMessage;
            errorTag.style.display = "block";
            errorTag.classList.add("show");
        }
    }
}

function showGlobalError(element, message) {
    /* 전역 에러 메시지 표시 */
    if (element) {
        element.textContent = message;
        element.style.display = "block";
        element.classList.add("show");
    } else {
        alert(message);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // ======== 로그인 로직 ========
    const loginForm = document.getElementById("loginForm");
    
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const userId = document.getElementById("loginId").value;
            const userPw = document.getElementById("loginPw").value;
            const errorMsg = document.getElementById("errorMessage");

            errorMsg.style.display = "none";

            try {
                const response = await fetch(`${API_BASE_URL}/auth/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: userId, password: userPw })
                });

                if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem("accessToken", data.access_token);
                    localStorage.setItem("userId", userId);
                    localStorage.setItem("userName", data.user_name || userId);

                    // 잠시 수정 (메세지 sender 구분 관련) (소영)
                    // 서버에서 내려주는 is_deaf 값을 source of truth로 사용
                    const isDeaf = Boolean(data.is_deaf);

                    localStorage.setItem("isDeaf", String(isDeaf));
                    localStorage.setItem("role", isDeaf ? "deaf" : "hearing");

                    window.location.href = "index.html";
                } else {
                    const errData = await response.json();
                    showGlobalError(errorMsg, errData.detail || "로그인 정보를 확인해주세요.");
                }
            } catch (error) {
                console.error("Login Error:", error);
                showGlobalError(errorMsg, "서버에 연결할 수 없습니다.");
            }
        });
    }

    // ======== 회원가입 로직 ========
    const signupForm = document.getElementById("signupForm");
    
    if (signupForm) {
        // 실시간 유효성 검사
        const inputs = [
            { id: "signupId", validate: validators.id, msg: "영문/숫자 4자 이상 입력하세요." },
            { id: "signupPw", validate: validators.pw, msg: "비밀번호는 8자 이상이어야 합니다." },
            { id: "signupName", validate: validators.name, msg: "한글 2자 이상 입력하세요." },
            { id: "signupPhone", validate: validators.phone, msg: "올바른 전화번호 형식이 아닙니다." },
            { id: "signupEmail", validate: validators.email, msg: "올바른 이메일 형식이 아닙니다." }
        ];

        inputs.forEach(({ id, validate, msg }) => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener("input", (e) => {
                    // 전화번호 자동 하이픈
                    if (id === "signupPhone") {
                        e.target.value = e.target.value
                            .replace(/[^0-9]/g, '')
                            .replace(/^(\d{0,3})(\d{0,4})(\d{0,4})$/g, "$1-$2-$3")
                            .replace(/(\-{1,2})$/g, "");
                    }
                    toggleError(id, validate(e.target.value), msg);
                });
            }
        });

        // 회원가입 제출
        signupForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            // 최종 유효성 검사
            for (const { id, validate, msg } of inputs) {
                const val = document.getElementById(id).value;
                if (!validate(val)) {
                    toggleError(id, false, msg);
                    document.getElementById(id).focus();
                    return;
                }
            }

            const isDeafVal = document.querySelector('input[name="is_deaf"]:checked')?.value;
            const isDeaf = (isDeafVal === "true");

            const formData = {
                user_id: document.getElementById("signupId").value,
                password: document.getElementById("signupPw").value,
                user_name: document.getElementById("signupName").value,
                phone_number: document.getElementById("signupPhone").value,
                email: document.getElementById("signupEmail").value,
                is_deaf: isDeaf
            };

            try {
                const response = await fetch(`${API_BASE_URL}/auth/signup`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(formData)
                });

                if (response.ok) {
                    alert("회원가입 성공! 로그인해주세요.");
                    window.location.href = "login.html";
                } else {
                    const errData = await response.json();
                    alert(`가입 실패: ${errData.detail}`);
                }
            } catch (error) {
                console.error("Signup Error:", error);
                alert("서버 오류가 발생했습니다.");
            }
        });
    }
});
