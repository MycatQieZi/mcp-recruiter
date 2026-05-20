# MCP Recruiter — 技术方案招聘系统

用 HR 招聘流程自动化评估和筛选市场上的 MCP 工具/API/Agent/Skill 候选方案。

```
你的需求 → 交互式 TUI → 海选 → 初试 → 笔试(沙盒) → 终面报告 → 推荐决策
```

## 概念

| HR 环节 | 系统阶段 | 做什么 |
|---------|---------|--------|
| JD 发布 | 需求定义 | 通过交互式 TUI 描述你的需求，自动生成结构化职位描述 |
| 海选 | Sea Selection | 从 GitHub / npm / MCP Hub 多源搜索，生成标准化简历 |
| 初试 | Screening | 硬性条件过滤 + 三维度加权打分，选出 Top N |
| 笔试 | Written Test | Docker/子进程沙盒中执行测试用例，记录延迟和质量 |
| 终面 | Final Report | 复合评分 → 排名表 → 雷达图 → HTML 报告 → 录用建议 |

## 快速开始

### 安装

```bash
# Python >= 3.11
git clone https://github.com/<your-org>/mcp-recruiter.git
cd mcp-recruiter
pip install -e .

# 可选：沙盒测试依赖 (Docker)
pip install -e ".[sandbox]"
```

### 使用

**方式一：交互式创建 + 一键运行**

```bash
# 自动引导创建 JD，然后运行全流程
mcp-recruiter run
```

**方式二：使用已有 JD 文件运行**

```bash
mcp-recruiter run -j examples/job_description_demo.yaml --skip-test
```

**方式三：分阶段执行**

```bash
mcp-recruiter create-job -o my_jd.yaml    # 只创建 JD
mcp-recruiter run -j my_jd.yaml --skip-test # 使用该 JD 运行
```

**完整参数**

```bash
mcp-recruiter run \
  --job examples/job_description.yaml \  # JD 文件（可选，不提供则交互创建）
  --query "filesystem search" \           # 搜索关键词
  --config config.yaml \                  # 配置文件
  --skip-test                             # 跳过沙盒测试
```

### 编写 JD（职位描述）

JD 文件是 YAML 格式。通过 `mcp-recruiter create-job` 交互生成，也可以手写：

```yaml
title: "文件系统 MCP 服务器"

problem_statement: >
  需要一个提供文件读写和搜索能力的 MCP 服务器

required_capabilities:
  - "file"
  - "search"
  - "filesystem"

hard_requirements:
  min_stars: 5
  max_days_since_update: 180
  min_tool_count: 2
  require_license: true

scoring_weights:
  preset: balanced   # balanced | perf_first | community_first | quick_scan

top_n_candidates: 5

test_scenarios:
  - name: "基本功能验证"
    test_cases:
      - name: "列举工具"
        mcp_tool_name: "tools/list"
        expected_behavior: "no_error"
```

## 项目结构

```
mcp-recruiter/
├── pyproject.toml                     # 项目元数据和依赖
├── src/mcp_recruiter/
│   ├── main.py                        # 入口
│   ├── cli/
│   │   ├── pipeline.py                # CLI 命令 + 全流程编排
│   │   └── interactive.py             # 交互式 JD 创建 TUI
│   ├── core/                          # 数据模型、状态机、持久化
│   │   ├── models.py                  # Pydantic 模型 (JD/Resume/ScoreCard)
│   │   ├── enums.py                   # 枚举
│   │   ├── state.py                   # 阶段状态机
│   │   ├── store.py                   # JSON 持久化
│   │   └── config.py                  # 配置加载
│   ├── registry/                      # 海选 — 多源搜索
│   │   ├── github_source.py           # GitHub API
│   │   ├── npm_source.py              # npm registry
│   │   ├── mcp_hub_source.py          # MCP Hub 社区索引
│   │   ├── aggregator.py              # 聚合 + 去重
│   │   └── cache.py                   # TTL 缓存
│   ├── screening/                     # 初试 — 筛选
│   │   ├── hard_filter.py             # 硬性条件过滤
│   │   ├── soft_scorer.py             # 软性加权打分
│   │   └── resume_builder.py          # 简历生成
│   ├── sandbox/                       # 笔试 — 沙盒测试
│   │   ├── manager.py                 # 子进程 + Docker 管理
│   │   ├── test_runner.py             # 测试编排
│   │   ├── scenario_loader.py         # 场景加载
│   │   └── capture.py                 # 结果采集
│   ├── scoring/                       # 评分引擎
│   │   ├── engine.py                  # 复合评分 + 排名
│   │   ├── factors.py                 # 评分因子
│   │   ├── normalizers.py             # 归一化器
│   │   └── weights.py                 # 权重预设
│   ├── reporting/                     # 报告输出
│   │   ├── terminal_render.py         # Rich 终端报告
│   │   ├── html_render.py             # HTML + Chart.js
│   │   └── templates/                 # Jinja2 模板
│   └── extensions/                    # 扩展点
│       ├── base.py                    # CandidateType 抽象接口
│       ├── mcp_tool.py                # MCP Tool 处理器
│       └── registry.py                # 类型注册中心
├── examples/
│   ├── job_description.yaml           # 严格版样例 JD
│   ├── job_description_demo.yaml      # 演示版样例 JD
│   └── test_scenario.yaml             # 独立测试场景
└── reports/                           # 生成的 HTML 报告
```

## 评分算法

### 四维评分

```
composite = w_cap * capability + w_health * health + w_eco * ecosystem + w_test * test_score
```

| 维度 | 因子 | 数据来源 |
|------|------|---------|
| 能力 | 工具数量、能力匹配度 (Jaccard)、资源数 | Resume |
| 健康 | Stars、Issue 比例、更新频率、贡献者数 | GitHub |
| 生态 | 依赖项目数、文档质量、周下载量 | npm / GitHub |
| 测试 | 成功率、P95 延迟、输出质量 | 沙盒执行 |

### 权重预设

| 预设 | 能力 | 健康 | 生态 | 测试 | 适用场景 |
|------|------|------|------|------|---------|
| balanced | 25% | 25% | 25% | 25% | 综合评估 |
| perf_first | 20% | 15% | 15% | 50% | 性能优先 |
| community_first | 20% | 30% | 30% | 20% | 社区长期维护考量 |
| quick_scan | 60% | 10% | 20% | 10% | 海选阶段快速筛选 |

## 扩展

### 支持新的候选类型

实现 `CandidateTypeHandler` 抽象接口，通过 Python entry point 注册：

```python
# my_plugin/agent_handler.py
from mcp_recruiter.extensions.base import CandidateTypeHandler

class AgentHandler(CandidateTypeHandler):
    @property
    def candidate_type(self) -> CandidateType:
        return CandidateType.AGENT

    def build_resume(self, raw_metadata: dict) -> Resume:
        # ... 自定义简历生成逻辑
```

未来计划支持的类型：API、Agent、Skill。

### 自定义评分因子

通过 `mcp_recruiter.scoring_factors` entry point 注册自定义评分维度。

## 技术栈

| 类别 | 库 |
|------|---|
| CLI | Typer + Rich |
| 数据模型 | Pydantic v2 |
| HTTP | httpx |
| 沙盒 | subprocess / Docker SDK (可选) |
| 模板 | Jinja2 |
| 持久化 | JSON (内建) / SQLite (可选) |
| 测试 | pytest |

## License

MIT
