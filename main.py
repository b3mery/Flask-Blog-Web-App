from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
import sqlalchemy.exc
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_gravatar import Gravatar


import email_manager
from forms import ContactForm, CreatePostForm, RegisterUserForm, LoginUserForm, CommentForm

import os
from datetime import date, datetime
from functools import wraps


### Constants
SITE_NAME = "My Blog Site"
CURRENT_YEAR = datetime.now().year
DEFAULT_POST_IMAGE_BG = "https://images.unsplash.com/photo-1432821596592-e2c18b78144f?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1470&q=80"
## Flask Password hash
HASH_METHOD = 'pbkdf2:sha256'
SALT_LEN = 8

################################################## Flask APP Set Up #############################################################################################################

app = Flask(__name__)
# os env varbale sourced from Heroku deployment
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'RanDOM123SECRET')
ckeditor = CKEditor(app)
Bootstrap(app)

# Postgres DB for deployment, sqlite for dev
uri = os.environ.get('DATABASE_URL', "sqlite:///blog.db")  #https://help.heroku.com/ZKNTJQSK/why-is-sqlalchemy-1-4-x-not-connecting-to-heroku-postgres
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialise Flask Login Manager 
login_manager = LoginManager()
login_manager.init_app(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)

################################################## Database Set Up #############################################################################################################
##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    first_name = db.Column(db.String(1000))
    last_name = db.Column(db.String(1000))
    is_admin = db.Column(db.Boolean, default=False)
    posts = db.relationship('BlogPost', back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # Foreign key
    # users.id references __tablename__ users
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    #***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="parent_post")

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    
    #***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)

db.create_all()

################################################## Decorators and Login Manager ######################################################################################################

# Load login user:
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin Decorator for restricted functions
def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if current_user.is_admin != 1:
            return abort(403)
        return function(*args, **kwargs)
    return decorated_function

def create_user_or_admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        print(kwargs.get('post_id'))
        post:BlogPost = BlogPost.query.get(kwargs.get('post_id'))
        if post.author.id != current_user.id and current_user.is_admin != 1:
            return abort(403)

        return function(*args, **kwargs)
    return decorated_function

################################################## Flask APP Routes #############################################################################################################

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterUserForm()
    if form.validate_on_submit():
        new_user = User(
            first_name = form.first_name.data,
            last_name =  form.last_name.data,
            email = form.email.data.lower(),
            password = generate_password_hash(form.password.data, method=HASH_METHOD, salt_length=SALT_LEN)
        )
        try:
            db.session.add(new_user)
            db.session.commit()
        except sqlalchemy.exc.IntegrityError:
            flash(f"The email you entered \'{form.email.data}\' already exists. Please Login instead!")
        else:
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginUserForm()
    if form.validate_on_submit():
        user:User = User.query.filter_by(email=form.email.data.lower()).first()
        if user is None:
            flash("That email does not exist, please try again")
        elif not check_password_hash(user.password ,form.password.data):
            flash("Incorrect password, please try again.")
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form = form, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>",  methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        new_comment = Comment(
            text = form.comment.data,
            comment_author = current_user,
            parent_post = requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id = requested_post.id))
    return render_template("post-modal.html", post=requested_post, logged_in=current_user.is_authenticated, form=form, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        if not email_manager.send_email_notification(form.name.data,form.email.data,form.phone.data,form.message.data):
            flash('Internal error submitting your form, please try agin later.')
        else:
            return redirect(url_for('contact'))
    return render_template("contact.html", logged_in=current_user.is_authenticated, form=form, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route("/new-post",  methods=['GET', 'POST'])
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title = form.title.data,
            subtitle = form.subtitle.data,
            body = form.body.data,
            img_url = (form.img_url.data or DEFAULT_POST_IMAGE_BG),
            author = current_user,
            date = date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route("/edit-post/<int:post_id>" , methods=['GET', 'POST'])
@create_user_or_admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=current_user,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = (edit_form.img_url.data or DEFAULT_POST_IMAGE_BG)
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, logged_in=current_user.is_authenticated, website_name=SITE_NAME, year=CURRENT_YEAR)


@app.route("/delete/<int:post_id>", methods=['GET', 'POST'])
@create_user_or_admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


################################################## Flask APP Run #############################################################################################################
if __name__ == "__main__":
    app.run()