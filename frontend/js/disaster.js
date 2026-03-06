/**
 * 재난문자 관리 모듈
 * SSE 기반 실시간 재난문자 수신 및 알림
 */

// ======== 재난문자 전역 변수 ========
let disasterEventSource = null;
let latestDisasterType = null; // 가장 최근 재난문자 등급 저장
let unreadDisasterCount = 0; // 읽지 않은 재난문자 개수

// ======== 지역 필터링 ========
/**
 * 재난문자 지역 필터링 체크
 * @param {string} disasterRegion - 재난문자 발생 지역 (예: "서울특별시 강남구")
 * @returns {boolean} - true: 수신, false: 필터링
 */
function shouldReceiveDisaster(disasterRegion) {
    // 재난 지역 정보가 없으면 모든 사용자에게 전송 (전국 재난)
    if (!disasterRegion) {
        console.log("📍 [필터링] 전국 재난 → 모든 사용자 수신");
        return true;
    }
    
    // localStorage에서 사용자 위치 정보 가져오기
    const userCity = localStorage.getItem("userRegion1"); // 시/도 (예: "서울특별시")
    const userDistrict = localStorage.getItem("userRegion2"); // 구/군 (예: "강남구")
    const gpsEnabled = localStorage.getItem("gpsEnabled"); // GPS 사용 여부
    
    // 위치 설정이 안되어 있으면 모든 재난문자 수신
    if (!userCity) {
        console.log("📍 [필터링] 위치 미설정 → 모든 재난 수신");
        return true;
    }
    
    // "전체" 설정 시 모든 재난문자 수신
    if (userCity === "전체") {
        console.log("📍 [필터링] 전체 설정 → 모든 재난 수신");
        return true;
    }
    
    // 위치 설정 방식 로그
    const locationSource = gpsEnabled === "true" ? "GPS" : "수동입력";
    console.log(`📍 [필터링] 내 위치 (${locationSource}): ${userCity} ${userDistrict || ''}`);
    
    // 대소문자 구분 없이 비교
    const regionLower = disasterRegion.toLowerCase();
    const cityLower = userCity.toLowerCase();
    const districtLower = userDistrict ? userDistrict.toLowerCase() : "";
    
    // 시/도 매칭 확인
    if (regionLower.includes(cityLower)) {
        // 구/군 정보가 있으면 구/군도 확인
        if (districtLower && !regionLower.includes(districtLower)) {
            console.log(`🔇 [필터링] ❌ 구/군 불일치 → 재난: ${disasterRegion} / 내위치: ${userCity} ${userDistrict}`);
            return false;
        }
        console.log(`✅ [필터링] ✔️ 지역 일치 → ${disasterRegion} 재난문자 수신`);
        return true;
    }
    
    console.log(`🔇 [필터링] ❌ 시/도 불일치 → 재난: ${disasterRegion} / 내위치: ${userCity} ${userDistrict || ''}`);
    return false;
}

