/**
 * 랜딩 페이지 (메인 화면)
 * 로그인 상태에 따라 버튼 동적 변경
 */

document.addEventListener("DOMContentLoaded", () => {
    const token = localStorage.getItem("accessToken");
    const authBox = document.getElementById("authBox");
    const startBtn = document.getElementById("startBtn");

    // 로그인 상태면 버튼 변경
    if (token) {
        if (authBox) {
            authBox.innerHTML = `
                <a href="chat.html" class="btn-signup">채팅방 입장</a>
                <button id="headerLogoutBtn" class="btn-logout">로그아웃</button>
            `;
            
            document.getElementById("headerLogoutBtn").addEventListener("click", handleLogout);
        }

        if (startBtn) {
            startBtn.href = "chat.html";
            startBtn.textContent = "채팅방 입장하기";
        }
    }
});

function handleLogout() {
    /* 로그아웃 처리 */
    localStorage.clear();
    window.location.reload();
}
