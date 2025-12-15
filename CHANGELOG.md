# Changelog

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

## [v1.2.0] - 2025-12-15

### 新增 (Added)
- ✨ 新增 **香港理工大学 (PolyU)** 爬虫支持
  - 完整支持 Taught Postgraduate 项目列表抓取
  - 智能过滤博士 (Doctor/PhD) 项目,可独立配置
  - 支持中英文项目名称提取
  - 自动提取 Local/Non-Local 申请截止日期
  - 固定申请链接配置: `https://www38.polyu.edu.hk/eAdmission/index.do`

### 修复 (Fixed)
- 🐛 修复 CityU 爬虫 deadline 抓取为空的 bug
  - 优化了 deadline 提取策略,增加多重匹配逻辑
  - 改进了 `prog_admission` 类的定位精度
  - 增强了对 "Non-local" 和 "Local" 字段的识别

### 优化 (Changed)
- 📝 更新 README.md,添加 CityU 和 PolyU 到支持学校矩阵
- ⚙️ 在 `config.py` 中注册 PolyU 学校配置
- 🔧 在 `main.py` 中注册 PolyU 爬虫类

---

## [v1.1.0] - 2025-12-13

### 新增 (Added)
- ✨ 新增 **香港城市大学 (CityU)** 爬虫支持
  - 强制有头模式 (Headful) 绕过 Incapsula WAF 防护
  - 采用"快照解析"策略避免频繁 Selenium 调用
  - 支持多学院表格容器解析

### 优化 (Changed)
- 🚀 提升并发性能,默认并发数调整为 24
- 📊 改进进度显示,使用 `CrawlerProgress` 统一管理
- 🔄 完善数据去重逻辑

---

## [v1.0.0] - 2024-12-XX

### 新增 (Added)
- 🎉 项目初始版本发布
- ✨ 支持 **香港大学 (HKU)** 爬虫
- ✨ 支持 **香港中文大学 (CUHK)** 爬虫
- 🔧 实现 BaseSpider 基类架构
- 📦 BrowserPool 浏览器对象池
- 💾 Excel 数据导出功能
- 🎨 Rich 美化控制台输出
- 🔄 智能数据去重机制
- 📝 完整的项目文档

---

## 图例 (Legend)

- ✨ 新增 (Added): 新功能
- 🐛 修复 (Fixed): Bug 修复
- 📝 文档 (Documentation): 文档更新
- 🚀 性能 (Performance): 性能优化
- ⚙️ 配置 (Configuration): 配置变更
- 🔧 重构 (Refactor): 代码重构
- 🗑️ 移除 (Removed): 移除功能
