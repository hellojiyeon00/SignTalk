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

// 개인 알림 방 등록 (소켓 연결 후 자동 실행)
socket.on("connect", () => {
    console.log("✅ [Socket] 연결됨");
    socket.emit("register_user", { user_id: myId });
    console.log("🔔 [알림] 개인 알림 방 등록:", myId);
});

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

    // 브라우저 알림 권한 요청
    requestNotificationPermission();
    
    // SSE로 재난문자 실시간 수신 시작
    connectDisasterSSE();

    // 엔터키 전송
    const chatInput = document.getElementById("messageInput");
    if (chatInput) {
        chatInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    }

    // 검색창 엔터키 및 자동완성
    const searchNameInput = document.getElementById("searchName");
    const searchIdInput = document.getElementById("searchId");
    
    let nameAutocompleteTimeout = null;
    let idAutocompleteTimeout = null;
    
    if (searchNameInput) {
        searchNameInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") searchUser();
        });
        
        // 실시간 자동완성 (이름)
        searchNameInput.addEventListener("input", (e) => {
            clearTimeout(nameAutocompleteTimeout);
            const query = e.target.value.trim();
            
            if (!query) {
                document.getElementById("nameAutocomplete").style.display = "none";
                return;
            }
            
            // 300ms 디바운싱
            nameAutocompleteTimeout = setTimeout(() => {
                autocompleteSearch("name", query);
            }, 300);
        });
        
        // 포커스 아웃 시 드롭다운 닫기
        searchNameInput.addEventListener("blur", () => {
            setTimeout(() => {
                document.getElementById("nameAutocomplete").style.display = "none";
            }, 200);
        });
    }
    
    if (searchIdInput) {
        searchIdInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") searchUser();
        });
        
        // 실시간 자동완성 (ID)
        searchIdInput.addEventListener("input", (e) => {
            clearTimeout(idAutocompleteTimeout);
            const query = e.target.value.trim();
            
            if (!query) {
                document.getElementById("idAutocomplete").style.display = "none";
                return;
            }
            
            // 300ms 디바운싱
            idAutocompleteTimeout = setTimeout(() => {
                autocompleteSearch("id", query);
            }, 300);
        });
        
        // 포커스 아웃 시 드롭다운 닫기
        searchIdInput.addEventListener("blur", () => {
            setTimeout(() => {
                document.getElementById("idAutocomplete").style.display = "none";
            }, 200);
        });
    }
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
        
        // 현재 채팅방에서 메시지를 받았는지 확인
        const isInCurrentRoom = currentRoomName && currentRoomName.includes(data.sender);
        
        // 상대방 메시지를 현재 채팅방에서 받으면 즉시 읽음 처리
        if (data.sender !== myId && isInCurrentRoom) {
            // 읽은 상태로 표시
            displayMessage(data.sender, data.sender_name, data.message, timeStr, true);
            
            // 즉시 읽음 처리 API 호출
            if (currentRoomId && currentRoomName) {
                fetch(`${BASE_URL}/chat/read?room_id=${currentRoomId}&user_id=${myId}`, {
                    method: "POST"
                }).then(() => {
                    console.log("✅ [즉시 읽음] 현재 채팅방 메시지 읽음 처리 완료");
                    // 발신자에게 읽음 알림 전송
                    socket.emit("notify_read", { 
                        room: currentRoomName, 
                        reader: myId 
                    });
                }).catch(err => {
                    console.error("❌ [즉시 읽음] 읽음 처리 실패:", err);
                });
            }
        } else {
            // 다른 채팅방의 메시지이거나 내가 보낸 메시지는 읽지 않은 상태
            displayMessage(data.sender, data.sender_name, data.message, timeStr, false);
            
            // 다른 채팅방의 메시지인 경우만 친구 목록 업데이트
            if (data.sender !== myId && !isInCurrentRoom) {
                fetchMyFriends();
            }
        }
    }
});

// 읽지 않은 메시지 알림 (다른 채팅방에서 메시지가 와도 알림)
socket.on("unread_notification", (data) => {
    console.log("🔔 [Socket] 읽지 않은 메시지 알림:", data);
    
    // 현재 그 채팅방에 있다면 알림 무시 (이미 receive_message에서 처리함)
    const isInCurrentRoom = currentRoomName && currentRoomName.includes(data.sender_id);
    if (!isInCurrentRoom) {
        // 친구 목록 새로고침 (새 메시지가 온 친구가 목록 맨 위로)
        fetchMyFriends();
    }
});

