Project Remnants AI 대화 한국어 변환

NPC의 한국어 명령 연결, GPT-6 Luna 대화 보완, 세이브의 NPC 프로필 편집을 제공합니다.

구성
- 게임 안의 보조 모드: 한국어 키워드를 Remnants 행동 명령에 연결하고 추가 상황을 수집합니다. 사용할 세이브에서 활성화하세요.
- 게임 밖의 Setup + Luna 변환기: AI 연결과 Luna 호환 처리, 대화 지침 보완을 담당합니다. 플레이 중 켜두세요.
- NPC 설정창: 프로필을 편집할 때만 엽니다. 게임을 완전히 종료한 뒤 저장하세요.

한국어 답변은 AI가 생성하며, 실제 행동은 Remnants가 실행합니다. 대사로 수락해도 행동이 완료됐다는 뜻은 아닙니다. 보조 모드만으로 AI 연결을 대신할 수는 없으며, 보조 모드를 끄면 한국어 명령 연결과 추가 상황 수집이 빠집니다.

준비
- Windows 64비트, Project Zomboid Build 42
- Project Remnants 모드와 Project Remnants Setup
- 본인의 OpenAI API 키, API 사용 요금 설정, 인터넷 연결

Remnants 설치: https://steamcommunity.com/sharedfiles/filedetails/?id=3738362476
Setup 다운로드: https://github.com/Patricklumowa/project-remnants-setup/releases
API 키 관리: https://platform.openai.com/api-keys
모델·요금: https://developers.openai.com/api/docs/models/gpt-6-luna

API는 대화와 NPC 설정·지침·상황 정보를 AI 서비스로 보내고 답변을 받는 연결입니다. 사용량에 따라 요금이 발생하며 ChatGPT 구독과 별도입니다. API 키는 다른 사람과 공유하지 마세요.

처음 설치
1. 공식 안내에 따라 Remnants와 Setup을 준비합니다.
2. 이 ZIP을 원하는 폴더에 모두 풉니다.
3. 보조 모드는 창작마당 구독 또는 게임 종료 후 Install-Korean-Addon.cmd 실행 중 한 방식으로 설치합니다. 창작마당에서 구독했다면 로컬 설치는 생략하세요.
4. 사용할 세이브에서 Project Remnants와 Project Remnants AI 대화 한국어 변환을 켭니다.
5. Start-Setup-And-Luna.cmd를 실행합니다. Setup을 찾지 못하면 ProjectRemnantsSetup.exe를 선택합니다.
6. Setup의 LLM Companion에서 OpenAI 호환 연결과 API 키를 설정합니다. 모델은 gpt-6-luna로 입력하고 Configure and Start를 누릅니다.
7. 원본 모드의 LLM 사용 옵션을 켜고 게임을 시작합니다. 행동 명령을 쓰려면 LLM 행동 사용 옵션도 켜세요.

Zomboid 사용자 데이터 폴더를 따로 쓴다면 3번 전에 Configure-Paths.cmd에서 지정하세요. 기본 위치는 Windows 사용자 폴더 아래 Zomboid입니다.

다음 플레이부터
Start-Setup-And-Luna.cmd 실행 → Setup에서 Configure and Start → 준비 완료 후 게임 실행.
Setup과 변환기는 플레이 중 켜둡니다. 변환기를 끄려면 Stop-Luna-Adapter.cmd를 실행하세요. 이전 연결 설정으로 복구됩니다.

필요할 때 쓰는 파일
- Open-NPC-Settings.cmd: 기존 NPC 프로필 불러오기·편집·저장 확인
- Create-Desktop-Shortcut.cmd: 현재 도구 위치로 바탕화면 바로가기 만들기
- Configure-Paths.cmd: Setup과 사용자 데이터 폴더 지정
- Start-Luna-Adapter.cmd: Setup 중계 서버가 켜진 상태에서 변환기만 실행
- GUIDE.html: 한국어 명령 키워드 전체 목록과 AI가 읽을 수 있는 상황
- COMMANDS.txt / GAME-CONTEXT.txt: 같은 가이드의 텍스트 목록

도구 폴더를 옮기면 바로가기를 다시 만드세요. 경로를 바꿨다면 변환기를 다시 실행합니다.

NPC 프로필과 대화 지침
설정창에서 세이브와 NPC를 고르면 기존 프로필을 불러옵니다. '항목별 작성 도움'은 입력란을 채우는 기능이며, 실제 저장은 '저장하고 확인'으로 합니다. 저장 전 내용은 자동 백업하고 실제 세이브를 다시 읽어 확인합니다. '저장 내용 확인'은 입력 내용과 저장된 프로필을 비교합니다.
기존 대화 기록과 관계 기억은 유지됩니다. 설치 위치를 찾지 못하면 설정창의 '설치 위치'에서 지정하세요.
공통 지침은 dialogue-guidance.txt를 UTF-8로 편집하면 다음 대화부터 반영됩니다. 비우면 지침 보완과 추가 상황 전달이 꺼집니다. 보완은 gpt-6-luna 계열에 적용됩니다.
보조 모드를 재설치해도 기존 한국어 명령 낱말 설정은 유지합니다.

알아둘 한계
AI는 화면과 소리를 직접 보고 듣지 않습니다. GUIDE.html의 상황 목록 밖 정보는 거의 직접 인지하지 못하며, 목록 안의 정보도 매 대화에 전부 전달되지는 않습니다. 명령 실행에는 물건·거리·경로 등 Remnants의 조건이 필요합니다.

작동하지 않을 때
- 연결: Setup에서 Configure and Start를 눌렀는지 확인합니다. 로컬 연결의 준비 완료는 API 사용 가능 여부까지 확인한 결과가 아닙니다.
- API 오류: 키, 결제 상태, 모델 이름과 사용 권한을 확인합니다.
- 명령·상황 전달: 해당 세이브의 보조 모드와 LLM 행동 옵션을 확인하고 게임을 완전히 종료한 뒤 다시 실행합니다.

Python 라이선스: runtime/LICENSE.txt
