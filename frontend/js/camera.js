// ===== DOM =====
const openBtn = document.getElementById("signCameraBtn");
const closeBtn = document.getElementById("closeCameraBtn");
const modal = document.getElementById("cameraModal");
const overlay = document.getElementById("cameraOverlay");
const videoFileInput = document.getElementById("videoFileInput");
const selectFileBtn = document.getElementById("selectFileBtn");
const video = document.getElementById("videoInput");
const videoLoading = document.getElementById("videoLoading");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const statusText = document.getElementById("statusText");
const cameraControls = document.getElementById("cameraControls");
const translationResult = document.getElementById("translationResult");
const translationInput = document.getElementById("translationInput");

// ===== 상태 =====
let stream = null;
let holistic = null;
let isCapturing = false;
let frameCount = 0;
let currentSendPromise = null;
let isFileMode = false;
let fileObjectURL = null;

// ===== 인덱스 =====
const POSE_LANDMARKS_IDX = [11, 12, 13, 14, 15, 16];
const HAND_LANDMARKS_IDX = Array.from({ length: 21 }, (_, i) => i);

// ===== MediaPipe 초기화 =====
function initHolistic() {
    console.log("📷 [MediaPipe] Initialize");

    holistic = new Holistic({
        locateFile: file =>
            `https://cdn.jsdelivr.net/npm/@mediapipe/holistic/${file}`
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

    // Socket.IO 전송(랜드마크 전송)
    socket.emit("send_landmarks", {
        room: currentRoomName,
        room_id: currentRoomId,
        username: myId,
        message: landmarks,
        status_stop: false
    });

    console.log(`📤 [Socket] 전송: ${landmarks}`);
}

// ===== 워밍업 =====
async function warmupHolistic() {
  // video 프레임 준비 여부 확인
    if (!holistic || !video.videoWidth) return;

  // 초기화 비용 미리 소모(결과 저장 X)
  for (let i = 0; i < 2; i++) {
    await holistic.send({ image: video });
  }
  console.log("🔥 [MediaPipe] Warmup Complete");
}

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

    isFileMode = false; // 웹캠 모드로 전환
    video.src = "";     // 파일 경로 제거
    video.style.transform = "scaleX(-1)"; // 웹캠은 다시 거울 모드로

    if (fileObjectURL) {
        URL.revokeObjectURL(fileObjectURL);
        fileObjectURL = null;
    }

    console.log("📷 [Camera] Open Camera")
    statusText.textContent = "카메라 준비 중...";

    modal.style.display = "block";
    overlay.style.display = "block";

    startBtn.disabled = true;
    stopBtn.disabled = true;

    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 480, height: 360 },
            audio: false
        });

        video.srcObject = stream;

        video.onloadedmetadata = async () => {
            await video.play();

            if (!holistic) initHolistic();

            // 🔥 워밍업 실행
            try {
                await warmupHolistic();
            } catch (e) {
                console.warn("🔥 [MediaPipe] Warmup Failed:", e);
            }

            statusText.textContent = "시작 버튼을 눌러주세요.";
            statusText.classList.add("active");
            startBtn.disabled = false;
        };
    }
    catch (e) {
        alert("카메라 접근 불가");
        closeCamera();
    }
});

// ===== 시작 =====
startBtn.addEventListener("click", () => {
    console.log("📷 [Camera] Start Send Landmarks")

    isCapturing = true;
    frameCount = 0;

    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusText.classList.remove("active");

    // 파일 모드일 경우 영상 처음부터 재생
    if (isFileMode) {
        video.currentTime = 0;
        video.play();

        // 영상이 끝나면 자동으로 중지 처리
        video.onended = () => {
            console.log("📁 [File] 영상 재생 완료 → 자동 중지");
            stopBtn.click();
        };
    }

    async function loop() {
        if (!isCapturing) return;

        // 파일 모드에서 영상이 끝난 경우 루프 종료
        if (isFileMode && video.ended) return;

        // 영상이 일시정지 상태면 다음 프레임까지 대기
        if (isFileMode && video.paused) {
            requestAnimationFrame(loop);
            return;
        }

        currentSendPromise = holistic.send({ image: video });
        await currentSendPromise;
        currentSendPromise = null;

        if (!isCapturing) return;

        requestAnimationFrame(loop);
    }
    loop();
});


