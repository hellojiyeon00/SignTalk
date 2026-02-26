/**
 * 채팅 기능
 * Socket.IO 기반 실시간 1:1 채팅
 */

const BASE_URL = "http://localhost:8000";
const myId = localStorage.getItem("userId");
const myName = localStorage.getItem("userName");

let currentRoomId = null;    // DB 방 번호
let currentRoomName = null;  // 소켓 방 이름 (user1_user2)

const socket = io(BASE_URL);

// ======== 초기화 ========
document.addEventListener("DOMContentLoaded", () => {
    if (!myId) {
        alert("로그인이 필요합니다.");
        window.location.href = "login.html";
        return;
    }

    // 프로필 표시
    const profileNameEl = document.getElementById("myProfileName");
    if (profileNameEl) {
        profileNameEl.textContent = `${myName}님`;
    }

    // 친구 목록 로드
    fetchMyFriends();

    // 엔터키 전송
    const chatInput = document.getElementById("messageInput");
    if (chatInput) {
        chatInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    }

    // 검색창 엔터키
    ["searchName", "searchId"].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("keypress", (e) => {
                if (e.key === "Enter") searchUser();
            });
        }
    });
});

// ======== 소켓 이벤트 ========
socket.on("receive_message", (data) => {
    console.log("📥 [Socket] 메시지 수신:", data);

    if (data.sender && data.message) {
        const timeStr = data.time || new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });

        // 수어 영상을 위해 추가 (소영)
        displayMessage(
            data.sender,
            data.sender_name,
            data.message,
            timeStr,
            data.gloss || "",
            data.urls || [],
            data.miss || []
        );
    }
});

// ======== API 함수 ========
async function fetchMyFriends() {
    /* 내 친구 목록 가져오기 */
    try {
        const response = await fetch(`${BASE_URL}/chat/list?user_id=${myId}`);
        const friends = await response.json();

        const listContainer = document.getElementById("friendList");
        listContainer.innerHTML = "";

        if (!friends || friends.length === 0) {
            listContainer.innerHTML = `
                <div style='padding:15px; text-align:center; color:#999; font-size:14px;'>
                    등록된 친구가 없습니다.<br>친구를 검색해서 추가해보세요!
                </div>`;
            return;
        }

        friends.forEach(user => {
            const itemDiv = document.createElement("div");
            itemDiv.className = "friend-item";
            itemDiv.innerHTML = `
                <div style="font-weight:500;">
                    ${user.user_name}
                    <span style="font-size:12px; color:#888;">(${user.user_id})</span>
                </div>`;
            itemDiv.onclick = () => startChat(user, itemDiv);
            listContainer.appendChild(itemDiv);
        });
    } catch (error) {
        console.error("❌ 친구 목록 로딩 실패:", error);
    }
}

async function searchUser() {
    /* 사용자 검색 */
    const nameVal = document.getElementById("searchName").value.trim();
    const idVal = document.getElementById("searchId").value.trim();

    if (!nameVal && !idVal) {
        alert("이름 또는 아이디를 입력해주세요.");
        return;
    }

    try {
        let queryParams = `my_id=${myId}`;
        if (nameVal) queryParams += `&name=${encodeURIComponent(nameVal)}`;
        if (idVal) queryParams += `&member_id=${encodeURIComponent(idVal)}`;

        const response = await fetch(`${BASE_URL}/chat/search?${queryParams}`);
        const results = await response.json();

        const resultArea = document.getElementById("searchResultArea");
        const resultList = document.getElementById("searchResultList");
        resultArea.style.display = "block";
        resultList.innerHTML = "";

        if (results.length === 0) {
            resultList.innerHTML = `
                <div style='padding:10px; color:#777; font-size:13px;'>
                    검색 결과가 없습니다.
                </div>`;
            return;
        }

        results.forEach(user => {
            const itemDiv = document.createElement("div");
            itemDiv.className = "friend-item";
            itemDiv.style.marginBottom = "5px";
            itemDiv.innerHTML = `
                <div>
                    <span style="font-weight:bold;">${user.user_name}</span>
                    <span style="font-size:12px; color:#666;">(${user.member_id})</span>
                </div>`;

            const addBtn = document.createElement("button");
            addBtn.textContent = "추가";
            addBtn.style.cssText = `
                font-size:12px; padding:4px 8px; cursor:pointer;
                background:#007bff; color:white; border:none; border-radius:4px;`;
            addBtn.onclick = (e) => {
                e.stopPropagation();
                addFriend(user.member_id);
            };

            itemDiv.appendChild(addBtn);
            resultList.appendChild(itemDiv);
        });
    } catch (error) {
        console.error("❌ 검색 실패:", error);
        alert("검색 중 오류가 발생했습니다.");
    }
}

