# 护龄智守

护龄智守是一套面向单房间固定摄像头场景的安全值守系统。系统以连续视频输入为基础，持续输出人员状态、风险变化、事件记录、会话摘要和历史归档，用于支持日常值守、异常处置和事后追溯。

## 1. 系统定位

系统只保留一条主技术路线：

`姿态估计 -> 时序状态识别 -> 事件引擎 -> 运行时服务 -> 历史归档`

系统不以单帧结果作为最终输出，而是以连续状态流、事件流和会话流作为主要交付对象。

当前系统支持两类输入形态：

- `实时接入`：通过摄像头、RTSP 或其他连续视频流接入运行时服务。
- `模拟监看`：在没有真实摄像头时，以固定机位样例视频模拟真实监看终端，完整演示推理、事件、归档和回看流程。

## 2. 主要能力

### 2.1 识别能力

系统当前输出五类状态：

- `normal`
- `near_fall`
- `fall`
- `recovery`
- `prolonged_lying`

在此基础上进一步生成以下事件：

- 高风险失衡提示
- 跌倒事件
- 长时间卧倒事件
- 恢复事件

### 2.2 应用能力

运行时界面固定为三页：

- `实时值守`：主屏展示监看画面、当前结论、建议动作、最近提醒和本段过程。
- `历史回看`：展示已归档记录、筛选条件、过程回放、关键阶段和关键时刻。
- `系统信息`：展示系统用途、状态定义、识别链路、运行参数和质量控制原则。

前端同时提供两种显示层次：

- `值守视图`：面向值守人员，优先回答当前是否安全、是否需要过去、最近发生了什么。
- `引擎透视`：展示状态分布、风险变化、骨架质量和运行参数，用于调试、复核和技术说明。

### 2.3 工程能力

- 单视频推理
- 批量视频推理
- 发布包部署
- 会话归档与历史回看
- 误报复查与区间标签回灌
- 定向再训练

## 3. 技术架构

系统采用单一路线架构：

1. `RTMO`
   负责逐帧人体姿态估计，输出 17 点骨架与关键点置信度。
2. `Grounding DINO + SAM 2`
   仅用于离线房间区域初始化，生成床、沙发、地面活动区和风险边缘等房间先验。
3. `Scene-Pose Temporal Net`
   融合骨架序列、运动学特征和场景关系特征，对时间窗进行五分类判断。
4. `EventEngine`
   将连续状态流稳定为业务事件流。
5. `FastAPI + SQLite + Vue + Docker`
   提供运行时接口、历史归档、前端页面和标准化部署封装。

## 4. 训练与交付边界

### 4.1 训练环境

训练环境使用 GPU 服务器，职责包括：

- 公开数据准备与骨架抽取
- 模型训练与评估
- 批量视频验证
- 导出运行时发布包

### 4.2 交付环境

最终交付不依赖训练服务器。标准交付形态为：

- `runtime-release/`：发布包，包含模型权重、运行时配置和发布清单
- `runtime-demo/`：模拟监看数据，包含视频、会话报告和预测结果
- `runtime-data/`：运行时归档目录
- `docker-compose.runtime.yml`：本机 Docker 启动入口

也就是说，训练机负责产出物，最终运行环境以本机 Docker 版运行时为准。

## 5. 数据与训练流程

当前训练主线以公开视频集为基础，包括 `CaucaFall`、`UP_Fall` 和 `UR Fall`。数据进入系统后遵循统一流程：

1. 生成原始视频 manifest
2. 使用 `RTMO` 离线抽取骨架
3. 构建特征缓存与时间窗
4. 训练 `Scene-Pose Temporal Net`
5. 进行窗口级、样本级、事件级和应用级评估
6. 打包发布并执行批量视频验证

训练前强制检查 `raw manifest -> pose manifest` 覆盖率，覆盖不完整时直接终止，避免残缺样本进入训练主链。

在没有真实摄像头和新增实拍数据的阶段，训练主线默认启用骨架时序增强，包括：

