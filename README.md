# 🦞 AstroStudy

> 一个 Flask + Bootstrap 5 构建的全栈学习备考助手，助你高效规划、专注冲刺。

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![Flask](https://img.shields.io/badge/flask-3.x-lightgrey)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## ✨ 功能一览

### 📚 课程 & 任务管理
- **三视图切换** — 列表 / 看板 / 日历，随心切换
- **拖拽排序** — 任务优先级自由调整
- **软删除 + 撤销** — 误删不怕，一键恢复
- **标签系统** — 多维度分类筛选

### 📝 笔记模块
- **富文本编辑** — 基于 Toast UI Editor（Markdown + WYSIWYG）
- **收藏 & 文件夹** — 结构化知识管理
- **置顶 & 导出** — 重点笔记常驻顶部，支持 Markdown 导出

### ⏱️ 番茄钟
- **自定义时长** — 专注 / 短休 / 长休自由调节
- **白噪音** — 内置环境音效，沉浸专注
- **会话统计** — 记录每次专注数据

### 📊 考试管理
- **倒计时** — 考试日程清晰展示
- **GitHub 风热力图** — 学习打卡可视化
- **数据导出** — 一键导出 CSV 报表

### 🔍 全局搜索
- **Ctrl+K** 呼出搜索面板
- 支持课程 / 任务 / 笔记 / 考试全量检索

### 🎨 其他亮点
- 🦞 吉祥物动画（Rive runtime）
- 🌓 响应式设计，手机 / 平板 / 桌面全适配
- 📦 PyInstaller 一键打包为 Windows exe

---

## 🚀 快速开始

### 环境要求
- Python 3.12+
- pip

### 安装运行

```bash
# 克隆仓库
git clone https://github.com/Cosmossssssssssss/AstroStudy.git
cd AstroStudy

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

浏览器访问 `http://127.0.0.1:5000` 即可使用。

### 打包为 exe

```bash
pip install pyinstaller
pyinstaller AstroStudy.spec
# 输出在 dist/ 目录
```

---

## 📁 项目结构

```
AstroStudy/
├── app.py                  # 主入口
├── blueprints/             # Flask 蓝图模块
│   ├── api.py              # RESTful API
│   ├── auth.py             # 用户认证
│   ├── courses.py          # 课程管理
│   ├── tasks.py            # 任务管理
│   ├── notes.py            # 笔记模块
│   ├── pomodoro.py         # 番茄钟
│   ├── exams.py            # 考试管理
│   ├── stats.py            # 统计热力图
│   ├── search.py           # 全局搜索
│   ├── export.py           # 数据导出
│   ├── profile.py          # 个人设置
│   ├── decorators.py       # 装饰器工具
│   └── utils.py            # 通用工具
├── templates/              # Jinja2 模板
├── static/                 # 静态资源
│   ├── vendor/             # 第三方库 (Toast UI, Rive)
│   └── riv/                # Rive 动画文件
├── requirements.txt        # Python 依赖
└── VERSION                 # 版本号
```

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| 后端 | Python 3.12, Flask 3.x |
| 数据库 | SQLite |
| 前端 | Bootstrap 5, Vanilla JS |
| 编辑器 | Toast UI Editor 3.x |
| 动画 | Rive runtime |
| 打包 | PyInstaller |

---

## 📄 License

MIT © Cosmossssssssssss
