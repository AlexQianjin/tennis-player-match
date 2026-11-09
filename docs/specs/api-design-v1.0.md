网球约球匹配微信小程序
接口设计文档（API Design）
版本：V1.0  |  基础路径：/api/v1  |  认证方式：微信登录态
1. 通用规范
请求方式：RESTful，主要使用 GET / POST
数据格式：JSON
认证：通过微信登录获取 token，后续请求携带 Authorization: Bearer {token}
通用响应格式：{ code: 0, message: "success", data: {} }
错误码：0=成功，400=参数错误，401=未登录，403=无权限，404=资源不存在，500=服务器错误
2. 用户相关接口
2.1 微信登录
POST /api/v1/auth/login
请求参数：
参数
类型
必填
说明
code
string
是
微信登录凭证
响应示例：
{ code: 0, data: { token: "xxx", isNewUser: true, userInfo: {...} } }
2.2 获取/更新个人资料
GET /api/v1/user/profile
返回当前用户完整资料
POST /api/v1/user/profile
请求参数：
参数
类型
必填
说明
nickname
string
否
昵称
ntrp
float
否
NTRP等级（需检查冷却期）
gender
string
否
性别
age
int
否
年龄
city
string
否
城市
style
string
否
打球风格
bio
string
否
简介
3. 球场相关接口
3.1 获取城市球场列表
GET /api/v1/courts
请求参数：
参数
类型
必填
说明
city
string
是
城市名称（武汉）
响应：球场列表（id, name, address, district）
4. 约球发布与推荐接口
4.1 发布约球
POST /api/v1/match/publish
请求参数：
参数
类型
必填
说明
date
string
是
开始日期 YYYY-MM-DD，今天起 30 天内
startTime
string
是
开始时间 HH:MM（北京时间，必须晚于现在）
endTime
string
是
结束时间 HH:MM。不晚于开始时间时表示次日结束。时长 30 分钟到 8 小时
courtId
string
是
球场ID
playerCount
int
是
1=单打 2=双打
expectedNtrpMin
float
否
期望最低等级
expectedNtrpMax
float
否
期望最高等级
genderPref
string
否
性别偏好
业务规则：同时只能发布一个进行中的约球
4.2 获取推荐列表
GET /api/v1/match/recommend
请求参数：
参数
类型
必填
说明
city
string
是
城市
ntrpMin
float
否
筛选等级下限
ntrpMax
float
否
筛选等级上限
gender
string
否
性别筛选
date
string
否
日期筛选
courtId
string
否
球场筛选
page
int
否
页码，默认1
pageSize
int
否
每页条数，默认10
排序规则：信用分高优先 + NTRP更接近优先
4.3 约球详情
GET /api/v1/match/detail/{id}
返回发布者信息 + 约球详情 + 当前用户申请状态
5. 申请与匹配接口
5.1 申请加入
POST /api/v1/match/apply
参数
类型
必填
说明
requestId
string
是
约球需求ID
5.2 处理申请（同意/拒绝）
POST /api/v1/match/handle
参数
类型
必填
说明
applicationId
string
是
申请记录ID
action
string
是
agree / reject
5.3 取消约球
POST /api/v1/match/cancel
参数
类型
必填
说明
requestId
string
是
约球需求ID
业务规则：匹配成功后双方均可取消，记录取消次数
6. 我的约球接口
6.1 我的约球列表
GET /api/v1/match/my
参数
类型
必填
说明
type
string
是
published / applied / matched
status
string
否
pending / confirmed / completed / cancelled
page
int
否
页码
7. 到场确认与评分接口
7.1 确认已到场
POST /api/v1/match/arrive
参数
类型
必填
说明
requestId
string
是
约球需求ID
业务规则：仅在约定时间后可点击，双方都点击后才算确认
7.2 提交评分
POST /api/v1/match/rate
参数
类型
必填
说明
requestId
string
是
约球需求ID
rating
int
是
1-5星
业务规则：仅在双方都确认到场后可评分，公开展示平均分
8. 状态流转说明
待匹配 → 已匹配（发布方同意申请）
已匹配 → 已完成（双方都点击已到场）
已匹配 → 已取消（任意一方取消，或24小时无人确认自动取消）
待匹配 → 已取消（发布方主动取消）
9. 接口汇总
模块
接口
方法
说明
认证
/auth/login
POST
微信登录
用户
/user/profile
GET/POST
获取/更新资料
球场
/courts
GET
获取球场列表
约球
/match/publish
POST
发布约球
约球
/match/recommend
GET
推荐列表
约球
/match/detail/{id}
GET
约球详情
匹配
/match/apply
POST
申请加入
匹配
/match/handle
POST
同意/拒绝
匹配
/match/cancel
POST
取消约球
我的
/match/my
GET
我的约球列表
到场
/match/arrive
POST
确认已到场
评分
/match/rate
POST
提交评分
—— 文档结束 ——