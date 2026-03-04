/**
 * 인증 관련 기능 (로그인/회원가입)
 */

const API_BASE_URL = CONFIG.API_BASE_URL;

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

function parseDetail(detail) {
    /* FastAPI detail 필드: 문자열 또는 배열 모두 처리 */
    if (!detail) return "알 수 없는 오류";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        return detail.map(e => e.msg || JSON.stringify(e)).join(", ");
    }
    return JSON.stringify(detail);
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
                    localStorage.setItem("refreshToken", data.refresh_token);
                    localStorage.setItem("userId", userId);
                    localStorage.setItem("userName", data.user_name || userId);
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

    // ======== 비밀번호 재설정 로직 ========
    const showResetBtn = document.getElementById("showResetBtn");

    if (showResetBtn) {
        let resetCodeVerified = false;

        // 영역 토글
        showResetBtn.addEventListener("click", (e) => {
            e.preventDefault();
            const sec = document.getElementById("resetSection");
            const visible = sec.style.display !== "none";
            sec.style.display = visible ? "none" : "block";
            showResetBtn.textContent = visible ? "비밀번호를 잊으셨나요?" : "비밀번호 찾기 닫기";
        });

        // ── 인증 코드 발송 ─────────────────────────────────────────
        document.getElementById("resetSendCodeBtn").addEventListener("click", async () => {
            const userId = document.getElementById("resetId").value.trim();
            const email  = document.getElementById("resetEmail").value.trim();
            const errEl  = document.getElementById("resetEmailError");

            if (!userId) { errEl.textContent = "아이디를 입력하세요."; errEl.style.display = "block"; return; }
            if (!validators.email(email)) { errEl.textContent = "올바른 이메일 형식이 아닙니다."; errEl.style.display = "block"; return; }
            errEl.style.display = "none";

            const btn = document.getElementById("resetSendCodeBtn");
            btn.disabled = true;
            btn.textContent = "발송 중...";

            try {
                const res = await fetch(`${API_BASE_URL}/auth/send-reset-email`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: userId, email })
                });
                const data = await res.json();
                if (res.ok) {
                    document.getElementById("resetCodeGroup").style.display = "block";
                    btn.textContent = "재발송 (60초)";
                    let sec = 60;
                    const timer = setInterval(() => {
                        sec--;
                        btn.textContent = `재발송 (${sec}초)`;
                        if (sec <= 0) { clearInterval(timer); btn.disabled = false; btn.textContent = "재발송"; }
                    }, 1000);
                } else {
                    btn.disabled = false;
                    btn.textContent = "인증 코드 발송";
                    errEl.textContent = parseDetail(data.detail) || "발송 실패";
                    errEl.style.display = "block";
                }
            } catch {
                btn.disabled = false;
                btn.textContent = "인증 코드 발송";
                alert("서버 오류가 발생했습니다.");
            }
        });

        // ── 인증 코드 확인 (형식만 검사 — 실제 코드 검증은 비밀번호 변경 시 서버에서 처리) ──
        document.getElementById("resetVerifyCodeBtn").addEventListener("click", () => {
            const code      = document.getElementById("resetVerifyCode").value.trim();
            const codeErrEl = document.getElementById("resetCodeError");

            if (code.length !== 6) {
                codeErrEl.textContent = "6자리 코드를 입력하세요.";
                codeErrEl.style.display = "block";
                return;
            }
            codeErrEl.style.display = "none";
            resetCodeVerified = true;
            document.getElementById("resetVerifiedMsg").style.display = "block";
            document.getElementById("resetVerifyCodeBtn").disabled = true;
            document.getElementById("resetVerifyCode").disabled = true;
            document.getElementById("resetNewPwGroup").style.display = "block";
            document.getElementById("resetSubmitBtn").style.display = "block";
        });

        // ── 비밀번호 변경 제출 ─────────────────────────────────────
        document.getElementById("resetSubmitBtn").addEventListener("click", async () => {
            const email          = document.getElementById("resetEmail").value.trim();
            const code           = document.getElementById("resetVerifyCode").value.trim();
            const newPw          = document.getElementById("resetNewPw").value;
            const newPwConfirm   = document.getElementById("resetNewPwConfirm").value;
            const pwErrEl        = document.getElementById("resetPwError");
            const globalErrEl    = document.getElementById("resetGlobalError");

            pwErrEl.style.display = "none";
            globalErrEl.style.display = "none";

            if (!resetCodeVerified) { globalErrEl.textContent = "이메일 인증을 먼저 완료해주세요."; globalErrEl.style.display = "block"; return; }
            if (newPw.length < 8) { pwErrEl.textContent = "비밀번호는 8자 이상이어야 합니다."; pwErrEl.style.display = "block"; return; }
            if (newPw !== newPwConfirm) { pwErrEl.textContent = "비밀번호가 일치하지 않습니다."; pwErrEl.style.display = "block"; return; }

            try {
                const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, code, new_password: newPw })
                });
                const data = await res.json();
                if (res.ok) {
                    alert("비밀번호가 변경되었습니다. 새 비밀번호로 로그인해주세요.");
                    document.getElementById("resetSection").style.display = "none";
                    showResetBtn.textContent = "비밀번호를 잊으셨나요?";
                } else {
                    globalErrEl.textContent = parseDetail(data.detail) || "변경 실패";
                    globalErrEl.style.display = "block";
                }
            } catch {
                alert("서버 오류가 발생했습니다.");
            }
        });
    }

    // ======== 회원가입 로직 ========
    const signupForm = document.getElementById("signupForm");
    
    if (signupForm) {
        let emailVerified = false; // 이메일 인증 완료 여부

        // 실시간 유효성 검사
        const inputs = [
            { id: "signupId", validate: validators.id, msg: "영문/숫자 4자 이상 입력하세요." },
            { id: "signupPw", validate: validators.pw, msg: "비밀번호는 8자 이상이어야 합니다." },
            { id: "signupName", validate: validators.name, msg: "한글 2자 이상 입력하세요." },
            { id: "signupPhone", validate: validators.phone, msg: "올바른 전화번호 형식이 아닙니다." },
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

        // ── 인증 코드 발송 ──────────────────────────────────────────
        const sendCodeBtn = document.getElementById("sendCodeBtn");
        sendCodeBtn.addEventListener("click", async () => {
            const email = document.getElementById("signupEmail").value;
            if (!validators.email(email)) {
                const errEl = document.getElementById("emailError");
                errEl.textContent = "올바른 이메일 형식이 아닙니다.";
                errEl.style.display = "block";
                return;
            }
            document.getElementById("emailError").style.display = "none";
            sendCodeBtn.disabled = true;
            sendCodeBtn.textContent = "발송 중...";

            try {
                const res = await fetch(`${API_BASE_URL}/auth/send-verify-email`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email })
                });
                const data = await res.json();
                if (res.ok) {
                    document.getElementById("codeGroup").style.display = "block";
                    sendCodeBtn.textContent = "재발송 (60초)";
                    // 60초 쿨다운 타이머
                    let sec = 60;
                    const timer = setInterval(() => {
                        sec--;
                        sendCodeBtn.textContent = `재발송 (${sec}초)`;
                        if (sec <= 0) {
                            clearInterval(timer);
                            sendCodeBtn.disabled = false;
                            sendCodeBtn.textContent = "재발송";
                        }
                    }, 1000);
                } else {
                    sendCodeBtn.disabled = false;
                    sendCodeBtn.textContent = "인증 코드 발송";
                    const errEl = document.getElementById("emailError");
                    errEl.textContent = parseDetail(data.detail) || "발송 실패";
                    errEl.style.display = "block";
                }
            } catch {
                sendCodeBtn.disabled = false;
                sendCodeBtn.textContent = "인증 코드 발송";
                alert("서버 오류가 발생했습니다.");
            }
        });

        // ── 인증 코드 확인 ──────────────────────────────────────────
        document.getElementById("verifyCodeBtn").addEventListener("click", async () => {
            const email = document.getElementById("signupEmail").value;
            const code = document.getElementById("verifyCode").value.trim();
            const codeError = document.getElementById("codeError");

            if (code.length !== 6) {
                codeError.textContent = "6자리 코드를 입력하세요.";
                codeError.style.display = "block";
                return;
            }
            codeError.style.display = "none";

            try {
                const res = await fetch(`${API_BASE_URL}/auth/verify-email-code`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, code })
                });
                const data = await res.json();
                if (res.ok) {
                    emailVerified = true;
                    document.getElementById("verifiedMsg").style.display = "block";
                    document.getElementById("verifyCodeBtn").disabled = true;
                    document.getElementById("verifyCode").disabled = true;
                    sendCodeBtn.disabled = true;
                } else {
                    codeError.textContent = parseDetail(data.detail) || "인증 실패";
                    codeError.style.display = "block";
                }
            } catch {
                alert("서버 오류가 발생했습니다.");
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

            // 이메일 형식 검사
            const emailVal = document.getElementById("signupEmail").value;
            if (!validators.email(emailVal)) {
                const errEl = document.getElementById("emailError");
                errEl.textContent = "올바른 이메일 형식이 아닙니다.";
                errEl.style.display = "block";
                document.getElementById("signupEmail").focus();
                return;
            }

            // 이메일 인증 완료 여부 확인
            if (!emailVerified) {
                const errEl = document.getElementById("emailError");
                errEl.textContent = "이메일 인증을 완료해주세요.";
                errEl.style.display = "block";
                return;
            }

            const isDeafVal = document.querySelector('input[name="is_deaf"]:checked')?.value;
            const isDeaf = (isDeafVal === "true");

            const formData = {
                user_id: document.getElementById("signupId").value,
                password: document.getElementById("signupPw").value,
                user_name: document.getElementById("signupName").value,
                phone_number: document.getElementById("signupPhone").value,
                email: emailVal,
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
                    alert(`가입 실패: ${parseDetail(errData.detail)}`);
                }
            } catch (error) {
                console.error("Signup Error:", error);
                alert("서버 오류가 발생했습니다.");
            }
        });
    }
});