import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 백엔드 연결은 .env 의 VITE_API_BASE_URL 에 서버 주소(예: http://localhost:8000)를 넣는 방식이 기본이다.
    // 비워두면 mock 모드가 된다(src/api/client.ts 의 USE_MOCK). 프록시를 쓰려면 아래를 해제하고
    // VITE_API_BASE_URL 에 Vite 주소(http://localhost:5173)를 넣어 /api 요청이 이쪽으로 오게 한다.
    // proxy: { '/api': 'http://localhost:8000' },
  },
})
