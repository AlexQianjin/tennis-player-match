网球约球匹配微信小程序
LLM 匹配服务接口设计文档
版本：V1.0  |  方案B：软性条件语义匹配  |  日期：2026年11月
1. 服务概述
本服务在规则引擎硬性过滤之后，对候选用户进行语义匹配打分
核心目标：理解打球风格、个人简介等自然语言偏好，提升推荐质量
采用混合架构：硬性条件由规则引擎保证，软性条件由 LLM 增强
支持降级：LLM 不可用时回退到纯规则排序
2. 整体架构
推荐请求 → 规则引擎硬过滤 → LLM 语义打分服务 → 综合排序 → 返回结果
硬过滤条件：NTRP ±0.5 + 时间重合 + 同一球场
LLM 输入：双方风格偏好 + 个人简介 + 期望条件
综合分数：信用分 30% + 等级接近度 30% + LLM 分 40%
3. 核心接口
3.1 单候选语义打分
POST /api/v1/llm/match/score
用途：对单个候选进行语义匹配打分
请求参数：
参数
类型
必填
说明
publisherId
string
是
发布方用户ID
candidateId
string
是
候选用户ID
publisherInfo
object
是
发布方资料（ntrp, style, bio, expectedNtrpMin/Max, genderPref）
candidateInfo
object
是
候选方资料（ntrp, style, bio）
响应示例：
{ code: 0, data: { score: 82, reason: "都偏好休闲双打，等级接近" } }
3.2 批量语义打分（推荐）
POST /api/v1/llm/match/batch-score
用途：一次调用对多个候选打分，降低延迟和成本
请求参数：
参数
类型
必填
说明
publisherId
string
是
发布方用户ID
publisherInfo
object
是
发布方资料
candidates
array
是
候选列表，每项含 candidateId 和 candidateInfo
响应示例：
{ code: 0, data: { results: [{ candidateId: "xxx", score: 82, reason: "..." }, ...] } }
3.3 集成到推荐列表
GET /api/v1/match/recommend
在原有推荐接口内部调用 LLM 服务，对硬过滤后的候选进行语义打分后综合排序
返回结果新增字段：llmScore、matchReason、finalScore
4. Prompt 设计
4.1 单候选 Prompt
你是一个网球约球匹配助手。请根据以下信息判断两人是否适合一起打球，重点考虑打球风格、个人简介中的偏好和期望是否匹配。

【发布方】
- NTRP等级：{publisher_ntrp}
- 打球风格：{publisher_style}
- 个人简介：{publisher_bio}
- 期望对手等级：{expected_range}
- 性别偏好：{gender_pref}

【候选方】
- NTRP等级：{candidate_ntrp}
- 打球风格：{candidate_style}
- 个人简介：{candidate_bio}

请输出严格的 JSON 格式：
{"score": 0到100的整数, "reason": "不超过30字的匹配理由"}
4.2 评分标准
分数区间
含义
说明
90-100
高度契合
风格和偏好几乎完全匹配
70-89
基本合适
主要偏好匹配，存在少量差异
50-69
勉强可以
有一定匹配度，但差异较明显
0-49
不太合适
风格或偏好存在较大冲突
5. 综合排序公式
finalScore = 0.3 * creditNorm + 0.3 * ntrpCloseness + 0.4 * (llmScore / 100)
creditNorm：信用分归一化（建议除以历史最大值或固定上限）
ntrpCloseness：1 - |ntrp差| / 0.5（差值为0时为1，差值为0.5时为0）
权重可配置，建议初始值如上
6. 缓存策略
缓存键：publisher_id + candidate_id
缓存时间：建议 3-7 天
缓存表：llm_match_cache
优先查缓存，未命中再调用 LLM
6.1 缓存表结构
字段名
类型
说明
id
VARCHAR(32)
主键
publisher_id
VARCHAR(32)
发布方ID
candidate_id
VARCHAR(32)
候选方ID
llm_score
INT
LLM 分数
reason
VARCHAR(100)
匹配理由
expire_time
DATETIME
过期时间
create_time
DATETIME
创建时间
唯一索引：UNIQUE(publisher_id, candidate_id)
7. 降级与异常处理
异常场景
处理方式
LLM 服务超时（>3秒）
回退到纯规则排序，不返回 matchReason
LLM 返回格式错误
记录日志，使用默认分数 50，reason 为空
LLM 服务不可用
直接使用规则排序，接口正常返回
候选数量过多（>20）
只对前 20 个调用 LLM，其余按规则分排序
缓存命中
直接使用缓存结果，不调用 LLM
8. 成本与性能控制
优先使用批量接口，减少调用次数
只对硬过滤后的候选调用 LLM
设置每日调用上限（可按用户或全局）
使用缓存大幅降低重复调用
选择延迟低、价格合理的模型
9. 与现有系统集成点
推荐列表接口（/match/recommend）内部调用 LLM 服务
用户资料变更时，可选择性清除相关缓存
前端展示 matchReason 作为推荐理由
后台可配置权重和是否启用 LLM
10. 后续优化方向
用户画像预计算（离线生成风格标签）
根据实际匹配成功率调整权重
支持更多软性维度（年龄偏好、历史约球反馈等）
A/B 测试不同 Prompt 和权重组合
—— 文档结束 ——