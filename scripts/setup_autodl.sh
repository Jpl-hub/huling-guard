#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${ENV_NAME:-huling}"
ENV_PREFIX="${ENV_PREFIX:-/root/autodl-tmp/envs/${ENV_NAME}}"
PYTHON_VERSION="${PYTHON_VERSION:-3.10}"
CUDA_WHL_INDEX="${CUDA_WHL_INDEX:-https://download.pytorch.org/whl/cu128}"
TORCH_VERSION="${TORCH_VERSION:-2.7.0}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.22.0}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.7.0}"
CONDA_PKGS_DIRS="${CONDA_PKGS_DIRS:-/root/autodl-tmp/conda-pkgs}"
PIP_CACHE_DIR="${PIP_CACHE_DIR:-/root/autodl-tmp/pip-cache}"
HF_HOME="${HF_HOME:-/root/autodl-tmp/hf-home}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-/root/autodl-tmp/.cache}"
CONDA_SOLVER="${CONDA_SOLVER:-libmamba}"
CONDA_CREATE_CHANNEL="${CONDA_CREATE_CHANNEL:-https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/}"
CONDA_CREATE_REPODATA_FN="${CONDA_CREATE_REPODATA_FN:-repodata.json}"

if command -v conda >/dev/null 2>&1; then
  CONDA_BIN="$(command -v conda)"
elif [[ -x /root/miniconda3/bin/conda ]]; then
  CONDA_BIN="/root/miniconda3/bin/conda"
else
  echo "conda is required on the AutoDL instance"
  exit 1
fi

mkdir -p "$(dirname "${ENV_PREFIX}")" "${CONDA_PKGS_DIRS}" "${PIP_CACHE_DIR}" "${HF_HOME}" "${XDG_CACHE_HOME}"
export CONDA_PKGS_DIRS
export PIP_CACHE_DIR
export HF_HOME
export XDG_CACHE_HOME

source "$("${CONDA_BIN}" info --base)/etc/profile.d/conda.sh"

if [[ ! -x "${ENV_PREFIX}/bin/python" ]]; then
  conda create -y \
    --solver "${CONDA_SOLVER}" \
    --override-channels \
    -c "${CONDA_CREATE_CHANNEL}" \
    --repodata-fn "${CONDA_CREATE_REPODATA_FN}" \
    -p "${ENV_PREFIX}" \
    "python=${PYTHON_VERSION}"
fi

conda activate "${ENV_PREFIX}"

python -m pip install --upgrade pip "setuptools==80.9.0" wheel openmim
python -m pip install "numpy==1.26.4"
python -m pip install \
  "torch==${TORCH_VERSION}" \
  "torchvision==${TORCHVISION_VERSION}" \
  "torchaudio==${TORCHAUDIO_VERSION}" \
  --index-url "${CUDA_WHL_INDEX}"

python -m pip install ninja cython psutil
python -m pip install "mmengine>=0.10.5"
python -m pip install "mmcv==2.1.0" --no-build-isolation
python -m pip install "chumpy==0.70" --no-build-isolation
python -m pip install "mmpose==1.3.2" --no-build-isolation
python -m pip install "mmdet==3.3.0" --no-build-isolation

python -m pip install -e .
python -m pip install -e git+https://github.com/IDEA-Research/GroundingDINO.git#egg=groundingdino
python -m pip install -e git+https://github.com/facebookresearch/sam2.git#egg=sam2

python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda", torch.version.cuda)
print("cuda_available", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device", torch.cuda.get_device_name(0))
PY

echo "AutoDL environment is ready."
