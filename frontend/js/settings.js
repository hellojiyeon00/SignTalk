/**
 * 설정 기능 모듈
 * 
 * 프로필 수정, 친구 관리, GPS 위치 설정 등 
 * 설정 관련 모든 기능을 담당합니다.
 * 
 * 의존성: chat.js의 전역 변수 (BASE_URL, myId)와 함수 (fetchMyFriends)
 */

// ==========================================
// 설정 창 관리
// ==========================================

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

function closeSettings() {
    /* 설정 창 닫기 */
    document.getElementById("settingsModal").style.display = "none";
    // 모든 서브 메뉴 초기화
    document.getElementById("settingsMenu").style.display = "block";
    document.getElementById("settingsEditProfile").style.display = "none";
    document.getElementById("settingsFriendManage").style.display = "none";
    document.getElementById("settingsLocationSettings").style.display = "none";
}

// ==========================================
// 프로필 수정
// ==========================================

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

// ==========================================
// 친구 목록 관리
// ==========================================

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

// ==========================================
// GPS 위치 설정
// ==========================================

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
            
            // Kakao API로 좌표를 주소로 변환
            reverseGeocode(lat, lng);
        },
        // 실패
        (error) => {
            console.error("GPS 오류:", error);
            locationDisplay.textContent = "위치를 가져올 수 없습니다. 권한을 확인하세요.";
            locationDisplay.style.color = "#e74c3c";
            
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    alert("위치 권한이 거부되었습니다. 브라우저 설정에서 위치 권한을 허용해주세요.");
                    break;
                case error.POSITION_UNAVAILABLE:
                    alert("위치 정보를 사용할 수 없습니다.");
                    break;
                case error.TIMEOUT:
                    alert("위치 정보 요청 시간이 초과되었습니다.");
                    break;
            }
        },
        // 옵션
        {
            enableHighAccuracy: true,  // 정확도 우선
            timeout: 10000,            // 10초 타임아웃
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

function parseLocationString(locationStr) {
    /**
     * 주소 문자열에서 시/도, 구/군 정보 추출
     * @param {string} locationStr - 입력한 주소 (예: "서울특별시 강남구", "경기도 성남시 분당구")
     * @returns {object} - {city: "시/도", district: "구/군/시"}
     */
    
    // 시/도 패턴: 특별시, 광역시, 도, 특별자치시, 특별자치도
    const cityPattern = /(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|경기도|강원특별자치도|강원도|충청북도|충청남도|전라북도|전북특별자치도|전라남도|경상북도|경상남도|제주특별자치도)/;
    
    // 구/군/시 패턴: ~구, ~군, ~시 (단, "특별시", "광역시"는 제외)
    const districtPattern = /([가-힣]+(?:구|군|시))(?!별|역)/;
    
    const result = {
        city: null,
        district: null
    };
    
    // 시/도 추출
    const cityMatch = locationStr.match(cityPattern);
    if (cityMatch) {
        result.city = cityMatch[1];
        
        // 시/도 이후 부분에서 구/군/시 추출
        const afterCity = locationStr.substring(cityMatch.index + cityMatch[1].length);
        const districtMatch = afterCity.match(districtPattern);
        
        if (districtMatch) {
            result.district = districtMatch[1];
        }
    }
    
    return result;
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
    
    // "전체" 입력 시 모든 재난문자 수신
    if (location === "전체" || location.toLowerCase() === "all") {
        localStorage.setItem("userRegion1", "전체");
        localStorage.removeItem("userRegion2");
        
        // 저장된 위치 정보 표시
        document.getElementById("savedLocationInfo").style.display = "block";
        document.getElementById("savedLocationText").textContent = location;
        
        alert("✅ 전국 모든 재난문자를 수신합니다.");
        console.log("✅ 수동 위치 저장: 전체 (모든 재난문자 수신)");
        return;
    }
    
    // 주소에서 시/도, 구/군 정보 추출
    const parsedLocation = parseLocationString(location);
    
    // 파싱된 지역 정보 저장 (재난문자 필터링용)
    if (parsedLocation.city) {
        localStorage.setItem("userRegion1", parsedLocation.city);
        console.log(`   시/도: ${parsedLocation.city}`);
    } else {
        localStorage.removeItem("userRegion1");
        console.warn("⚠️ 시/도 정보를 추출하지 못했습니다.");
    }
    
    if (parsedLocation.district) {
        localStorage.setItem("userRegion2", parsedLocation.district);
        console.log(`   구/군: ${parsedLocation.district}`);
    } else {
        localStorage.removeItem("userRegion2");
    }
    
    // 저장된 위치 정보 표시
    document.getElementById("savedLocationInfo").style.display = "block";
    document.getElementById("savedLocationText").textContent = location;
    
    // 사용자 피드백
    if (parsedLocation.city) {
        alert(`위치가 저장되었습니다.\n📍 ${parsedLocation.city} ${parsedLocation.district || ''}`);
        console.log("✅ 수동 위치 저장:", location);
        console.log(`   재난 필터링 활성화: ${parsedLocation.city} ${parsedLocation.district || ''}`);
    } else {
        alert("위치가 저장되었으나 시/도 정보를 인식하지 못했습니다.\n재난 필터링이 작동하지 않을 수 있습니다.");
        console.log("⚠️ 수동 위치 저장 (필터링 불가):", location);
    }
}

