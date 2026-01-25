# VLM server 실행 방법

이 문서는 Time Travel Summarization Extension을 사용하기 위한 VLM 서버를 실행하는 방법을 설명하는 설명서입니다.  

*   VLM 서버는 VLM container와 video process pipeline (NVIDIA VSS) 로 구성되어, 각각 컨테이너를 실행해야합니다.
*   GPU는 SV4000-2 서버 기준으로 l40 또는 A100 40GB 한대면 충분.(Qwen3-vl-8b 기준)

## 1. NVIDIA VSS clone
*   아래 깃헙 레포지토리에서 NVIDIA VSS (Video search and summarization) 을 clone.
*   *   https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization.git
*   *   **주의** 라이센스 이슈 방치를 위해 2차 배포 (연구실 또는 개인 레포지토리에 fork) 하지말고, 서버상에서 Time Travel Summarization 실행 용도로만 사용할 것. (또한 git push도 하지 않도록 주의)
*   NVIDIA VSS는 비디오나 이미지 파일을 기반으로 Video Summarization, Q&A, alert 의 기능을 제공하는 Agent Blueprint 임.
*   비디오 청킹 및 디코딩 역할을 하는 `via-server`만을 차용하여 Time Travel Summarization Framework의 비디오 처리 파이프라인으로 사용함.

## 2. 실행
오픈소스 VLM 이냐 상용 VLM (ChatGPT) 이냐에 따라 실행 방식에 차이가 존재함.
*   오픈소스 VLM
*   *   VSS 실행 디렉토리: video-search-and-summarization/deploy/docker/remote_llm_deployment/
*   상용 VLM
*   *   VSS 실행 디렉토리: video-search-and-summarization/deploy/docker/remote_vlm_deployment/
환경변수(`.env`)와 vlm endpoint의 프리셋 차이

### 2.1. 오픈소스 VLM
NVIDIA 제공 모델과 OpenAI API Compatible VLM 사용 가능
https://docs.nvidia.com/vss/latest/content/installation-vlms-docker-compose.html#

#### OpenAI API Compatible VLM (Qwen3-vl-8b)

VLM 컨테이너와 비디오 처리 파이프라인(VSS) 컨테이너 각각 실행

**1.** 서버 (ex. SV4000-2) 에서 VLM container (run_qwen3-vl-8b.sh) 실행

vLLM 기반으로 Qwen3-vl-8b 모델 실행

```
docker run -d \
  --name qwen3-vl-8b \
  --gpus '"device=2"' \
  --network host \
  --ipc=host \
  --shm-size=16g \
  -v /home/netai/wonjune/models/Qwen3-VL-8B-Instruct:/models/Qwen3-VL-8B-Instruct:ro \
  vllm/vllm-openai:latest \
    --model /models/Qwen3-VL-8B-Instruct \
    --served-model-name Qwen3-VL-8B-Instruct \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --max-num-seqs 256 \
    --max-num-batched-tokens 8192 \
    --media-io-kwargs '{"video": {"num_frames": -1}}' \
    --host 0.0.0.0 \
    --port 38011
```
*   적당한 GPU 번호 선택 --gpus '"device=2"' \ 
*   기존 VSS 코드 내부에 수정이 필요하므로 다음 볼륨 마운트 필요
    -v /home/netai/wonjune/models/Qwen3-VL-8B-Instruct:/models/Qwen3-VL-8B-Instruct:ro \
*   VSS가 사용할 포트 번호 --port 38011

**2.** VSS의 레포지토리의 `video-search-and-summarization/deploy/docker/remote_llm_deployment/` 경로로 이동

**3.** `remote_llm_deployment_env.env` 의 환경변수로 기존의 `.env` 의 환경변수를 대체.

*   VSS 레포지토리 기존의 `.env`를 지우고, `remote_llm_deployment_env.env` 를 `.env`로 명명.
*   `.env` 파일 최상단의 NVIDIA_API_KEY 에 기입.  
*   NVIDIA_API_KEY 발급 필요
*   *   https://build.nvidia.com/explore/discover 에서 로그인 후 `Manage API Keys` 에서 발급

