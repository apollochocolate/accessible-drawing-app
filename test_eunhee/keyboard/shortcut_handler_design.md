# shortcut_handler 설계 문서

## 개요

`keyboard-mapping.py`를 훼손하지 않고 import하여,  
레이저 포인터로 **수식키(Shift/Ctrl/Alt/Win) + 일반키 조합**을 감지하고 단축어를 수행한다.

---

## 확정된 동작 규칙

| 항목 | 규칙 |
|------|------|
| 수식키 유지 조건 | 레이저가 수식키 위에 **계속** 올려져 있어야 유지 |
| 수식키 해제 조건 | 레이저가 수식키 영역을 **벗어나는 순간** 즉시 해제 |
| 단축키 수행 후 | 즉시 **IDLE**로 복귀 |
| 타임아웃 | 수식키를 유지한 채 일정 시간(기본 3초) 안에 일반키 미입력 시 IDLE 복귀 |

---

## 상태 정의

```
IDLE       수식키 감지 없음. 대기 중.
HOLDING    수식키가 현재 레이저로 눌려 있는 상태. 일반키 입력 대기.
```

---

## 상태 전이 다이어그램

```
                     ┌─────────────────────────────────────────────────────┐
                     │                                                     │
                     ▼                                                     │
              ┌────────────┐                                               │
              │    IDLE    │                                               │
              └─────┬──────┘                                               │
                    │                                                      │
         레이저가 수식키(Shift/Ctrl/Alt/Win) 위에 올라옴                   │
                    │                                                      │
                    ▼                                                      │
              ┌────────────┐   레이저가 다른 수식키 위로 이동    ┌──────┐  │
              │  HOLDING   │ ─────────────────────────────────▶ │ 추가 │  │
              │            │ ◀───────────────────────────────── │ 유지 │  │
              └──────┬─────┘                                    └──────┘  │
                     │                                                     │
          ┌──────────┼─────────────────────┐                              │
          │          │                     │                              │
          ▼          ▼                     ▼                              │
   레이저가      타임아웃             일반키 감지                           │
   수식키 벗어남  (3초)              (예: Z)                               │
          │          │                     │                              │
          ▼          ▼                     ▼                              │
       IDLE 복귀  IDLE 복귀        단축어 수행 → IDLE 복귀 ───────────────┘
```

---

## 프레임별 처리 흐름 (feed 함수)

```
매 프레임마다 detected_key 입력
        │
        ├─ None (레이저 없음)
        │       └─ HOLDING 중이면 → 수식키 전부 해제 → IDLE
        │
        ├─ 수식키 (Shift / Ctrl / Alt / Win)
        │       ├─ IDLE 상태    → held_modifiers에 추가, HOLDING으로 전환
        │       └─ HOLDING 상태 → held_modifiers에 추가 (복수 수식키 허용)
        │
        └─ 일반키 (A~Z, 숫자, F키 등)
                ├─ IDLE 상태    → 단순 입력 (단축키 없음, 무시)
                └─ HOLDING 상태 → 단축어 테이블 조회 → 수행 → IDLE 복귀
```

---

## 수식키 유지/해제 판단 로직

레이저 입력은 "현재 프레임에 가리키고 있는 키" 하나만 존재한다.  
따라서 **수식키 유지 = 매 프레임마다 같은 수식키가 계속 감지되는 것**.

```
이전 프레임: LShift 감지  →  held = {"Shift"},  state = HOLDING
현재 프레임: LShift 감지  →  held = {"Shift"} 유지 (타임아웃 리셋)
현재 프레임: Z 감지       →  Shift+Z 수행 → IDLE
현재 프레임: None         →  held 전부 해제 → IDLE
현재 프레임: 다른 키      →  held 전부 해제 → IDLE (수식키가 벗어났으므로)
```

> ⚠️ 레이저는 한 번에 하나의 키만 가리킬 수 있으므로,  
> **수식키를 유지하면서 일반키를 동시에 가리키는 것은 불가능**하다.  
> 따라서 "수식키 영역을 벗어나는 순간" = "감지된 키가 수식키가 아닌 순간"으로 처리한다.

