# 자사 인스타그램 데일리 피드 대시보드

자사 인스타 4개 계정의 피드를 매일 아침 7시(KST)에 수집해
인스타 피드 모양의 HTML 대시보드로 GitHub Pages 에 배포합니다.

- 계정당 최근 **120개** 게시물 표시
- 성과(조회·좋아요·댓글·저장·공유)는 **게시 후 30일까지만** 매일 갱신, 이후 동결(`확정` 배지)
- 계정 목록·표시 개수는 `config.yaml` 에서 수정

## 일회성 셋업

### 1. 인스타 계정 준비
1. 4개 계정 모두 비즈니스 계정인지 확인 (완료됨)
2. 각 계정을 페이스북 페이지에 연결 (인스타 앱 → 설정 → 페이지 연결)
3. 4개 페이지를 하나의 비즈니스 관리자(business.facebook.com)에 추가

### 2. Meta 앱 + 토큰
1. https://developers.facebook.com → 앱 생성 (유형: Business)
2. 비즈니스 관리자 → 시스템 사용자 생성 → 앱과 페이지 자산 할당
3. 시스템 사용자 토큰 발급 — scope:
   `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement`, `pages_show_list`
4. 이 토큰은 만료되지 않음. 절대 커밋하지 말 것

### 3. GitHub
1. 이 저장소를 GitHub 에 push (public — Pages 무료 사용 조건)
2. Settings → Secrets and variables → Actions → `META_ACCESS_TOKEN` 등록
3. Settings → Pages → Source: **GitHub Actions** 선택
4. Actions 탭 → daily-feed → **Run workflow** 로 첫 실행
5. 배포 URL 확인 → 노션에 링크 등록

## 로컬 실행 (검증용)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export META_ACCESS_TOKEN="..."
python -m src.main
open site/index.html
```

## 테스트

```bash
pytest -v
```

## 트러블슈팅
- **계정이 안 잡힘** — 해당 인스타 계정이 페이지에 연결됐는지, 그 페이지가 시스템 사용자에 할당됐는지 확인
- **(#100) 지표 오류** — 자동으로 해당 지표만 제외하고 재시도함. 노출이 빈 값이면 정상 동작
- **실행 실패 메일** — GitHub 이 workflow 실패 시 자동 발송. Actions 탭에서 로그 확인