`NGC_API_KEY`는 꼭 필요하지 않음
```
export NVIDIA_API_KEY=nvapi-*** #api key to access NIM endpoints. Should come from build.nvidia.com
```

**4.** 레포지토리 기존의 `compose.yaml` 수정

*   `services/via-server/volumes`에 `- /home/netai/wonjune/timetravel/video-search-and-summarization/src/vss-engine/src/vlm_pipeline:/opt/nvidia/via/via-engine/vlm_pipeline` 추가
*   *   VSS 코드를 수정하여 사용해야함. 수정된 파일을 마운트하기 위함
*   `services/via-server/environment` 에 `VIA_VLM_ENDPOINT: "${VIA_VLM_ENDPOINT:-}"` 추가
*   *   VLM container의 endpoint를 전달해주기 위함
*   `services/via-server/depdnes_on` 을 비활성화
*   *   비디오 파이프라인 이외의 기능을 비활성화 하기 위함
비활성화 목록
```
    # depends_on:
    #   milvus-standalone:
    #     condition: service_healthy
    #   graph-db:
    #     condition: service_started
    #   arango-db:
    #     condition: service_started
    #   minio:
    #     condition: service_started
```

**5.** `docker compose up via-server` 명령어로 비디오 파이프라인 실행

**참고** VLM 모델 교체하기.
*   Qwen과 같은 Open AI compatible REST API를 지원하는 모델은 제공된 run_qwen3-vl-8b.sh 스크립트를 수정하여 모델 교체된 컨테이너를 실행한 뒤 `export VIA_VLM_OPENAI_MODEL_DEPLOYMENT_NAME="Qwen3-VL-8B-Instruct"` 모델 이름 수정해주면 됨. 참고: https://docs.nvidia.com/vss/latest/content/installation-vlms-docker-compose.html#

*   NVIDIA에서 제공하는 모델 (cosmos-reaseon 등등)은 `.env`에 `model selection` 부분에서 모델 별로 코멘트 해제하여 선택 가능.
*   *   이들은 따로 VLM 컨테이너를 실행해주지 않아도 via-server를 실행할 때 자동으로 vlm 서버도 실행해줌.
*   *   이때 `export NVIDIA_VISIBLE_DEVICES=` 에서 설정된 GPU에 VLM과 비디오 파이프라인 둘다 실행됨.
```
# model selection - uncomment the model you want to use

#Set VLM to Cosmos-Reason1
# export VLM_MODEL_TO_USE=cosmos-reason1
# export MODEL_PATH=git:https://huggingface.co/nvidia/Cosmos-Reason1-7B
# export NVIDIA_VISIBLE_DEVICES=2
```


VLM_MODEL_TO_USE=openai-compat in the .env file.

Open AI compatible REST API 지원하지 않는 모델은 다음 문서 참조
https://docs.nvidia.com/vss/latest/content/installation-vlms-docker-compose.html#other-custom-models-docker-compose



Qwen3 container와의 연결을 지원하는 환경변수 설정.
```
#Set VLM to Qwen3-VL-8B 
export VLM_MODEL_TO_USE=openai-compat
export OPENAI_API_KEY="empty"
export VIA_VLM_ENDPOINT="http://host.docker.internal:38011/v1"
export VIA_VLM_OPENAI_MODEL_DEPLOYMENT_NAME="Qwen3-VL-8B-Instruct" 
export NVIDIA_VISIBLE_DEVICES=2 # VSS pipeline이 청킹 및 디코딩을 하는 GPU 설정 (vss가 직접 vllm을 실행하는 cosmos-reason의 경우에는 해당 gpu에서 vllm과 비디오 파이프라인 둘 다 실행.)
```
참고: https://docs.nvidia.com/vss/latest/content/installation-vlms-docker-compose.html#