// 메시지 읽음 처리 알림 (상대방이 채팅방에 입장하면 내가 보낸 메시지의 "1" 제거)
socket.on("messages_read", (data) => {
    console.log("✅ [Socket] 메시지 읽음 처리:", data);
    
    // 나 자신이 읽은 게 아니라면 (상대방이 읽음)
    if (data.reader !== myId) {
        // 내가 보낸 메시지 중 읽지 않은 것들의 "1" 제거
        const unreadBadges = document.querySelectorAll('.message-mine .unread-badge');
        console.log(`🔍 찾은 읽지 않은 배지 개수: ${unreadBadges.length}`);
        unreadBadges.forEach(badge => {
            badge.remove();  // style.display = 'none' 대신 완전히 제거
        });
        console.log("✅ 모든 읽지 않은 배지 제거 완료");
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
            
            // 읽지 않은 메시지 배지
            const unreadBadge = user.unread_count > 0 
                ? `<span style="background:#ff4444; color:white; border-radius:10px; padding:2px 8px; font-size:11px; font-weight:bold; margin-left:5px;">${user.unread_count}</span>` 
                : '';
            
            itemDiv.innerHTML = `
                <div style="font-weight:500;">
                    ${user.user_name} 
                    <span style="font-size:12px; color:#888;">(${user.user_id})</span>
                    ${unreadBadge}
                </div>`;
            itemDiv.onclick = () => startChat(user, itemDiv);
            listContainer.appendChild(itemDiv);
        });
    } catch (error) {
        console.error("❌ 친구 목록 로딩 실패:", error);
    }
}

// ======== 초성 검색 유틸리티 ========
function getChosung(str) {
    /* 한글 문자열을 초성으로 변환 */
    const chosungList = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];
    let result = '';
    
    for (let i = 0; i < str.length; i++) {
        const code = str.charCodeAt(i) - 44032;
        if (code > -1 && code < 11172) {
            result += chosungList[Math.floor(code / 588)];
        } else {
            result += str.charAt(i);
        }
    }
    return result;
}

function matchChosung(target, query) {
    /* 초성 매칭 검사 */
    const targetChosung = getChosung(target);
    const queryChosung = getChosung(query);
    
    // 완전 일치 검사
    if (target.includes(query)) return true;
    
    // 초성 일치 검사
    if (targetChosung.includes(queryChosung)) return true;
    
    return false;
}

