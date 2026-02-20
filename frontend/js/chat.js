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
        displayMessage(data.sender, data.sender_name, data.message, timeStr);
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
            } catch(e) {}

            displayMessage(chat.sender, chat.sender_name, chat.message, timeStr);
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

function displayMessage(senderId, senderName, msg, time) {
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

    const timeSpan = document.createElement("span");
    timeSpan.className = "message-time";
    timeSpan.textContent = time;

    contentDiv.appendChild(bubbleDiv);
    contentDiv.appendChild(timeSpan);
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

// ======== 설정 관련 ========
function openSettings() {
    /* 설정창 열기 */
    const modal = document.getElementById("settingsModal");
    document.getElementById("settingsMenu").style.display = "block";
    document.getElementById("settingsEditProfile").style.display = "none";
    document.getElementById("settingsFriendManage").style.display = "none";
    document.getElementById("settingsLocationSettings").style.display = "none";
    modal.style.display = "flex";
}

function showSettingsMenu() {
    /* 설정 메뉴로 돌아가기 */
    document.getElementById("settingsMenu").style.display = "block";
    document.getElementById("settingsEditProfile").style.display = "none";
    document.getElementById("settingsFriendManage").style.display = "none";
    document.getElementById("settingsLocationSettings").style.display = "none";
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
    // 모든 서브 메뉴 초기화
    document.getElementById("settingsMenu").style.display = "block";
    document.getElementById("settingsEditProfile").style.display = "none";
    document.getElementById("settingsFriendManage").style.display = "none";
    document.getElementById("settingsLocationSettings").style.display = "none";
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

// ======== 친구 목록 관리 ========
async function goToFriendManage() {
    /* 친구 목록 관리 화면으로 이동 */
    document.getElementById("settingsMenu").style.display = "none";
    document.getElementById("settingsFriendManage").style.display = "block";
    
    // 친구 목록 로드
    await loadFriendList();
}

async function loadFriendList() {
    /* 친구 목록 로드 */
    try {
        const res = await fetch(`${BASE_URL}/chat/friends?user_id=${myId}`);
        if (!res.ok) throw new Error("친구 목록 로딩 실패");
        
        const friends = await res.json();
        const listContainer = document.getElementById("friendManageList");
        listContainer.innerHTML = "";

        if (friends.length === 0) {
            listContainer.innerHTML = `
                <div style='padding:20px; text-align:center; color:#999;'>
                    등록된 친구가 없습니다.
                </div>`;
            return;
        }

        friends.forEach(friend => {
            const itemDiv = document.createElement("div");
            itemDiv.style.cssText = `
                padding: 12px; 
                border: 1px solid #e0e0e0; 
                border-radius: 8px; 
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            `;

            // 친구 정보
            const infoDiv = document.createElement("div");
            const statusText = friend.is_blocked ? ' <span style="font-size:11px; color:#ff9800;">(차단됨)</span>' : '';
            infoDiv.innerHTML = `
                <div style="font-weight:bold; margin-bottom:5px;">${friend.user_name}${statusText}</div>
                <div style="font-size:12px; color:#666;">${friend.user_id}</div>
            `;

            // 차단/차단 해제 버튼
            const actionBtn = document.createElement("button");
            
            if (friend.is_blocked) {
                // 차단된 친구 → 차단 해제 버튼
                actionBtn.textContent = "차단 해제";
                actionBtn.style.cssText = `
                    padding: 6px 15px; 
                    background: #4caf50; 
                    color: white; 
                    border: none; 
                    border-radius: 4px; 
                    cursor: pointer;
                    font-size: 13px;
                `;
                actionBtn.onclick = () => unblockFriend(friend.user_id);
            } else {
                // 활성 친구 → 차단 버튼
                actionBtn.textContent = "차단";
                actionBtn.style.cssText = `
                    padding: 6px 15px; 
                    background: #ff9800; 
                    color: white; 
                    border: none; 
                    border-radius: 4px; 
                    cursor: pointer;
                    font-size: 13px;
                `;
                actionBtn.onclick = () => blockFriend(friend.user_id);
            }

            itemDiv.appendChild(infoDiv);
            itemDiv.appendChild(actionBtn);
            listContainer.appendChild(itemDiv);
        });
    } catch (e) {
        console.error(e);
        alert("친구 목록을 불러올 수 없습니다.");
    }
}

async function blockFriend(friendId) {
    /* 친구 차단 */
    if (!confirm(`'${friendId}'님을 차단하시겠습니까?\n차단된 친구는 목록에서 숨겨지며, 차단 해제 시 다시 표시됩니다.`)) return;

    try {
        const res = await fetch(`${BASE_URL}/chat/friend/block?my_id=${myId}&friend_id=${friendId}`, {
            method: "POST"
        });
        
        const result = await res.json();
        
        if (res.ok) {
            alert(result.message);
            await loadFriendList(); // 목록 새로고침
            fetchMyFriends(); // 사이드바 친구 목록도 새로고침
        } else {
            alert("차단 실패: " + result.detail);
        }
    } catch (e) {
        console.error(e);
        alert("서버 오류가 발생했습니다.");
    }
}

async function unblockFriend(friendId) {
    /* 친구 차단 해제 */
    if (!confirm(`'${friendId}'님의 차단을 해제하시겠습니까?`)) return;

    try {
        const res = await fetch(`${BASE_URL}/chat/friend/unblock?my_id=${myId}&friend_id=${friendId}`, {
            method: "POST"
        });
        
        const result = await res.json();
        
        if (res.ok) {
            alert(result.message);
            await loadFriendList(); // 목록 새로고침
            fetchMyFriends(); // 사이드바 친구 목록도 새로고침
        } else {
            alert("차단 해제 실패: " + result.detail);
        }
    } catch (e) {
        console.error(e);
        alert("서버 오류가 발생했습니다.");
    }
}

// ======== GPS 위치 설정 ========
function goToLocationSettings() {
    /* GPS 위치 설정 화면으로 이동 */
    document.getElementById("settingsMenu").style.display = "none";
    document.getElementById("settingsLocationSettings").style.display = "block";
    
    // 저장된 설정 불러오기
    loadLocationSettings();
}

function loadLocationSettings() {
    /* localStorage에서 GPS 설정 불러오기 */
    const gpsEnabled = localStorage.getItem("gpsEnabled") === "true";
    const savedLocation = localStorage.getItem("userLocation");
    
    // 토글 상태 복원
    document.getElementById("gpsToggle").checked = gpsEnabled;
    
    // UI 업데이트
    if (gpsEnabled) {
        document.getElementById("gpsLocationDisplay").style.display = "block";
        document.getElementById("manualLocationInput").style.display = "none";
        // GPS로 현재 위치 가져오기
        getCurrentLocation();
    } else {
        document.getElementById("gpsLocationDisplay").style.display = "none";
        document.getElementById("manualLocationInput").style.display = "block";
        
        // 수동 입력값 복원
        if (savedLocation) {
            document.getElementById("manualLocation").value = savedLocation;
        }
    }
    
    // 저장된 위치 정보 표시
    if (savedLocation) {
        document.getElementById("savedLocationInfo").style.display = "block";
        document.getElementById("savedLocationText").textContent = savedLocation;
    } else {
        document.getElementById("savedLocationInfo").style.display = "none";
    }
}

function toggleGPS() {
    /* GPS 토글 스위치 변경 */
    const isEnabled = document.getElementById("gpsToggle").checked;
    
    if (isEnabled) {
        // GPS 켜기 - 권한 요청
        if ("geolocation" in navigator) {
            document.getElementById("gpsLocationDisplay").style.display = "block";
            document.getElementById("manualLocationInput").style.display = "none";
            
            localStorage.setItem("gpsEnabled", "true");
            getCurrentLocation();
        } else {
            alert("이 브라우저는 GPS를 지원하지 않습니다.");
            document.getElementById("gpsToggle").checked = false;
        }
    } else {
        // GPS 끄기 - 수동 입력으로 전환
        document.getElementById("gpsLocationDisplay").style.display = "none";
        document.getElementById("manualLocationInput").style.display = "block";
        
        localStorage.setItem("gpsEnabled", "false");
        
        // 기존 저장된 위치 불러오기
        const savedLocation = localStorage.getItem("userLocation");
        if (savedLocation) {
            document.getElementById("manualLocation").value = savedLocation;
        }
    }
}

function getCurrentLocation() {
    /* GPS로 현재 위치 가져오기 */
    const locationDisplay = document.getElementById("currentLocation");
    locationDisplay.textContent = "위치를 가져오는 중...";
    
    navigator.geolocation.getCurrentPosition(
        // 성공
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            
            console.log(`📍 GPS 좌표: ${lat}, ${lng}`);
            
            // 좌표를 주소로 변환 (Reverse Geocoding)
            reverseGeocode(lat, lng);
        },
        // 실패
        (error) => {
            console.error("GPS 오류:", error.message);
            
            let errorMsg = "";
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMsg = "위치 권한이 거부되었습니다. 브라우저 설정에서 위치 권한을 허용해주세요.";
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMsg = "위치 정보를 사용할 수 없습니다.";
                    break;
                case error.TIMEOUT:
                    errorMsg = "위치 정보 요청 시간이 초과되었습니다.";
                    break;
                default:
                    errorMsg = "알 수 없는 오류가 발생했습니다.";
            }
            
            locationDisplay.textContent = errorMsg;
            locationDisplay.style.color = "#d32f2f";
        },
        // 옵션
        {
            enableHighAccuracy: true,  // 고정밀 모드 (GPS 사용)
            timeout: 10000,            // 10초 제한
            maximumAge: 0              // 캐시 사용 안 함
        }
    );
}

