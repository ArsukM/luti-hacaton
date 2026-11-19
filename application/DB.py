from DB_CONNECTION import db_conn
from datetime import datetime

def get_current_user(user_id):
	if not user_id:
		return None

	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT 
				u.user_id,
				u.first_name,
				u.second_name,
				r.role_name,
				m.user_email_id,
				m.user_mail
			FROM [users$] u
			JOIN [roles$] r ON u.fk_role = r.role_id
			LEFT JOIN [users_mail$] m ON u.fk_email = m.user_email_id
			WHERE u.user_id = ?
		""", (user_id,))
		row = cursor.fetchone()
		if row:
			return {
				'id': row.user_id,
				'name': f"{row.first_name} {row.second_name}",
				'role': row.role_name.strip().lower(),
				'email_id': row.user_email_id,
				'email': row.user_mail
			}
	return None


def get_categories():
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("SELECT category_id, category_name FROM [categories$] ORDER BY category_name")
		return cursor.fetchall()


def get_upcoming_events(q = '', category_id = None, event_date = ''):
	with db_conn() as conn:
		cursor = conn.cursor()
		query = """
			SELECT 
				e.event_id,
				e.code,
				e.title,
				e.description,
				e.starts_at,
				e.capacity,
				c.category_name,
				cab.cabinet_name,
				(e.capacity - COUNT(r.register_id)) AS available_seats
			FROM [events$] e
			JOIN [categories$] c ON e.fk_category = c.category_id
			JOIN [cabinets$] cab ON e.fk_cabinet = cab.cabinet_id
			LEFT JOIN [registrations$] r ON e.code = r.event_code
			WHERE e.starts_at >= GETDATE()
		"""
		params = []

		if q:
			query += " AND (e.title LIKE ? OR e.description LIKE ?)"
			params.extend([f"%{q}%", f"%{q}%"])

		if category_id is not None:
			query += " AND e.fk_category = ?"
			params.append(category_id)

		if event_date:
			query += " AND CAST(e.starts_at AS DATE) = ?"
			params.append(event_date)

		query += """
			GROUP BY 
				e.event_id, e.code, e.title, e.description, 
				e.starts_at, e.capacity, c.category_name, cab.cabinet_name
			ORDER BY e.starts_at ASC
		"""
		cursor.execute(query, params)
		return cursor.fetchall()


def authenticate_user(email):
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT u.user_id 
			FROM [users$] u
			JOIN [users_mail$] m ON u.fk_email = m.user_email_id
			WHERE m.user_mail = ?
		""", (email,))
		row = cursor.fetchone()
		return row.user_id if row else None


def get_groups_and_roles():
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("SELECT group_id, group_name FROM [groups$] ORDER BY group_name")
		groups = cursor.fetchall()
		cursor.execute("SELECT role_id, role_name FROM [roles$] ORDER BY role_id")
		roles = cursor.fetchall()
		return groups, roles


def register_new_user(first_name, second_name, middle_name, email, group_id, role_id):
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("SELECT user_email_id FROM [users_mail$] WHERE user_mail = ?", (email,))
		if cursor.fetchone():
			return None, "Этот email уже зарегистрирован."

		cursor.execute(
			"INSERT INTO [users_mail$] (user_mail) OUTPUT INSERTED.user_email_id VALUES (?)",
			(email,)
		)
		new_email_id = cursor.fetchval()

		cursor.execute("""
			INSERT INTO [users$] (first_name, second_name, middle_name, fk_email, fk_group, fk_role)
			OUTPUT INSERTED.user_id
			VALUES (?, ?, ?, ?, ?, ?)
		""", (first_name, second_name, middle_name, new_email_id, group_id, int(role_id)))
		new_user_id = cursor.fetchval()

		conn.commit()
		return new_user_id, None



def is_student_registered(student_email_id, event_code):
	if not student_email_id:
		return False
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT register_id 
			FROM [registrations$] 
			WHERE fk_student_email = ? AND event_code = ?
		""", (student_email_id, event_code))
		return cursor.fetchone() is not None


def register_for_event(student_email_id, event_code):
	if not student_email_id:
		return "У вашего профиля не указан email для регистрации."

	with db_conn() as conn:
		cursor = conn.cursor()

		cursor.execute("""
			SELECT register_id FROM [registrations$] 
			WHERE fk_student_email = ? AND event_code = ?
		""", (student_email_id, event_code))
		if cursor.fetchone():
			return "Вы уже записаны на это событие."

		cursor.execute("""
			SELECT e.capacity, e.starts_at, COUNT(r.register_id) AS booked
			FROM [events$] e
			LEFT JOIN [registrations$] r ON e.code = r.event_code
			WHERE e.code = ?
			GROUP BY e.capacity, e.starts_at
		""", (event_code,))
		row = cursor.fetchone()
		if not row:
			return "Событие не найдено."
		if row.booked >= row.capacity:
			return "Свободных мест больше нет."

		cursor.execute("""
					INSERT INTO [registrations$] (fk_student_email, event_code, registered_at)
					VALUES (?, ?, GETDATE())
				""", (student_email_id, event_code))
		conn.commit()
		return None



def cancel_registration(student_email_id, event_code):
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			DELETE FROM [registrations$] 
			WHERE fk_student_email = ? AND event_code = ?
		""", (student_email_id, event_code))
		conn.commit()