async function autocompleteSearch(type, query) {
    /* 자동완성 검색 */
    try {
        let queryParams = `my_id=${myId}`;
        
        if (type === "name") {
            queryParams += `&name=${encodeURIComponent(query)}`;
        } else {
            queryParams += `&member_id=${encodeURIComponent(query)}`;
        }
        
        const response = await fetch(`${BASE_URL}/chat/search?${queryParams}`);
        const results = await response.json();
        
        const dropdownId = type === "name" ? "nameAutocomplete" : "idAutocomplete";
        const dropdown = document.getElementById(dropdownId);
        
        if (!dropdown) return;
        
        dropdown.innerHTML = "";
        
        if (results.length === 0) {
            dropdown.innerHTML = '<div class="autocomplete-empty">검색 결과가 없습니다</div>';
            dropdown.style.display = "block";
            return;
        }
        
        // 초성 필터링 (프론트엔드에서 추가 필터링)
        const filteredResults = results.filter(user => {
            if (type === "name") {
                return matchChosung(user.user_name, query);
            } else {
                return user.member_id.toLowerCase().includes(query.toLowerCase());
            }
        });
        
        if (filteredResults.length === 0) {
            dropdown.innerHTML = '<div class="autocomplete-empty">검색 결과가 없습니다</div>';
            dropdown.style.display = "block";
            return;
        }
        
        filteredResults.forEach(user => {
            const item = document.createElement("div");
            item.className = "autocomplete-item";
            item.innerHTML = `
                <div>
                    <span style="font-weight:bold;">${user.user_name}</span>
                    <span style="font-size:11px; color:#666; margin-left:5px;">(${user.member_id})</span>
                </div>
                <button onclick="addFriend('${user.member_id}')" 
                        style="font-size:11px; padding:3px 8px; background:#007bff; color:white; border:none; border-radius:3px; cursor:pointer; white-space:nowrap; min-width:40px;">
                    추가
                </button>
            `;
            
            // 클릭 시 입력창에 값 채우기
            item.addEventListener("mousedown", (e) => {
                if (e.target.tagName !== 'BUTTON') {
                    if (type === "name") {
                        document.getElementById("searchName").value = user.user_name;
                    } else {
                        document.getElementById("searchId").value = user.member_id;
                    }
                    dropdown.style.display = "none";
                }
            });
            
            dropdown.appendChild(item);
        });
        
        dropdown.style.display = "block";
    } catch (error) {
        console.error("❌ 자동완성 검색 실패:", error);
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
        
        // 초성 필터링 적용 (이름 검색 시)
        let filteredResults = results;
        if (nameVal) {
            filteredResults = results.filter(user => matchChosung(user.user_name, nameVal));
        }

        const resultArea = document.getElementById("searchResultArea");
        const resultList = document.getElementById("searchResultList");
        resultArea.style.display = "block";
        resultList.innerHTML = "";

        if (filteredResults.length === 0) {
            resultList.innerHTML = `
                <div style='padding:10px; color:#777; font-size:13px;'>
                    검색 결과가 없습니다.
                </div>`;
            return;
        }

        filteredResults.forEach(user => {
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
                background:#007bff; color:white; border:none; border-radius:4px; 
                white-space:nowrap; min-width:45px;`;
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
    
    // 자동완성 드롭다운도 닫기
    document.getElementById("nameAutocomplete").style.display = "none";
    document.getElementById("idAutocomplete").style.display = "none";
}

async function addFriend(targetId) {
    /* 친구 추가 */
    if(!confirm(`'${targetId}'님을 친구로 추가하시겠습니까?`)) return;

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
        
        // 메시지 읽음 처리
        try {
            await fetch(`${BASE_URL}/chat/read?room_id=${currentRoomId}&user_id=${myId}`, {
                method: "POST"
            });
            console.log("✅ 메시지 읽음 처리 완료");
            // 친구 목록 새로고침 (읽지 않은 메시지 개수 업데이트)
            fetchMyFriends();
        } catch (readError) {
            console.error("❌ 읽음 처리 실패:", readError);
        }

        // 소켓 방 이름 생성
        const participants = [myId, friend.user_id].sort();
        currentRoomName = participants.join("_");

        // 화면 초기화
        document.getElementById("messages").innerHTML = "";
        document.getElementById("chatTitle").textContent = `${friend.user_name}님과의 대화`;
        document.getElementById("messageInput").focus();
        
        // 뒤로가기 버튼 표시
        document.getElementById("backToChatListBtn").style.display = "inline-block";
        
        // 디폴트 뷰 숨기기
        const defaultView = document.getElementById("defaultChatView");
        if (defaultView) defaultView.style.display = "none";

        // 소켓 방 입장
        socket.emit("join_room", { room: currentRoomName, username: myId });
        console.log(`🏠 [Socket] 방 입장: ${currentRoomName} (ID: ${currentRoomId})`);

        // 과거 대화 내역 로드
        const historyRes = await fetch(`${BASE_URL}/chat/history/${currentRoomId}?user_id=${myId}`);
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
            } catch(e) {}

            displayMessage(chat.sender, chat.sender_name, chat.message, timeStr, chat.is_read);
        });

        // 스크롤 맨 아래로
        const msgBox = document.getElementById("messages");
        msgBox.scrollTop = msgBox.scrollHeight;
    } catch (error) {
        console.error("❌ 채팅방 입장 실패:", error);
        alert("채팅방을 불러오는 데 실패했습니다.");
    }
}

function leaveChatRoom() {
    /* 채팅방 나가기 - 디폴트 뷰로 복귀 */
    // 소켓 방 퇴장
    if (currentRoomName) {
        socket.emit("leave_room", { room: currentRoomName, username: myId });
        console.log(`🚪 [Socket] 방 퇴장: ${currentRoomName}`);
    }
    
    // 상태 초기화
    currentRoomId = null;
    currentRoomName = null;
    
    // UI 초기화
    document.getElementById("chatTitle").textContent = "대화 상대를 선택해주세요";
    document.getElementById("messages").innerHTML = "";
    document.getElementById("messageInput").value = "";
    document.getElementById("backToChatListBtn").style.display = "none";
    
    // 디폴트 뷰 표시
    const defaultView = document.getElementById("defaultChatView");
    if (defaultView) {
        document.getElementById("messages").innerHTML = `
            <div id="defaultChatView" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #999; text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 20px;">💬</div>
                <div style="font-size: 1.2rem; font-weight: bold; margin-bottom: 10px;">수어톡에 오신 것을 환영합니다!</div>
                <div style="font-size: 0.95rem;">왼쪽에서 친구를 선택하여 대화를 시작하세요.</div>
            </div>
        `;
    }
    
    // 친구 목록 활성화 해제
    const allItems = document.querySelectorAll('.friend-item');
    allItems.forEach(item => item.classList.remove('active'));
    
    console.log("✅ 채팅방 나가기 완료");
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

function displayMessage(senderId, senderName, msg, time, isRead = true) {
    /* 말풍선 렌더링 */
    const msgBox = document.getElementById("messages");
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

    // 시간 + 읽음 표시를 감싸는 래퍼
    const timeWrapper = document.createElement("div");
    timeWrapper.style.cssText = "display:flex; flex-direction:column; align-items:center; gap:2px;";
    
    // 읽지 않은 메시지 표시 (내가 보낸 메시지만, 시간 위에)
    if (isMine && !isRead) {
        const unreadBadge = document.createElement("span");
        unreadBadge.className = "unread-badge";
        unreadBadge.textContent = "1";
        unreadBadge.style.cssText = "color:#ffeb33; font-size:12px; font-weight:bold;";
        timeWrapper.appendChild(unreadBadge);
    }
    
    const timeSpan = document.createElement("span");
    timeSpan.className = "message-time";
    timeSpan.textContent = time;
    timeWrapper.appendChild(timeSpan);

    contentDiv.appendChild(bubbleDiv);
    contentDiv.appendChild(timeWrapper);
    rowDiv.appendChild(nameDiv);
    rowDiv.appendChild(contentDiv);
    msgBox.appendChild(rowDiv);
    
    msgBox.scrollTop = msgBox.scrollHeight;
}

function logout() {
    /* 로그아웃 */
    localStorage.clear();
    window.location.href = "index.html";
}

// ======== 설정 관련 기능 ========
// 설정 관련 기능은 settings.js로 분리되었습니다.
// openSettings, goToProfileEdit, goToFriendManage, goToLocationSettings 등

// ---------------------------------------------------------
// [신규] 1. SSE로 재난 문자 실시간 수신
// ---------------------------------------------------------
let disasterEventSource = null;

function connectDisasterSSE() {
    /* SSE 연결로 재난문자 수신 */
    if (disasterEventSource) {
        disasterEventSource.close();
    }
    
    // SSE 연결 생성
    disasterEventSource = new EventSource(`${BASE_URL}/disaster/stream?user_id=${myId}`);
    
    // 재난문자 수신 이벤트
    disasterEventSource.addEventListener('disaster', (event) => {
        const data = JSON.parse(event.data);
        console.log("🚨 [SSE] 재난문자 수신:", data);
        
        // 1) 우측 하단에 팝업(Toast) 띄우기
        showToast(data.message);
        
        // 2) 재난문자 전용 모달창에도 내용 추가하기
        addDisasterMessageToRoom(data.message, data.time);
        
        // 3) 브라우저 알림 표시 (다른 탭을 보고 있어도 알림이 뜸)
        showBrowserNotification("🚨 재난 문자 알림", data.message);
    });
    
    // 연결 상태 이벤트
    disasterEventSource.addEventListener('open', () => {
        console.log("✅ [SSE] 재난문자 스트림 연결됨");
    });
    
    // 연결 유지용 ping 이벤트
    disasterEventSource.addEventListener('ping', (event) => {
        // keep-alive 메시지, 로그 출력 안 함
    });
    
    // 오류 처리 (자동 재연결)
    disasterEventSource.onerror = (error) => {
        console.error("❌ [SSE] 재난문자 스트림 오류:", error);
        
        // EventSource는 자동 재연결을 시도합니다.
        // readyState가 CLOSED(2)면 수동으로 재연결
        if (disasterEventSource.readyState === EventSource.CLOSED) {
            console.log("🔄 [SSE] 5초 후 재연결 시도...");
            setTimeout(connectDisasterSSE, 5000);
        }
    };
}

// ---------------------------------------------------------
// [신규] 2. 브라우저 알림 권한 요청
// ---------------------------------------------------------
function requestNotificationPermission() {
    if ("Notification" in window) {
        console.log(`📢 현재 알림 권한 상태: ${Notification.permission}`);
        
        if (Notification.permission === "default") {
            Notification.requestPermission().then(permission => {
                if (permission === "granted") {
                    console.log("✅ 브라우저 알림 권한 허용됨");
                } else {
                    console.log("❌ 브라우저 알림 권한 거부됨");
                }
            });
        } else if (Notification.permission === "granted") {
            console.log("✅ 알림 권한이 이미 허용되어 있습니다.");
        } else if (Notification.permission === "denied") {
            console.log("❌ 알림 권한이 차단되어 있습니다. 브라우저 설정에서 변경하세요.");
        }
    } else {
        console.log("⚠️ 이 브라우저는 알림을 지원하지 않습니다.");
    }
}

// ---------------------------------------------------------
// [신규] 3. 브라우저 알림 표시 (OS 차원 알림)
// ---------------------------------------------------------
function showBrowserNotification(title, message) {
    // 권한이 허용된 경우에만 알림 표시
    if ("Notification" in window && Notification.permission === "granted") {
        const notification = new Notification(title, {
            body: message,
            tag: "disaster-alert", // 같은 태그는 중복 알림 방지
            requireInteraction: false, // 자동으로 사라지게 (true면 사용자가 클릭해야 사라짐)
        });
        
        // 알림 클릭 시 재난문자 전용방 열기
        notification.onclick = () => {
            window.focus(); // 브라우저 창을 앞으로 가져옴
            openDisasterRoom();
            notification.close();
        };
        
        // 5초 후 자동으로 알림 닫기
        setTimeout(() => notification.close(), 5000);
    }
}

// ---------------------------------------------------------
// [신규] 4. 우측 하단 팝업(Toast) 그리기 함수
// ---------------------------------------------------------
function showToast(message) {
    const container = document.getElementById("toastContainer");
    
    // 알림창(div) 생성
    const toast = document.createElement("div");
    toast.className = "toast-message";
    
    // 글자가 너무 길면 자르기 (요약해서 보여주기)
    const shortMessage = message.length > 30 ? message.substring(0, 30) + "..." : message;
    toast.innerHTML = `<strong>🚨 재난 알림</strong><br><span style="font-size: 13px;">${shortMessage}</span>`;
    
    // 팝업을 클릭하면 재난문자 전용방이 열리도록 설정
    toast.onclick = () => {
        openDisasterRoom();
        toast.remove(); // 클릭하면 팝업은 바로 닫힘
    };

    container.appendChild(toast);

    // 5초(5000ms) 뒤에 자동으로 알림창이 사라지게 함
    setTimeout(() => {
        if (toast.parentElement) toast.remove();
    }, 5000);
}

// ---------------------------------------------------------
// [신규] 5. 재난문자 전용방 열기/닫기/메시지 추가
// ---------------------------------------------------------
function openDisasterRoom() {
    document.getElementById("disasterModal").style.display = "flex";
}

function closeDisasterRoom() {
    document.getElementById("disasterModal").style.display = "none";
}

function addDisasterMessageToRoom(msg, time) {
    const msgBox = document.getElementById("disasterMessages");
    
    // 첫 메시지면 안내 문구 지우기
    if (msgBox.innerHTML.includes("이곳에 실시간 재난")) {
        msgBox.innerHTML = ""; 
    }

    // 재난문자 말풍선 디자인
    const alertDiv = document.createElement("div");
    alertDiv.style.cssText = "background-color: #fff; border: 1px solid #ffcdd2; border-left: 4px solid #d32f2f; padding: 10px; margin-bottom: 10px; border-radius: 4px;";
    
    alertDiv.innerHTML = `
        <div style="font-size: 11px; color: #888; margin-bottom: 5px;">${time}</div>
        <div style="font-size: 14px; color: #333; line-height: 1.4;">${msg}</div>
    `;
    
    msgBox.appendChild(alertDiv);
    
    // 새 문자가 오면 스크롤 맨 아래로 내리기
    msgBox.scrollTop = msgBox.scrollHeight;
}
