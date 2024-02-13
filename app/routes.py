
from flask import render_template, flash, redirect, url_for, request
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, EmptyForm, PostForm, SearchForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Post
from urllib.parse import urlsplit

from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')

import json

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body=form.post.data, author=current_user)
        post_embedding = model.encode(form.post.data)
        try:
            with open('embeddings.json', 'r+') as file:
                if file.read() == '':
                    file_data = []
                else:
                    file.seek(0)
                    file_data = json.load(file)
                file_data.append({"body": form.post.data, "embedding": post_embedding.tolist()})
                file.seek(0)
                json.dump(file_data, file)
                file.truncate()
        except FileNotFoundError:
            with open('embeddings.json', 'w') as file:
                json.dump([{"body": form.post.data, "embedding": post_embedding.tolist()}], file)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(current_user.following_posts(), page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    prev_url = url_for('index', page=posts.prev_num) if posts.has_prev else None
    next_url = url_for('index', page=posts.next_num) if posts.has_next else None
    return render_template('index.html', title='Homepage', form=form, posts=posts, prev_url=prev_url, next_url=next_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    query = user.posts.select().order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    prev_url = url_for('user', username=username, page=posts.prev_num) if posts.has_prev else None
    next_url = url_for('user', username=username, page=posts.next_num) if posts.has_next else None
    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts, prev_url=prev_url, next_url=next_url, form=form)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))
    
@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))
    
@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
    prev_url = url_for('explore', page=posts.prev_num) if posts.has_prev else None
    next_url = url_for('explore', page=posts.next_num) if posts.has_next else None
    return render_template('index.html', title='Explore', posts=posts.items, prev_url=prev_url, next_url=next_url)

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    form = SearchForm()
    if form.validate_on_submit():
        search_term = form.search.data
        return redirect(url_for('search', search=search_term))
    elif request.method == 'GET':
        search_term = request.args.get('search')
        if search_term:
            search_embedding = model.encode(search_term)
            with open('embeddings.json', 'r') as file:
                embeddings = json.load(file)
            similar_messages = []
            for item in embeddings:
                similarity = cosine_similarity([search_embedding], [np.array(item['embedding'])])
                similar_messages.append((item['body'], similarity[0][0]))
            similar_messages.sort(key=lambda x: x[1], reverse=True)
            similar_messages = similar_messages[:3]
            similar_messages_body = [message[0] for message in similar_messages]

            page = request.args.get('page', 1, type=int)
            query = (
                sa.select(Post)
                .where(Post.body.in_(similar_messages_body))
                .order_by(Post.timestamp.desc())
            )
            posts = db.paginate(query, page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
            prev_url = url_for('search', search=search_term, page=posts.prev_num) if posts.has_prev else None
            next_url = url_for('search', search=search_term, page=posts.next_num) if posts.has_next else None
            return render_template('search.html', title='Search', form=form, posts=posts.items, prev_url=prev_url, next_url=next_url)
        else:
            search_term = request.args.get('search')
            page = request.args.get('page', 1, type=int)
            query = (
                sa.select(Post)
                .where(Post.body.ilike(f'%{search_term}%'))
                .order_by(Post.timestamp.desc())
            )
            posts = db.paginate(query, page=page, per_page=app.config['POSTS_PER_PAGE'], error_out=False)
            prev_url = url_for('search', search=search_term, page=posts.prev_num) if posts.has_prev else None
            next_url = url_for('search', search=search_term, page=posts.next_num) if posts.has_next else None
            return render_template('search.html', title='Search', form=form, posts=posts.items, prev_url=prev_url, next_url=next_url)
    else:
        return render_template('search.html', title='Search', form=form, posts=[])