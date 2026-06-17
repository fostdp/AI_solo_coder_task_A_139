
# 古代咸阳宫夯土墙抗风蚀仿真与加固方案优化系统

秦咸阳宫遗址夯土墙保护研究全栈应用系统。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                        前端 (HTML5)                       │
│  ┌─────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │ Three.js│  │ Canvas 2D  │  │ Chart.js / Paho MQTT │  │
│  │ 3D模型  │  │ 风场粒子   │  │ 数据图表 / 告警推送   │  │
│  └─────────┘  └────────────┘  └──────────────────────┘  │
└─────────────────────────────┬───────────────────────────┘
                              │ HTTP / WebSocket
                              ▼
┌─────────────────────────────────────────────────────────┐
│                   后端 (Python FastAPI)                  │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │
│  │ 风蚀仿真   │  │ TOPSIS评估 │  │  MQTT告警服务     │   │
│  │ 模型服务   │  │ 优化服务   │  │  (paho-mqtt)      │   │
│  └────────────┘  └────────────┘  └──────────────────┘   │
└─────────────────────────────┬───────────────────────────┘
                              │ SQLAlchemy Async
                              ▼
┌─────────────────────────────────────────────────────────┐
│                  时序数据库 (TimescaleDB)                │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │
│  │ 超表      │  │ 连续聚合  │  │  空间索引        │   │
│  │ (Hypertable) │  (Continuous │                    │   │
│  └────────────┘  │  Aggregate) │  └──────────────────┘   │
│                  └────────────┘                          │
└─────────────────────────────────────────────────────────┘
                              ▲
                              │ 4G DTU / MQTT
                        ┌─────┴─────┐
                        │  传感器   │
                        │  模拟器   │
                        └───────────┘
```

## 核心功能

### 1. 风蚀仿真模型
- 基于**风沙两相流理论**和**颗粒撞击理论**
- 计算起动摩阻风速（Shields参数）
- 风沙输运率公式（Bagnold型）
- 考虑硬度因子、湿度因子、颗粒形状因子
- 支持气候变化因子的未来预测

### 2. 加固方案优化 (TOPSIS)
- 支持硅酸乙酯(TEOS)、糯米灰浆等5种加固材料
- 渗透深度计算模型（考虑硬度、湿度、施工压力）
- 多目标决策指标：加固效果、渗透深度、耐用年限、成本、施工难度、环保性
- 自动生成5种加固方案并排序

### 3. 实时监测与告警
- 每小时通过4G DTU上报数据
- 风蚀速率超过0.5mm/年触发预警
- 裂缝扩展监测告警
- MQTT实时推送（支持三级告警级别）

### 4. 三维可视化
- Three.js夯土墙参数化建模（8段墙体）
- 风蚀区域颜色标注（绿-橙-红渐变）
- 风场流线粒子系统（500个粒子）
- Canvas动态纹理生成

## 目录结构

```
AI_solo_coder_task_A_139/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI主应用
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   ├── models/
│   │   ├── __init__.py
│   │   ├── orm.py              # SQLAlchemy ORM模型
│   │   └── schemas.py          # Pydantic数据模型
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── wall_segments.py    # 墙体段管理API
│   │   ├── sensor_data.py      # 传感器数据API
│   │   ├── erosion.py          # 风蚀仿真API
│   │   ├── reinforcement.py    # 加固方案API
│   │   ├── alerts.py           # 告警管理API
│   │   ├── wind_field.py       # 风场可视化API
│   │   └── statistics.py       # 统计数据API
│   └── services/
│       ├── __init__.py
│       ├── erosion_model.py    # 风蚀仿真核心模型
│       ├── topsis_optimizer.py # TOPSIS评估器
│       └── mqtt_alert.py       # MQTT告警服务
├── database/
│   └── init.sql                # TimescaleDB初始化脚本
├── frontend/
│   ├── index.html              # 主页面
│   ├── css/
│   │   └── style.css           # 样式文件
│   └── js/
│       ├── wall3d.js           # Three.js 3D模型
│       ├── windField.js        # 风场粒子可视化
│       ├── dataCharts.js       # 数据图表
│       └── main.js             # 主页面逻辑
├── simulator/
│   └── sensor_simulator.py     # 4G DTU传感器模拟器
├── requirements.txt            # Python依赖
├── .env                        # 环境变量
└── README.md                   # 本文件
```

## 快速开始

### 1. 环境准备

#### 1.1 安装数据库

**PostgreSQL + TimescaleDB:**

```bash
# Docker方式（推荐）
docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=rammed_earth_wall \
  timescale/timescaledb:latest-pg16