function closeSearch() {
    /* 검색창 닫기 */
    document.getElementById("searchResultArea").style.display = "none";
    document.getElementById("searchName").value = "";
    document.getElementById("searchId").value = "";
}

async function addFriend(targetId) {
    /* 친구 추가 */
    if (!confirm(`'${targetId}'님을 친구로 추가하시겠습니까?`)) return;

    try {
        const response = await fetch(`${BASE_URL}/chat/room`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ my_id: myId, target_id: targetId })
        });

        const result = await response.json();
        alert(result.message);

        closeSearch();
        fetchMyFriends();
    } catch (error) {
        console.error("❌ 친구 추가 실패:", error);
    }
}

// ======== 채팅 핵심 로직 ========
async function startChat(friend, clickedElement) {
    /* 채팅방 입장 */
    // UI 활성화
    const allItems = document.querySelectorAll('.friend-item');
    allItems.forEach(item => item.classList.remove('active'));
    if (clickedElement) clickedElement.classList.add('active');

    // 이전 방 퇴장
    if (currentRoomName) {
        socket.emit("leave_room", { room: currentRoomName, username: myId });
    }

    try {
        // 방 번호 조회/생성
        const roomRes = await fetch(`${BASE_URL}/chat/room`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ my_id: myId, target_id: friend.user_id })
        });
        const roomData = await roomRes.json();
        currentRoomId = roomData.room_id;

        // 소켓 방 이름 생성
        const participants = [myId, friend.user_id].sort();
        currentRoomName = participants.join("_");

        // 화면 초기화
        document.getElementById("messages").innerHTML = "";
        document.getElementById("chatTitle").textContent = `${friend.user_name}님과의 대화`;
        document.getElementById("messageInput").focus();

        // 소켓 방 입장
        socket.emit("join_room", { room: currentRoomName, username: myId });
        console.log(`🏠 [Socket] 방 입장: ${currentRoomName} (ID: ${currentRoomId})`);

        // 과거 대화 내역 로드
        const historyRes = await fetch(`${BASE_URL}/chat/history/${currentRoomId}`);
        const historyArr = await historyRes.json();

        historyArr.forEach(chat => {
            let timeStr = chat.date;
            try {
                const dateObj = new Date(chat.date);
                if (!isNaN(dateObj)) {
                    timeStr = dateObj.toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    });
                }
            } catch (e) { }

            // 수어 영상 히스토리 저장을 위해 추가 (소영)
            // 히스토리 영상 보존: url_path(문자열) -> urls(배열)로 변환
            let historyUrls = [];
            if (Array.isArray(chat.urls) && chat.urls.length > 0) {
                // 기존에 urls 배열에 내려오는 경우(호환)
                historyUrls = chat.urls;
            } else if (typeof chat.url_path === "string" && chat.url_path.trim().length > 0) {
                // DB에서 STRING_AGG로 내려온 "a, b, c" 형태 처리
                historyUrls = chat.url_path
                    .split(",")
                    .map(s => s.trim())
                    .filter(Boolean);
            }

            displayMessage(
                chat.sender,
                chat.sender_name,
                chat.message,
                timeStr,
                chat.gloss || "",
                chat.urls || [],
                chat.miss || []
            );
        });

        // 스크롤 맨 아래로
        const msgBox = document.getElementById("messages");
        msgBox.scrollTop = msgBox.scrollHeight;
    } catch (error) {
        console.error("❌ 채팅방 입장 실패:", error);
        alert("채팅방을 불러오는 데 실패했습니다.");
    }
}

