# TRON USDT Gateway - Admin Dashboard

3단계 RBAC 권한 시스템이 적용된 **웹 관리자 대시보드**입니다.

## 🏗️ 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                    3단계 권한 시스템 (RBAC)                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Tier 1: Super Admin (최상위 관리자)                      │ │
│  │ - 모든 데이터 접근 권한                                   │ │
│  │ - 파트너(업체) 생성 및 관리                               │ │
│  │ - 시스템 전역 설정 변경                                   │ │
│  │ - 모든 입출금 내역 모니터링                               │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Tier 2: Partner Admin (업체 대표)                        │ │
│  │ - 본인 산하의 사용자 지갑 생성 및 관리                    │ │
│  │ - 본인 업체의 입출금 내역만 조회                          │ │
│  │ - 출금 신청 및 승인 권한                                  │ │
│  │ - Partner Staff 생성 가능                                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Tier 3: Partner Staff (업체 직원)                        │ │
│  │ - 본인 업체의 데이터 '조회'만 가능 (ReadOnly)             │ │
│  │ - 입금 내역 모니터링 용도                                 │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 🛠️ 기술 스택

### Backend
- **FastAPI** - 고성능 비동기 API 프레임워크
- **SQLAlchemy 2.0** - 비동기 ORM
- **JWT** - 액세스/리프레시 토큰 인증
- **bcrypt** - 비밀번호 해싱
- **PyOTP** - 2FA 지원

### Frontend
- **Next.js 14** - React 서버 컴포넌트
- **Tailwind CSS** - 유틸리티 기반 CSS
- **Framer Motion** - 애니메이션
- **Recharts** - 차트 라이브러리
- **Zustand** - 상태 관리

## 📁 프로젝트 구조

```
tron-gateway-admin/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin_server.py      # 메인 API 서버
│   │   │   ├── dashboard_router.py  # 대시보드 API
│   │   │   ├── partner_router.py    # 파트너 관리 API
│   │   │   └── system_router.py     # 시스템 설정 API
│   │   ├── auth/
│   │   │   ├── auth_service.py      # 인증 서비스
│   │   │   └── auth_router.py       # 인증 API
│   │   └── db/
│   │       └── admin_models.py      # 관리자 DB 모델
│   ├── scripts/
│   │   └── create_super_admin.py    # 초기 관리자 생성
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── login/page.tsx       # 로그인 페이지
    │   │   ├── dashboard/page.tsx   # 대시보드
    │   │   ├── wallets/page.tsx     # 지갑 관리
    │   │   └── partners/page.tsx    # 파트너 관리
    │   ├── components/
    │   │   ├── layout/              # 레이아웃 컴포넌트
    │   │   ├── ui/                  # UI 컴포넌트
    │   │   └── dashboard/           # 대시보드 컴포넌트
    │   ├── lib/
    │   │   ├── api.ts               # API 클라이언트
    │   │   └── utils.ts             # 유틸리티 함수
    │   ├── stores/
    │   │   └── authStore.ts         # 인증 상태 관리
    │   └── types/
    │       └── index.ts             # TypeScript 타입
    └── package.json
```

## 🚀 설치 및 실행

### 1. Backend 설정

```bash
cd backend

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 수정

# 초기 Super Admin 생성
python scripts/create_super_admin.py

# 서버 실행
uvicorn app.api.admin_server:app --reload --port 8000
```

### 2. Frontend 설정

```bash
cd frontend

# 의존성 설치
npm install

# 환경변수 설정
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# 개발 서버 실행
npm run dev
```

### 3. 접속

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs

## 🔑 권한 매트릭스

| 기능 | Super Admin | Partner Admin | Partner Staff |
|------|:-----------:|:-------------:|:-------------:|
| 시스템 설정 | ✅ | ❌ | ❌ |
| 파트너 관리 | ✅ | ❌ | ❌ |
| 모든 데이터 조회 | ✅ | ❌ | ❌ |
| 지갑 생성 | ✅ | ✅ | ❌ |
| 지갑 조회 | ✅ | ✅ | ✅ |
| 입금 조회 | ✅ | ✅ | ✅ |
| 출금 조회 | ✅ | ✅ | ✅ |
| 출금 요청 | ✅ | ✅ | ❌ |
| 출금 승인 | ✅ | ✅ | ❌ |
| 스위핑 실행 | ✅ | ❌ | ❌ |
| 관리자 생성 | ✅ | ✅ (Staff만) | ❌ |

## 📡 API 엔드포인트

### 인증
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/auth/login` | 로그인 |
| POST | `/api/auth/refresh` | 토큰 갱신 |
| POST | `/api/auth/logout` | 로그아웃 |
| GET | `/api/auth/me` | 현재 사용자 정보 |

### 대시보드
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/dashboard/stats` | 통계 |
| GET | `/api/dashboard/chart/transactions` | 차트 데이터 |
| GET | `/api/dashboard/transactions/recent` | 최근 트랜잭션 |
| GET | `/api/dashboard/deposits` | 입금 목록 |
| GET | `/api/dashboard/withdrawals` | 출금 목록 |
| GET | `/api/dashboard/wallets` | 지갑 목록 |

### 파트너 관리 (Super Admin)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/partners` | 파트너 목록 |
| POST | `/api/partners` | 파트너 생성 |
| GET | `/api/partners/{id}` | 파트너 상세 |
| PATCH | `/api/partners/{id}` | 파트너 수정 |
| DELETE | `/api/partners/{id}` | 파트너 삭제 |

## 🎨 디자인 특징

- **다크 모드** 기반 프리미엄 UI
- **Glassmorphism** 효과 적용
- **실시간** 트랜잭션 모니터링
- **모바일 반응형** 지원
- **부드러운 애니메이션** 효과

## 🔒 보안 기능

- JWT 액세스/리프레시 토큰
- 비밀번호 bcrypt 해싱
- 2FA (TOTP) 지원
- 로그인 시도 제한 및 계정 잠금
- 감사 로그 기록
- 세션 관리

## 📝 라이선스

MIT License