# 或本地安装
# 参考: https://docs.timescale.com/install/latest/
```

**初始化数据库:**

```bash
# 连接数据库
psql -h localhost -U postgres -d rammed_earth_wall

# 执行初始化脚本
\i d:/SOLO-2/AI_solo_coder_task_A_139/database/init.sql
```

#### 1.2 安装MQTT Broker

```bash
# Eclipse Mosquitto (Docker方式)
docker run -d --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto:latest
```

#### 1.3 安装Python依赖

```bash
cd d:/SOLO-2/AI_solo_coder_task_A_139
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件：

```env
# 数据库连接
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rammed_earth_wall

# MQTT配置
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC=wall/alert
MQTT_USERNAME=
MQTT_PASSWORD=

# 告警阈值
EROSION_THRESHOLD=0.5
CRACK_THRESHOLD=0.1

# API配置
API_HOST=0.0.0.0
API_PORT=8000

# 墙体段配置
WALL_SEGMENTS=8
```

### 3. 启动系统

#### 3.1 启动后端服务

```bash
cd d:/SOLO-2/AI_solo_coder_task_A_139
python -m backend.main
```

服务启动后访问：
- 主页面: http://localhost:8000
- API文档: http://localhost:8000/docs
- 前端页面: http://localhost:8000/frontend/index.html

#### 3.2 启动传感器模拟器

新终端窗口：

```bash
cd d:/SOLO-2/AI_solo_coder_task_A_139
python -m simulator.sensor_simulator
```

模拟器将：
- 模拟8段墙体的传感器数据
- 每小时上报一次（可配置）
- 包含季节因子和日变化因子
- 支持生成历史数据

### 4. 系统使用

#### 4.1 生成历史数据

方式一：通过模拟器
```bash
python -m simulator.sensor_simulator --generate-history --hours 720
```

方式二：通过API
```bash
curl -X POST http://localhost:8000/api/sensor-data/generate-history \
  -H "Content-Type: application/json" \
  -d '{"hours": 720}'
```

#### 4.2 运行风蚀仿真

1. 打开前端页面 http://localhost:8000/frontend/index.html
2. 选择"风蚀仿真"标签页
3. 设置预测年限和气候变化因子
4. 点击"运行仿真"

#### 4.3 评估加固方案

1. 选择"加固方案"标签页
2. 设置土体含水量、表面硬度、施工压力参数
3. 点击"TOPSIS评估"
4. 查看方案排序和推荐结果

#### 4.4 查看数据图表

选择"数据图表"标签页，查看：
- 风蚀深度趋势
- 风速变化趋势
- 各段风蚀速率对比
- 风险等级分布
- 含水量变化
- 硬度变化趋势

## API接口说明

### 墙体段管理
- `GET /api/wall-segments` - 获取所有墙体段
- `GET /api/wall-segments/{id}` - 获取指定墙体段详情
- `GET /api/wall-segments/{id}/status` - 获取墙体段实时状态

### 传感器数据
- `POST /api/sensor-data` - 上报单条传感器数据
- `POST /api/sensor-data/batch` - 批量上报传感器数据
- `GET /api/sensor-data/query` - 查询历史数据
- `POST /api/sensor-data/generate-history` - 生成历史数据

### 风蚀仿真
- `POST /api/erosion/predict` - 风蚀预测
- `POST /api/erosion/simulate` - 风沙两相流仿真
- `GET /api/erosion/rate/{segment_id}` - 获取风蚀速率

