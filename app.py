# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import send_from_directory
from pathlib import Path

import os
import secrets
import uuid
from api.ffmpeg import extract_middle_frame

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.py 中修改后的配置和上传逻辑
app.config['UPLOAD_FOLDER'] = 'static/uploads/videos'
app.config['THUMBNAIL_FOLDER'] = 'static/uploads/thumbnails'
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 500MB

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['THUMBNAIL_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# 数据模型 - 修改了关系名称，使用 user 而非 uploader
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    videos = db.relationship('Video', backref='user', lazy=True)  # 修改这里

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    videos = db.relationship('Video', backref='category', lazy=True)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(255), nullable=False)
    thumbnail = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    views = db.Column(db.Integer, default=0)
    upload_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    
    
categories_list = ['电影','动漫']
categories_dict = {}
# 初始化分类数据
def init_categories():
    categories = categories_list
    for name in categories:
        if not Category.query.filter_by(name=name).first():
            category = Category(name=name)
            db.session.add(category)
    db.session.commit()

# 自定义路由：返回默认缩略图：
@app.route('/thumbnails/default')
def get_default_thumbnail():
    # 1. 定义图片所在的绝对路径
    # app.root_path 是项目根目录的绝对路径
    thumbnail_dir = os.path.join(app.root_path, 'static', 'uploads', 'thumbnails')
    
    # 2. 检查文件是否存在
    default_thumbnail_path = os.path.join(thumbnail_dir, 'default_thumbnail.jpg')
    if not os.path.exists(default_thumbnail_path):
        # 如果文件不存在，返回404或自定义响应
        return "默认缩略图不存在", 404
    
    # 3. 返回图片文件（send_from_directory会自动处理文件读取和响应头）
    return send_from_directory(
        directory=thumbnail_dir,  # 图片所在目录
        path='default_thumbnail.jpg',  # 文件名
        mimetype='image/jpeg'  # 明确指定图片类型（可选，Flask会自动识别）
    )

