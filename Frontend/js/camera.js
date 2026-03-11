// ===== DOM =====
const openBtn = document.getElementById("signCameraBtn");
const closeBtn = document.getElementById("closeCameraBtn");
const modal = document.getElementById("cameraModal");
const overlay = document.getElementById("cameraOverlay");
const video = document.getElementById("videoInput");
const videoLoading = document.getElementById("videoLoading");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const statusText = document.getElementById("statusText");
const cameraControls = document.getElementById("cameraControls");
const translationResult = document.getElementById("translationResult");
const translationInput = document.getElementById("translationInput");

// ===== 상태 =====
let mediaRecorder;
let recordedChunks = [];
let stream = null;

const mimeType = 'video/webm; codecs=vp8';

function showLoading() {
  videoLoading.classList.remove("hidden");
  video.style.visibility = "hidden";
}

function hideLoading() {
  videoLoading.classList.add("hidden");
  video.style.visibility = "visible";
}

// ===== 카메라 열기 =====
openBtn.addEventListener("click", async () => {
    if (!currentRoomName || !currentRoomId) {
        alert("대화 상대를 먼저 선택해주세요.");
        return;
    }

    // 1. 모달 표시
    modal.style.display = "block";
    overlay.style.display = "block";

    video.style.transform = "scaleX(-1)"; // 거울 모드

    console.log("📷 [Camera] Open Camera")
    statusText.textContent = "카메라 준비 중...";

    startBtn.disabled = true;
    stopBtn.disabled = true;

    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 480, height: 360 },
            audio: false
        });
        video.srcObject = stream;

        video.onloadedmetadata = () => {
            startBtn.disabled = false;
            statusText.classList.add("active");
            statusText.textContent = "시작 버튼을 눌러주세요.";
        };
    }
    catch (e) {
        alert("카메라 접근 불가");
        closeCamera();
    }
});

// ===== 시작 =====
startBtn.addEventListener("click", () => {
    if (!stream) return;
    
    console.log("📷 [Camera] Start Recording")

    recordedChunks = []; // 이전 데이터 초기화

    try {
        mediaRecorder = new MediaRecorder(stream, { mimeType });

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = uploadVideo;

        mediaRecorder.start(); 

        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusText.classList.remove("active");
        statusText.textContent = "녹화 중...";
    } catch (err) {
        console.error("Recorder Error:", err);
        alert("녹화를 시작할 수 없습니다.");
    }
});


// ===== 중지 =====
stopBtn.addEventListener("click", async () => {
    console.log("📷 [Camera] Stop Recording")

    // onstop 이벤트(uploadVideo) 발생
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }

    stopBtn.disabled = true;
    statusText.textContent = "";
});

// ===== 서버 전송 함수 추가 =====
async function uploadVideo() {
    if (recordedChunks.length === 0) return;

    console.log("📤 [Camera] Uploading Video");
    
    // 로딩 UI 표시
    showLoading();

    const videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
    const formData = new FormData();
    
    // 채팅방 정보
    const fileName = `${currentRoomId}_${myNo}_video.webm`
    formData.append('file', videoBlob, fileName);
    formData.append('room', currentRoomName);
    formData.append('room_id', currentRoomId);
    formData.append('username', myId);
    formData.append('userno', myNo);

    try {
        const response = await fetch(`${BASE_URL}/sign2text/save_video`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("서버 응답 오류");

        const result = await response.json();
        console.log("✅ [Camera] Translation Success:", result);

        // 번역 결과 UI 처리
        onTranslationComplete(result)

    } catch (error) {
        console.error("❌ [Camera] Upload Failed:", error);
        statusText.textContent = "번역 실패";
        alert("번역 중 오류가 발생했습니다.");

    } finally {
        if (videoLoading) videoLoading.classList.add('hidden');
        startBtn.disabled = false;
    }
}

// ===== 닫기 =====
function closeCamera() {
    console.log("📷 [Camera] Close Camera")

    // 스트림 정지 (카메라 불 끄기)
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    
    // 비디오 소스 초기화
    video.srcObject = null;
    
    // UI 닫기
    modal.style.display = "none";
    overlay.style.display = "none";
    
    // 상태 초기화
    video.style.display = "block";
    cameraControls.classList.remove("hidden");
    translationInput.value = "";
    translationResult.classList.add("hidden");
    statusText.textContent = "";
}

closeBtn.addEventListener("click", closeCamera);

// 번역 완료 처리: '번역 완료' 표시 → 카메라 종료 → 입력창에 텍스트 입력
function onTranslationComplete(data) {
    
    // 로딩바 숨기기
    hideLoading();

    // 카메라 제어 영역과 비디오 숨기기
    if (cameraControls) cameraControls.classList.add("hidden");
    if (video) video.style.display = "none"; // 비디오를 아예 안보이게 처리
    statusText.textContent = "";

    // 번역 결과 입력창 표시
    const resultText = data.message;
    if (translationInput && translationResult) {
        translationInput.value = resultText;
        translationResult.classList.remove("hidden");
        
        // 입력창에 포커스 (약간의 지연시간을 주어 렌더링 후 실행되게 함)
        setTimeout(() => translationInput.focus(), 50);
    }

    console.log("✅ [Camera] 번역 완료 → 결과 표시");
}

// ===== 모달 내 전송 버튼 =====
function sendTranslation() {
    const text = translationInput.value.trim();
    if (!text) return;

    // Socket.IO 전송(랜드마크 전송 중단)
    socket.emit("send_translation", {
        room: currentRoomName,
        room_id: currentRoomId,
        username: myId,
        message: text,
    });

    console.log(`📤 [Socket] 전송: ${text}`);

    closeCamera();
}