- 时间窗抖动
- 短时遮挡
- 骨架噪声
- 关键点置信度缺失模拟

## 6. 运行时接口

运行时服务提供以下接口与页面：

- `GET /dashboard`
- `GET /health /meta /system-profile`
- `GET /summary /timeline /state /incidents /session-report`
- `GET /archives /archives/summary /archives/{session_id}`
- `GET /demo-videos /demo-sessions/{filename}`
- `GET /live-source /live-frame`
- `POST /pose-frame /live-frame`

## 7. 仓库结构

```text
configs/                    训练配置与运行时配置
docs/                       架构文档与系统设计文档
scripts/                    数据准备、训练编排、评估与发布脚本
src/huling_guard/           主代码
frontend/                   Vue 前端
tests/                      纯逻辑测试
```

## 8. 部署方式

### 8.1 本机 Docker 启动

```bash
docker compose -f docker-compose.runtime.yml up --build
```

默认页面地址：

- [实时值守](http://127.0.0.1:18014/dashboard#/live)
- [历史回看](http://127.0.0.1:18014/dashboard#/records)
- [系统信息](http://127.0.0.1:18014/dashboard#/system)

默认挂载目录：

- `runtime-release/`
- `runtime-demo/`
- `runtime-data/`

相关路径可通过 [`.env.runtime.example`](/mnt/d/code/myproject/.env.runtime.example) 中的以下变量调整：

- `HULING_RELEASE_DIR`
- `HULING_RUNTIME_DATA_DIR`
- `HULING_DEMO_DIR`
- `HULING_RUNTIME_PORT`

### 8.2 本机直接启动

```bash
PYTHONPATH=src python -m huling_guard.cli serve-release   --release-dir /path/to/release   --frontend-dist /path/to/frontend/dist   --archive-root /path/to/archive   --host 0.0.0.0   --port 8014
```

### 8.3 构建参数

Docker 版默认采用 CPU 推理镜像。以下变量用于控制构建来源：

- `HULING_RUNTIME_BASE_IMAGE`
- `HULING_PIP_INDEX_URL`
- `HULING_PIP_EXTRA_INDEX_URL`
- `HULING_TORCH_INDEX_URL`
- `HULING_TORCH_VERSION`

## 9. 前端开发

前端本地开发入口：

```bash
cd frontend
npm run typecheck
npm run build
npx vite --host 127.0.0.1 --port 4174
```

开发模式下，Vite 代理运行时接口到本地 `127.0.0.1:18014`。

## 10. 常用命令

环境初始化：

```bash
bash scripts/setup_autodl.sh
```

公开数据合并训练：

```bash
PYTHONPATH=src python scripts/run_public_corpus_training.py   --run-name public_merged   --kinematic-feature-set v2   --runtime-config-template configs/runtime_room.yaml   --train
```

三数据集合并训练：

```bash
PYTHONPATH=src python scripts/run_public_plus_ur_training.py   --python /root/autodl-tmp/envs/huling/bin/python   --data-root /root/autodl-tmp/huling-data   --run-name public_plus_ur_v1   --kinematic-feature-set v2   --runtime-config-template configs/runtime_room.yaml   --train
```

运行时批量视频推理：

```bash
PYTHONPATH=src python -m huling_guard.cli run-release-video-batch   --release-dir /path/to/release   --manifest /path/to/batch_manifest.json   --output-dir /path/to/output   --write-video
```

## 11. 工程约束

- 不引入备用模型栈
- 不保留双路线切换
- 不在运行时链路中混用不同坐标语义
- 不以窗口级分数单独决定主干升级
- 不以单次训练结果替代应用级验证
- 所有整轮实验必须生成摘要、对比、发布包校验和完成检查

## 12. 文档

- [系统架构](/mnt/d/code/myproject/docs/architecture.md)
- [系统设计说明](/mnt/d/code/myproject/docs/项目设计说明.md)
- [状态定义手册](/mnt/d/code/myproject/docs/状态定义手册.md)
- [开源对标与方向校验](/mnt/d/code/myproject/docs/开源对标与方向校验.md)
