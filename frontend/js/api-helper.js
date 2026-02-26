/**
 * API 호출 헬퍼 함수
 * JWT 인증 토큰을 자동으로 포함합니다.
 */

const API_BASE_URL = CONFIG.API_BASE_URL;

// 토큰 갱신 중 플래그 (중복 갱신 방지)
let isRefreshing = false;
let refreshPromise = null;

/**
 * 리프레시 토큰으로 새 액세스 토큰 발급
 */
async function refreshAccessToken() {
    const refreshToken = localStorage.getItem("refreshToken");
    
    if (!refreshToken) {
        throw new Error("리프레시 토큰이 없습니다.");
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        
        if (!response.ok) {
            throw new Error("토큰 갱신 실패");
        }
        
        const data = await response.json();
        
        // 새 액세스 토큰 저장
        localStorage.setItem("accessToken", data.access_token);
        localStorage.setItem("userId", data.user_id);
        localStorage.setItem("userName", data.user_name);
        
        console.log("✅ [Auth] 토큰이 자동으로 갱신되었습니다.");
        return data.access_token;
        
    } catch (error) {
        console.error("❌ [Auth] 토큰 갱신 실패:", error);
        // 리프레시 토큰도 만료된 경우 로그아웃
        localStorage.removeItem("accessToken");
        localStorage.removeItem("refreshToken");
        localStorage.removeItem("userId");
        localStorage.removeItem("userName");
        throw error;
    }
}

/**
 * 인증 헤더를 포함한 fetch 요청 (자동 토큰 갱신 지원)
 */
async function authFetch(url, options = {}) {
    const token = localStorage.getItem("accessToken");
    
    if (!token) {
        // 토큰이 없으면 로그인 페이지로 리다이렉트
        window.location.href = "login.html";
        throw new Error("인증 토큰이 없습니다.");
    }
    
    // 기본 헤더에 Authorization 추가
    const headers = {
        ...options.headers,
        "Authorization": `Bearer ${token}`
    };
    
    // Content-Type이 없고 body가 있으면 자동으로 JSON 타입 추가
    if (!headers["Content-Type"] && options.body && typeof options.body === "string") {
        headers["Content-Type"] = "application/json";
    }
    
    const response = await fetch(url, {
        ...options,
        headers
    });
    
    // 401 Unauthorized 에러 처리 (토큰 만료)
    if (response.status === 401) {
        try {
            // 토큰 갱신 중복 방지
            if (!isRefreshing) {
                isRefreshing = true;
                refreshPromise = refreshAccessToken().finally(() => {
                    isRefreshing = false;
                    refreshPromise = null;
                });
            }
            
            // 토큰 갱신 완료 대기
            await refreshPromise;
            
            // 새 토큰으로 원래 요청 재시도
            const newToken = localStorage.getItem("accessToken");
            headers["Authorization"] = `Bearer ${newToken}`;
            
            return await fetch(url, {
                ...options,
                headers
            });
            
        } catch (error) {
            // 토큰 갱신 실패 시 로그인 페이지로 리다이렉트
            alert("로그인이 만료되었습니다. 다시 로그인해주세요.");
            window.location.href = "login.html";
            throw new Error("인증 실패");
        }
    }
    
    return response;
}

/**
 * SSE 스트림 연결 (JWT 인증 포함)
 * EventSource는 커스텀 헤더를 지원하지 않으므로 fetch로 직접 구현
 */
async function createSSEConnection(url, handlers = {}) {
    const token = localStorage.getItem("accessToken");
    
    if (!token) {
        window.location.href = "login.html";
        throw new Error("인증 토큰이 없습니다.");
    }
    
    const response = await fetch(url, {
        headers: {
            "Authorization": `Bearer ${token}`,
            "Accept": "text/event-stream"
        }
    });
    
    if (!response.ok) {
        if (response.status === 401) {
            alert("로그인이 만료되었습니다. 다시 로그인해주세요.");
            window.location.href = "login.html";
        }
        throw new Error(`SSE 연결 실패: ${response.status}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    
    // SSE 이벤트 파싱 및 처리
    const processSSE = async () => {
        console.log("🔄 [SSE] 스트림 읽기 시작");
        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    console.log("🔌 [SSE] 스트림이 서버에서 종료되었습니다 (done=true)");
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || ""; // 마지막 불완전한 줄은 buffer에 보관
                
                let event = null;
                let data = "";
                let eventId = null;
                
                for (const line of lines) {
                    if (line.startsWith("event:")) {
                        event = line.substring(6).trim();
                    } else if (line.startsWith("data:")) {
                        data = line.substring(5).trim();
                    } else if (line.startsWith("id:")) {
                        eventId = line.substring(3).trim();
                    } else if (line === "" || line === "\r") {
                        // 빈 줄은 이벤트 끝을 의미 (\r도 처리)
                        if (event && data) {
                            const handler = handlers[event] || handlers.message;
                            if (handler) {
                                try {
                                    // JSON 파싱 시도
                                    const parsedData = JSON.parse(data);
                                    handler({ event, data: parsedData, id: eventId });
                                } catch {
                                    // JSON이 아니면 문자열 그대로 전달
                                    handler({ event, data, id: eventId });
                                }
                            }
                        }
                        event = null;
                        data = "";
                        eventId = null;
                    }
                }
            }
        } catch (error) {
            console.error("❌ [SSE] 스트림 읽기 오류:", error);
            if (handlers.error) {
                handlers.error(error);
            }
        } finally {
            console.log("🔌 [SSE] processSSE finally 블록 실행");
            if (handlers.close) {
                handlers.close();
            }
        }
    };
    
    processSSE();
    
    // 연결 종료 함수 반환
    return {
        close: () => {
            reader.cancel();
            if (handlers.close) {
                handlers.close();
            }
        }
    };
}