// ======== SSE 연결 ========
async function connectDisasterSSE() {
    /* SSE 연결로 재난문자 수신 (fetch 기반 SSE - JWT 인증 포함) */
    if (disasterEventSource) {
        disasterEventSource.close();
        disasterEventSource = null;
    }
    
    try {
        // createSSEConnection은 fetch 기반 SSE 구현 (JWT 토큰 자동 포함)
        disasterEventSource = await createSSEConnection(`${BASE_URL}/disaster/stream`, {
            // 재난문자 수신 이벤트
            disaster: (event) => {
                let data = event.data;
            // 🔥 SSE payload가 문자열로 오는 경우 JSON 파싱
                if (typeof data === "string") {
                    try {
                        data = JSON.parse(data);
                    } catch (e) {
                        console.error("❌ [SSE] disaster payload JSON parse 실패:", e, data);
                        return;
                    }
                }

                console.log("🚨 [SSE] 재난문자 수신:", data);
                                
                // 📍 지역 필터링 체크
                if (!shouldReceiveDisaster(data.region)) {
                    return; // 필터링: 처리 중단
                }
                
                // 🔔 재난문자 알림 설정 확인
                const disasterNotificationEnabled = localStorage.getItem("disasterNotificationEnabled") !== "false";
                if (!disasterNotificationEnabled) {
                    console.log("🔇 [알림] 재난문자 알림이 비활성화되어 있습니다.");
                    return; // 알림 비활성화 시 아무것도 표시하지 않음
                }
                
                // 최신 재난문자 등급 저장 및 개수 증가
                latestDisasterType = data.type_code;
                unreadDisasterCount++;
                
                // model_server URL 매칭
                const gloss = data.gloss || null;
                const urls  = Array.isArray(data.urls) ? data.urls : [];

                // 1) 우측 하단에 팝업(Toast) 띄우기 (등급 정보 + 이미지 포함)
                showToast(data.message, data.type_code, data.type_name, data.disaster_type);
                
                // 2) 재난문자 전용 모달창에도 내용 추가하기 (등급 정보 + 이미지 포함)
                addDisasterMessageToRoom(data.message, data.time, data.type_code, data.type_name, data.disaster_type, urls, gloss);
                
                // 3) 브라우저 알림 표시 (등급에 따른 제목)
                const alertTitle = getDisasterTitle(data.type_code, data.type_name);
                showBrowserNotification(alertTitle, data.message, data.type_code);
                
                // 4) 재난문자 버튼 업데이트 (등급에 따른 스타일 + 개수)
                updateDisasterButton(data.type_code, unreadDisasterCount);
            },
            
            // 연결 유지용 ping 이벤트
            ping: (event) => {
                // keep-alive 메시지, 로그 출력 안 함
            },
            
            // shutdown 이벤트: 서버가 중복 연결을 감지했을 때
            shutdown: (event) => {
                console.log("🔄 [SSE] 서버가 중복 연결을 감지했습니다. 이 연결을 종료합니다.");
                if (disasterEventSource) {
                    disasterEventSource.close();
                    disasterEventSource = null;
                }
            },
            
            // 오류 처리
            error: (error) => {
                console.error("❌ [SSE] 재난문자 스트림 오류:", error);
                console.log("🔄 [SSE] 5초 후 재연결 시도...");
                disasterEventSource = null;
                setTimeout(connectDisasterSSE, 5000);
            },
            
            // 연결 종료
            close: () => {
                console.log("🔌 [SSE] 재난문자 스트림 연결 종료");
            }
        });
        
        console.log("✅ [SSE] 재난문자 스트림 연결 중...");
        
    } catch (error) {
        console.error("❌ [SSE] 연결 실패:", error);
        console.log("🔄 [SSE] 5초 후 재연결 시도...");
        setTimeout(connectDisasterSSE, 5000);
    }
}