function sendMessage() {
    /* 메시지 전송 */
    const input = document.getElementById("messageInput");
    const msg = input.value.trim();

    if (!msg) return;
    if (!currentRoomName || !currentRoomId) {
        alert("대화 상대를 먼저 선택해주세요.");
        return;
    }

    socket.emit("send_message", {
        room: currentRoomName,
        room_id: currentRoomId,
        username: myId,
        message: msg
    });

    console.log(`📤 [Socket] 전송: ${msg}`);
    input.value = "";
    input.focus();
}

function displayMessage(senderId, senderName, msg, time, gloss = "", urls = [], miss = []) {
    /* 말풍선 렌더링 */
    const msgBox = document.getElementById("messages");

    // urls 방어: null/undefined/빈문자 제거 (video.src 오류 방지)
    if (Array.isArray(urls)) {
        urls = urls
            .map(u => (typeof u === "string" ? u.trim() : ""))
            .filter(u => u.length > 0);
    } else {
        urls = [];
    }
    const isMine = (senderId === myId);

    const rowDiv = document.createElement("div");
    rowDiv.className = `message-row ${isMine ? "message-mine" : "message-other"}`;

    const nameDiv = document.createElement("div");
    nameDiv.className = "message-name";
    nameDiv.textContent = senderName;

    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";

    const bubbleDiv = document.createElement("div");
    bubbleDiv.className = "message-bubble";
    bubbleDiv.textContent = msg;
    
    const hasGloss = (typeof gloss === "string" && gloss.trim().length > 0);
    const hasUrls = (Array.isArray(urls) && urls.length > 0);
    const hasMiss = (Array.isArray(miss) && miss.length > 0);

    // 말풍선 + 버튼을 묶는 래퍼 (버튼을 말풍선 아래로 내리기)
    const bubbleWrap = document.createElement("div");
    bubbleWrap.className = "message-bubble-wrap";

    bubbleWrap.appendChild(bubbleDiv);

    const timeSpan = document.createElement("span");
    timeSpan.className = "message-time";
    timeSpan.textContent = time;

    // urls (팝업 버튼) - 말풍선 바로 아래에 붙임(별도 요소)
    if (hasUrls) {
        const openBtn = document.createElement("button");
        openBtn.type = "button";
        openBtn.className = "video-open-btn";
        openBtn.textContent = "🎬 영상 보기";

        openBtn.addEventListener("click", () => {
            openVideoModal(urls);
        });

        bubbleWrap.appendChild(openBtn);
    }

    // gloss (UI 숨김, 콘솔만)
    if (hasGloss) {
        console.log("[GLOSS]", gloss);
    }
    // miss (UI 숨김, 콘솔만)
    if (hasMiss) {
        console.log("[MISS]", miss);
    }

    contentDiv.appendChild(bubbleWrap);
    contentDiv.appendChild(timeSpan);

    rowDiv.appendChild(nameDiv);
    rowDiv.appendChild(contentDiv);
    msgBox.appendChild(rowDiv);

    msgBox.scrollTop = msgBox.scrollHeight;
}

// 영상 설정을 위해 추가 (소영)
function ensureVideoModal() {
    if (document.getElementById("videoModalOverlay")) return;

    const overlay = document.createElement("div");
    overlay.id = "videoModalOverlay";
    overlay.className = "video-modal-overlay";

    const modal = document.createElement("div");
    modal.className = "video-modal";

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "video-modal-close";
    closeBtn.textContent = "닫기";
    closeBtn.addEventListener("click", closeVideoModal);

    const video = document.createElement("video");
    video.id = "videoModalPlayer";
    video.className = "video-modal-player";
    video.controls = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.muted = true;

    modal.appendChild(closeBtn);
    modal.appendChild(video);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // 바깥 클릭 닫기
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeVideoModal();
    });

    // ESC 닫기
    document.addEventListener("keydown", (e) => {
        const ov = document.getElementById("videoModalOverlay");
        if (e.key === "Escape" && ov && ov.classList.contains("is-open")) {
            closeVideoModal();
        }
    });
}

