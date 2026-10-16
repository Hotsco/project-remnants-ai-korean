# Project Remnants AI 대화 한국어 변환

NPC에게 한국어 명령을 내리고, AI 대화의 상황·성격 지침을 보완하며, 세이브에 저장된 NPC 프로필을 편집하는 도구입니다.

## 다운로드

**[최신 버전 다운로드](https://github.com/Hotsco/project-remnants-ai-korean/releases/latest)**에서 `ProjectRemnants-Luna-Windows-x64.zip`을 받아 전체 압축을 풀어주세요. Python 실행 환경이 포함되어 있습니다.

GitHub의 `Source code` 파일은 개발용 소스입니다. 일반 사용자는 위 Windows ZIP을 받으세요.

## 두 부분이 함께 작동합니다

| 구성 | 역할 |
|---|---|
| 게임 안의 보조 모드 | 한국어 키워드를 행동 명령에 연결하고 추가 상황 수집 |
| 게임 밖의 Setup + AI 대화 변환기 | AI 연결, API 호환 처리와 대화 지침 보완 |
| 외부 NPC 설정창 | 기존 프로필 불러오기·편집·실제 저장 내용 확인 |

보조 모드는 창작마당 구독과 ZIP의 로컬 설치 중 한 방식으로 설치합니다. 창작마당 구독 시 `Install-Korean-Addon.cmd`는 실행하지 않습니다.

## 시작하기

1. [Project Remnants](https://steamcommunity.com/sharedfiles/filedetails/?id=3738362476)의 원본 설치 안내와 [Setup](https://github.com/Patricklumowa/project-remnants-setup/releases)을 준비합니다.
2. ZIP의 `README.txt`에 따라 보조 모드를 설치·활성화합니다.
3. `Start-Setup-And-Luna.cmd`를 실행합니다. Setup에서 **OpenAI-compatible API**를 선택하고 사용할 서비스의 API 주소·키·모델을 설정한 뒤 **Configure and Start**를 누릅니다.
4. 원본의 LLM 대화·행동 옵션을 켜고 게임을 시작합니다. Setup과 변환기는 플레이 중 켜두세요.

Windows 64비트와 Project Zomboid Build 42가 필요합니다. 사용할 서비스의 API 키와 사용 권한이 필요하며, 요금은 해당 서비스의 API 기준을 따릅니다. 상황 전달과 성격 지침은 모델 이름에 관계없이 적용됩니다.

## 안내

- [설치·실행·문제 해결](tool/README.txt)
- [한국어 명령 키워드 전체 목록](tool/COMMANDS.txt)
- [AI가 읽을 수 있는 게임 상황](tool/GAME-CONTEXT.txt)
- 다운로드한 도구의 `GUIDE.html`에서 표로 된 가이드를 볼 수 있습니다.

NPC 프로필은 `Open-NPC-Settings.cmd`에서 불러오고 저장합니다. 저장할 때는 게임을 완전히 종료하세요. 기존 대화 기록과 관계 기억은 유지됩니다.

AI는 화면과 모든 소리를 직접 보고 듣지 않습니다. 가이드의 목록 밖 실시간 상황은 거의 직접 인지하지 못하며, 목록 안의 정보도 매 대화에 모두 전달되지는 않습니다. 특정 행동을 하는 개체를 골라 공격하는 기능은 구현되지 않았습니다.

## 소스 구성

`tool/`에는 외부 도구와 보조 모드 소스가 들어 있습니다. Python 런타임은 Windows 배포 ZIP에만 포함되며 라이선스는 그 안의 `runtime/LICENSE.txt`에서 확인할 수 있습니다. 원본 게임과 Project Remnants, Setup 파일은 포함하지 않습니다.

`build_workshop.py`를 Python으로 실행하면 `dist/ProjectRemnants_AI_Korean`에 창작마당 업로드용 폴더를 만듭니다. 이 폴더를 Zomboid 사용자 데이터 폴더의 `Workshop` 아래에 넣으면 게임의 창작마당 업로드 목록에서 선택할 수 있습니다.