// ===== 중지 =====
stopBtn.addEventListener("click", async () => {
    console.log("📷 [Camera] Stop Send Landmarks")

    isCapturing = false;
    if (isFileMode) video.pause(); // 파일 재생 중지

    stopBtn.disabled = true;
    statusText.textContent = "";

    if (currentSendPromise) {
        await currentSendPromise;
    }
    
    showLoading();

    // Socket.IO 전송(랜드마크 전송 중단)
    socket.emit("send_landmarks", {
        room: currentRoomName,
        room_id: currentRoomId,
        username: myId,
        message: null,
        status_stop: true
    });
});

// ===== 닫기 =====
function closeCamera() {
    console.log("📷 [Camera] Close Camera")
    
    isCapturing = false;
    hideLoading();

    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        stream = null;
    }

    video.onended = null;

    video.srcObject = null;
    video.style.display = "block"; // 다음 오픈을 위해 복구
    cameraControls.classList.remove("hidden"); // 제어 버튼 복구
    translationResult.classList.add("hidden"); // 결과창 초기화

    modal.style.display = "none";
    overlay.style.display = "none";
}

closeBtn.addEventListener("click", closeCamera);

// ===== 번역 결과 수신 및 자동 처리 =====
socket.on("translation_result", (data) => {
    console.log("📤 [Socket] 번역 결과 수신:", data.message);
    onTranslationComplete(data);
});

// 번역 완료 처리: '번역 완료' 표시 → 카메라 종료 → 입력창에 텍스트 입력
function onTranslationComplete(data) {
    
    // 1. 로딩바 숨기기
    hideLoading();

    // 2. 카메라 제어 영역과 비디오 숨기기
    if (cameraControls) cameraControls.classList.add("hidden");
    if (video) video.style.display = "none"; // 비디오를 아예 안보이게 처리
    statusText.textContent = "";

    // 3. 번역 결과 입력창 표시
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

// 1. 📁 버튼 클릭 시 파일 선택창 열기
selectFileBtn.addEventListener("click", () => {
    videoFileInput.click();
});

// ===== 📁 파일 첨부 처리 =====
videoFileInput.addEventListener("change", async () => {
    // 파일 모드일 때는 정방향
    video.style.transform = "scaleX(1)";
    
    const file = videoFileInput.files[0];
    if (!file) return;

    console.log("📁 [File] 영상 파일 선택:", file.name);

    isFileMode = true;

    // 기존 웹캠 스트림 종료
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
        stream = null;
    }

    // 기존 Object URL 해제
    if (fileObjectURL) {
        URL.revokeObjectURL(fileObjectURL);
        fileObjectURL = null;
    }

    // 파일을 video 태그에 로드
    fileObjectURL = URL.createObjectURL(file);
    video.srcObject = null;
    video.src = fileObjectURL;
    video.loop = false;
    video.muted = true;

    video.onloadedmetadata = async () => {
        await video.play();
        video.pause();  // 자동 재생 방지, 시작 버튼으로 제어

        if (!holistic) initHolistic();

        try {
            await warmupHolistic();
        } catch (e) {
            console.warn("🔥 [MediaPipe] Warmup Failed:", e);
        }

        statusText.textContent = `📁 ${file.name} | 시작 버튼을 눌러주세요.`;
        statusText.classList.add("active");
        startBtn.disabled = false;
    };

    // input 초기화 (같은 파일 재선택 가능하도록)
    videoFileInput.value = "";
});