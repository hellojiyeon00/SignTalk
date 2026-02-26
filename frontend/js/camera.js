// ===== DOM =====
const openBtn = document.getElementById("signCameraBtn");
const closeBtn = document.getElementById("closeCameraBtn");
const modal = document.getElementById("cameraModal");
const overlay = document.getElementById("cameraOverlay");
const video = document.getElementById("videoInput");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const statusText = document.getElementById("statusText");
const messagesDiv = document.getElementById("messages");

// ===== 상태 =====
let stream = null;
let holistic = null;
let isCapturing = false;
let frameCount = 0;

// ===== 인덱스 =====
const POSE_LANDMARKS_IDX = [11, 12, 13, 14, 15, 16];
const HAND_LANDMARKS_IDX = Array.from({ length: 21 }, (_, i) => i);

// ===== MediaPipe 초기화 =====
function initHolistic() {
    console.log("📷 [MediaPipe] Initialize MediaPipe")
    holistic = new Holistic({
        locateFile: file =>
            `${CONFIG.MEDIAPIPE_CDN_BASE}/${file}`
    });

    holistic.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });

    holistic.onResults(onResults);
}

// ===== 랜드마크 처리 =====
function getCoord(landmarks, indices) {
    if (!landmarks) return new Array(indices.length * 2).fill(0);

    return indices.flatMap(i => {
        const lm = landmarks[i];
        return lm ? [lm.x, lm.y] : [0, 0];
    });
}

function onResults(results) {
    if (!isCapturing) return;

    const landmarks = [
        ...getCoord(results.poseLandmarks, POSE_LANDMARKS_IDX),
        ...getCoord(results.leftHandLandmarks, HAND_LANDMARKS_IDX),
        ...getCoord(results.rightHandLandmarks, HAND_LANDMARKS_IDX),
    ];

    frameCount++;
    statusText.textContent = `인식 중... (${frameCount} 프레임)`;

    // ✅ Socket.IO 전송(랜드마크 전송)
    socket.emit("send_landmarks", {
        room: currentRoomName,
        room_id: currentRoomId,
        username: myId,
        message: landmarks,
        status_stop: false
    });

    console.log(`📤 [Socket] 전송: ${landmarks}`);
}

// ===== 버튼 =====
openBtn.addEventListener("click", async () => {
    if (!currentRoomName || !currentRoomId) {
        alert("대화 상대를 먼저 선택해주세요.");
        return;
    }

    console.log("📷 [Camera] Open Camera")
    
    modal.style.display = "block";
    overlay.style.display = "block";

    startBtn.disabled = false;
    stopBtn.disabled = true;
    statusText.textContent = "카메라 준비 중...";

    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 480, height: 360 },
            audio: false
        });
        video.srcObject = stream;

        // 비디오가 실제로 로드될 때까지 대기(이 코드의 역할은?)
        video.onloadedmetadata = () => {
            video.play();
        };

        if (!holistic) initHolistic();
        statusText.textContent = "카메라 준비 완료";
    }
    catch {
        alert("카메라 접근 불가");
        closeCamera();
    }
});

startBtn.addEventListener("click", () => {
    console.log("📷 [Camera] Start Send Landmarks")

    isCapturing = true;
    frameCount = 0;

    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusText.classList.add("active");

    async function loop() {
        if (!isCapturing) return;
        await holistic.send({ image: video });
        requestAnimationFrame(loop);
    }
    loop();
});

// TODO: 정지 버튼 클릭 시 로딩 바가 돌아가고 문자을 반환받으면 번역 완료 문구 출력 후 카메라 화면 자동 종료
// 종료 후 (입력 창에 바로 텍스트 출력 or 정지 버튼이 전송 버튼으로 변환)
stopBtn.addEventListener("click", () => {
    console.log("📷 [Camera] Stop Send Landmarks")

    isCapturing = false;
    startBtn.disabled = true;
    stopBtn.disabled = true;
    statusText.textContent = "분석 중…";
    statusText.classList.remove("active");

    // ✅ Socket.IO 전송(랜드마크 전송 중지)
    socket.emit("send_landmarks", {
        room: currentRoomName,
        room_id: currentRoomId,
        username: myId,
        message: null,
        status_stop: true
    });
});

// TODO: 정지 버튼을 누르지 않고 카메라 화면을 닫으면 '전송하지 않고 닫으시겠습니까?' 팝업 출력
function closeCamera() {
    console.log("📷 [Camera] Close Camera")
    
    isCapturing = false;

    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        stream = null;
    }
    video.srcObject = null;
    modal.style.display = "none";
    overlay.style.display = "none";
}

closeBtn.addEventListener("click", closeCamera);