---

## 복수 수식키 시나리오 (예: Ctrl + Shift + Z)

```
프레임 1: LCtrl  → held = {"Ctrl"},          state = HOLDING
프레임 2: LCtrl  → held = {"Ctrl"} 유지
프레임 3: LShift → held = {"Ctrl", "Shift"}, state = HOLDING  ← 수식키 이동
프레임 4: LShift → held = {"Ctrl", "Shift"} 유지
프레임 5: Z      → Ctrl+Shift+Z 수행 → IDLE
```

> 수식키를 하나씩 순서대로 레이저로 가리킨 뒤 일반키로 이동하는 방식.

---

## 타임아웃 동작

- 수식키를 유지한 채 `HOLD_TIMEOUT`(기본 3.0초) 안에 일반키가 오지 않으면 IDLE 복귀.
- 수식키가 연속으로 감지되는 동안은 타임아웃 카운트를 **리셋**한다.
- 즉, 타임아웃은 "마지막으로 수식키를 감지한 시점"부터 측정.

```
t=0.0s  LShift 감지  → HOLDING, timer 시작
t=0.5s  LShift 감지  → timer 리셋
t=1.0s  LShift 감지  → timer 리셋
t=4.0s  LShift 감지  → (마지막 감지로부터 3초 경과 없음, 리셋 중이므로 유지)
t=4.0s  None         → held 해제 → IDLE  ← 레이저가 사라짐
```

```
t=0.0s  LShift 감지  → HOLDING, timer 시작
t=0.5s  None         → timer 카운트 시작 (수식키 벗어남 = 해제)
t=0.5s  IDLE 복귀    ← 벗어나는 즉시 해제
```

---

## 단축키 테이블 구조

```python
SHORTCUT_TABLE = {
    # (frozenset(수식키명), 일반키) → (설명, 실행함수)
    (frozenset({"Shift"}), "Z"): ("Shift+Z 테스트", action_shift_z),
    (frozenset({"Ctrl"}),  "C"): ("복사",            action_copy),
    ...
}
```

---

## 화면 표시

| 상태 | 좌하단 표시 | 색상 |
|------|------------|------|
| IDLE, 레이저 없음 | `Key: ---` | 초록 |
| IDLE, 일반키 감지 | `Key: Z` | 초록 |
| HOLDING | `HOLD: Shift` | 노랑 |
| HOLDING 복수 | `HOLD: Ctrl+Shift` | 노랑 |
| 단축키 수행됨 | `⚡ Shift+Z` (상단 1.5초) | 흰색 |
| 타임아웃 | `TIMEOUT` (잠깐 표시) | 빨강 |

---

## 파일 구성

```
📁 프로젝트 폴더
 ├── keyboard-mapping.py     ← 원본 (절대 수정 안 함)
 └── shortcut_handler.py     ← 이 설계대로 구현할 파일
```

---

## 구현 체크리스트

- [ ] `_load_kb_symbols()` : keyboard-mapping.py cv2 stub으로 안전하게 로드
- [ ] `MODIFIER_KEYS` : Shift/Ctrl/Alt/Win 수식키 집합 정의
- [ ] `SHORTCUT_TABLE` : 단축키 → 액션 매핑 테이블
- [ ] `ShortcutDetector.feed(detected_key)` : 매 프레임 호출, 상태 전이 처리
  - [ ] None 입력 시 수식키 즉시 해제 → IDLE
  - [ ] 수식키 입력 시 held에 추가, HOLDING 전환, 타임아웃 리셋
  - [ ] 일반키 입력 시 테이블 조회 → 수행 → IDLE
  - [ ] 타임아웃 처리 (마지막 수식키 감지 기준)
- [ ] `ShortcutDetector.status_text()` : 오버레이 표시용 텍스트
- [ ] 메인 루프 : `__name__ == "__main__"` 블록으로 분리