# 路由
@app.route('/')
def index():
    search_query = request.args.get('search', '')
    category_id = request.args.get('category', type=int)
    
    videos = Video.query
    
    if search_query:
        videos = videos.filter(Video.title.ilike(f'%{search_query}%') | 
                              Video.description.ilike(f'%{search_query}%'))
    
    if category_id:
        videos = videos.filter_by(category_id=category_id)
    
    videos = videos.order_by(Video.upload_date.desc()).all()
    categories = Category.query.all()
    current_category = Category.query.get(category_id) if category_id else None
    
    return render_template('index.html', videos=videos, categories=categories, 
                          current_category=current_category, search_query=search_query)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('登录成功', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('已退出登录', 'success')
    return redirect(url_for('index'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    video_info = {}
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('login'))
    
    categories = Category.query.all()
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category_id = request.form['category']
        video_file = request.files['video']
        thumbnail_file = request.files.get('thumbnail')
        
        if not video_file:
            flash('请选择视频文件', 'error')
            return redirect(url_for('upload'))

        # 生成唯一文件名
        video_ext = os.path.splitext(video_file.filename)[1]
        video_filename = f"{uuid.uuid4().hex}{video_ext}"
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
        video_file.save(video_path)
        video_info["video"] = video_path
        
        thumbnail_filename = None
        if thumbnail_file:
            thumb_ext = os.path.splitext(thumbnail_file.filename)[1]
            thumbnail_filename = f"{uuid.uuid4().hex}{thumb_ext}"
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
            thumbnail_file.save(thumbnail_path)
            video_info["img"] = thumbnail_path
        else:
            # 如果没有提供缩略图，使用默认缩略图
            thumbnail_filename = 'default_thumbnail.jpg'
            path = os.path.splitext(video_filename)[0]
            thumbnail_filename = f"{path}.jpg"
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
            video_info["img"] = thumbnail_path
            thumbnail_file.save(thumbnail_path)
                
        video = Video(
            title=title,
            description=description,
            filename=video_filename,
            thumbnail=thumbnail_filename,
            category_id=category_id,
            user_id=session['user_id']
        )
        db.session.add(video)
        db.session.commit()
        #确保文件有内容
        if os.path.getsize(video_info["img"]) == 0:
            extract_middle_frame(video_info["video"],video_info["img"])
                
        flash('视频上传成功', 'success')
        return redirect(url_for('index'))

    return render_template('upload.html', categories=categories)

@app.route('/video/<int:video_id>')
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)
    video.views += 1
    db.session.commit()
    
    # 查询相关视频（同分类的其他视频）
    related_videos = Video.query.filter(
        Video.category_id == video.category_id,
        Video.id != video.id
    ).order_by(Video.upload_date.desc()).limit(5).all()
    
    # 查询所有分类
    categories = Category.query.all()
    
    return render_template('video_detail.html', video=video, videos=related_videos, categories=categories)

@app.route('/video/<int:video_id>/delete', methods=['POST'])
def delete_video(video_id):
    # 1. 验证用户是否登录
    if 'user_id' not in session:
        flash('请先登录', 'error')
        return redirect(url_for('login'))
    
    # 2. 获取视频并验证是否存在
    video = Video.query.get_or_404(video_id)
    
    # 3. 验证权限（只有上传者才能删除）
    if video.user_id != session['user_id']:
        abort(403)  # 权限不足
    
    # 4. 物理删除视频文件和缩略图
    try:
        # 删除视频文件
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
        if os.path.exists(video_path):
            os.remove(video_path)
        
        # 删除缩略图（跳过默认缩略图）
        if video.thumbnail != 'default_thumbnail.jpg':
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
    
    except Exception as e:
        flash(f'文件删除失败：{str(e)}', 'error')
        return redirect(url_for('video_detail', video_id=video_id))
    
    # 5. 从数据库删除记录
    db.session.delete(video)
    db.session.commit()
    
    flash('视频已成功删除', 'success')
    return redirect(url_for('index'))

def handle_new_video_in_fixed_folder(path):
    if not os.path.exists(path):
        # 不存在则创建
        os.makedirs(path)
    traverse_directory(path)

def get_category_by_name(name) -> int:
    id = categories_dict.get(name)
    if id:
        return id
    else:
        return -1

def save_file(file_path) -> str:
    video_ext = os.path.splitext(file_path)[1]
    video_filename = f"{uuid.uuid4().hex}{video_ext}"
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    source = Path(file_path)
    destination = Path(video_path)
    destination.write_bytes(source.read_bytes())
    os.remove(file_path)
    return video_path

def save_thumbnail(new_file_path) -> str:
    path = os.path.split(new_file_path)[1]
    path = os.path.splitext(path)[0]
    thumbnail_filename = f"{path}.jpg"
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
    extract_middle_frame(new_file_path,thumbnail_path)
    return thumbnail_path

def upload_to_database(dir_name,filepath):
    category_id = -1
    new_file_path = ""
    filename = os.path.split(filepath)[1]
    filename = os.path.splitext(filename)[0]
    category_id = get_category_by_name(dir_name)
    if category_id == -1:
        print("pass:{filepath}")
        return
    new_file_path = save_file(filepath)
    new_thumbnail = save_thumbnail(new_file_path)
    new_file_path = os.path.split(new_file_path)[1]
    new_thumbnail = os.path.split(new_thumbnail)[1]
    print(filename)
    print(new_file_path)
    print(new_thumbnail)
    print(category_id)
    video = Video(
            title=filename,
            description=" ",
            filename=new_file_path,
            thumbnail=new_thumbnail,
            category_id=category_id,
            user_id=1
        )
    db.session.add(video)
    db.session.commit()    


def traverse_second_directory(dir_name,dir_path):
    # 遍历目录树
    print(dir_name)
    print(dir_path)
    for dirpath, dirnames, filenames in os.walk(dir_path):
        # 打印文件
        print(filenames)
        for filename in filenames:
            print(dir_name)
            upload_to_database(dir_name,os.path.join(dirpath, filename))
               
def traverse_directory(root_dir):
    """
    递归遍历指定目录下的所有内容，并打印出目录和文件的路径
    :param root_dir: 要遍历的根目录
    """
    # 检查目录是否存在
    if not os.path.exists(root_dir):
        print(f"错误：目录 '{root_dir}' 不存在")
        return
    if not os.path.isdir(root_dir):
        print(f"错误：'{root_dir}")
        print(f"错误：'{root_dir}' 不是一个目录")
        return

    # 遍历目录树
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 打印子目录
        for dirname in dirnames:
            traverse_second_directory(dirname,os.path.join(dirpath, dirname))    
        return

def clean_old_categories():
    """删除不在categories_list中的分类（保留列表内的分类）"""
    # 1. 获取所有当前数据库中的分类
    all_categories = Category.query.all()
    
    # 2. 提取预设分类列表中的名称（用于比对）
    valid_category_names = set(categories_list)
    
    # 3. 遍历数据库分类，删除不在预设列表中的分类
    for category in all_categories:
        if category.name not in valid_category_names:
            # 检查该分类下是否有视频（避免删除有视频的分类）
            if len(category.videos) > 0:
                print(f"警告：分类 '{category.name}' 下有视频，未删除")
            else:
                # 无视频的分类可安全删除
                db.session.delete(category)
                print(f"已删除历史分类：{category.name}")
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_categories()
        clean_old_categories()

        for list in categories_list:
            category = Category.query.filter_by(name=list).first()
            if category:
                categories_dict[list] = category.id
        handle_new_video_in_fixed_folder("video")
    app.run(debug=True,host="0.0.0.0",port=80)
