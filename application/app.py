from flask import Flask, render_template, request, session, redirect, url_for
from DB import *

app = Flask(__name__)
app.secret_key = 'nikita-molodec'  # Нужòн для работы сессий (не убирать и не менять (ну пж (прям реально прошу)))
luti_password_ot_admina = 'regedit0'

@app.route('/')
def index():
    current_user = get_current_user(session.get('user_id'))

    q = request.args.get('q', '').strip()
    cat_raw = request.args.get('category', '').strip()
    selected_category = int(cat_raw) if cat_raw.isdigit() else None
    event_date = request.args.get('date', '').strip()

    categories = get_categories()
    events = get_upcoming_events(q=q, category_id=selected_category, event_date=event_date)

    return render_template(
        'index.html',
        current_user=current_user,
        events=events,
        categories=categories,
        selected_category=selected_category,
        search_q=q,
        search_date=event_date
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user_id = authenticate_user(email)

        if user_id:
            session['user_id'] = user_id
            return redirect(url_for('index'))
        else:
            error = "Пользователь с таким email не найден."

    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    groups, roles = get_groups_and_roles()

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        second_name = request.form.get('second_name', '').strip()
        middle_name = request.form.get('middle_name', '').strip() or None
        email = request.form.get('email', '').strip()
        group_id = request.form.get('group_id') or None
        role_id = request.form.get('role_id')
        org_code = request.form.get('org_code', '').strip()

        selected_role_name = ''
        for r in roles:
            if str(r.role_id) == str(role_id):
                selected_role_name = r.role_name.strip().lower()
                break

        if not (first_name and second_name and email and role_id):
            error = "Заполните обязательные поля."
        elif selected_role_name == 'организатор' and org_code != luti_password_ot_admina:
            error = "Для регистрации организатора необходимо ввести верный код доступа."
        else:
            new_user_id, reg_error = register_new_user(
                first_name=first_name,
                second_name=second_name,
                middle_name=middle_name,
                email=email,
                group_id=group_id,
                role_id=role_id
            )
            if reg_error:
                error = reg_error
            else:
                session['user_id'] = new_user_id
                return redirect(url_for('index'))

    return render_template('register.html', groups=groups, roles=roles, error=error)




@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/event/<int:event_id>', methods=['GET', 'POST'])
def event_detail(event_id):
    current_user = get_current_user(session.get('user_id'))
    event = get_event_by_id(event_id)

    if not event:
        return "Событие не найдено", 404

    message = None
    is_registered = False

    if current_user and current_user['role'] == 'студент':
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'register':
                err = register_for_event(current_user['email_id'], event.code)
                message = err if err else "Вы успешно записались на событие."
                event = get_event_by_id(event_id)
            elif action == 'cancel':
                cancel_registration(current_user['email_id'], event.code)
                message = "Запись отменена."
                event = get_event_by_id(event_id)

        is_registered = is_student_registered(current_user['email_id'], event.code)

    return render_template(
        'event_detail.html',
        current_user=current_user,
        event=event,
        is_registered=is_registered,
        message=message
    )


@app.route('/my-events')
def my_events():
    current_user = get_current_user(session.get('user_id'))
    if not current_user or current_user['role'] != 'студент':
        return redirect(url_for('login'))

    events = get_student_registrations(current_user['email_id'])
    return render_template('my_events.html', current_user=current_user, events=events)


@app.route('/organizer/events')
def organizer_events():
    current_user = get_current_user(session.get('user_id'))
    if not current_user or current_user['role'] != 'организатор':
        return redirect(url_for('login'))

    events = get_organizer_events(current_user['email_id'])
    return render_template('organizer_events.html', current_user=current_user, events=events)


@app.route('/organizer/create', methods=['GET', 'POST'])
def organizer_create():
    current_user = get_current_user(session.get('user_id'))
    if not current_user or current_user['role'] != 'организатор':
        return redirect(url_for('login'))

    error = None
    categories = get_categories()
    cabinets = get_cabinets()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id')
        starts_at = request.form.get('starts_at', '').strip()
        cabinet_id = request.form.get('cabinet_id')
        capacity = request.form.get('capacity', '').strip()

        if not (title and category_id and starts_at and cabinet_id and capacity):
            error = "Заполните все обязательные поля."
        else:
            err = create_event(
                title=title,
                description=description,
                category_id=category_id,
                starts_at=starts_at,
                cabinet_id=cabinet_id,
                capacity=capacity,
                organizer_email_id=current_user['email_id']
            )
            if err:
                error = err
            else:
                return redirect(url_for('organizer_events'))

    return render_template(
        'organizer_form.html',
        current_user=current_user,
        categories=categories,
        cabinets=cabinets,
        event=None,
        error=error
    )


@app.route('/organizer/edit/<int:event_id>', methods=['GET', 'POST'])
def organizer_edit(event_id):
    current_user = get_current_user(session.get('user_id'))
    if not current_user or current_user['role'] != 'организатор':
        return redirect(url_for('login'))

    event = get_event_for_edit(event_id, current_user['email_id'])
    if not event:
        return "Событие не найдено или нет прав доступа", 404

    error = None
    categories = get_categories()
    cabinets = get_cabinets()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id')
        starts_at = request.form.get('starts_at', '').strip()
        cabinet_id = request.form.get('cabinet_id')
        capacity = request.form.get('capacity', '').strip()

        if not (title and category_id and starts_at and cabinet_id and capacity):
            error = "Заполните все обязательные поля."
        else:
            update_event(
                event_id=event_id,
                organizer_email_id=current_user['email_id'],
                title=title,
                description=description,
                category_id=category_id,
                starts_at=starts_at,
                cabinet_id=cabinet_id,
                capacity=capacity
            )
            return redirect(url_for('organizer_events'))

    return render_template(
        'organizer_form.html',
        current_user=current_user,
        categories=categories,
        cabinets=cabinets,
        event=event,
        error=error
    )


@app.route('/organizer/delete/<int:event_id>', methods=['POST'])
def organizer_delete(event_id):
    current_user = get_current_user(session.get('user_id'))
    if not current_user or current_user['role'] != 'организатор':
        return redirect(url_for('login'))

    delete_event(event_id, current_user['email_id'])
    return redirect(url_for('organizer_events'))


@app.route('/organizer/participants/<int:event_id>')
def organizer_participants(event_id):
    current_user = get_current_user(session.get('user_id'))
    if not current_user or current_user['role'] != 'организатор':
        return redirect(url_for('login'))

    event = get_event_for_edit(event_id, current_user['email_id'])
    if not event:
        return "Событие не найдено или нет прав доступа", 404

    participants = get_event_participants(event_id, current_user['email_id'])
    return render_template(
        'organizer_participants.html',
        current_user=current_user,
        event=event,
        participants=participants
    )

if __name__ == '__main__': # Если оно всё работает, то я себе руки целовал
    app.run(debug = True)