function reverseGeocode(lat, lng) {
    /* 좌표를 주소로 변환 (백엔드 Kakao REST API 사용) */
    const locationDisplay = document.getElementById("currentLocation");
    
    // 로딩 상태 표시
    locationDisplay.textContent = "주소 검색 중...";
    locationDisplay.style.color = "#999";
    
    // 백엔드 API 호출
    fetch(`${BASE_URL}/location/reverse-geocode`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            latitude: lat,
            longitude: lng
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        // 주소 표시
        const locationText = data.address;
        locationDisplay.textContent = locationText;
        locationDisplay.style.color = "#333";
        
        // localStorage에 저장 (주소 + 좌표)
        localStorage.setItem("userLocation", locationText);
        localStorage.setItem("userLatitude", lat);
        localStorage.setItem("userLongitude", lng);
        localStorage.setItem("userRegion1", data.region_1depth); // 시/도
        localStorage.setItem("userRegion2", data.region_2depth); // 구/군
        localStorage.setItem("userRegion3", data.region_3depth); // 동/읍/면
        
        // 저장된 위치 정보 업데이트
        document.getElementById("savedLocationInfo").style.display = "block";
        document.getElementById("savedLocationText").textContent = locationText;
        
        console.log("✅ 위치 정보 저장 완료:", locationText);
        console.log("   행정구역:", data.region_1depth, data.region_2depth, data.region_3depth);
    })
    .catch(error => {
        console.error("❌ 주소 변환 실패:", error);
        
        // 에러 시 좌표만 표시
        const locationText = `위도: ${lat.toFixed(6)}, 경도: ${lng.toFixed(6)}`;
        
        // 에러 메시지 파싱 시도
        let errorMsg = " (주소 변환 실패)";
        if (error.message && error.message.includes("Kakao Map API")) {
            errorMsg = " (Kakao Map API 비활성화)";
        }
        
        locationDisplay.textContent = locationText + errorMsg;
        locationDisplay.style.color = "#e74c3c";
        
        // 좌표만 저장
        localStorage.setItem("userLocation", locationText);
        localStorage.setItem("userLatitude", lat);
        localStorage.setItem("userLongitude", lng);
        
        document.getElementById("savedLocationInfo").style.display = "block";
        document.getElementById("savedLocationText").textContent = locationText;
    });
}

function refreshLocation() {
    /* 위치 새로고침 버튼 */
    getCurrentLocation();
}

function saveManualLocation() {
    /* 수동 입력한 위치 저장 */
    const location = document.getElementById("manualLocation").value.trim();
    
    if (!location) {
        alert("위치를 입력해주세요.");
        return;
    }
    
    // localStorage에 저장
    localStorage.setItem("userLocation", location);
    localStorage.setItem("gpsEnabled", "false");
    
    // 저장된 위치 정보 표시
    document.getElementById("savedLocationInfo").style.display = "block";
    document.getElementById("savedLocationText").textContent = location;
    
    alert("위치가 저장되었습니다.");
    console.log("✅ 수동 위치 저장:", location);
}

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