def get_student_registrations(student_email_id):
	if not student_email_id:
		return []
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT 
				e.event_id,
				e.code,
				e.title,
				e.starts_at,
				c.category_name,
				cab.cabinet_name,
				r.registered_at
			FROM [registrations$] r
			JOIN [events$] e ON r.event_code = e.code
			JOIN [categories$] c ON e.fk_category = c.category_id
			JOIN [cabinets$] cab ON e.fk_cabinet = cab.cabinet_id
			WHERE r.fk_student_email = ?
			ORDER BY e.starts_at ASC
		""", (student_email_id,))
		return cursor.fetchall()


def get_event_by_id(event_id):
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT 
				e.event_id,
				e.code,
				e.title,
				e.description,
				e.starts_at,
				e.capacity,
				c.category_name,
				cab.cabinet_name,
				u.first_name + ' ' + u.second_name AS organizer_name,
				m.user_mail AS organizer_email,
				(e.capacity - COUNT(r.register_id)) AS available_seats
			FROM [events$] e
			JOIN [categories$] c ON e.fk_category = c.category_id
			JOIN [cabinets$] cab ON e.fk_cabinet = cab.cabinet_id
			LEFT JOIN [users_mail$] m ON e.fk_organizer_email = m.user_email_id
			LEFT JOIN [users$] u ON u.fk_email = m.user_email_id
			LEFT JOIN [registrations$] r ON e.code = r.event_code
			WHERE e.event_id = ?
			GROUP BY 
				e.event_id, e.code, e.title, e.description, 
				e.starts_at, e.capacity, c.category_name, cab.cabinet_name,
				u.first_name, u.second_name, m.user_mail
		""", (event_id,)) # Ужасный запрос, очень его любил
		return cursor.fetchone()


def get_cabinets():
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("SELECT cabinet_id, cabinet_name FROM [cabinets$] ORDER BY cabinet_name")
		return cursor.fetchall()


def get_organizer_events(organizer_email_id):
	if not organizer_email_id:
		return []
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT 
				e.event_id,
				e.code,
				e.title,
				e.starts_at,
				e.capacity,
				c.category_name,
				cab.cabinet_name,
				COUNT(r.register_id) AS booked_count
			FROM [events$] e
			JOIN [categories$] c ON e.fk_category = c.category_id
			JOIN [cabinets$] cab ON e.fk_cabinet = cab.cabinet_id
			LEFT JOIN [registrations$] r ON e.code = r.event_code
			WHERE e.fk_organizer_email = ?
			GROUP BY 
				e.event_id, e.code, e.title, e.starts_at, 
				e.capacity, c.category_name, cab.cabinet_name
			ORDER BY e.starts_at DESC
		""", (organizer_email_id,)) # Ещё один прекрасный запрос, щя, я даже смайлики прогуглю 🥲🔫
		return cursor.fetchall()


def get_event_for_edit(event_id, organizer_email_id):
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT 
				event_id, code, title, description, 
				fk_category, starts_at, fk_cabinet, capacity
			FROM [events$]
			WHERE event_id = ? AND fk_organizer_email = ?
		""", (event_id, organizer_email_id))
		return cursor.fetchone()


def create_event(title, description, category_id, starts_at, cabinet_id, capacity, organizer_email_id):
	if not organizer_email_id:
		return "У вашего профиля не указан email организатора."

	starts_at_dt = datetime.strptime(starts_at, '%Y-%m-%dT%H:%M')

	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("SELECT ISNULL(MAX(event_id), 0) + 1 FROM [events$]")
		next_num = cursor.fetchval()
		event_code = f"EVT-{next_num}"

		cursor.execute("""
			INSERT INTO [events$] (
				code, title, description, fk_category, 
				starts_at, fk_cabinet, capacity, fk_organizer_email
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		""", (event_code, title, description, int(category_id), starts_at_dt, int(cabinet_id), int(capacity), organizer_email_id))
		conn.commit()
		return None


def update_event(event_id, organizer_email_id, title, description, category_id, starts_at, cabinet_id, capacity):
	starts_at_dt = datetime.strptime(starts_at, '%Y-%m-%dT%H:%M')
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			UPDATE [events$]
			SET title = ?, description = ?, fk_category = ?, 
				starts_at = ?, fk_cabinet = ?, capacity = ?
			WHERE event_id = ? AND fk_organizer_email = ?
		""", (title, description, int(category_id), starts_at_dt, int(cabinet_id), int(capacity), event_id, organizer_email_id))
		conn.commit()



def delete_event(event_id, organizer_email_id):
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT code FROM [events$] 
			WHERE event_id = ? AND fk_organizer_email = ?
		""", (event_id, organizer_email_id))
		row = cursor.fetchone()
		if row:
			cursor.execute("DELETE FROM [registrations$] WHERE event_code = ?", (row.code,))
			cursor.execute("DELETE FROM [events$] WHERE event_id = ?", (event_id,))
			conn.commit()


def get_event_participants(event_id, organizer_email_id):
	with db_conn() as conn:
		cursor = conn.cursor()
		cursor.execute("""
			SELECT 
				u.second_name,
				u.first_name,
				u.middle_name,
				g.group_name,
				m.user_mail,
				r.registered_at
			FROM [events$] e
			JOIN [registrations$] r ON e.code = r.event_code
			JOIN [users_mail$] m ON r.fk_student_email = m.user_email_id
			LEFT JOIN [users$] u ON u.fk_email = m.user_email_id
			LEFT JOIN [groups$] g ON u.fk_group = g.group_id
			WHERE e.event_id = ? AND e.fk_organizer_email = ?
			ORDER BY r.registered_at ASC
		""", (event_id, organizer_email_id))
		return cursor.fetchall()