### 加固方案
- `GET /api/reinforcement/plans` - 获取加固方案列表
- `POST /api/reinforcement/evaluate` - TOPSIS评估
- `GET /api/reinforcement/materials` - 获取加固材料列表

### 告警管理
- `GET /api/alerts` - 获取告警列表
- `POST /api/alerts/{id}/acknowledge` - 确认告警
- `POST /api/alerts/test-mqtt` - 测试MQTT告警

### 风场可视化
- `GET /api/wind-field/streamlines` - 获取风场流线数据
- `POST /api/wind-field/generate` - 生成风场快照

### 统计数据
- `GET /api/statistics/dashboard` - 获取数据看板统计
- `GET /api/statistics/erosion-rates` - 获取各段风蚀速率

## 核心算法说明

### 风蚀速率计算

```
E = α * Q * K_h * K_m * K_s
其中:
- α: 风蚀系数
- Q: 风沙输运率 (Bagnold公式)
- K_h: 硬度因子 exp(-β*H)
- K_m: 湿度因子 exp(-γ*M)
- K_s: 颗粒形状因子
```

### 起动摩阻风速 (Shields参数)

```
u_τt = √(θ_t * (ρ_p - ρ_a) * g * d / ρ_a)
其中:
- θ_t: 临界Shields参数 (~0.03)
- ρ_p: 沙粒密度 (2650 kg/m³)
- ρ_a: 空气密度 (1.225 kg/m³)
- d: 沙粒粒径
```

### TOPSIS评估步骤

1. **矩阵归一化**: r_ij = x_ij / √Σx_ij²
2. **加权处理**: v_ij = w_j * r_ij
3. **确定理想解**: 正理想解S⁺，负理想解S⁻
4. **计算距离**: D_i⁺ = √Σ(v_ij - v_j⁺)², D_i⁻同理
5. **计算贴近度**: C_i = D_i⁻ / (D_i⁺ + D_i⁻)
6. **方案排序**: 按C_i降序排列

## 告警级别

| 级别 | 风蚀速率范围 | 颜色 | MQTT QoS |
|------|-------------|------|----------|
| warning | 0.5-0.8 mm/年 | 黄色 | 0 |
| danger | 0.8-1.2 mm/年 | 橙色 | 1 |
| critical | >1.2 mm/年 | 红色 | 2 |

## 技术栈

**后端:**
- Python 3.10+
- FastAPI 0.109+
- SQLAlchemy 2.0 (异步)
- TimescaleDB (PostgreSQL 16+)
- paho-mqtt
- NumPy / SciPy

**前端:**
- Three.js 0.160+
- Chart.js 4.4+
- Paho MQTT
- Canvas 2D

**数据库:**
- PostgreSQL 16
- TimescaleDB 2.13+

## 性能优化

1. **时序数据库优化**:
   - 使用Hypertable按天分区
   - 连续聚合视图（小时/天粒度）
   - 索引优化（time DESC, segment_id）

2. **前端优化**:
   - Canvas离屏渲染
   - 粒子系统对象池
   - 数据懒加载和虚拟滚动

3. **后端优化**:
   - 异步SQL查询
   - 连接池管理
   - 缓存热点数据

## 故障排查

### 数据库连接失败
```bash
# 检查PostgreSQL是否运行
docker ps | grep timescaledb

# 检查端口
netstat -ano | findstr :5432
```

### MQTT连接失败
```bash
# 检查Mosquitto是否运行
docker ps | grep mosquitto

# 测试MQTT连接
mosquitto_pub -h localhost -t "test" -m "hello"
```

### 前端无法加载3D模型
- 检查浏览器是否支持WebGL
- 查看控制台是否有Three.js错误
- 确认CDN资源可访问

## 开发计划

- [ ] 支持更多加固材料模型
- [ ] 添加有限元分析模块
- [ ] 移动端适配
- [ ] 数据导出功能
- [ ] 用户权限管理
- [ ] 多语言支持

## 许可证

本项目用于学术研究目的。

## 联系方式

考古团队：秦咸阳宫遗址保护研究中心
技术支持：文化遗产数字化保护实验室
