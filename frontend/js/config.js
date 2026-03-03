/**
 * 환경 설정 파일
 * API 엔드포인트 및 외부 서비스 URL 관리
 * 
 * 배포 환경에 따라 이 파일만 수정하면 됩니다.
 */

const CONFIG = {
    // API 서버 기본 URL
    API_BASE_URL: "",
    
    // 외부 CDN 및 라이브러리 URL
    SOCKET_IO_CDN: "https://cdn.socket.io/4.0.0/socket.io.min.js",
    MEDIAPIPE_HOLISTIC: "https://cdn.jsdelivr.net/npm/@mediapipe/holistic/holistic.js",
    MEDIAPIPE_CAMERA: "https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js",
    MEDIAPIPE_DRAWING: "https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js",
    MEDIAPIPE_CDN_BASE: "https://cdn.jsdelivr.net/npm/@mediapipe/holistic",
    
    // Google Fonts
    GOOGLE_FONTS: "https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap"
};

// 배포 환경 감지 (선택사항)
// 현재 도메인에 따라 자동으로 API URL 변경 가능
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    // 프로덕션 환경
    // CONFIG.API_BASE_URL = "https://your-production-domain.com";
}

// 읽기 전용으로 설정
Object.freeze(CONFIG);
