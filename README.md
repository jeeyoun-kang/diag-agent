# 🩺 AI 시스템 진단 에이전트 (AIOps 미니)

Linux(메인)/Windows(서브) 시스템이 느려지면 AI 에이전트가 도구를 스스로 호출해 원인을 자율 진단하고, 텔레그램 승인 후 조치하며, 진단 정확도를 정량 추적하는 크로스플랫폼 AIOps 툴.

## 컨셉

- 수집 계층을 **어댑터로 추상화**: Linux를 메인 대상으로, Windows는 서브로 확장성 증명
- AI 에이전트는 OS를 몰라도 동일 인터페이스(`get_disk_usage()` 등)로 호출
- 핵심 차별점: "API 한 번 호출"이 아니라 **AI가 도구를 골라 멀티스텝 추론 + 진단 정확도 정량화**

```
[진단 에이전트 - 공통 로직]
        ↓ (도구 인터페이스 동일)
[플랫폼 어댑터]
  └─ PsutilCollector  ← 공통: CPU·메모리·프로세스·디스크·디스크 I/O·네트워크 (psutil)
       ├─ LinuxCollector   ← 메인: systemctl·journalctl
       └─ WindowsCollector ← 서브: Windows 서비스 (이벤트로그는 미지원)
```

### 에이전트 도구

| 도구 | 내용 |
|---|---|
| `get_cpu_percent` | 시스템 전체 CPU 사용률 |
| `get_memory_detail` | 메모리 총량/사용량/사용률 |
| `get_top_processes` | CPU 또는 메모리(`sort_by`) 기준 상위 프로세스 |
| `get_disk_usage` | 디스크 용량 |
| `get_disk_io` | 1초간 읽기/쓰기 MB/s, IOPS (Linux는 busy %) |
| `get_network_summary` | 연결 상태 분포, 연결이 몰린 IP·포트·프로세스, 인터페이스 오류 |
| `check_service_status` | 서비스 상태 (Linux는 재시작 횟수 포함) |
| `read_recent_logs` | 최근 시스템 로그 (Linux만, Windows는 미지원 에러 반환) |

### 진단 출력

에이전트는 도구를 자유롭게 호출한 뒤, 최종 답변을 structured outputs(`output_config.format`)로 고정된 JSON으로 낸다.

```json
{
  "summary": "...", "root_cause": "...", "evidence": ["..."],
  "confidence": "low | medium | high",
  "action": { "description": "...", "risk_level": "low | medium | high" }
}
```

조치는 **제안만** 한다 (`action_proposed`에 저장). 실행 경로는 없다.

## 아키텍처

```
[Linux 서버(메인) / Windows(서브) 백그라운드 프로세스]
   ① 어댑터로 주기적 지표 수집 (CPU/메모리/디스크/프로세스 top N)
        ↓
   ② 가벼운 트리거 (임계값 초과 or 급등)
        ↓
   ③ AI 에이전트에 "진단해" 위임
        → AI가 도구를 스스로 골라 호출 (멀티스텝, OS 무관 동일 인터페이스)
        → 가설 → 검증 → 재가설 루프
        ↓
   ④ 텔레그램 알림 (진단 + 조치제안 + 승인버튼)
        ↓
   ⑤ 승인 시 조치 실행 (위험도별 게이팅)
        ↓
   ⑥ 사후 검증 (개선됐나?) → 진단 정확도 기록  ← 정량화
```

## 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| OS | Linux(메인) + Windows(서브) | Linux=EC2/VM/Docker, Windows=내 PC |
| 수집 | Python + psutil + 어댑터 | 공통 인터페이스, OS별 구현 분기 |
| LLM | Claude API | Function Calling(Tool Use) |
| 저장 | SQLite | 인시던트 이력 + 정확도 기록 |
| 알림/승인 | 텔레그램 봇 | inline keyboard 승인 버튼 |
| 대시보드 | (Phase 4) Streamlit | 정량 지표 시각화 |

