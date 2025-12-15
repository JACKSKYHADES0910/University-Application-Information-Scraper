# Git Tag v1.2.0 发布信息

## 版本号
**v1.2.0**

## 标签名称
```bash
v1.2.0
```

## 发布标题
🎓 新增 PolyU 支持 + 修复 CityU Deadline Bug

## 发布说明 (Release Notes)

### 🌟 主要更新

#### ✨ 新增功能
- **新增香港理工大学 (PolyU) 爬虫支持**
  - 完整支持 Taught Postgraduate 项目列表页抓取
  - 智能过滤博士 (Doctor/PhD) 项目，可独立配置
  - 自动提取中英文项目名称
  - 准确抓取 Local/Non-Local 申请截止日期
  - 配置固定申请链接

#### 🐛 Bug 修复
- **修复 CityU 爬虫 deadline 抓取为空的问题**
  - 优化 deadline 提取策略,增加多重匹配逻辑
  - 改进 `prog_admission` 类定位精度
  - 增强 Non-local/Local 字段识别能力

#### 📝 文档更新
- 更新 README.md 支持学校矩阵
- 新增 CHANGELOG.md 版本历史记录

---

### 📊 当前支持学校

| 学校 | 状态 | 字段覆盖率 |
|:-----|:-----|:-----------|
| HKU | ✅ Stable | 100% |
| CUHK | ✅ Stable | 95% |
| CityU | ✅ Stable | 100% |
| **PolyU** | ✅ **NEW** | 100% |

---

## Git 命令参考

### 1. 创建标签
```bash
# 切换到主分支
git checkout main

# 拉取最新代码
git pull origin main

# 创建带注释的标签
git tag -a v1.2.0 -m "新增 PolyU 支持 + 修复 CityU Deadline Bug

主要更新:
- 新增香港理工大学 (PolyU) 爬虫
- 修复 CityU deadline 抓取为空的问题
- 更新文档和 README"
```

### 2. 推送标签
```bash
# 推送单个标签
git push origin v1.2.0

# 或推送所有标签
git push origin --tags
```

### 3. 查看标签
```bash
# 查看所有标签
git tag

# 查看标签详情
git show v1.2.0
```

### 4. 删除标签 (如需要)
```bash
# 删除本地标签
git tag -d v1.2.0

# 删除远程标签
git push origin --delete v1.2.0
```

---

## GitHub Release 描述模板

```markdown
## 🎓 v1.2.0 - 新增 PolyU 支持 + 修复 CityU Bug

### ✨ 新增功能
- 🏫 **新增香港理工大学 (PolyU) 爬虫支持**
  - 完整抓取 Taught Postgraduate 项目信息
  - 智能过滤博士项目 (Doctor/PhD)
  - 准确提取截止日期和申请链接

### 🐛 Bug 修复
- 🔧 修复 CityU 爬虫 deadline 抓取为空的问题
  - 优化多重匹配策略
  - 改进字段定位精度

### 📝 其他改进
- 更新 README.md 支持学校列表
- 新增 CHANGELOG.md 版本历史

### 📥 使用方法
```bash
# 克隆或拉取最新代码
git clone https://github.com/JACKSKYHADES0910/MySpiderProject.git
cd MySpiderProject

# 安装依赖
pip install -r requirements.txt

# 运行 PolyU 爬虫
python main.py polyu
```

**完整更新日志**: [CHANGELOG.md](https://github.com/JACKSKYHADES0910/MySpiderProject/blob/main/CHANGELOG.md)
```

---

## 提交信息参考

```bash
git add .
git commit -m "feat: 新增 PolyU 爬虫 + 修复 CityU deadline bug

- 新增香港理工大学 (PolyU) 完整爬虫实现
- 支持博士项目智能过滤
- 修复 CityU deadline 提取为空的问题
- 更新 README 和新增 CHANGELOG"

git push origin main
```
