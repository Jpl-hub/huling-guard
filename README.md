# 护龄智守

护龄智守是一套面向居家照护与机构值守场景的单房间安全监测系统。系统以固定摄像头为输入，持续输出人员状态、风险变化、事件记录和历史会话归档，用于支持日常值守、异常处置和事后追溯。

## 应用界面

系统前端采用 `Vue 3 + Vite + Arco Design Vue + ECharts` 实现，运行时界面固定为三页：

- `实时值守`
  以监控画面为主屏，展示当前状态、是否需要立即到场、最近事件和过程回看。
- `历史会话`
  展示已归档记录、筛选条件、关键阶段和关键时刻预览。
- `系统信息`
  展示识别链路、状态定义、部署参数和系统适用范围。

前端支持两种显示层次：

- `值守视图`
  面向值班人员，优先呈现监控画面、处置建议、最近事件和过程回看。
- `引擎透视`
  仅在独立模式下显示状态分布、风险时间线和部署参数，不干扰主屏判断。

## 工程能力

- 支持基于发布包的单视频推理、批量视频推理和运行时服务部署
- 支持基于历史记录的误报复查、区间标签回灌和定向再训练

## 总体架构

系统采用单一路线架构：

1. `RTMO`
负责逐帧人体姿态估计，输出 17 点骨架与关键点置信度。

2. `Grounding DINO + SAM 2`
仅用于离线房间区域初始化，生成床、沙发、地面活动区和风险边缘等房间先验。

3. `Scene-Pose Temporal Net`
融合骨架序列、运动学特征和场景关系特征，对时间窗进行五分类判断。

4. `EventEngine`
将连续状态流稳定为可直接使用的事件流，包括高风险失衡、跌倒、长时间卧倒和恢复事件。

5. `FastAPI + SQLite + Vue + Docker`
提供运行时接口、历史会话归档、前端页面和标准化部署封装。

## 仓库结构

```text
configs/                    训练配置与运行时配置
docs/                       架构文档与系统设计文档
scripts/                    数据准备、训练编排、评估与发布脚本
src/huling_guard/           主代码
frontend/                   Vue 前端
tests/                      纯逻辑测试
```

## 运行时服务

运行时服务提供以下接口与页面：

- `GET /dashboard`
  运行时前端入口。

- `GET /health /meta /system-profile`
  服务健康状态、部署参数和系统资料。

- `GET /summary /timeline /state /incidents /session-report`
  当前状态、风险时间线、事件流和会话摘要。

- `GET /archives /archives/summary /archives/{session_id}`
  历史归档查询与记录预览。

- `GET /demo-videos /demo-sessions/{filename}`
  演示视频源与配套推理结果。

## 数据与训练

当前训练主线以公开视频集为基础，包括 `CaucaFall`、`UP_Fall` 和 `UR Fall`。数据进入系统后遵循统一流程：

1. 生成原始视频 manifest
2. 用 `RTMO` 离线抽取骨架
3. 构建特征缓存与时间窗
4. 训练 `Scene-Pose Temporal Net`
5. 进行窗口级、样本级和事件级评估
6. 打包发布并执行批量视频验证

系统会在训练前强制检查 `raw manifest -> pose manifest` 的覆盖率，覆盖不完整时直接终止，避免残缺语料进入训练主链。
在没有真实摄像头和新增实拍数据的阶段，训练主线默认启用骨架时序增强，包括时间窗抖动、短时遮挡、骨架噪声和置信度缺失模拟，用于提高对轻度遮挡、关键点抖动和短时丢帧的鲁棒性。

## 部署方式

运行时服务支持本机启动和 Docker 启动。

本机启动入口：

```bash
PYTHONPATH=src python -m huling_guard.cli serve-release \
  --release-dir /path/to/release \
  --frontend-dist /path/to/frontend/dist \
  --host 0.0.0.0 \
  --port 8014 \
  --archive-root /path/to/archive
```

Docker 方式可使用：

```bash
docker compose -f docker-compose.runtime.yml up --build
```

Docker 镜像将自动完成前端构建，并在运行时服务中直接提供 `/dashboard` 页面。默认归档路径为容器内 `/runtime-data/archive`。

## 前端开发

前端本地开发入口：

```bash
cd frontend
npx vite --host 127.0.0.1 --port 4174
```

开发模式下，Vite 会代理运行时接口到本地 `127.0.0.1:18014`。页面采用 hash 路由，便于部署到 `/dashboard`。

## 常用命令

环境初始化：

```bash
bash scripts/setup_autodl.sh
```

公开数据合并训练：

```bash
PYTHONPATH=src python scripts/run_public_corpus_training.py \
  --run-name public_merged \
  --kinematic-feature-set v2 \
  --runtime-config-template configs/runtime_room.yaml \
  --train
```

三数据集合并训练：

```bash
PYTHONPATH=src python scripts/run_public_plus_ur_training.py \
  --python /root/autodl-tmp/envs/huling/bin/python \
  --data-root /root/autodl-tmp/huling-data \
  --run-name public_plus_ur_v1 \
  --kinematic-feature-set v2 \
  --runtime-config-template configs/runtime_room.yaml \
  --train
```

整轮实验编排：

```bash
PYTHONPATH=src python scripts/run_public_plus_ur_experiment.py \
  --python /root/autodl-tmp/envs/huling/bin/python \
  --data-root /root/autodl-tmp/huling-data \
  --run-name public_plus_ur_v1 \
  --kinematic-feature-set v2 \
  --prepare-ur \
  --finalize-ur \
  --train \
  --package-release \
  --resume \
  --batch-manifest /root/autodl-tmp/huling-data/eval/batch_videos.json \
  --batch-output-dir /root/autodl-tmp/huling-data/eval_outputs/public_plus_ur_v1 \
  --write-video
```

运行时批量视频推理：

```bash
PYTHONPATH=src python -m huling_guard.cli run-release-video-batch \
  --release-dir /path/to/release \
  --manifest /path/to/batch_manifest.json \
  --output-dir /path/to/output \
  --write-video
```

## 代码质量要求

- 不引入备用模型栈
- 不保留双路线切换
- 不在运行时链路中混用不同坐标语义
- 所有整轮实验均要求生成摘要、对比、发布包校验和完成检查
- 所有运行时变更必须保持接口可测、归档可用、页面可读

## 文档

- [系统架构](/D:/code/myproject/docs/architecture.md)
- [系统设计说明](/D:/code/myproject/docs/项目设计说明.md)
- [开源对标与方向校验](/D:/code/myproject/docs/开源对标与方向校验.md)
