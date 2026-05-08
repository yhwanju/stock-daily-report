# Stock Daily Report

Python 기반 자동 주식 데일리 리포트 시스템입니다.

현재 구현 범위는 **데일리 리포트**입니다. 종목 분석 리포트는 `src/stock_reports/stock_analysis` 아래에 완전히 분리된 확장 영역으로만 남겨 두었습니다.

## 핵심 구조

```text
stock_daily_report/
  config/
    daily_report.example.yaml
  scripts/
    run_daily_report.py
  src/
    stock_reports/
      core/
        config.py
      integrations/
        discord.py
      daily_report/
        data_sources/
          market_data.py
          news.py
          news_sources.py
        renderers/
          card_news.py
        processing/
          deduplication.py
          enrichment.py
          impact.py
          scoring.py
          summarizer.py
          theme_classifier.py
        models.py
        report_builder.py
        sample_data.py
        scheduler.py
        service.py
        templates/
          card_news.html
          card_news.css
      stock_analysis/
        README.md
  requirements.txt
```

## 실행 준비

1. 의존성 설치

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

2. 환경 변수 설정

`.env.example`을 참고해 `.env`를 만들고 Discord Webhook URL을 입력합니다.

```text
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

3. 데일리 리포트 1회 실행

```powershell
python scripts/run_daily_report.py --once --dry-run
```

`--dry-run`은 Discord로 보내지 않고 콘솔에 출력합니다. 네트워크 수집이 실패하면 내장 샘플 데이터로 리포트를 생성합니다.

4. 샘플 데이터로 리포트 출력

```powershell
python scripts/run_daily_report.py --once --dry-run --sample-data
```

5. 샘플 데이터로 카드뉴스 PNG 생성

```powershell
python scripts/run_daily_report.py --once --dry-run --sample-data --template card_news
```

결과물은 `output/` 아래에 생성됩니다.

```text
output/daily_report_YYYYMMDD_card_01.png
output/daily_report_YYYYMMDD_card_02.png
output/daily_report_YYYYMMDD_card_03.png
...
```

6. 실제 수집 후 Discord 발송

```powershell
python scripts/run_daily_report.py --once --send
```

7. 카드뉴스 PNG를 Discord에 첨부해 발송

```powershell
python scripts/run_daily_report.py --once --send --template card_news
```

8. 평일 오전 7시 45분 자동 발송

```powershell
python scripts/run_daily_report.py --schedule --send
```

## 데일리 뉴스 수집 방식

- 국내 뉴스는 네이버 금융, 네이버 증권에서 수집합니다.
- 해외 뉴스는 Yahoo Finance, Reuters, CNBC에서 수집합니다.
- `config/daily_report.example.yaml`의 `provider`, `method`, `url`만 바꾸면 추후 뉴스 API나 다른 RSS/HTML 소스로 교체할 수 있습니다.
- 수집된 기사는 헤드라인, 요약, 링크, 발행 시간, 국내/해외 구분을 보관합니다.
- `processing/theme_classifier.py`에서 AI반도체, HBM, 전력설비, 원전, ESS, 우주항공, 방산 등 영향 테마를 분류합니다.
- `processing/scoring.py`에서 금리, CPI, FOMC, 엔비디아, 환율, 유가, 구리, 정책, 수주, 실적 키워드를 반영해 영향 강도 1~5점을 산출합니다.
- `processing/summarizer.py`에서 기사별 핵심 투자 영향을 3줄 중심으로 요약하며, 최대 5줄까지 허용합니다.
- 제목 유사도와 영향 테마를 함께 사용해 중복 기사와 유사 흐름을 병합합니다.
- 기본 출력은 권장 개수인 최대 7개이며, 설정상 하드 제한은 10개입니다.
- 국내 증시와 해외 증시는 리포트 섹션에서 분리됩니다.

현재 기본 소스:

```yaml
news_sources:
  - provider: naver_finance
    method: html
  - provider: naver_stock
    method: html
  - provider: yahoo_finance
    method: rss
  - provider: reuters
    method: html
  - provider: cnbc
    method: rss
```

## Discord 메시지 예시

샘플 출력 예시는 [examples/discord_message_example.md](examples/discord_message_example.md)에 있습니다.

## 카드뉴스 이미지 리포트

기존 Markdown 텍스트 리포트는 그대로 유지됩니다. 추가로 `--template card_news` 옵션을 주면 같은 리포트 데이터를 카드뉴스형 PNG로 렌더링합니다.

카드뉴스 구성:

- 1장: 표지, 날짜, 오늘 시장 한줄 판단
- 2장: TODAY MARKET, 지수와 매크로/원자재 2열 카드
- 3장: 오늘 강세 예상 테마 TOP5
- 4장 이후: 국내 증시 뉴스, 해외 증시 뉴스
- 뉴스가 많으면 3개 단위로 추가 페이지 생성

Discord 발송 시:

- `markdown`: 기존 텍스트 리포트 발송
- `card_news`: 짧은 텍스트 요약 + PNG 이미지 첨부 발송

PNG 생성은 Playwright Chromium을 사용합니다. 최초 1회 아래 명령이 필요합니다.

```powershell
python -m playwright install chromium
```

## 실제 실행 예시

Python 환경이 준비된 상태에서 아래 명령을 실행하면 API 키 없이도 샘플 리포트를 확인할 수 있습니다.

```powershell
python scripts/run_daily_report.py --once --dry-run --sample-data
```

카드뉴스까지 생성하려면:

```powershell
python scripts/run_daily_report.py --once --dry-run --sample-data --template card_news
```

예상 출력 일부:

```text
📰 투자 영향도 데일리 리포트
2026-05-08 07:45

━━━━━━━━━━━━━━━━━━
TODAY MARKET
━━━━━━━━━━━━━━━━━━
[지수] KOSPI 2,734.18 (+0.42%) | KOSDAQ 857.31 (+0.68%) | NASDAQ 16,511.18 (+1.24%) | SOX 5,128.74 (+2.18%)

• 위험선호 우세. 성장주와 반도체 중심의 매수 심리 확인 필요.
• AI반도체·HBM·전력설비 테마 강세 가능성.
• 금리와 환율 안정 시 성장주 우호적 흐름 지속 가능.

━━━━━━━━━━━━━━━━━━
🇰🇷 국내 증시
━━━━━━━━━━━━━━━━━━
[샘플] HBM 공급 부족 전망에 국내 AI반도체 밸류체인 재부각

• AI 서버 투자 확대와 고대역폭메모리 수요 증가 전망이 함께 부각됐다.
• AI반도체 / HBM 관련 자금 흐름과 업종 수급에 영향 가능.
• 시장 방향성까지 흔들 수 있는 재료라 장 초반 지수·선물 반응 확인 필요.
```

전체 예시는 [examples/sample_run_output.md](examples/sample_run_output.md)에 있습니다.

## 설계 원칙

- `daily_report`: 장 시작 전 시장 분위기, 핵심 뉴스, 테마 강도를 요약하는 데일리 리포트 전용 영역
- `stock_analysis`: 향후 개별 종목 분석 리포트 전용 영역
- `core`: 설정, 공통 유틸리티
- `integrations`: Discord 등 외부 연동

데일리 리포트와 종목 분석은 서로 import하지 않는 구조를 기준으로 유지합니다.
