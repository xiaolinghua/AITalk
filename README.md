AI 热点追踪助手基于 Flask 框架开发，整合 DeepSeek API 实现定时热点分析功能。系统支持用户通过前端配置关键词、分析方法和执行间隔，后端使用 Flask-APScheduler 按设定间隔自动运行任务：获取模拟热点数据后调用 DeepSeek API 进行分析，解析返回的结构化结果存储到 SQLite 数据库。
前端提供对话式交互和结果展示，用户可实时与ai对话并查看最新分析结果
### 部署说明
安装 Flask、OpenAI 等依赖包，从 DeepSeek 获取 API 密钥，修改api_key=os.environ.get('OPENAI_API_KEY'),赋值为你的 API 密钥，通过python app.py启动应用