// ======== 브라우저 알림 ========
function requestNotificationPermission() {
    /* 브라우저 알림 권한 요청 */
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

function showBrowserNotification(title, message, typeCode = 'EM') {
    /* 브라우저 알림 표시 (OS 차원 알림) */
    if ("Notification" in window && Notification.permission === "granted") {
        // 위급/긴급 재난은 사용자가 직접 닫아야 함
        const requireInteraction = (typeCode === 'EX' || typeCode === 'EM');
        
        const notification = new Notification(title, {
            body: message,
            tag: "disaster-alert", // 같은 태그는 중복 알림 방지
            requireInteraction: requireInteraction, // 위급/긴급은 true, 안전안내는 false
        });
        
        // 알림 클릭 시 재난문자 전용방 열기
        notification.onclick = () => {
            window.focus(); // 브라우저 창을 앞으로 가져옴
            openDisasterRoom();
            notification.close();
        };
        
        // 안전안내(SA)만 5초 후 자동으로 알림 닫기
        if (typeCode === 'SA') {
            setTimeout(() => notification.close(), 12000);
        }
        // EX(위급), EM(긴급)은 사용자가 직접 닫을 때까지 유지
    }
}

// ======== 재난문자 등급/이미지 설정 ========
function getDisasterConfig(typeCode) {
    /* 재난문자 등급에 따른 설정 반환 */
    const configs = {
        'EX': { // 위급재난 (가장 심각)
            icon: '🚨',
            color: '#d32f2f',
            bgColor: '#ffebee',
            borderColor: '#ef5350',
            title: '위급재난'
        },
        'EM': { // 긴급재난
            icon: '⚠️',
            color: '#f57c00',
            bgColor: '#fff3e0',
            borderColor: '#ff9800',
            title: '긴급재난'
        },
        'SA': { // 안전안내
            icon: 'ℹ️',
            color: '#1976d2',
            bgColor: '#e3f2fd',
            borderColor: '#42a5f5',
            title: '안전안내'
        }
    };
    
    // 등록되지 않은 코드는 기본값 (긴급재난)
    return configs[typeCode] || configs['EM'];
}

function getDisasterImage(disasterType) {
    /* 재난 유형에 따른 이미지 경로 반환 */
    const imageMap = {
        '미세먼지': `${BASE_URL}/images/ultra_fine_microdust.png`,
        '한파': `${BASE_URL}/images/bitter_cold.png`,
        '폭염': `${BASE_URL}/images/heat_wave.png`,
        '산불': `${BASE_URL}/images/forest_fire.png`,
        '악천후': `${BASE_URL}/images/bad_weather.png`,
        '열대야': `${BASE_URL}/images/tropical_night.png`,
        '전염병': `${BASE_URL}/images/infectious_disease.png`,
        '지진': `${BASE_URL}/images/earthquake.png`,
        '태풍': `${BASE_URL}/images/typhoon.png`,
        '지진해일': `${BASE_URL}/images/tsunami.png`,
        '홍수': `${BASE_URL}/images/deluge_flood.png`,
        '화재': `${BASE_URL}/images/fire.png`,
        '민방공': `${BASE_URL}/images/war.png`,
        '기타': `${BASE_URL}/images/etc_disaster.png`
    };
    
    // 등록되지 않은 유형은 기타로 처리
    return imageMap[disasterType] || imageMap['기타'];
}

function getDisasterTitle(typeCode, typeName) {
    /* 재난문자 등급별 제목 생성 */
    const config = getDisasterConfig(typeCode);
    return `${config.icon} ${typeName || config.title} 알림`;
}

// ======== 토스트 알림 ========
function showToast(message, typeCode = 'EM', typeName = null, disasterType = null) {
    /* 우측 하단 팝업(Toast) 표시 */
    const container = document.getElementById("toastContainer");
    const config = getDisasterConfig(typeCode);
    
    // 알림창(div) 생성
    const toast = document.createElement("div");
    toast.className = "toast-message";
    toast.style.backgroundColor = config.bgColor;
    toast.style.borderLeft = `4px solid ${config.borderColor}`;
    toast.style.position = "relative"; // 닫기 버튼 위치를 위해
    
    // 글자가 너무 길면 자르기 (요약해서 보여주기)
    const shortMessage = message.length > 30 ? message.substring(0, 30) + "..." : message;
    const displayTitle = typeName || config.title;
    
    // 위급/긴급 재난은 닫기 버튼 추가
    const closeButton = (typeCode === 'EX' || typeCode === 'EM') 
        ? `<button onclick="this.parentElement.remove()" style="position:absolute; top:5px; right:5px; background:none; border:none; color:${config.color}; font-size:16px; cursor:pointer; padding:0; width:20px; height:20px;">✕</button>`
        : '';
    
    // 긴급/위급 재난은 이미지 표시
    // let imageHtml = '';
    // if ((typeCode === 'EX' || typeCode === 'EM' || typeCode === 'SA') && disasterType) {
    //     const imagePath = getDisasterImage(disasterType);
    //     imageHtml = `<img src="${imagePath}" alt="${disasterType}" style="width:100%; max-width:200px; height:auto; border-radius:8px; margin-bottom:10px; display:block;">`;
    // }

    // 긴급/위급/안전안내 재난은 기존 재난 이미지(disasterType)만 표시
    let imageHtml = '';
    if ((typeCode === 'EX' || typeCode === 'EM') && disasterType) {
        const imagePath = getDisasterImage(disasterType);
        imageHtml = `<img src="${imagePath}" alt="${disasterType}" style="width:100%; max-width:200px; height:auto; border-radius:8px; margin-bottom:10px; display:block;">`;
    }
    
    toast.innerHTML = `
        ${closeButton}
        <strong style="color:${config.color};">${config.icon} ${displayTitle}</strong><br>
        ${imageHtml}
        <span style="font-size: 13px; color: #333;">${shortMessage}</span>
    `;
    
    // 팝업을 클릭하면 재난문자 전용방이 열리도록 설정 (닫기 버튼 제외)
    toast.onclick = (e) => {
        // 닫기 버튼 클릭이 아닐 때만 실행
        if (e.target.tagName !== 'BUTTON') {
            openDisasterRoom();
            toast.remove(); // 클릭하면 팝업은 바로 닫힘
        }
    };

    container.appendChild(toast);

    // 등급에 따라 자동 제거 설정
    // EX(위급), EM(긴급): 자동으로 사라지지 않음 (사용자가 직접 닫아야 함)
    // SA(안전안내): 5초 후 자동 제거
    if (typeCode === 'SA') {
        setTimeout(() => {
            if (toast.parentElement) toast.remove();
        }, 5000);
    }
}

// ======== 재난문자 모달 ========
function updateDisasterButton(typeCode, count = 0) {
    /* 재난문자 버튼을 등급에 따라 업데이트 */
    const button = document.querySelector('[onclick="openDisasterRoom()"]');
    if (!button) return;
    
    const config = getDisasterConfig(typeCode);
    
    // 버튼 스타일 업데이트
    button.style.backgroundColor = config.bgColor;
    button.style.color = config.color;
    button.style.borderColor = config.borderColor;
    
    // 버튼 텍스트 업데이트 (읽지 않은 개수 표시)
    const countBadge = count > 0 
        ? `<span style="background:${config.color}; color:white; border-radius:50%; min-width:20px; height:20px; display:inline-flex; align-items:center; justify-content:center; font-size:11px; margin-left:5px; padding:0 5px;">${count}</span>`
        : '';
    
    button.innerHTML = `${config.icon} 재난 문자 알림 ${countBadge}`;
}

function openDisasterRoom() {
    /* 재난문자 모달 열기 */
    const modal = document.getElementById("disasterModal");
    modal.style.display = "flex";
    
    // 모달 제목 업데이트 (최신 등급에 따라)
    const modalTitle = modal.querySelector("h3");
    if (modalTitle && latestDisasterType) {
        const config = getDisasterConfig(latestDisasterType);
        modalTitle.innerHTML = `${config.icon} 재난 문자 알림방`;
        modalTitle.style.color = config.color;
    }
    
    // 읽음 처리: 카운트 초기화 및 버튼 업데이트
    unreadDisasterCount = 0;
    if (latestDisasterType) {
        updateDisasterButton(latestDisasterType, 0);
    }
}

function closeDisasterRoom() {
    /* 재난문자 모달 닫기 */
    document.getElementById("disasterModal").style.display = "none";
}

function addDisasterMessageToRoom(msg, time, typeCode = 'EM', typeName = null, disasterType = null, urls = [], gloss = null) {
    /* 재난문자 모달에 메시지 추가 */
    const msgBox = document.getElementById("disasterMessages");
    const config = getDisasterConfig(typeCode);
    
    // 첫 메시지면 안내 문구 지우기
    if (msgBox.innerHTML.includes("이곳에 실시간 재난")) {
        msgBox.innerHTML = ""; 
    }

    // 재난문자 말풍선 디자인 (등급별 색상 적용)
    const alertDiv = document.createElement("div");
    alertDiv.style.cssText = `
        background-color: ${config.bgColor}; 
        border: 1px solid ${config.borderColor}; 
        border-left: 4px solid ${config.color}; 
        padding: 10px; 
        margin-bottom: 10px; 
        border-radius: 4px;
    `;
    
    // 긴급/위급/안전안내 재난은 이미지 표시
    // let imageHtml = '';
    // if ((typeCode === 'EX' || typeCode === 'EM' || typeCode === 'SA') && disasterType) {
    //     const imagePath = getDisasterImage(disasterType);
    //     console.log(`🖼️ [모달 이미지] 재난 유형: ${disasterType}, 경로: ${imagePath}`);
    //     imageHtml = `<img src="${imagePath}" alt="${disasterType}" style="width:100%; max-width:300px; height:auto; border-radius:8px; margin-bottom:10px; display:block;" onerror="console.error('모달 이미지 로드 실패:', '${imagePath}'); this.style.display='none';">`;
    // } else {
    //     console.log(`ℹ️ [모달 이미지] 표시 안 함 - 등급: ${typeCode}, 유형: ${disasterType}`);
    // }

    // SA만: urls 시퀀스(video) 우선, 그 외(EX/EM)는 기존 이미지 유지
    let mediaHtml = "";

    if (typeCode === "SA") {
        const seqUrls = Array.isArray(urls)
            ? urls.filter(u => typeof u === "string" && u.trim())
            : [];

        if (seqUrls.length > 0) {
            mediaHtml = `
                <video
                    class="disaster-seq-video"
                    src="${seqUrls[0]}"
                    data-idx="0"
                    data-urls="${encodeURIComponent(JSON.stringify(seqUrls))}"
                    controls
                    muted
                    playsinline
                    preload="metadata"
                    style="width:100%; max-width:360px; border-radius:8px; margin-bottom:10px; display:block;"
                ></video>
            `;
        } else {
            console.log("ℹ️ [SA] urls 없음 → 영상 미표시");
            mediaHtml = "";
        }
    } else {
        // EX/EM: 기존 이미지 유지
        if (disasterType) {
            const imagePath = getDisasterImage(disasterType);
            mediaHtml = `
                <img
                    src="${imagePath}"
                    alt="${disasterType}"
                    style="width:100%; max-width:300px; border-radius:8px; margin-bottom:10px;"
                >
            `;
        }
    }

    // 등급명(typeName)이 있으면 표시, 없으면 config의 기본 제목 사용
    const displayTitle = typeName || config.title;
    alertDiv.innerHTML = `
        <div style="font-size: 12px; font-weight: bold; color: ${config.color}; margin-bottom: 5px;">
            ${config.icon} ${displayTitle}
            <span style="font-weight: normal; color: #888; margin-left: 8px;">${time}</span>
        </div>
        ${mediaHtml}
        <div style="font-size: 14px; color: #333; line-height: 1.4;">${msg}</div>
    `;

    msgBox.appendChild(alertDiv);

    // ✅ SA만: 끝나면 다음 영상으로 자동 재생 (버튼 없이, video 컨트롤로 시작)
    if (typeCode === "SA") {
        const videoEl = alertDiv.querySelector(".disaster-seq-video");

        if (videoEl) {
            const getList = () => {
                try {
                    const raw = videoEl.getAttribute("data-urls") || "";
                    return raw ? JSON.parse(decodeURIComponent(raw)) : [];
                } catch (e) {
                    console.error("❌ [SA] data-urls parse 실패:", e);
                    return [];
                }
            };

            const resetToFirst = () => {
                const list = getList();
                if (list.length === 0) return;

                videoEl.setAttribute("data-idx", "0");
                videoEl.src = list[0];
                videoEl.load();          // 재생은 하지 않음(사용자가 ▶️ 누르면 0번부터 시작)
                videoEl.currentTime = 0; // ✅ load() 뒤에 두는 게 안전
            };

            const playAt = (i) => {
                const list = getList();
                if (!list[i]) return;

                videoEl.src = list[i];
                videoEl.setAttribute("data-idx", String(i));

                console.log("🎬 [SA] set src =", videoEl.src);

                videoEl.load();
                videoEl.play().catch((e) => {
                    // 자동재생 정책/네트워크 문제 로그
                    console.warn("❌ [SA] play() blocked/failed:", e);
                });
            };

            videoEl.addEventListener("error", () => {
                const list = getList();
                const current = parseInt(videoEl.getAttribute("data-idx") || "0", 10);
                const next = current + 1;

                console.error("❌ [SA] video error:", videoEl.error, "src=", videoEl.src);

                if (next < list.length) {
                    playAt(next);
                } else {
                    console.log("✅ [SA] error로 시퀀스 종료 → 다음 재생을 위해 0번으로 리셋");
                    resetToFirst();
                }
            });

            // 첫 재생은 사용자가 컨트롤 ▶️ 눌러서 시작
            // 이후 ended 시점에만 다음 영상으로 자동 넘김
            videoEl.addEventListener("ended", () => {
                const list = getList();
                const current = parseInt(videoEl.getAttribute("data-idx") || "0", 10);
                const next = current + 1;

                console.log("🎬 [SA] ended. current=", current, "next=", next, "len=", list.length);

                if (next < list.length) {
                    playAt(next);
                    
                } else {
                    console.log("✅ [SA] 시퀀스 재생 완료 → 다음 재생을 위해 0번으로 리셋");
                    resetToFirst();
                }
            });
        } else {
            console.log("ℹ️ [SA] videoEl not found");
        }
    }
    // 새 문자가 오면 스크롤 맨 아래로 내리기
    msgBox.scrollTop = msgBox.scrollHeight;
}

// ======== 브라우저 종료/새로고침 시 SSE 연결 해제 ========
window.addEventListener('beforeunload', () => {
    // 브라우저가 닫히거나 새로고침될 때 SSE 연결을 안전하게 해제하여 서버 리소스 낭비 방지
    if (disasterEventSource) {
        disasterEventSource.close();
        console.log("🔌 [브라우저 종료/새로고침] SSE 연결을 안전하게 해제했습니다.");
    }
});

// ======== 페이지 로드 시 자동으로 SSE 연결 시작 ========
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log("✅ [재난문자] 페이지 로드 완료, SSE 연결 시작");
        connectDisasterSSE();
    });
} else {
    // 스크립트가 늦게 로드된 경우 즉시 실행
    console.log("✅ [재난문자] SSE 연결 즉시 시작");
    connectDisasterSSE();
}