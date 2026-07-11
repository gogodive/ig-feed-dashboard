# 인스타 자사계정 데일리 피드 대시보드 — 설계

- 작성일: 2026-07-11
- 상태: 사용자 승인 완료

## 목적

자사 인스타그램 계정 4개의 피드를 매일 아침 7시(KST)에 자동 수집해,
실제 인스타 피드 모양의 HTML 대시보드로 보여준다. 직원들이 매일 출근해서
어느 게시물의 성과가 좋고 나쁜지 한눈에 파악하는 것이 목표.

## 대상 계정

| 브랜드 | 인스타 계정 | 노션 페이지 |
|---|---|---|
| 고고다이브 | @gogodive | https://app.notion.com/p/39a39eba97ed801ebf1fd3385cdcfedf |
| 인투더블루 | @intotheblue_store | https://app.notion.com/p/39a39eba97ed803f892dd3897ed11d8b |
| 라세린 | @laserin_swim | https://app.notion.com/p/39a39eba97ed805789b3d09c25aad7c9 |
| 시크릿스 | @secrets__fit | https://app.notion.com/p/39a39eba97ed80c7b914c38a8d9651b9 |

노션 상위 페이지(자사 인스타그램 매일 분석): https://app.notion.com/p/39a39eba97ed80549640dfb33fad1bda

## 확정된 결정 사항

1. **인증**: Instagram Graph API + 페이스북 페이지 연결 방식.
   4개 계정(이미 비즈니스 계정)을 각각 FB 페이지에 연결하고 하나의 비즈니스 관리자에 묶어
   **시스템 사용자 토큰 1개(만료 없음)** 로 전 계정 조회.
2. **표시 범위**: 계정당 누적 최대 **120개** 게시물을 피드에 표시.
3. **성과 갱신**: **게시 후 30일 이내** 게시물만 매일 인사이트 갱신.
   30일 경과 시 마지막 수치로 **동결**(이후 API 호출 안 함), 동결값은 저장소 내 JSON에 보관.
4. **출력**: HTML 대시보드 1페이지를 **GitHub Pages** 로 호스팅(공개 저장소, noindex).
   노션에는 대시보드 링크만 넣는다(일회성).
5. **실행**: **GitHub Actions cron** — 매일 22:00 UTC(= 07:00 KST) 실행 → 수집 → HTML 생성 → 커밋 → Pages 자동 배포. 로컬 맥 의존 없음.
6. **덮어쓰기**: 대시보드는 항상 최신 상태만 표시(날짜별 스냅샷 보관 없음).

## 아키텍처

```
GitHub 저장소 (public) = 시스템 전체
├── .github/workflows/daily.yml   # cron 22:00 UTC + 수동 실행(workflow_dispatch)
├── src/
│   ├── instagram.py              # Graph API 클라이언트 (지표 거부 시 해당 지표 제외 재시도)
│   ├── collect.py                # 수집 + 30일 동결 병합 로직
│   └── render.py                 # HTML 생성
├── data/<account>.json           # 게시물별 성과 기록·동결값 (Actions가 커밋)
├── site/index.html               # 생성된 대시보드 — Actions가 Pages로 배포
└── requirements.txt
```

- 토큰은 GitHub Secrets `META_ACCESS_TOKEN` 에만 저장. 코드/저장소에 노출 금지.

## 데이터 흐름 (매일 1회)

1. 계정별: 팔로워 수 + 최근 미디어 목록(최대 120개, 페이지네이션) 조회
   - fields: id, caption, media_type, media_product_type, permalink, timestamp, media_url, thumbnail_url
2. 게시 후 30일 이내 게시물만 `/insights` 호출 (reach, views, likes, comments, saved, shares, total_interactions)
3. `data/<account>.json` 과 병합: 30일 경과 게시물은 저장된 동결값 사용
4. HTML 생성 → 커밋 → Pages 배포

썸네일은 매일 새로 받은 인스타 CDN URL을 그대로 사용(매일 재생성이므로 만료 문제 없음).
실행이 실패한 날은 다음 성공 시까지 일부 썸네일이 깨질 수 있음 — 감수하기로 결정.

## 대시보드 화면

- 상단: 브랜드 4개 탭 + "마지막 갱신: YYYY-MM-DD HH:MM" 표시
- 탭 내용: 3열 그리드 피드(인스타 프로필 모양), 최신순, 최대 120개
- 각 셀: 썸네일 / 게시일 / 조회수·좋아요·댓글·저장·공유
- 상태 배지: `집계중 D+n`(30일 이내) / `확정`(동결)
- 썸네일 클릭 → 실제 인스타 게시물(permalink)
- `<meta name="robots" content="noindex">`, 모바일 반응형

## 오류 처리

- 지표 단위: API가 특정 지표 거부(#100) 시 해당 지표만 빼고 재시도, 끝내 실패하면 빈 값
- 계정 단위: 한 계정 실패해도 나머지 3개 정상 갱신. 실패 계정은 전날 데이터 유지 +
  화면에 해당 계정의 데이터 기준일 표시
- 실행 단위: workflow 실패 시 GitHub 기본 알림(저장소 주인에게 이메일)

## 일회성 셋업 (구현과 별도 진행)

1. 인스타 4개 계정 ↔ FB 페이지 연결, 비즈니스 관리자로 묶기 — 사용자 작업
2. Meta 개발자 앱 생성 + 시스템 사용자 토큰 발급 — 사용자 작업(안내 필요)
   - scope: instagram_basic, instagram_manage_insights, pages_read_engagement, pages_show_list
3. GitHub 저장소 생성, Secrets 등록, Pages 활성화 — 함께 진행
4. 노션 페이지에 대시보드 링크 삽입 — Claude가 처리

## 테스트 / 검증

- 수집기: 실제 API 없이 검증 가능하도록 30일 동결 병합 로직은 순수 함수로 분리해 단위 테스트
- 렌더러: 샘플 JSON → HTML 생성 스냅샷 확인
- 전체: workflow_dispatch 수동 실행으로 종단 검증(토큰 발급 후)