function openVideoModal(urls) {
    ensureVideoModal();

    const overlay = document.getElementById("videoModalOverlay");
    const video = document.getElementById("videoModalPlayer");

    const safeUrls = Array.isArray(urls) ? urls : [];
    let idx = 0;

    if (!overlay || !video) return;

    overlay.classList.add("is-open");

    if (safeUrls.length === 0) {
        video.removeAttribute("src");
        video.load();
        return;
    }

    const playAt = (i) => {
        idx = i;
        video.src = safeUrls[idx];
        video.load();
        video.play().catch(() => {});
    };

    // 연속 재생
    video.onended = () => {
        const next = idx + 1;
        if (next < safeUrls.length) playAt(next);
    };

    playAt(0);
}

function closeVideoModal() {
    const overlay = document.getElementById("videoModalOverlay");
    const video = document.getElementById("videoModalPlayer");

    if (!overlay || !video) return;

    video.onended = null;
    video.pause();
    video.removeAttribute("src");
    video.load();

    overlay.classList.remove("is-open");
}

function logout() {
    /* 로그아웃 */
    localStorage.clear();
    window.location.href = "index.html";
}

// ======== 설정 관련 ========
function openSettings() {
    /* 설정창 열기 */
    const modal = document.getElementById("settingsModal");
    document.getElementById("settingsMenu").style.display = "block";
    document.getElementById("settingsEditProfile").style.display = "none";
    modal.style.display = "flex";
}

function showSettingsMenu() {
    /* 설정 메뉴로 돌아가기 */
    document.getElementById("settingsMenu").style.display = "block";
    document.getElementById("settingsEditProfile").style.display = "none";
}

async function goToProfileEdit() {
    /* 프로필 수정 화면으로 이동 */
    try {
        const res = await fetch(`${BASE_URL}/auth/me?user_id=${myId}`);
        if (!res.ok) throw new Error("정보 로딩 실패");

        const data = await res.json();

        document.getElementById("editName").value = data.user_name;
        document.getElementById("editPhone").value = data.phone_number;
        document.getElementById("editPw").value = "";

        document.getElementById("settingsMenu").style.display = "none";
        document.getElementById("settingsEditProfile").style.display = "block";
    } catch (e) {
        alert("정보를 불러올 수 없습니다.");
        console.error(e);
    }
}

function closeSettings() {
    document.getElementById("settingsModal").style.display = "none";
}

async function updateMember() {
    /* 회원정보 수정 */
    const newName = document.getElementById("editName").value;
    const newPhone = document.getElementById("editPhone").value;
    const newPw = document.getElementById("editPw").value;

    const updateData = {
        user_id: myId,
        user_name: newName || null,
        phone_number: newPhone || null,
        password: newPw || null
    };

    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updateData)
        });

        const result = await res.json();

        if (res.ok) {
            alert(result.message);
            if (newName) {
                localStorage.setItem("userName", newName);
                document.getElementById("myProfileName").textContent = newName + "님";
            }
            closeSettings();
        } else {
            alert("수정 실패: " + result.detail);
        }
    } catch (e) {
        console.error(e);
        alert("서버 오류가 발생했습니다.");
    }
}

async function deleteMember() {
    /* 회원 탈퇴 */
    if (!confirm("정말로 탈퇴하시겠습니까?\n탈퇴 후에는 복구할 수 없습니다.")) return;

    try {
        const res = await fetch(`${BASE_URL}/auth/me?user_id=${myId}`, {
            method: "DELETE"
        });

        if (res.ok) {
            alert("탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.");
            logout();
        } else {
            const err = await res.json();
            alert("탈퇴 실패: " + err.detail);
        }
    } catch (e) {
        console.error(e);
        alert("서버 오류가 발생했습니다.");
    }
}
