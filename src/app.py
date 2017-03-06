"""
TODO: Implement other error handlers - http://flask.pocoo.org/docs/0.12/patterns/errorpages/
TODO: Shit-loads of refactoring
TODO: Proper Error Handling of Entries in report_filter()
TODO: Implement logout.html
TODO: Add button to point to rest.html on login page
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2, datetime

from config import DB_NAME, HOST, PORT, APP_SECRET_KEY


# Run Server
app = Flask(__name__)
app.secret_key = APP_SECRET_KEY


# MARK: DATABASE FUNCTIONS
def db_query(sql_string, data_list):
	"""This function is designed to take a SQL query string and a list of data to be used - in order - as injection-safe, variable fill-ins for the query."""
	conn = psycopg2.connect(dbname=DB_NAME, host=HOST, port=PORT)
	cur = conn.cursor()
	cur.execute(sql_string, data_list)

	# Return data as an array of dictionaries
	result = cur.fetchall()
	records = []

	# If the query returns something...
	if len(result) != 0:
		entries = result
		for row in entries:
			records.append(row)
	else:
		# No results in query
		return None

	conn.commit()
	cur.close()
	conn.close()
	return records


def db_change(sql_string, data_list):
	"""This function is designed to take a SQL query string and a list of data to be used (in order) as injection-safe, variable fill-ins for the query."""
	conn = psycopg2.connect(dbname=DB_NAME, host=HOST, port=PORT)
	cur = conn.cursor()
	try:
		cur.execute(sql_string, data_list)
	except:
		print("QUERY FAILED")
		redirect(url_for('failed_query'))

	conn.commit()
	cur.close()
	conn.close()


def duplicate_check(sql_string, data_list):
	"""This function is designed to return True if a query yields a result and False if not."""
	conn = psycopg2.connect(dbname=DB_NAME, host=HOST, port=PORT)
	cur = conn.cursor()
	cur.execute(sql_string, data_list)
	result = cur.fetchall()
	cur.close()
	conn.close()
	if result:
		return True
	else:
		return False


def validate_date(date_string):
	"""This function checks to see if the user entered a date in the MM/DD/YYYY format."""
	try:
		date = datetime.datetime.strptime(date_string, '%m/%d/%Y').date()
		return date
	except ValueError:
		# TODO: Send error via flash
		raise ValueError('Incorrect data format, should be MM/DD/YYYY')


# MARK: TEMPLATES
@app.route('/')
@app.route('/index')
@app.route('/index.html')
def index():
	return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
	if session.get('logged_in'):
		return redirect(url_for('dashboard'))

	if request.method == 'POST':
		username = request.form.get('username', None)
		password = request.form.get('password', None)

		if username is None:
			flash('Please enter a username.')
			return render_template('login.html')
		elif password is None:
			flash('Please enter a password.')
			return render_template('login.html')
		else:
			check_for_user = "SELECT * FROM users WHERE username = %s;"
			result = db_query(check_for_user, [username])
			# Result is ([user_pk, role_fk, username, password])

			if result is None:
				# User DOES NOT exist:
				flash('There is no record of this account.')
				return render_template('login.html')
			else:
				# User DOES exist:
				if password == result[0][3]:
					# Password is correct
					session['username'] = username
					session['logged_in'] = True
					session['perms'] = result[0][1]
					welcome_message = 'Welcome ' + str(session.get('username')) + '!'
					flash(welcome_message)
					return redirect('/dashboard')
				else:
					# Password is incorrect
					flash('Password is incorrect.')
					return render_template('login.html')

	return render_template('login.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
	session['logged_in'] = False
	return render_template('logout.html')


@app.route('/dashboard', methods=['GET'])
def dashboard():
	if not session.get('logged_in'):
		flash('You must login before being allowed access to the dashboard')
		return redirect(url_for('login'))
	else:
		return render_template('dashboard.html')


@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
	if request.method == 'POST':
		username = request.form.get('username', None).strip()
		password = request.form.get('password', None)
		role = request.form.get('role', 'Guest')

		if not username or not password or password == '':
			flash('Please enter a username and password.')
		else:
			# Form was completed
			matching_user = "SELECT user_pk FROM users WHERE username = %s;"
			user_does_exist = duplicate_check(matching_user, [username])

			if user_does_exist:
				flash('Username already exists')
			else:
				# User does not already exist - create it
				new_user = "INSERT INTO users (username, password, role_fk) VALUES (%s, %s, %s);"
				db_change(new_user, [username, password, role])
				flash('Your account was created!')

	return render_template('create_user.html')


@app.route('/add_facility', methods=['GET', 'POST'])
def add_facility():
	if request.method == 'POST':
		fcode = request.form.get('fcode', None).strip()
		common_name = request.form.get('common_name', None)
		location = request.form.get('location', None)

		# Get all current facilities for table population
		all_facilities = db_query("SELECT * FROM facilities;", [])

		# If something is missing from the form...
		if not fcode or not common_name or not location:
			flash('Please complete the form')
			return render_template('add_facility.html', data=all_facilities)

		else:
			# Check for duplicate entry attempt...
			matching_facilities = "SELECT facility_pk FROM facilities WHERE fcode=%s OR common_name=%s;"
			facility_does_exist = duplicate_check(matching_facilities, [fcode, common_name])

			if facility_does_exist:
				flash('There already exists a facility with that fcode or common name!')
				return render_template('add_facility.html', data=all_facilities)
			else:
				# Facility does not already exist - create it
				new_facility = "INSERT INTO facilities (fcode, common_name, location) VALUES (%s, %s, %s);"
				db_change(new_facility, [fcode, common_name, location])
				flash('New facility was created!')

	# Update all_facilities after insert, but before template rendering
	all_facilities = db_query("SELECT * FROM facilities;", [])

	return render_template('add_facility.html', data=all_facilities)


@app.route('/add_asset', methods=['GET', 'POST'])
def add_asset():
	# Create Query Strings for GET and POST utilization
	all_assets_query_string = "SELECT assets.asset_tag, assets.description, facilities.location FROM assets JOIN facilities ON assets.facility_fk = facilities.facility_pk;"
	all_facilities_query_string = "SELECT * FROM facilities;"

	if request.method == 'POST':
		asset_tag = request.form.get('asset_tag', None).strip()
		description = request.form.get('description', None)
		facility = request.form.get('facility')
		date = request.form.get('date')
		disposed = False

		# Get all current assets and facilities for table/drop-down population
		all_assets = db_query(all_assets_query_string, [])
		all_facilities = db_query(all_facilities_query_string, [])

		# Handle table when no assets in database
		if all_assets is None:
			all_assets = [('NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES')]

		# If something is missing from the form...
		if not asset_tag or not description or not facility or not date:
			flash('Please complete the form')
			return render_template('add_asset.html', assets_list=all_assets, facilities_list=all_facilities)
		else:
			try:
				validated_date = validate_date(date)
			except ValueError or TypeError or UnboundLocalError:
				flash('Please enter the date in the following format:\nMM/DD/YYYY')
				return render_template('add_asset.html', assets_list=all_assets, facilities_list=all_facilities)

			# Check for duplicate entry attempt...
			matching_assets = "SELECT asset_pk FROM assets WHERE asset_tag=%s;"
			asset_does_exist = duplicate_check(matching_assets, [asset_tag])

			if asset_does_exist:
				flash('There already exists an asset with that tag!')
			else:
				# Asset does not already exist - create it...
				new_asset = "INSERT INTO assets (facility, asset_tag, description, disposed) VALUES (%s, %s, %s, %s);"
				db_change(new_asset, [facility, asset_tag, description, disposed])

				recently_added_asset = "SELECT asset_pk FROM assets WHERE asset_tag = %s"
				asset_fk = db_query(recently_added_asset, [asset_tag])

				new_asset_at = "INSERT INTO asset_at (asset_fk, facility, arrive_dt) VALUES (%s, %s, %s);"
				db_change(new_asset_at, [asset_fk[0][0], facility, validated_date])
				flash('New asset added!')

	# Update all_assets after insert, but before template rendering
	all_assets = db_query(all_assets_query_string, [])
	all_facilities = db_query(all_facilities_query_string, [])

	# Handle situation of no assets in database
	if all_assets is None:
		all_assets = [('NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES')]

	return render_template('add_asset.html', assets_list=all_assets, facilities_list=all_facilities)


@app.route('/dispose_asset', methods=['GET', 'POST'])
def dispose_asset():
	if session.get('perms') != 2:
		# Not a logistics officer...
		flash('You are not a Logistics Officer.\nYou do not have permissions to remove assets!')
		return render_template('dashboard.html')
	else:
		# Get all current assets for table population
		all_assets_query_string = "SELECT assets.asset_tag, assets.description, facilities.location, assets.disposed FROM assets " \
								  "JOIN facilities ON assets.facility_fk = facilities.facility_pk;"
		all_assets = db_query(all_assets_query_string, [])

		# Handle table when no assets in database
		if all_assets is None:
			all_assets = [('NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES')]
			flash('There are currently no assets to remove')
			return render_template('dispose_asset.html', assets_list=all_assets)

		if request.method == 'POST':
			asset_tag = request.form.get('asset_tag', None).strip()
			date = request.form.get('date')

			# If something is missing from the form...
			if not asset_tag or not date:
				flash('Please complete the form')
				return render_template('dispose_asset.html', assets_list=all_assets)
			else:
				try:
					validated_date = validate_date(date)
				except ValueError or TypeError or UnboundLocalError:
					flash('Please enter the date in the following format:\nMM/DD/YYYY')
					return render_template('dispose_asset.html', assets_list=all_assets)

				# Check for matching tag...
				matching_asset = "SELECT asset_pk FROM assets WHERE asset_tag=%s;"
				asset_does_exist = duplicate_check(matching_asset, [asset_tag])

				if asset_does_exist:
					# Get asset_fk for asset_at update (returns a tuple in an array)
					asset_fk = db_query(matching_asset, [asset_tag])[0][0]

					# Change asset_at table to reflect impending disposal
					update_asset_at = "UPDATE asset_at SET depart_dt=%s WHERE asset_fk=%s;"
					db_change(update_asset_at, [validated_date, asset_fk])

					# Remove asset from assets
					asset_to_dispose = "UPDATE assets SET disposed=TRUE WHERE asset_tag=%s;"
					db_change(asset_to_dispose, [asset_tag])

					# Update current assets for table population ('disposed' column will have changed)
					all_assets = db_query(all_assets_query_string, [])

					# Handle table when no assets in database
					if all_assets is None:
						all_assets = [('NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES')]

					flash('Asset removed!')
					return render_template('dispose_asset.html', assets_list=all_assets)
				else:
					flash('There does not exist an asset with that tag!')
					return render_template('dispose_asset.html', assets_list=all_assets)

		return render_template('dispose_asset.html', assets_list=all_assets)


@app.route('/asset_report', methods=['GET', 'POST'])
def asset_report():
	all_facilities_query_string = "SELECT * FROM facilities;"

	# If a form has been submitted
	if request.method == 'POST':
		# List of single-tuples of all facilities to populate drop-down
		all_facilities = db_query(all_facilities_query_string, [])

		# User Input from Form
		facility = request.form.get('facility')
		date = request.form.get('date')

		# Validate Inputs
		if not date:
			flash('Please complete the form')
			return render_template('asset_report.html', facilities_list=all_facilities, report=False)
		else:
			try:
				validated_date = validate_date(date)
			except ValueError or TypeError or UnboundLocalError:
				flash('Please enter the date in the following format:\nMM/DD/YYYY')
				return render_template('asset_report.html', facilities_list=all_facilities, report=False)

		# Assets at all facilities
		if facility == 'All':
			all_assets_report = "SELECT assets.asset_tag, assets.description, facilities.location, asset_at.arrive_dt, asset_at.depart_dt FROM assets " \
								"JOIN facilities ON assets.facility_fk = facilities.facility_pk JOIN asset_at ON assets.asset_pk = asset_at.asset_fk " \
								"WHERE (asset_at.depart_dt >= %s OR asset_at.depart_dt IS NULL) " \
								"AND asset_at.arrive_dt <= %s;"
			all_assets = db_query(all_assets_report, [validated_date, validated_date])

			# No Results
			if all_assets is None:
				all_assets = [('NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES')]
				msg = ('There exists no asset within any facility on', validated_date)
				flash(msg)

			# Handle <h4> at top of asset_report for all facilities option - sought for as facility[2]
			facility = ['', '', 'all facilities']

			return render_template('asset_report.html', facility=facility, date=validated_date, assets_list=all_assets, facilities_list=all_facilities, report=True)

		# Assets at a specific facility
		else:
			individual_facility_report = "SELECT assets.asset_tag, assets.description, facilities.location, asset_at.arrive_dt, asset_at.depart_dt " \
										 "FROM assets " \
					   					 "JOIN (SELECT facility_pk, location FROM facilities WHERE facility_pk = %s) as facilities ON facilities.facility_pk = assets.facility_fk " \
					   					 "JOIN asset_at ON assets.asset_pk = asset_at.asset_fk " \
										 "WHERE (asset_at.depart_dt >= %s OR asset_at.depart_dt IS NULL) " \
										 "AND asset_at.arrive_dt <= %s;"
			filtered_assets = db_query(individual_facility_report, [facility, validated_date, validated_date])

			# No Results
			if filtered_assets is None:
				filtered_assets = [('NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES', 'NO ENTRIES')]
				msg = ('There exists no asset within', filtered_assets[2], 'on', validated_date)
				flash(msg)

			return render_template('asset_report.html', facility=filtered_assets[0][2], date=validated_date, assets_list=filtered_assets, facilities_list=all_facilities, report=True)

	# List of single-tuples of all facilities to populate drop-down
	all_facilities = db_query(all_facilities_query_string, [])

	return render_template('asset_report.html', facilities_list=all_facilities, report=False)


# MARK: ERROR PAGES
@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404


@app.route('/failed_query', methods=['GET'])
def failed_query(query_string):
	return render_template('failed_query.html', query=query_string)


# Application Deployment
if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8080, debug=True)
