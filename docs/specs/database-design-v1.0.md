网球约球匹配微信小程序
数据库表结构详细设计
版本：V1.0  |  建议数据库：MySQL 8.0+  |  字符集：utf8mb4
1. 设计原则
主键统一使用雪花算法生成的字符串ID（或自增BIGINT）
所有表包含 create_time、update_time 字段
软删除：使用 is_deleted 字段（0正常 1已删除）
信用分通过 confirm_count - cancel_count 计算，不单独存储冗余值（也可冗余存储便于排序）
NTRP 等级使用 DECIMAL(2,1) 存储
2. 用户表 user
存储用户基本信息与信用相关数据
字段名
类型
约束
说明
id
VARCHAR(32)
PK
用户ID
openid
VARCHAR(64)
UNIQUE, NOT NULL
微信openid
nickname
VARCHAR(64)
NOT NULL
昵称
avatar
VARCHAR(512)

头像URL
ntrp
DECIMAL(2,1)
NOT NULL
NTRP等级 1.0-7.0
gender
TINYINT
NOT NULL
1男 2女
age
INT

年龄
city
VARCHAR(32)
NOT NULL
城市
style
VARCHAR(32)

打球风格偏好
bio
VARCHAR(500)

个人简介
confirm_count
INT
DEFAULT 0
确认到场次数
cancel_count
INT
DEFAULT 0
取消次数
avg_rating
DECIMAL(2,1)
DEFAULT 0
平均评分
rating_count
INT
DEFAULT 0
评分次数
ntrp_update_time
DATETIME

上次修改NTRP时间
create_time
DATETIME
NOT NULL
创建时间
update_time
DATETIME
NOT NULL
更新时间
is_deleted
TINYINT
DEFAULT 0
是否删除
索引建议：UNIQUE(openid)，INDEX(city)，INDEX(ntrp)
3. 球场表 court
字段名
类型
约束
说明
id
VARCHAR(32)
PK
球场ID
name
VARCHAR(100)
NOT NULL
球场名称
city
VARCHAR(32)
NOT NULL
城市
district
VARCHAR(32)

区域
address
VARCHAR(255)
NOT NULL
详细地址
latitude
DECIMAL(10,6)

纬度
longitude
DECIMAL(10,6)

经度
create_time
DATETIME
NOT NULL
创建时间
is_deleted
TINYINT
DEFAULT 0
是否删除
索引建议：INDEX(city)
4. 约球需求表 match_request
字段名
类型
约束
说明
id
VARCHAR(32)
PK
约球ID
publisher_id
VARCHAR(32)
NOT NULL, FK
发布者用户ID
court_id
VARCHAR(32)
NOT NULL, FK
球场ID
date
DATE
NOT NULL
约球日期
time_slot
VARCHAR(32)
NOT NULL
时段 如14:00-16:00
player_count
TINYINT
NOT NULL
1单打 2双打
expected_ntrp_min
DECIMAL(2,1)

期望最低等级
expected_ntrp_max
DECIMAL(2,1)

期望最高等级
gender_pref
TINYINT
DEFAULT 0
0不限 1男 2女
status
TINYINT
NOT NULL
1待匹配 2已匹配 3已完成 4已取消
matched_user_id
VARCHAR(32)

匹配成功的用户ID
create_time
DATETIME
NOT NULL
发布时间
update_time
DATETIME
NOT NULL
更新时间
is_deleted
TINYINT
DEFAULT 0
是否删除
索引建议：INDEX(publisher_id)，INDEX(status, date)，INDEX(court_id, date)
业务规则：同一用户同时只能有一个 status in (1,2) 的记录
5. 申请记录表 application
字段名
类型
约束
说明
id
VARCHAR(32)
PK
申请ID
request_id
VARCHAR(32)
NOT NULL, FK
约球需求ID
applicant_id
VARCHAR(32)
NOT NULL, FK
申请者用户ID
status
TINYINT
NOT NULL
1待处理 2已同意 3已拒绝 4已取消
apply_time
DATETIME
NOT NULL
申请时间
handle_time
DATETIME

处理时间
create_time
DATETIME
NOT NULL
创建时间
索引建议：UNIQUE(request_id, applicant_id)，INDEX(applicant_id, status)
6. 到场确认与评分表 attendance
字段名
类型
约束
说明
id
VARCHAR(32)
PK
记录ID
request_id
VARCHAR(32)
NOT NULL, FK
约球需求ID
user_id
VARCHAR(32)
NOT NULL, FK
用户ID
arrived
TINYINT
DEFAULT 0
0未确认 1已确认
arrived_time
DATETIME

确认到场时间
rating
TINYINT

评分 1-5
rating_time
DATETIME

评分时间
create_time
DATETIME
NOT NULL
创建时间
索引建议：UNIQUE(request_id, user_id)
业务规则：双方 arrived=1 后才允许填写 rating，并触发信用分更新
7. 表关系说明
user 1 : N match_request（一个用户可发布多个约球，但同时仅一个进行中）
user 1 : N application（一个用户可申请多个约球）
match_request 1 : N application（一个约球可被多人申请）
match_request 1 : 2 attendance（一个约球对应双方的到场记录）
court 1 : N match_request（一个球场可有多个约球）
8. 信用分计算逻辑
信用分 = confirm_count - cancel_count（最低为0）
双方都确认到场后：双方 confirm_count +1
匹配成功后取消：取消方 cancel_count +1
24小时无人确认自动取消：不增加 cancel_count
推荐排序时优先使用 credit_score = confirm_count - cancel_count
9. 关键索引汇总
表名
索引
用途
user
UNIQUE(openid)
登录查询
user
INDEX(city, ntrp)
推荐筛选
match_request
INDEX(status, date)
推荐列表
match_request
INDEX(publisher_id, status)
我的发布
application
UNIQUE(request_id, applicant_id)
防重复申请
attendance
UNIQUE(request_id, user_id)
到场确认
—— 文档结束 ——