## 프로젝트 구조

```
diag-agent/
├── .venv/                      Python 3.10 가상환경
├── .env.example                API 키·임계값 템플릿
├── requirements.txt
├── data/                        SQLite DB 저장 위치
├── src/
│   ├── config.py                환경변수·임계값·DB경로·OS 판별
│   ├── main.py                  모니터링 루프 (임계값 초과 → 인시던트 → 진단 → 저장, 정상 복귀 시 resolve)
│   ├── collectors/
│   │   ├── base.py              SystemCollector 인터페이스 + PsutilCollector 공통 구현
│   │   ├── linux_collector.py   systemctl/journalctl
│   │   └── windows_collector.py Windows 서비스
│   ├── storage/
│   │   ├── schema.sql           incidents 테이블
│   │   └── db.py
│   ├── agent/
│   │   ├── tools.py             Claude tool 정의 + dispatcher
│   │   └── agent_loop.py        멀티스텝 진단 루프 (tool_use 반복, 구조화 출력, 토큰 사용량 집계)
│   └── bot/
│       └── telegram_bot.py      텔레그램 봇 (핑퐁/승인 게이팅)
└── tests/
    ├── test_collectors.py       실제 수집값 + systemctl 출력 파싱
    ├── test_tools.py            도구 정의 ↔ dispatcher 일치
    ├── test_agent.py            가짜 Claude 클라이언트로 루프 검증
    └── test_monitor.py          임시 DB로 인시던트 수명주기 검증
```

## 시작하기

```bash
cp .env.example .env
# .env에 ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN 채우기

./.venv/Scripts/python.exe -m src.main            # 모니터링 루프
./.venv/Scripts/python.exe -m src.bot.telegram_bot # 텔레그램 봇
./.venv/Scripts/python.exe -m pytest              # 테스트
```

## 정량 지표 (AI 활용도 증명 KPI)

| 지표 | 의미 |
|---|---|
| 진단 정확도 % | 조치 후 실제 개선된 비율 (핵심 KPI) |
| 평균 진단 스텝 수 | 에이전트가 몇 번 도구 호출했나 |
| 첫 가설 적중률 | 첫 진단이 맞은 비율 |
| 복구시간 단축 | 수동 대비 감소폭 (분) |
| 자동 처리 비율 | 승인 없이 처리된 저위험 조치 % |
| 재발 패턴 탐지율 | 과거 이력 참조로 잡은 재발 건 |

## 로드맵

- [x] **Phase 1 — 모니터링 뼈대**: psutil 수집, 임계값 감지, SQLite 인시던트 스키마
- [x] **Phase 2 — 진단 에이전트** ★핵심: Function Calling 루프로 AI 자율 진단
  - 실측 1회 (Windows, 메모리 91%): 도구 4회 호출, 29.5초, 약 $0.035 (claude-sonnet-5)
  - 남은 것: Linux 실환경 검증, `main.py` 루프 전체 실측, 앱별 메모리 합계·스왑 정보 도구, 임계값 기준 재설계
- [ ] **Phase 3 — 텔레그램 + 정확도 추적** ★정량화: 승인 게이팅, 사후 검증 루프
- [ ] **Phase 3.5 — 평가 계층** ★★진짜 차별점: 3계층 평가(최종답변·궤적·컴포넌트), 트레이싱, 골든 데이터셋
- [ ] **Phase 4 — 고도화 + 대시보드**: RAG-lite 재발 탐지, LLM-as-a-Judge, Streamlit 대시보드

## 설계 원칙

- **측정 먼저, 기능 나중** — 정확도 추적이 축, 기능은 그 숫자를 올리는 수단
- **조치는 반드시 승인 게이트** — 고위험 조치는 사람 확인 필수
- **검증 AI(LLM-as-a-Judge)는 3단계 이후** — 진단·측정 판이 깔린 뒤 도입
