# PROJECT STATUS

## 완료 기능
- Discord 자동 발송
- GitHub Actions 자동 실행
- 카드뉴스 PNG 생성
- 링크 정합성 개선
- 07:45 DAILY MARKET BRIEF
- 07:50 RESEARCH UPDATE
- RESEARCH UPDATE 자연스러운 의역 및 테마 fallback 개선
- TODAY MARKET 시장 조합별 해석 보강
- GitHub Actions Playwright Chromium 캐시 적용
- 출력 경로 금지 표현 정리

## 현재 개선 중
- 다음 자동 발송 결과 기준 문장 반복 여부 점검
- 해외 리포트 의역 품질 추가 개선
- README/examples 샘플 출력 최신화

## 금지 표현
- 자금 흐름
- 업종 수급
- 영향 가능
- 종목별 탄력 차이
- 이슈가 부각됐습니다

## 요약 스타일 방향
- 직역보다 의역
- 시장 해석형 요약
- 투자 판단 가능 형태
- 기사 핵심 + 시장 해석 + 관련 테마 구조
- 반복 generic 문장보다 기사별 변화 요인 우선

## 현재 구조
07:45:
- DAILY MARKET BRIEF
- 카드뉴스 PNG
- 시장 요약
- 뉴스
- 테마

07:50:
- RESEARCH UPDATE
- 증권사/해외 리포트 변화
- 텍스트 중심
- 기사 제목/요약 기반 보조 테마 분류

## 현재 이슈
- 다음 GitHub Actions 실행 결과 확인 필요
- README/examples 출력 예시가 최신 문장 톤과 일부 다를 수 있음
- 로컬 Windows 환경은 Python Store alias만 잡혀 있어 로컬 py_compile 검증 불가

## 다음 작업
- GitHub Actions 수동 실행 또는 다음 자동 실행 로그 확인
- 실제 Discord 발송 결과에서 RESEARCH UPDATE 중복 문장 점검
- 카드뉴스 PNG 샘플 산출물 기준 문구 길이 확인
- README/examples 샘플 출력 최신화
