from openai import OpenAI
import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import json

# 应用初始化
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'
db = SQLAlchemy(app)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# 初始化OpenAI客户端
client = OpenAI(
    api_key=os.environ.get('OPENAI_API_KEY'),
    base_url="https://api.deepseek.com"
)


# 数据模型
class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    keywords = db.Column(db.String(255))
    analysis_method = db.Column(db.String(50))
    interval = db.Column(db.Integer)
    active = db.Column(db.Boolean)
    last_run = db.Column(db.DateTime)


class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    summary = db.Column(db.Text)
    structured_result = db.Column(db.JSON)
    config_id = db.Column(db.Integer, db.ForeignKey('config.id'))


# 使用OpenAI SDK调用DeepSeek API
def analyze_data(data, method):
    try:
        system_prompts = {
            "summary": "你是一个专业的热点追踪助手。请对提供的关于某个话题的最新动态进行总结，提取关键信息、主要发展和趋势。",
            "trends": "你是一个专业的趋势分析助手。请分析给定话题的最新动态，识别并解释其中的主要趋势、模式和发展方向。",
            "detailed": "你是一个专业的内容分析助手。请对提供的关于某个话题的最新动态进行深入分析，包括背景、现状、影响因素和未来展望。"
        }

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompts.get(method, "你是一个专业的助手")},
                {"role": "user", "content": f"分析以下关于'{data[:50]}'的最新动态并提供{method}分析：{data}"}
            ],
            temperature=0.3,
            max_tokens=1000
        )

        content = response.choices[0].message.content

        try:
            structured_result = json.loads(content)
        except:
            structured_result = {
                "summary": content,
                "key_points": extract_key_points(content),
                "trends": extract_trends(content, method)
            }

        return {
            "summary": content,
            "structured_result": structured_result
        }

    except Exception as e:
        app.logger.error(f"DeepSeek API调用失败: {e}")
        return {
            "error": str(e),
            "summary": "分析失败，请检查API连接",
            "structured_result": {}
        }


# 辅助函数：提取关键点和趋势
def extract_key_points(content):
    # 简单提取关键点的逻辑
    lines = content.split('\n')
    key_points = []
    for line in lines:
        if line.startswith("- ") or line.startswith("• ") or line.startswith("1. ") or line.startswith(
                "2. ") or line.startswith("3. "):
            key_points.append(line.strip())
    return key_points[:5]


def extract_trends(content, method):
    # 根据分析方法提取趋势
    if method == "trends":
        # 更复杂的趋势提取逻辑
        return content.split('\n')[:3]
    return []


# 模拟数据获取（实际应用中应替换为真实数据源）
def fetch_data(keywords):
    # 模拟获取关于关键词的最新动态
    # 实际应用中应连接到新闻API、社交媒体等数据源
    return f"""
    关于"{keywords}"的最新热点动态：

    1. 最新研究表明，{keywords}技术在过去三个月内取得了重大突破，新算法提高了30%的效率。
    2. 市场趋势显示，{keywords}相关产品的需求在本季度增长了25%，预计明年将继续上升。
    3. 行业应用方面，越来越多的企业开始采用{keywords}技术，特别是在金融和医疗领域。
    4. 专家预测，{keywords}将在未来5年内成为主流技术，改变多个行业的运作方式。
    5. 挑战与限制：尽管有进展，但{keywords}技术仍面临数据隐私和计算资源限制等问题。
    """


# 保存分析结果
def save_result(analysis_result, config_id):
    result = Result(
        summary=analysis_result.get("summary", "无摘要"),
        structured_result=analysis_result.get("structured_result", {}),
        config_id=config_id
    )
    db.session.add(result)

    # 更新配置的最后运行时间
    config = Config.query.get(config_id)
    if config:
        config.last_run = datetime.utcnow()
        db.session.commit()


# 定时任务
@scheduler.task('interval', id='run_analysis', minutes=1)
def run_analysis():
    with scheduler.app.app_context():
        config = Config.query.first()
        if config and config.active:
            app.logger.info(f"执行定时分析任务: {config.keywords}, {config.analysis_method}")
            data = fetch_data(config.keywords)
            analysis_result = analyze_data(data, config.analysis_method)
            save_result(analysis_result, config.id)


# API路由 - 获取配置
@app.route('/api/config', methods=['GET'])
def get_config():
    config = Config.query.first() or Config(
        keywords="人工智能",
        analysis_method="summary",
        interval=1,
        active=True,
        last_run=None
    )

    return jsonify({
        'keywords': config.keywords,
        'analysis_method': config.analysis_method,
        'interval': config.interval,
        'active': config.active,
        'last_run': config.last_run.isoformat() if config.last_run else None
    })


# API路由 - 更新配置
@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.get_json()

    # 如果配置不存在，创建新配置
    config = Config.query.first()
    if not config:
        config = Config()
        db.session.add(config)

    # 更新配置
    config.keywords = data.get('keywords', '')
    config.analysis_method = data.get('analysis_method', 'summary')
    config.interval = data.get('interval', 1)
    config.active = data.get('active', False)

    db.session.commit()

    # 重启定时任务以应用新的间隔
    if scheduler.get_job('run_analysis'):
        scheduler.reschedule_job('run_analysis', trigger='interval', minutes=config.interval)

    return jsonify({
        'keywords': config.keywords,
        'analysis_method': config.analysis_method,
        'interval': config.interval,
        'active': config.active,
        'last_run': config.last_run.isoformat() if config.last_run else None
    })


# API路由 - 获取分析结果
@app.route('/api/results', methods=['GET'])
def get_results():
    results = Result.query.order_by(Result.timestamp.desc()).limit(5).all()

    result_list = []
    for result in results:
        result_list.append({
            'id': result.id,
            'timestamp': result.timestamp.isoformat(),
            'summary': result.summary,
            'structured_result': result.structured_result
        })

    return jsonify(result_list)


# API路由 - 手动触发分析
@app.route('/api/analyze', methods=['POST'])
def manual_analyze():
    config = Config.query.first()
    if not config:
        return jsonify({'error': '配置不存在'}), 400

    data = fetch_data(config.keywords)
    analysis_result = analyze_data(data, config.analysis_method)
    save_result(analysis_result, config.id)

    return jsonify({
        'summary': analysis_result.get("summary", "无摘要"),
        'structured_result': analysis_result.get("structured_result", {})
    })


# 前端路由
@app.route('/')
def index():
    return render_template('index.html')


# 初始化数据库
with app.app_context():
    db.create_all()

    # 如果没有配置，创建默认配置
    if not Config.query.first():
        default_config = Config(
            keywords="人工智能",
            analysis_method="summary",
            interval=1,
            active=True
        )
        db.session.add(default_config)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)