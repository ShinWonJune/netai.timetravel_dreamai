timetravel_dreamai extension의 사용법에 대한 Readme를 작성하려고해. Extension의 작동 순서대로 각각의 모듈에 대한 설명을 할거야. 모듈 설명은 하는 역할과 사용 방법 위주로 설명할거야. timetravel_dreamai의 이름을 timetravel_summarization으로 바꿀거야. 현재 이름과 다르다는것을 염두해줘.
단계는 다음과 같아.


이 문서는 현재 버전의 TimeTravel Summarization Extension 사용법이다.
해당 익스텐션은 여러 모듈로 구성된 Time Travel Summarization Framework를 구현하며 시계열 궤적 데이터를 활용하여 디지털트윈 기반의 Event-based Summarization을 생성한다. (현재 요약 가능한 event는 '충돌')

Note
- 이 문서에서 Timetravel이란 시간의 흐름에 따라 객체의 위치 상태를 복원하는 기능을 뜻한다(= 과거 상태 복원). 다만 공식적인(교수님 관점) "Time Travel"은 단순한 과거 상태를 복원을 넘어 통합적인 시공간 분석 기능의 통칭을 뜻한다. 즉 해당 프레임워크는 "Time Travel"을 도와주는 하나의 시공간 분석 기능이다.
- 전체 프레임워크의 핵심이 되는 과거 상태 복원 기능을 제공하는 TimeTravel은 core.py, window.py에 구현, 이외에 분석을 도와주는 기능 (view_overlay, vlm_client, event_post_processing)은 각각의 명칭_core.py, 명칭_window.py 에 구현되었다. Extension.py를 통해 통합적으로 초기화된다.
- Movie Capture Extension은 USD Composer에 기본적으로 설치되어있는 Extension이다. 


1. 궤적 데이터 생성
utils/trajectory_data_generater_XAI_Studio.py 실행
2. config 설정 (config.py)
- 생성된 궤적 데이터로 "data_path" 설정
- timetravel용 객체 생성에 참조할 astronaut_usd 파일의 경로 설정
3. Extension Initialization: USD Composer의 Extension창에서 TimeTravel_dream_ai extension initialization.
3-1 Extension 기능
- 앞서 생성된 데이터를 기반으로 시간의 흐름에 따라 astronaut 위치 반영 (= 과거 상태 복원)
- 데이터에 포함된 id의 갯수 만큼 astronaut 생성 및 매핑
- Go to Time: 특정 시점(timestamp)의 상태 복원
- 타임 스크롤: 선형적으로 timestamp 조절
- Play 버튼: 시간의 흐름에 따라 과거 상태 재생
- Speed: 재생 속도 조절 가능
- View_overlay module, VLM  client module, event post-processing module 의 window UI도 함께 initiate.
3-2 구현
- core.py
- window.py 를 통해 Extension의 window UI 구현

4. View Overlay: 복원된 장면에 objectID, Timestamp를 overlay. (View Overlay)
4-1 목적
복원된 디지털트윈
4-2 구현
-view_overlay_core.py 는 overlay logic 담당
-view_overlay_window.py는 UI window 담당.

5. 부분 시각화 및 재생 속도 조절: 디지털트윈 환경 세팅
디지털트윈의 유연한 시공간 환경 조절 능력을 활용하여, VLM 추론에 효과적인 영상 데이터를 제공하기 위한 목적이다.
- 
6. 동영상 추출 (Movie Capture Extension)
USD Composer 기존 Extension 활용.
이 부분에서 시간적인 병목 현상이 크게 발생함. 
VLM에 영상 전달 방식을 스트리밍으로 확장 필요 (동영상 청킹, 디코딩 등 pipeline 역할을 하는 NVIDIA VSS가 RTSP(real time streaming protocol)를 지원함)
6-1 캡쳐 가이드
- Camera: BEV_cam
- Framerate: 30
- Custom Range: Seconds
-- End: 촬영 결과물에 맞게 설정
-- 예) 1분 범위의 궤적 데이터 기준으로, 1배속 영상 생성시 60초, 3배속 영상 생성시 20초로 설정
-- 이때, 1배속 영상(60초)을 생성하기 위해서는 timetravel 재생속도를 0.33배 해줘야하며, 3배속 영상 (20초) 생성할 때는 timetravel 1x 재생속도로 설정 해야함
-- 그 이유는, movie capture는 default로 10FPS로 캡쳐하기 때문. 
-- Real time capture 용도가 아니라 그런듯. Frame rate와 custom range 설정 후, 실제 시뮬레이션 및 렌더링 속도를 조절하여 capture 해야함
- Resolution: 532*280 (변경해도 상관 무)
-- 이 Resolution은 Cosmos-Reason1 의 기본 input resolution config를 따름
-- 빠른 추론속도와 성능을 위하여 2K Vision Token을 유지 (Cosmos 기준. 모델 마다 토큰 계산 방식이 다름)
-- 참조: https://docs.nvidia.com/vss/latest/content/via_customization.html, [Tuning the Input Vision Token Length for Cosmos-Reason1]
- Output Path: 적당한 경로 설정
- Name: 주의, 동영상 이름은 **video_n** 의 형태 이어야함. VSS 가 해당 이름 형식을 필요로함. 
- 캡쳐 형태: mp4로 설정.
7. VLM Client를 통해 VLM Server에 동영상 전달
7-1 기능
- video: 앞서 생성한 동영상 이름
- Upload 버튼을 통해 업로드. Generate 버튼을 통해 결과 생성 요청 및 반환.
- Model: VLM 서버에서 실행중인 모델의 이름을 선택
- Preset: vlm_client_core.py에 미리 저장해둔 Prompt 선택 (twin_view, simple_view)
-- Twin_view: VLM에 전달되는 동영상을 디지털트윈 기반의 시뮬레이션으로 묘사
-- Simple view: VLM에 전달되는 동영상을 도형의 움직임 수준으로 묘사

7-2 구현
- vlm_client_core.py
- vlm_cleint_window.py

8. Event Post Processing 모듈로 output을 Event list로 가공
8-1 기능 output json file 명