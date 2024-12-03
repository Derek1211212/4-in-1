from flask import Flask, jsonify, request, render_template, session, redirect, url_for, flash
from werkzeug.security import check_password_hash

from datetime import datetime
import logging
import mysql.connector
import math
from mysql.connector import Error
from config import Config
import os
import pandas as pd
import io
from flask import send_file
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from math import radians, cos, sin, sqrt, atan2
from geopy.geocoders import Nominatim
from decimal import Decimal
from functools import wraps
from geopy.distance import geodesic
import psycopg2
import psycopg2.extras
from functools import lru_cache
from flask_mail import Mail, Message



logging.basicConfig(level=logging.DEBUG)  # Capture debug-level logs
app = Flask(__name__)
app.config.from_object(Config)
app.logger.setLevel(logging.DEBUG)

def get_db_connection():
    try:
        # Print database credentials for debugging
        app.logger.debug(f"Connecting to database with credentials: "
                         f"Host: {app.config['MYSQL_HOST']}, "
                         f"User: {app.config['MYSQL_USER']}, "
                         f"Database: {app.config['MYSQL_DB']}, "
                         f"Port: {app.config['MYSQL_PORT']}")

        connection = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB'],
            port=app.config['MYSQL_PORT']  # Use the port from the config
        )
        if connection.is_connected():
            app.logger.info("Database connection established successfully.")
            return connection
    except Error as e:
        app.logger.error(f"Error connecting to MySQL: {e}")
        return None  # Handle the error as you see fit


from datetime import datetime, timedelta

@app.route('/login', methods=['GET', 'POST'])
def login():
    app.logger.debug("Login route accessed.")

    if request.method == 'POST':
        app.logger.debug("POST request received.")
        user_id = request.form['user_id']
        username = request.form['username']
        password = request.form['password']
        app.logger.debug(f"Received user_id: {user_id}, username: {username}")

        connection = get_db_connection()
        if not connection:
            app.logger.error("Database connection failed!")
            flash('Database connection failed!', 'danger')
            return redirect(url_for('login'))

        cursor = connection.cursor(dictionary=True)
        try:
            app.logger.debug("Executing query to fetch user.")
            cursor.execute("SELECT * FROM users WHERE user_id = %s AND name = %s", (user_id, username))
            user = cursor.fetchone()
            app.logger.debug(f"Query result: {user}")

            if user:
                if user['password'] == password:
                    role = user.get('role', '').lower()
                    app.logger.info(f"User authenticated. Role: {role}")
                    session['user_id'] = user['user_id']
                    flash('Login successful!', 'success')

                    if role == 'mechanic':
                        return redirect(url_for('mechanic_dashboard'))
                    elif role == 'car_owner':
                        return redirect(url_for('car_owner_dashboard'))
                    elif role == 'parts_seller':
                        return redirect(url_for('upload_part'))
                    elif role == 'towing_company':
                        return redirect(url_for('tow_service_ad_upload'))
                    else:
                        flash('Role not recognized!', 'danger')
                else:
                    app.logger.warning("Incorrect password entered.")
                    flash('Incorrect password.', 'danger')
            else:
                app.logger.warning("No user found with the provided credentials.")
                flash('Invalid user ID or username.', 'danger')
        except Exception as e:
            app.logger.error(f"Error during login: {e}")
            flash('An error occurred while processing your login.', 'danger')
        finally:
            cursor.close()
            connection.close()
            app.logger.debug("Database connection closed.")

    return render_template('login.html')




def login_required(f):
	    @wraps(f)
	    def decorated_function(*args, **kwargs):
	        if 'user_id' not in session:
	            flash('Please log in first!', 'danger')
	            return redirect(url_for('login'))
	        return f(*args, **kwargs)
	    return decorated_function


@app.route('/')
def home():
    return render_template('Homepage.html')



@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/homepage')
def homepage():
    if 'user_id' in session:
        connection = get_db_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            sql = "SELECT role FROM users WHERE user_id = %s"
            cursor.execute(sql, (session['user_id'],))
            user = cursor.fetchone()
            
            if user:
                role = user['role']
                app.logger.debug(f"User role: {role}")  # Log the retrieved role
                if role == 'mechanic':
                    app.logger.debug("Redirecting to mechanic_dashboard")
                    return redirect(url_for('mechanic_dashboard'))
                elif role == 'car_owner':
                    app.logger.debug("Redirecting to car_owner_dashboard")
                    return redirect(url_for('car_owner_dashboard'))
                elif role == 'parts_seller':
                    app.logger.debug("Redirecting to upload_part")
                    return redirect(url_for('upload_part'))
                elif role == 'Towing_Company':
                    app.logger.debug("Redirecting to tow_service_ad_upload")
                    return redirect(url_for('tow_service_ad_upload'))
            else:
                flash('User not found!', 'danger')
                return redirect(url_for('login'))
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    else:
        flash('Please log in first!', 'danger')
        return redirect(url_for('login'))



def get_pending_appointments_count():
    		conn = get_db_connection()
    		cursor = conn.cursor()
    		cursor.execute("SELECT COUNT(*) FROM appointments WHERE status = 'pending'")
    		count = cursor.fetchone()[0]
    		cursor.close()
    		conn.close()
   	 	return count
       



@app.route('/mechanic_dashboard')
@login_required
def mechanic_dashboard():
    app.logger.debug("Accessing mechanic_dashboard route")  # Debugging statement
    if 'user_id' in session:
        user_id = session['user_id']
        app.logger.debug(f"Session User ID: {user_id}")  # Debugging statement
        connection = get_db_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            try:
                # Fetch mechanic's name using user_id from session
                cursor.execute("""SELECT name FROM mechanic WHERE user_id = %s""", (user_id,))
                mechanic = cursor.fetchone()
                
                # Fetch the count of pending appointments
                pending_appointments = get_pending_appointments_count()
                
                app.logger.debug(f"Fetched Mechanic Data: {mechanic}")  # Debugging statement

                if mechanic:
                    mechanic_name = mechanic['name']
                    app.logger.debug(f"Fetched Mechanic Name: {mechanic_name}")  # Debugging statement

                    # Render the mechanic dashboard with mechanic name and pending appointment count
                    return render_template('mechanic_dashboard.html', mechanic_name=mechanic_name, pending_appointments=pending_appointments)
                else:
                    app.logger.debug("No mechanic found with the given user_id.")  # Debugging statement
                    flash('Mechanic not found!', 'danger')
                    return redirect(url_for('login'))

            except mysql.connector.Error as e:
                app.logger.error(f"MySQL error: {e}")
                flash('An error occurred while fetching data from the database.', 'danger')
                return redirect(url_for('login'))

        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
    else:
        flash('Please log in first!', 'danger')
        return redirect(url_for('login'))





@app.route('/view_service_history/<int:vehicle_id>')
@login_required
def view_service_history(vehicle_id):
    if 'user_id' in session:
        connection = get_db_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            # Query to fetch the service history of the vehicle
            sql = """
                SELECT s.name AS service_name, ml.work_description, ml.log_date 
                FROM maintenance_logs ml
                JOIN services s ON ml.service_id = s.service_id
                WHERE ml.vehicle_id = %s
                ORDER BY ml.log_date DESC
            """
            cursor.execute(sql, (vehicle_id,))
            service_history = cursor.fetchall()
            return render_template('view_service_history.html', service_history=service_history)
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    else:
        flash('Please log in first!', 'danger')
        return redirect(url_for('login'))


@app.route('/service_catalog')
@login_required
def service_catalog():
    if 'user_id' in session:
        connection = get_db_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            # Fetch list of services from the database
            sql = "SELECT * FROM services"
            cursor.execute(sql)
            services = cursor.fetchall()
            return render_template('service_catalog.html', services=services)
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    else:
        flash('Please log in first!', 'danger')
        return redirect(url_for('login'))


@app.route('/inventory_management')
@login_required
def inventory_management():
    if 'user_id' in session:
        connection = get_db_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM inventory")
            inventory = cursor.fetchall()
            return render_template('inventory_management.html', inventory=inventory)
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    else:
        flash('Please log in first!', 'danger')
        return redirect(url_for('login'))


@app.route('/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    preferred_mechanic = None
    
    if request.method == 'POST':
        # Get form data
        full_name = request.form['full_name']
        phone_number = request.form['phone_number']
        email_address = request.form['email_address']
        address = request.form['address']
        communication_pref = request.form['communication_pref']
        emergency_contact_name = request.form['emergency_contact_name']
        emergency_contact_number = request.form['emergency_contact_number']
        
        # Connect to the database and insert the data
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            query = """
                INSERT INTO Customer (full_name, phone_number, email_address, address,
                                      preferred_mechanic, communication_pref, created_at,
                                      emergency_contact_name, emergency_contact_number)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s)
            """
            cursor.execute(query, (full_name, phone_number, email_address, address,
                                   preferred_mechanic, communication_pref,
                                   emergency_contact_name, emergency_contact_number))
            conn.commit()
            cursor.close()
            conn.close()
            
            return redirect(url_for('add_customer'))  # Redirect after POST

    # Retrieve mechanic_id from the session
    if 'user_id' in session:
        user_id = session['user_id']
        # Query to get the mechanic_id based on the user_id
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mechanic_id FROM mechanic WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            if result:
                preferred_mechanic = result[0]  # Get mechanic_id from result
            cursor.close()
            conn.close()
    
    return render_template('add_customer.html', preferred_mechanic=preferred_mechanic)  # Render the form for GET request


@app.route('/customers', methods=['GET', 'POST'])
@login_required
def view_customers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Retrieve user_id from the session
    user_id = session.get('user_id')  # Ensure this is set during login

    # Base query to fetch customers filtered by user_id
    base_query = "SELECT * FROM Customer WHERE user_id = %s"
    query_params = [user_id]

    # Check if the request is POST (searching)
    if request.method == 'POST':
        surname = request.form.get('surname')
        if surname:
            # Add condition for partial surname match
            base_query += " AND full_name LIKE %s"
            query_params.append(f"%{surname}%")

    cursor.execute(base_query, query_params)
    customers = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('view_customers.html', customers=customers)



@app.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        full_name = request.form['full_name']
        phone_number = request.form['phone_number']
        email_address = request.form['email_address']
        address = request.form['address']
        communication_pref = request.form['communication_pref']
        emergency_contact_name = request.form['emergency_contact_name']
        emergency_contact_number = request.form['emergency_contact_number']
        
        query = """
            UPDATE Customer SET full_name = %s, phone_number = %s, email_address = %s,
                                address = %s, communication_pref = %s,
                                emergency_contact_name = %s, emergency_contact_number = %s
            WHERE customer_id = %s
        """
        cursor = conn.cursor()
        cursor.execute(query, (full_name, phone_number, email_address, address, 
                               communication_pref, emergency_contact_name, emergency_contact_number, customer_id))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('view_customers'))

    # Fetch the customer data for the given customer_id to pre-fill the form
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Customer WHERE customer_id = %s", (customer_id,))
    customer = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('edit_customer.html', customer=customer)



@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
@login_required
def delete_customer(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete the customer from the database
    query = "DELETE FROM Customer WHERE customer_id = %s"
    cursor.execute(query, (customer_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('view_customers'))



@app.route('/vehicles', methods=['GET', 'POST'])
@login_required
def view_vehicles():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Initialize the vehicles list
    vehicles = []

    # Retrieve the user_id from the session
    user_id = session.get('user_id')

    # Check if the request is POST (searching)
    if request.method == 'POST':
        vin = request.form.get('vin')
        if vin:
            # Search by VIN (partial match) and filter by user_id
            query = "SELECT * FROM Vehicle WHERE vin LIKE %s AND customer_id IN (SELECT customer_id FROM customer WHERE user_id = %s)"
            cursor.execute(query, (f"%{vin}%", user_id))
        else:
            # No search term, show all vehicles for the current user
            query = "SELECT * FROM Vehicle WHERE customer_id IN (SELECT customer_id FROM customer WHERE user_id = %s)"
            cursor.execute(query, (user_id,))
    else:
        # GET request, show all vehicles for the current user
        query = "SELECT * FROM Vehicle WHERE customer_id IN (SELECT customer_id FROM customer WHERE user_id = %s)"
        cursor.execute(query, (user_id,))

    vehicles = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('view_vehicles.html', vehicles=vehicles)


@app.route('/add_vehicle', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        make = request.form['make'].strip().upper()
        model = request.form['model'].strip().upper()
        year = request.form['year']
        license_plate_number = request.form['license_plate_number'].strip().upper()

        # Generate the VIN
        if make and model and year and license_plate_number:
            vin = (
                make[-3:] + model[:2] + str(year)[-2:] + license_plate_number[-2:] + str(customer_id)
            ).upper()

            # Retrieve the user_id from the session
            user_id = session.get('user_id')

            # Insert the vehicle into the database with user_id associated to the customer
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                query = """
                    INSERT INTO Vehicle (customer_id, make, model, year, vin, license_plate_number)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (customer_id, make, model, year, vin, license_plate_number))
                conn.commit()
                flash('Vehicle added successfully!', 'success')
            except mysql.connector.IntegrityError:
                flash('Invalid customer ID.', 'error')
                return redirect(url_for('add_vehicle'))  # Redirect back to the add vehicle form on error
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for('view_vehicles'))

    return render_template('add_vehicle.html')





# Route to edit a vehicle
@app.route('/edit_vehicle/<int:vehicle_id>', methods=['GET', 'POST'])
@login_required
def edit_vehicle(vehicle_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        customer_id = request.form['customer_id']
        make = request.form['make']
        model = request.form['model']
        year = request.form['year']
        vin = request.form['vin']
        license_plate_number = request.form['license_plate_number']

        cursor.execute("""
            UPDATE Vehicle SET customer_id = %s, make = %s, model = %s, year = %s, vin = %s, 
                               license_plate_number = %s WHERE vehicle_id = %s
        """, (customer_id, make, model, year, vin, license_plate_number, vehicle_id))
        conn.commit()

        flash('Vehicle updated successfully!', 'success')
        cursor.close()
        conn.close()
        return redirect(url_for('view_vehicles'))

    # Pre-fill the form with the vehicle's data
    cursor.execute("SELECT * FROM Vehicle WHERE vehicle_id = %s", (vehicle_id,))
    vehicle = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_vehicle.html', vehicle=vehicle)

# Route to delete a vehicle
@app.route('/delete_vehicle/<int:vehicle_id>', methods=['POST'])
@login_required
def delete_vehicle(vehicle_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Vehicle WHERE vehicle_id = %s", (vehicle_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Vehicle deleted successfully!', 'success')
    return redirect(url_for('view_vehicles'))

@app.route('/add_maintenance_log', methods=['GET', 'POST'])
@login_required
def add_maintenance_log():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Get form data
        vin = request.form['vin'].strip().upper()  # Capture VIN from the form
        work_description = request.form['work_description']
        parts_used = request.form['parts_used']
        cost_of_parts = request.form['cost_of_parts']
        labor_cost = request.form['labor_cost']
        total_cost = request.form['total_cost']
        log_date = request.form['log_date']
        next_scheduled_service = request.form['next_scheduled_service']
        service_type = request.form['service_type']
        warranty_information = request.form['warranty_information']
        mechanic_ids = request.form.getlist('mechanic_ids')  # List of selected mechanic IDs

        # Get the vehicle ID using VIN
        cursor.execute("SELECT vehicle_id FROM Vehicle WHERE vin = %s", (vin,))
        vehicle = cursor.fetchone()
        if vehicle is None:
            flash('Invalid VIN. No vehicle found.', 'error')
            return redirect(url_for('add_maintenance_log'))

        vehicle_id = vehicle[0]

        # Insert the maintenance log
        cursor.execute("""
            INSERT INTO maintenance_logs (
                vehicle_id, vin, work_description, parts_used, cost_of_parts, labor_cost, 
                total_cost, log_date, next_scheduled_service, service_type, warranty_information
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (vehicle_id, vin, work_description, parts_used, cost_of_parts, labor_cost,
              total_cost, log_date, next_scheduled_service, service_type, warranty_information))
        log_id = cursor.lastrowid  # Get the ID of the newly inserted log

        # Insert into the join table for each selected mechanic
        for mechanic_id in mechanic_ids:
            cursor.execute("INSERT INTO maintenance_log_mechanics (log_id, mechanic_id) VALUES (%s, %s)", (log_id, mechanic_id))

        conn.commit()
        flash('Maintenance log added successfully!', 'success')
        return redirect(url_for('view_maintenance_logs'))

    # Query mechanics to display in the dropdown
    cursor.execute("SELECT employee_id AS user_id, employee_name AS name FROM Company_Employees WHERE role = 'mechanic'")
    mechanics = cursor.fetchall()

    # Query service types to display in the dropdown
    cursor.execute("SELECT service_id, name FROM services")
    services = cursor.fetchall()

    conn.close()
    return render_template('add_maintenance_log.html', mechanics=mechanics, services=services)




 
@app.route('/view_maintenance_logs', methods=['GET', 'POST'])
@login_required
def view_maintenance_logs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Handle filtering by log date if a date is provided
    log_date_filter = request.form.get('log_date_filter')
    if log_date_filter:
        cursor.execute(""" 
            SELECT ml.*, e.name AS mechanic_name
            FROM maintenance_logs ml
            JOIN employees e ON ml.employee_id = e.employee_id
            WHERE ml.log_date = %s
        """, (log_date_filter,))
    else:
        cursor.execute(""" 
            SELECT ml.*, e.name AS mechanic_name
            FROM maintenance_logs ml
            JOIN employees e ON ml.employee_id = e.employee_id
        """)

    logs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('view_maintenance_logs.html', logs=logs)




@app.route('/edit_log/<int:log_id>', methods=['GET', 'POST'])
@login_required
def edit_log(log_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Update log details with form data
        log_data = {
            'work_description': request.form.get('work_description'),
            'parts_used': request.form.get('parts_used'),
            'cost_of_parts': request.form.get('cost_of_parts'),
            'labor_cost': request.form.get('labor_cost'),
            'total_cost': request.form.get('total_cost'),
            'log_date': request.form.get('log_date'),
            'service_type': request.form.get('service_type'),
            'warranty_information': request.form.get('warranty_information'),
            'next_scheduled_service': request.form.get('next_scheduled_service')  # New field
        }
        
        cursor.execute(""" 
            UPDATE maintenance_logs
            SET work_description = %s,
                parts_used = %s,
                cost_of_parts = %s,
                labor_cost = %s,
                total_cost = %s,
                log_date = %s,
                service_type = %s,
                warranty_information = %s,
                next_scheduled_service = %s  -- Update the new field
            WHERE log_id = %s
        """, (log_data['work_description'], log_data['parts_used'], log_data['cost_of_parts'],
              log_data['labor_cost'], log_data['total_cost'], log_data['log_date'],
              log_data['service_type'], log_data['warranty_information'], 
              log_data['next_scheduled_service'], log_id))

        conn.commit()
        flash('Log updated successfully!')
        return redirect(url_for('view_maintenance_logs'))

    # Retrieve the specific log for editing
    cursor.execute("SELECT * FROM maintenance_logs WHERE log_id = %s", (log_id,))
    log = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('edit_log.html', log=log)




@app.route('/delete_log/<int:log_id>', methods=['POST'])
@login_required
def delete_log(log_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # First, delete associated mechanics from maintenance_log_mechanics
        cursor.execute('DELETE FROM maintenance_log_mechanics WHERE log_id = %s', (log_id,))

        # Then, delete the log itself
        cursor.execute('DELETE FROM maintenance_logs WHERE log_id = %s', (log_id,))

        conn.commit()
        flash('Log deleted successfully!')
    except mysql.connector.Error as err:
        conn.rollback()  # Rollback the transaction if there's an error
        flash(f'Error occurred: {err}')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('view_maintenance_logs'))



@app.route('/export_logs', methods=['GET'])
@login_required
def export_logs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT ml.*, GROUP_CONCAT(u.name SEPARATOR ', ') AS mechanics
        FROM maintenance_logs ml
        JOIN maintenance_log_mechanics mlm ON ml.log_id = mlm.log_id
        JOIN users u ON mlm.mechanic_id = u.user_id
        GROUP BY ml.log_id
    """)
    logs = cursor.fetchall()

    cursor.close()
    conn.close()

    # Create a Pandas DataFrame
    df = pd.DataFrame(logs)

    # Create an Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Maintenance Logs', index=False)

    output.seek(0)
    return send_file(output, as_attachment=True, download_name='maintenance_logs.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/mechanic/appointments')
@login_required
def view_appointments():
    # Retrieve the user_id from the session
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to fetch appointments associated with the logged-in user
    cursor.execute("""
        SELECT 
            a.appointment_id, 
            a.appointment_date, 
            s.name AS service_name, 
            v.make, 
            v.model,
            c.full_name, 
            c.phone_number, 
            c.email_address 
        FROM appointments a 
        JOIN services s ON a.service_id = s.service_id 
        JOIN Vehicle v ON a.vehicle_id = v.vehicle_id 
        JOIN Customer c ON a.customer_id = c.customer_id
        JOIN mechanic m ON a.mechanic_id = m.mechanic_id
        WHERE a.status = 'pending' AND m.user_id = %s
    """, (user_id,))
    
    appointments = cursor.fetchall()

    # Convert tuples to dictionaries
    appointments_list = [
        {
            'appointment_id': appointment[0],
            'appointment_date': appointment[1],
            'service_name': appointment[2],
            'make': appointment[3],
            'model': appointment[4],
            'full_name': appointment[5],
            'phone_number': appointment[6],
            'email_address': appointment[7]
        }
        for appointment in appointments
    ]

    conn.close()
    return render_template('appointments.html', appointments=appointments_list)


# Approve Appointment Route
@app.route('/mechanic/approve_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def approve_appointment(appointment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = 'completed' WHERE appointment_id = %s", (appointment_id,))
    conn.commit()
    conn.close()
    flash('Appointment approved successfully!', 'success')
    return redirect(url_for('view_appointments'))

# Deny Appointment Route
@app.route('/mechanic/deny_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def deny_appointment(appointment_id):
    denial_reason = request.form['denial_reason']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = 'canceled', denial_reason = %s WHERE appointment_id = %s", (denial_reason, appointment_id))
    conn.commit()
    conn.close()
    flash('Appointment denied with reason.', 'danger')
    return redirect(url_for('view_appointments'))



@app.route('/mechanic/create_appointment', methods=['POST'])
@login_required
def create_appointment():
    mechanic_id = request.form['mechanic_id']
    customer_id = request.form['customer_id']
    vehicle_id = request.form['vehicle_id']
    service_id = request.form['service_id']
    appointment_date = request.form['appointment_date']

    user_id = session.get('user_id')  # Retrieve user_id from session

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (appointment_date, service_id, vehicle_id, customer_id, user_id, mechanic_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending')
    """, (appointment_date, service_id, vehicle_id, customer_id, user_id, mechanic_id))
    conn.commit()
    conn.close()
    
    flash('Appointment created successfully!', 'success')
    return redirect(url_for('view_appointments'))



@app.route('/mechanic/services', methods=['GET'])
@login_required
def get_services():
    # Retrieve the user_id from the session
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query to fetch services associated with the logged-in mechanic
    cursor.execute("""
        SELECT s.service_id, s.name 
        FROM services s
        JOIN mechanic m ON s.mechanic_id = m.mechanic_id
        WHERE m.user_id = %s
    """, (user_id,))

    services = cursor.fetchall()
    conn.close()
    return jsonify(services)




@app.route('/customer/vehicles', methods=['GET'])
@login_required
def get_vehicles():
    # Retrieve the user_id from the session
    user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query to fetch vehicles associated with customers belonging to the logged-in user
    cursor.execute("""
        SELECT v.vehicle_id, v.make, v.model 
        FROM Vehicle v
        JOIN Customer c ON v.customer_id = c.customer_id
        WHERE c.user_id = %s
    """, (user_id,))

    vehicles = cursor.fetchall()
    conn.close()
    return jsonify(vehicles)



@app.route('/mechanic/create_appointment', methods=['GET'])
@login_required
def render_create_appointment():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all mechanics
    cursor.execute("SELECT mechanic_id, name FROM mechanic")
    mechanics = cursor.fetchall()

    # Fetch all customers
    cursor.execute("SELECT customer_id, full_name FROM Customer")
    customers = cursor.fetchall()

    conn.close()
    return render_template('create_appointment.html', mechanics=mechanics, customers=customers)


# Route to display inventory
@app.route('/inventory')
@login_required
def inventory():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Retrieve the user_id from the session
    user_id = session.get('user_id')

    # Query to fetch inventory data, filtering by user_id
    cursor.execute('SELECT * FROM inventory WHERE user_id = %s', (user_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('inventory.html', items=items)

@app.route('/add_inventory', methods=['GET', 'POST'])
@login_required
def add_inventory():
    if request.method == 'POST':
        name = request.form['name']
        quantity = request.form['quantity']
        supplier_name = request.form['supplier_name']
        cost = request.form['cost']
        reorder_level = request.form['reorder_level']
        part_description = request.form['part_description']

        # Retrieve the user_id from the session
        user_id = session.get('user_id')

        # Fetch the mechanic_id based on the user_id
        connection = get_db_connection()
        if connection:
            with connection.cursor() as cursor:
                mechanic_id_query = "SELECT mechanic_id FROM mechanic WHERE user_id = %s"
                cursor.execute(mechanic_id_query, (user_id,))
                mechanic_id = cursor.fetchone()

                if mechanic_id:
                    # Insert into the inventory table
                    insert_query = """
                    INSERT INTO inventory (name, quantity, supplier_name, cost, reorder_level, part_description, mechanic_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (name, quantity, supplier_name, cost, reorder_level, part_description, mechanic_id[0]))
                    connection.commit()  # Commit the transaction
                    flash('Inventory item added successfully!', 'success')
                    return redirect(url_for('inventory'))
                else:
                    flash('Mechanic ID not found!', 'error')
        else:
            flash('Database connection error!', 'error')

    # GET request: Fetch supplier names for the dropdown
    connection = get_db_connection()
    suppliers = []  # Initialize suppliers list
    if connection:
        with connection.cursor() as cursor:
            suppliers_query = "SELECT supplier_name FROM suppliers"
            cursor.execute(suppliers_query)
            suppliers = cursor.fetchall()  # Fetch all suppliers

    return render_template('add_inventory.html', suppliers=suppliers)





@app.route('/add_supplier', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        supplier_name = request.form['supplier_name']
        contact_person = request.form['contact_person']
        contact_number = request.form['contact_number']
        email = request.form['email']
        address = request.form['address']

        # Retrieve the user_id from the session
        user_id = session.get('user_id')

        # Fetch the mechanic_id based on the user_id
        connection = get_db_connection()
        if connection:
            with connection.cursor() as cursor:
                mechanic_id_query = "SELECT mechanic_id FROM mechanic WHERE user_id = %s"
                cursor.execute(mechanic_id_query, (user_id,))
                mechanic_id = cursor.fetchone()

                if mechanic_id:
                    # Insert into the suppliers table with the user_id
                    insert_query = """
                    INSERT INTO suppliers (supplier_name, contact_person, contact_number, email, address, mechanic_id, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (supplier_name, contact_person, contact_number, email, address, mechanic_id[0], user_id))
                    connection.commit()  # Commit the transaction
                    flash('Supplier added successfully!', 'success')
                    return redirect(url_for('view_suppliers'))
                else:
                    flash('Mechanic ID not found!', 'error')
        else:
            flash('Database connection error!', 'error')

    return render_template('add_supplier.html')


@app.route('/suppliers')
@login_required
def view_suppliers():
    # Retrieve the user_id from the session
    user_id = session.get('user_id')

    connection = get_db_connection()
    if connection:
        with connection.cursor() as cursor:
            # Fetch suppliers associated with the user_id
            query = "SELECT * FROM suppliers WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            suppliers = cursor.fetchall()
    else:
        suppliers = []

    return render_template('view_suppliers.html', suppliers=suppliers)



@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')



  
# Route to display mechanic settings
@app.route('/mechanic-settings', methods=['GET'])
@login_required
def mechanic_settings():
    conn = get_db_connection()
    if conn is None:
        return "Database connection failed!", 500

    cursor = conn.cursor()
    cursor.execute('SELECT mechanic_id, name FROM mechanic WHERE user_id = %s', (session['user_id'],))
    mechanics = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('mechanic_settings.html', mechanics=mechanics)

# Route to edit a specific mechanic
@app.route('/mechanic/edit/<int:mechanic_id>', methods=['GET', 'POST'])
@login_required
def edit_mechanic(mechanic_id):
    conn = get_db_connection()
    if conn is None:
        return "Database connection failed!", 500

    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        working_hours = request.form['working_hours']
        service_locations = request.form['service_locations']
        skills_certifications = request.form['skills_certifications']

        # Update mechanic info in the database
        cursor.execute('''
            UPDATE mechanic 
            SET name = %s, working_hours = %s, service_locations = %s, skills_certifications = %s 
            WHERE mechanic_id = %s
        ''', (name, working_hours, service_locations, skills_certifications, mechanic_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('mechanic_settings'))

    # If GET, fetch current mechanic info
    cursor.execute('SELECT * FROM mechanic WHERE mechanic_id = %s', (mechanic_id,))
    mechanic = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_mechanic.html', mechanic=mechanic)



@app.route('/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        position = request.form['position']
        date_hired = request.form['date_hired']

        # Validate inputs
        if not name or not email or not date_hired:
            flash('Name, Email, and Date Hired are required fields.', 'error')
            return redirect(url_for('add_employee'))

        user_id = session['user_id']  # Get the user_id from the session

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO employees (user_id, name, email, phone, position, date_hired) VALUES (%s, %s, %s, %s, %s, %s)',
                       (user_id, name, email, phone, position, date_hired))
        conn.commit()
        cursor.close()
        conn.close()

        flash('Employee added successfully!', 'success')
        return redirect(url_for('add_employee'))

    return render_template('add_employee.html')




@app.route('/employees')
@login_required
def employee_list():
    user_id = session['user_id']  # Get the user_id from the session

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Fetch results as dictionaries
    cursor.execute('SELECT * FROM employees WHERE user_id = %s', (user_id,))
    employees = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('employee_list.html', employees=employees)



@app.route('/support')
@login_required
def support():
    return render_template('support.html')

@app.route('/legal')
@login_required
def legal_information():
    return render_template('legal.html')

@app.route('/security-privacy')
@login_required
def security_privacy():
    return render_template('security_privacy.html')   



@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    # Get the user_id from the session
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        description = request.form['description']
        amount = request.form['amount']
        date_expense = request.form['date']
        category = request.form['category']

        # Insert the expense with user_id
        cursor.execute(
            'INSERT INTO expenses (description, amount, date, category, user_id) VALUES (%s, %s, %s, %s, %s)',
            (description, amount, date_expense, category, user_id)
        )
        conn.commit()
        return redirect(url_for('expenses'))

    # Filter by date range if provided
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date and end_date:
        # Fetch expenses filtered by date range and user_id
        query = 'SELECT * FROM expenses WHERE user_id = %s AND date BETWEEN %s AND %s ORDER BY date DESC'
        cursor.execute(query, (user_id, start_date, end_date))
    else:
        # Fetch all expenses filtered by user_id
        cursor.execute('SELECT * FROM expenses WHERE user_id = %s ORDER BY date DESC', (user_id,))

    expenses = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('expenses.html', expenses=expenses, start_date=start_date, end_date=end_date, datetime=datetime)



from flask import session

from decimal import Decimal
@app.route('/revenue', methods=['GET', 'POST'])
@login_required
def record_revenue():
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session.get('user_id')  # Retrieve user_id from session

    # Fetch customers
    cursor.execute("SELECT customer_id, full_name FROM customer WHERE user_id = %s", (user_id,))
    customers = cursor.fetchall()

    # Fetch services
    cursor.execute("SELECT service_id, name, price FROM services WHERE user_id = %s", (user_id,))
    services = cursor.fetchall()

    # Fetch parts
    cursor.execute("SELECT part_id, name, price FROM parts WHERE user_id = %s", (user_id,))
    parts = cursor.fetchall()

    # Retrieve mechanic_id using user_id from the 'mechanic' table
    cursor.execute("SELECT mechanic_id FROM mechanic WHERE user_id = %s", (user_id,))
    mechanic_result = cursor.fetchone()
    if mechanic_result:
        mechanic_id = mechanic_result[0]
    else:
        flash("No mechanic record found for the logged-in user. Please contact support.", "error")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Handle form data
        customer_id = request.form.get('customer_id')
        service_ids = request.form.getlist('service_ids')  # Multiple services
        part_ids = request.form.getlist('part_ids')  # Multiple parts
        revenue_date = request.form.get('date')

        # Handle new service addition
        new_service_name = request.form.get('new_service_name')
        new_service_price = request.form.get('new_service_price')

        if new_service_name and new_service_price:
            try:
                cursor.execute(
                    "INSERT INTO services (name, price, user_id) VALUES (%s, %s, %s)",
                    (new_service_name, float(new_service_price), user_id)
                )
                conn.commit()
                flash(f"Service '{new_service_name}' added successfully!", "success")
            except Error as e:
                flash(f"Error adding service: {str(e)}", "error")
                return redirect(url_for('record_revenue'))

        # Recalculate services after adding new service
        cursor.execute("SELECT service_id, name, price FROM services WHERE user_id = %s", (user_id,))
        services = cursor.fetchall()

        # Calculate total price for the selected services
        total_service_price = 0
        selected_services = []
        for service_id in service_ids:
            cursor.execute("SELECT price FROM services WHERE service_id = %s", (service_id,))
            service_price = cursor.fetchone()[0]
            total_service_price += service_price
            selected_services.append({
                'service_id': service_id,
                'service_price': service_price
            })

        # Calculate total price for the selected parts
        total_part_price = 0
        selected_parts = []
        for part_id in part_ids:
            cursor.execute("SELECT price FROM parts WHERE part_id = %s", (part_id,))
            part_price = cursor.fetchone()[0]
            total_part_price += part_price
            selected_parts.append({
                'part_id': part_id,
                'part_price': part_price
            })

        # Calculate the total price (sum of selected services and parts)
        total_price = total_service_price + total_part_price

        # Insert revenue for each selected service
        for service in selected_services:
            cursor.execute(
                '''INSERT INTO revenue (customer_id, service_id, service_price, part_id, part_price, mechanic_id, user_id, total_price, revenue_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (customer_id, service['service_id'], service['service_price'], None, None, mechanic_id, user_id, service['service_price'], revenue_date)
            )
            conn.commit()

        # Insert revenue for each selected part
        for part in selected_parts:
            cursor.execute(
                '''INSERT INTO revenue (customer_id, service_id, service_price, part_id, part_price, mechanic_id, user_id, total_price, revenue_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (customer_id, None, None, part['part_id'], part['part_price'], mechanic_id, user_id, part['part_price'], revenue_date)
            )
            conn.commit()

        flash("Revenue recorded successfully!", "success")
        return redirect(url_for('record_revenue'))

    return render_template('revenue.html', customers=customers, services=services, parts=parts)


@app.route('/revenue_summary', methods=['GET', 'POST'])
@login_required
def revenue_summary():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve mechanic_id based on user_id from the session
    user_id = session.get('user_id')
    cursor.execute("SELECT mechanic_id FROM mechanic WHERE user_id = %s", (user_id,))
    mechanic_id = cursor.fetchone()

    revenue_records = []

    if mechanic_id:
        mechanic_id = mechanic_id[0]

        if request.method == 'POST':
            start_date = request.form['start_date']
            end_date = request.form['end_date']

            if start_date and end_date:
                query = '''
                    SELECT r.revenue_id, r.revenue_date, c.full_name, 
                           IFNULL(s.name, 'No Service'), 
                           r.service_price, 
                           IFNULL(p.name, 'No Part'), 
                           r.part_price,
                           COALESCE(r.service_price, 0) + COALESCE(r.part_price, 0) AS total_price
                    FROM revenue r
                    JOIN customer c ON r.customer_id = c.customer_id
                    LEFT JOIN services s ON r.service_id = s.service_id
                    LEFT JOIN parts p ON r.part_id = p.part_id
                    WHERE r.revenue_date BETWEEN %s AND %s AND r.mechanic_id = %s
                '''
                cursor.execute(query, (start_date, end_date, mechanic_id))
                revenue_records = cursor.fetchall()

        else:
            query = '''
                SELECT r.revenue_id, r.revenue_date, c.full_name, 
                       IFNULL(s.name, 'No Service'), 
                       r.service_price, 
                       IFNULL(p.name, 'No Part'), 
                       r.part_price,
                       COALESCE(r.service_price, 0) + COALESCE(r.part_price, 0) AS total_price
                FROM revenue r
                JOIN customer c ON r.customer_id = c.customer_id
                LEFT JOIN services s ON r.service_id = s.service_id
                LEFT JOIN parts p ON r.part_id = p.part_id
                WHERE r.mechanic_id = %s
            '''
            cursor.execute(query, (mechanic_id,))
            revenue_records = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('revenue_summary.html', revenue_records=revenue_records)


@app.route('/edit_revenue/<int:revenue_id>', methods=['GET', 'POST'])
def edit_revenue(revenue_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    user_id = session.get('user_id')

    # Fetch the revenue record to edit
    cursor.execute("SELECT * FROM revenue WHERE revenue_id = %s", (revenue_id,))
    revenue_record = cursor.fetchone()

    # Fetch customers, services, and parts
    cursor.execute("SELECT customer_id, full_name FROM customer WHERE user_id = %s", (user_id,))
    customers = cursor.fetchall()

    cursor.execute("SELECT service_id, name, price FROM services WHERE user_id = %s", (user_id,))
    services = cursor.fetchall()

    cursor.execute("SELECT part_id, name, price FROM parts WHERE user_id = %s", (user_id,))
    parts = cursor.fetchall()

    if request.method == 'POST':
        # Retrieve form data
        date = request.form['date']
        customer_id = request.form.get('customer') or None
        service_id = request.form.get('service') or None
        service_price = request.form.get('service_price') or None
        part_id = request.form.get('part') or None
        part_price = request.form.get('part_price') or None

        # Convert prices to float
        service_price = float(service_price) if service_price else 0
        part_price = float(part_price) if part_price else 0

        # Calculate the total price (service + part price)
        total_price = service_price + part_price

        # Update the revenue record
        cursor.execute("""
            UPDATE revenue 
            SET revenue_date = %s, customer_id = %s, service_id = %s, service_price = %s, 
                part_id = %s, part_price = %s, total_price = %s
            WHERE revenue_id = %s
        """, (date, customer_id, service_id, service_price, part_id, part_price, total_price, revenue_id))

        connection.commit()
        cursor.close()
        connection.close()

        return redirect('/revenue_summary')

    cursor.close()
    connection.close()
    return render_template('edit_revenue.html', revenue_record=revenue_record, customers=customers, services=services, parts=parts)




@app.route('/delete_revenue/<int:revenue_id>', methods=['POST'])
@login_required
def delete_revenue(revenue_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete the record from the database
    cursor.execute("DELETE FROM revenue WHERE revenue_id = %s", (revenue_id,))
    conn.commit()

    # Redirect back to the revenue summary page
    return redirect(url_for('revenue_summary'))









@app.route('/services', methods=['GET', 'POST'])
@login_required
def manage_services():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve mechanic_id from the session
    user_id = session.get('user_id')  # Assuming user_id is stored in the session
    cursor.execute("SELECT mechanic_id FROM mechanic WHERE user_id = %s", (user_id,))
    mechanic = cursor.fetchone()

    if mechanic:
        mechanic_id = mechanic[0]

        # Fetch services for the mechanic
        cursor.execute("SELECT * FROM services WHERE mechanic_id = %s", (mechanic_id,))
        services = cursor.fetchall()

        if request.method == 'POST':
            # Retrieve the form data
            service_name = request.form.get('name', '').strip()
            service_description = request.form.get('description', '').strip()
            service_price = request.form.get('price', '').strip()
            service_duration = request.form.get('duration', '').strip()
            service_category = request.form.get('category', '').strip()
            service_availability = request.form.get('availability', '').strip()

            # Validate the description length
            if len(service_description) > 100:
                flash('Description cannot exceed 100 characters.', 'danger')
                return redirect(url_for('manage_services'))

            if 'edit_service_id' in request.form:
                # Update existing service
                service_id = request.form['edit_service_id']
                cursor.execute(
                    '''UPDATE services SET name = %s, description = %s, price = %s, duration = %s, category = %s, availability = %s, updated_at = NOW()
                       WHERE service_id = %s AND mechanic_id = %s''',
                    (service_name, service_description, service_price, service_duration, service_category, service_availability, service_id, mechanic_id)
                )
                conn.commit()
                flash('Service updated successfully!', 'success')

            elif 'delete_service_id' in request.form:
                # Delete service
                service_id = request.form['delete_service_id']
                cursor.execute("DELETE FROM services WHERE service_id = %s AND mechanic_id = %s", (service_id, mechanic_id))
                conn.commit()
                flash('Service deleted successfully!', 'success')

            else:
                # Add new service
                cursor.execute(
                    '''INSERT INTO services (mechanic_id, name, description, price, duration, category, availability, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())''',
                    (mechanic_id, service_name, service_description, service_price, service_duration, service_category, service_availability)
                )
                conn.commit()
                flash('Service added successfully!', 'success')

            return redirect(url_for('manage_services'))

        cursor.close()
        conn.close()
        return render_template('services.html', services=services)

    cursor.close()
    conn.close()
    flash('Mechanic ID not found. Please contact support.', 'danger')
    return redirect(url_for('some_error_page'))


@app.route('/edit/<int:service_id>', methods=['GET', 'POST'])
@login_required
def edit_service(service_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve mechanic_id from the session
    user_id = session.get('user_id')
    cursor.execute("SELECT mechanic_id FROM mechanic WHERE user_id = %s", (user_id,))
    mechanic = cursor.fetchone()
    
    if mechanic:
        mechanic_id = mechanic[0]

        if request.method == 'POST':
            # Process form submission
            service_name = request.form['name']
            service_description = request.form['description']
            service_price = request.form['price']
            service_duration = request.form['duration']
            service_category = request.form['category']
            service_availability = request.form['availability']

            cursor.execute(
                '''UPDATE services SET name = %s, description = %s, price = %s, duration = %s, category = %s, availability = %s, updated_at = NOW()
                   WHERE service_id = %s AND mechanic_id = %s''',
                (service_name, service_description, service_price, service_duration, service_category, service_availability, service_id, mechanic_id)
            )
            conn.commit()
            return redirect(url_for('manage_services'))

        # Fetch the current service details
        cursor.execute("SELECT * FROM services WHERE service_id = %s AND mechanic_id = %s", (service_id, mechanic_id))
        service = cursor.fetchone()

        if service:
            # Render edit form with existing service details
            return render_template('edit_service.html', service=service)

    cursor.close()
    conn.close()
    return redirect(url_for('some_error_page'))  # Handle case when mechanic_id is not found


    
@app.route('/analysis', methods=['GET'])
@login_required
def analysis():
    return render_template('analysis.html')

@app.route('/perform_analysis', methods=['POST'])
@login_required
def perform_analysis():
    analysis_type = request.json.get('analysis_type')
    user_id = session['user_id']  # Get user_id from session
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if analysis_type == 'revenue':
            cursor.execute("SELECT revenue_date, total_price FROM revenue WHERE user_id = %s", (user_id,))
            revenue_data = cursor.fetchall()
            df = pd.DataFrame(revenue_data, columns=['date', 'total_price'])
            analysis_result = analyze_revenue_trend(df)
        elif analysis_type == 'expense':
            cursor.execute("SELECT date, amount, category FROM expenses WHERE user_id = %s", (user_id,))
            expense_data = cursor.fetchall()
            df = pd.DataFrame(expense_data, columns=['date', 'amount', 'category'])
            analysis_result = analyze_expense_trend(df)
        else:
            return jsonify({'error': 'Invalid analysis type'}), 400

        return jsonify(analysis_result)

    except Exception as e:
        app.logger.error(f'Error during analysis: {e}')
        return jsonify({'error': 'Analysis failed'}), 500
    finally:
        cursor.close()
        conn.close()


def analyze_revenue_trend(df):
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df.set_index('date', inplace=True)
    monthly_trend = df['total_price'].resample('M').sum()
    monthly_trend = monthly_trend.to_frame()
    monthly_trend['moving_avg'] = monthly_trend['total_price'].rolling(window=3).mean()

    result = {
        'months': monthly_trend.index.strftime('%Y-%m').tolist(),
        'total_prices': monthly_trend['total_price'].fillna(0).tolist(),
        'moving_avgs': monthly_trend['moving_avg'].fillna(0).tolist()
    }
    return result

def analyze_expense_trend(df):
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df.set_index('date', inplace=True)
    monthly_expense = df['amount'].resample('M').sum()
    monthly_expense = monthly_expense.to_frame()
    monthly_expense['moving_avg'] = monthly_expense['amount'].rolling(window=3).mean()

    result = {
        'months': monthly_expense.index.strftime('%Y-%m').tolist(),
        'amounts': monthly_expense['amount'].fillna(0).tolist(),
        'moving_avgs': monthly_expense['moving_avg'].fillna(0).tolist()
    }
    return result

@app.route('/analyze_revenue', methods=['POST'])
@login_required
def analyze_revenue():
    app.logger.info('Received revenue analysis request.')
    user_id = session['user_id']  # Get user_id from session
    connection = get_db_connection()
    if connection is None:
        app.logger.error('Database connection failed.')
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT part_id, SUM(total_price) AS total_sales FROM revenue WHERE user_id = %s GROUP BY part_id", (user_id,))
        results = cursor.fetchall()

        most_profitable_part_id = None
        total_sales = 0
        
        for part_id, sales in results:
            if sales > total_sales:
                total_sales = sales
                most_profitable_part_id = part_id
        
        response_data = {
            'most_profitable_part': {
                'part_id': most_profitable_part_id,
                'total_sales': total_sales,
                'profitability': total_sales
            }
        }
        app.logger.debug(f'Revenue response data: {response_data}')
        return jsonify(response_data)

    except Exception as e:
        app.logger.error(f'Error during revenue analysis: {e}')
        return jsonify({'error': 'Revenue analysis failed'}), 500
    finally:
        cursor.close()
        connection.close()



@app.route('/highest_service_sales', methods=['GET'])
@login_required
def highest_service_sales():
    user_id = session['user_id']  # Get user_id from session
    connection = get_db_connection()
    if not connection:
        return {'error': 'Database connection failed'}, 500
    
    try:
        cur = connection.cursor()
        cur.execute("""SELECT service_id, SUM(service_price) AS total_sales
                       FROM revenue
                       WHERE user_id = %s
                       GROUP BY service_id
                       ORDER BY total_sales DESC
                       LIMIT 1""", (user_id,))
        highest_service = cur.fetchone()

        if highest_service:
            service_id = highest_service[0]
            total_sales = highest_service[1]

            # Get the service name
            cur.execute("SELECT name FROM services WHERE service_id = %s", (service_id,))
            service_name = cur.fetchone()

            return {
                'service_id': service_id,
                'service_name': service_name[0] if service_name else None,
                'total_sales': total_sales
            }
        else:
            return {'error': 'No sales data available'}, 404

    except Exception as e:
        app.logger.error(f"Error fetching highest service sales: {e}")
        return {'error': 'Error fetching data from the database'}, 500
    finally:
        connection.close()




@app.route('/highest_part_sales', methods=['GET'])
@login_required
def highest_part_sales():
    user_id = session['user_id']  # Get user_id from session
    connection = get_db_connection()
    if not connection:
        return {'error': 'Database connection failed'}, 500

    try:
        cur = connection.cursor()
        cur.execute("""SELECT part_id, SUM(part_price) AS total_sales
                       FROM revenue
                       WHERE user_id = %s
                       GROUP BY part_id
                       ORDER BY total_sales DESC
                       LIMIT 1""", (user_id,))
        highest_part = cur.fetchone()

        if highest_part:
            part_id = highest_part[0]
            total_sales = highest_part[1]

            # Get the part name
            cur.execute("SELECT name FROM parts WHERE part_id = %s", (part_id,))
            part_name = cur.fetchone()

            return {
                'part_id': part_id,
                'part_name': part_name[0] if part_name else None,
                'total_sales': total_sales
            }
        else:
            return {'error': 'No sales data available'}, 404

    except Exception as e:
        app.logger.error(f"Error fetching highest part sales: {e}")
        return {'error': 'Error fetching data from the database'}, 500
    finally:
        connection.close()




@app.route('/service_sales_ranking', methods=['GET'])
@login_required
def service_sales_ranking():
    user_id = session['user_id']  # Get user_id from session
    connection = get_db_connection()
    if not connection:
        return {'error': 'Database connection failed'}, 500

    try:
        cursor = connection.cursor()
        cursor.execute("""SELECT service_id, SUM(service_price) AS total_sales
                          FROM revenue
                          WHERE user_id = %s
                          GROUP BY service_id
                          ORDER BY total_sales DESC""", (user_id,))
        results = cursor.fetchall()
        
        sales_data = []
        for service_id, total_sales in results:
            # Get the service name
            cursor.execute("SELECT name FROM services WHERE service_id = %s", (service_id,))
            service_name = cursor.fetchone()

            sales_data.append({
                'service_id': service_id,
                'service_name': service_name[0] if service_name else None,
                'total_sales': total_sales
            })

        return jsonify(sales_data)

    except Exception as e:
        app.logger.error(f"Error fetching service sales ranking: {e}")
        return {'error': 'Error fetching data from the database'}, 500
    finally:
        connection.close()




@app.route('/part_sales_ranking', methods=['GET'])
@login_required
def part_sales_ranking():
    user_id = session['user_id']  # Get user_id from session
    connection = get_db_connection()
    if not connection:
        return {'error': 'Database connection failed'}, 500

    try:
        cursor = connection.cursor()
        cursor.execute("""SELECT part_id, SUM(part_price) AS total_sales
                          FROM revenue
                          WHERE user_id = %s
                          GROUP BY part_id
                          ORDER BY total_sales DESC""", (user_id,))
        results = cursor.fetchall()
        
        sales_data = []
        for part_id, total_sales in results:
            # Get the part name
            cursor.execute("SELECT name FROM parts WHERE part_id = %s", (part_id,))
            part_name = cursor.fetchone()

            sales_data.append({
                'part_id': part_id,
                'part_name': part_name[0] if part_name else None,
                'total_sales': total_sales
            })

        return jsonify(sales_data)

    except Exception as e:
        app.logger.error(f"Error fetching part sales ranking: {e}")
        return {'error': 'Error fetching data from the database'}, 500
    finally:
        connection.close()





# Configure Flask-Mail for Gmail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587  # TLS
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'Derickbill3@gmail.com'  # Your Gmail address
app.config['MAIL_PASSWORD'] = 'bxyw odgw iwvl tpad'   # Your Gmail password or App password
app.config['MAIL_DEFAULT_SENDER'] = ('MyMechanic', 'Derickbill3@gmail.com')

mail = Mail(app)


@app.route('/maintenance_due', methods=['GET', 'POST'])
@login_required
def maintenance_due():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Query to find 'vin' values and next scheduled service date from 'maintenance_logs' with dates >= today
            query = """
                SELECT ml.vin, ml.next_scheduled_service, c.full_name, c.phone_number, c.email_address
                FROM maintenance_logs ml
                JOIN vehicle v ON ml.vin = v.vin
                JOIN customer c ON v.customer_id = c.customer_id
                WHERE ml.next_scheduled_service <= CURDATE();
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            # Handle email sending on button click (via POST)
            if request.method == 'POST':
                # Send email to all customers whose maintenance is due
                for record in results:
                    send_maintenance_email(record['full_name'], record['email_address'])
                
                flash('Notification emails sent successfully!', 'success')
            
            return render_template('maintenance_due.html', maintenance_due=results)
        except Error as e:
            app.logger.error(f"Error fetching data: {e}")
            return "An error occurred while fetching data."
        finally:
            cursor.close()
            connection.close()
    else:
        return "Database connection failed."


def send_maintenance_email(customer_name, customer_email):
    """ Function to send an email to the customer about maintenance due """
    try:
        msg = Message(
            subject="Car Maintenance Due",
            recipients=[customer_email]
        )
        msg.body = f"Dear {customer_name},\n\nYour car maintenance is due. Please schedule an appointment with us.\n\nBest regards,\nYour Mechanic Service Team"
        
        # Send the email
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Error sending email: {e}")
        flash('Error sending emails, please try again later.', 'danger')


@app.route('/car-owner-dashboard')
@login_required
def car_owner_dashboard():
    return render_template('car_owner_dashboard.html')


@app.route('/maintenance_history', methods=['GET', 'POST'])
@login_required
def maintenance_history():
    if 'user_id' not in session:
        flash('Please log in first!', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    filter_plate = None
    maintenance_data = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Query to get vehicle details for the user
        cursor.execute("SELECT make, license_plate_number FROM vehicle WHERE user_id = %s", (user_id,))
        vehicles = cursor.fetchall()

        if request.method == 'POST':
            filter_plate = request.form.get('license_plate')
        
        # Query to get maintenance logs
        query = """
            SELECT v.make, v.license_plate_number, ml.work_description, ml.parts_used, ml.total_cost,
                   ml.next_scheduled_service, ml.log_date
            FROM maintenance_logs ml
            JOIN vehicle v ON ml.vehicle_id = v.vehicle_id
            WHERE v.user_id = %s
        """
        params = [user_id]

        if filter_plate:
            query += " AND v.license_plate_number = %s"
            params.append(filter_plate)

        cursor.execute(query, tuple(params))
        maintenance_data = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f"Error retrieving data: {err}", 'danger')

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('maintenance_history.html', vehicles=vehicles, maintenance_data=maintenance_data)


UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/uploaded-ads', methods=['GET'])
@login_required
def uploaded_ads():
    user_id = session.get('user_id')  # Assuming you're using session to store user_id
    ads = []

    if user_id:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ad_id, part_category, status, upload_date, image1, image2, image3, image4
                    FROM shopping
                    WHERE user_id = %s
                """, (user_id,))
                ads = cursor.fetchall()
                cursor.close()
            except Error as e:
                app.logger.error(f"Error retrieving ads: {e}")
            finally:
                conn.close()

    return render_template('uploaded_ads.html', ads=ads)



@app.route('/change-ad/<int:ad_id>', methods=['GET', 'POST'])
def change_ad(ad_id):
    connection = get_db_connection()  # Get a new database connection
    if not connection:
        flash('Unable to connect to the database. Please try again later.', 'error')
        return redirect(url_for('uploaded_ads'))  # Redirect if the connection fails

    cursor = connection.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Get the form data
        part_category = request.form.get('part_category')
        upload_date = request.form.get('upload_date')

        # Handle optional image upload
        image = request.files.get('image1')  # Ensure you're using the correct input field name
        image_filename = None
        if image and image.filename != '':
            image_filename = f'uploads/{image.filename}'
            image.save(f'static/images/{image_filename}')

        # Update the ad in the database
        update_query = """
            UPDATE shopping
            SET part_category = %s, upload_date = %s
        """
        update_values = [part_category, upload_date]

        if image_filename:
            update_query += ", image1 = %s"
            update_values.append(image_filename)
        update_query += " WHERE ad_id = %s"
        update_values.append(ad_id)

        try:
            cursor.execute(update_query, update_values)
            connection.commit()
            flash('Ad updated successfully!', 'success')
            return redirect(url_for('uploaded_ads'))
        except Exception as e:
            connection.rollback()
            flash(f'Error updating ad: {e}', 'error')
        finally:
            cursor.close()
            connection.close()

    # Fetch the ad details for GET request
    try:
        cursor.execute("SELECT * FROM shopping WHERE ad_id = %s", (ad_id,))
        ad = cursor.fetchone()
        if not ad:
            flash('Ad not found!', 'error')
            return redirect(url_for('uploaded_ads'))
    except Exception as e:
        flash(f'Error retrieving ad details: {e}', 'error')
        return redirect(url_for('uploaded_ads'))
    finally:
        cursor.close()
        connection.close()

    return render_template('change_ad.html', ad=ad)






@app.route('/upload-part', methods=['GET', 'POST'])
@login_required
def upload_part():
    # Fetch user_id from session
    user_id = session.get('user_id')

    # Get total ads and estimated revenue
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Query to count total ads uploaded by the current user
            cursor.execute("SELECT COUNT(ad_id) FROM shopping WHERE user_id = %s", (user_id,))
            total_ads = cursor.fetchone()[0]

            # Query to sum up the 'Product_Price' values for the current user
            cursor.execute("SELECT SUM(price) FROM shopping WHERE user_id = %s", (user_id,))
            total_revenue = cursor.fetchone()[0] or 0  # Default to 0 if no ads exist

            # Process form submission for uploading part
            if request.method == 'POST':
                try:
                    # Default to 'Free' if not paid
                    payment_status = 'Free'

                    # Check if the form is for paid submission
                    if 'payment_status' in request.form and request.form['payment_status'] == 'Paid':
                        payment_status = 'Paid'  # Set payment status to 'Paid' if it's a paid upload

                    # Form data for the part being uploaded
                    shop_name = request.form['shop_name']
                    part_category = request.form['part_category']
                    part_name = request.form['part_name']
                    part_description = request.form['part_description']  # New field for description
                    seller_contact = request.form['seller_contact']  # New field for seller contact
                    product_price = float(request.form['product_price'])  # New field for price
                    status = "Premium" if payment_status == 'Paid' else "Free"  # Premium for paid ads, free for free ads
                    images = request.files.getlist('images')  # Get all images uploaded
                    brand = request.form['brand']
                    condition = request.form['condition']

                    # Save images
                    image_paths = []
                    for image in images[:4]:  # Limit to 4 images
                        if image:
                            filename = secure_filename(image.filename)
                            image_path = os.path.join('static/images', filename)
                            image.save(image_path)
                            image_paths.append(filename)

                    # Insert into the database with the provided details
                    cursor.execute("""
                        INSERT INTO shopping (shop_name, part_category, part_name, part_description, seller_contact, price, status, payment_status, user_id, image1, image2, image3, image4, brand, condition)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (shop_name, part_category, part_name, part_description, seller_contact, product_price, status, payment_status, user_id, *image_paths, brand, condition))
                    conn.commit()

                    # Return success response
                    return jsonify(status='success', message='Part uploaded successfully.')

                except Exception as e:
                    app.logger.error(f"Error inserting data: {e}")
                    return jsonify(status='error', message='Failed to upload part.'), 500

            # Render the template for the upload page with statistics
            return render_template('upload_part.html', total_ads=total_ads, total_revenue=total_revenue)

        except Exception as e:
            app.logger.error(f"Error fetching stats: {e}")
            return jsonify(status='error', message='Failed to retrieve statistics.'), 500
        finally:
            cursor.close()
    else:
        return jsonify(status='error', message='Database connection failed.'), 500




@app.route('/set-location', methods=['POST'])
@login_required
def set_location():
    user_id = session.get('user_id')
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """UPDATE shopping SET latitude = %s, longitude = %s WHERE user_id = %s""",
            (latitude, longitude, user_id),
        )
        conn.commit()
        return jsonify({"message": "Location set successfully!"})
    except Exception as e:
        return jsonify({"message": "Failed to set location."}), 500
    finally:
        cursor.close()




@app.route('/upload-part-direct', methods=['POST'])
@login_required
def upload_part_direct():
    # Fetch user_id from session
    user_id = session.get('user_id')

    # Form data for the part being uploaded
    shop_name = request.form['shop_name']
    part_category = request.form['part_category']
    part_name = request.form['part_name']
    price = float(request.form['product_price'])  # Get the product price from the form
    status = "Free"  # Direct upload, no payment
    images = request.files.getlist('images')  # Get all images uploaded

    # Handle image paths
    image_paths = []
    for image in images[:4]:  # Limit to 4 images
        if image:
            filename = secure_filename(image.filename)
            image_path = os.path.join('static/images', filename)
            image.save(image_path)
            image_paths.append(filename)

    # Connect to the database
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Insert into the database
            cursor.execute(""" 
                INSERT INTO shopping (shop_name, part_category, part_name, price, status, user_id, image1, image2, image3, image4)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (shop_name, part_category, part_name, price, status, user_id, *image_paths))
            conn.commit()

            # Return success response
            return jsonify(status='success', message='Part uploaded successfully.')

        except Exception as e:
            app.logger.error(f"Error inserting data: {e}")
            return jsonify(status='error', message='Failed to upload part.'), 500
        finally:
            cursor.close()
    else:
        return jsonify(status='error', message='Database connection failed.'), 500



@app.route('/log_impression/<ad_id>', methods=['POST'])
@login_required
def log_impression(ad_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ad_statistics (ad_id, event_type, event_date)
        VALUES (%s, 'Impression', NOW())
    """, (ad_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "success"}), 200


from datetime import datetime  # Correct import

@app.route('/shopping', methods=['GET', 'POST'])
@login_required
def shopping_page():
    user_latitude = None
    user_longitude = None
    location = None
    ads = []
    part_category = request.form.get('part_category', '')  # Get part category filter
    part_name = request.form.get('part_name', '')  # Get part name filter

    # Check if location is provided
    if request.method == 'POST' and request.form.get('location'):
        location = request.form.get('location')

        # Automatically append 'Ghana' to the user input
        location_with_country = location + ", Ghana"

        # Geocode the location using Geopy
        geolocator = Nominatim(user_agent="ad_search")
        location_data = geolocator.geocode(location_with_country)

        # If location data is None, continue without coordinates
        if location_data:
            # Get latitude and longitude of the input location
            user_latitude = location_data.latitude
            user_longitude = location_data.longitude

    try:
        # Build the query with optional filters
        query = "SELECT * FROM shopping WHERE 1=1"
        params = []

        # If part_name filter is provided, add it to the query
        if part_name:
            keywords = part_name.split()
            keyword_conditions = " OR ".join([f"(part_name LIKE %s OR part_description LIKE %s)" for _ in keywords])
            params.extend([f"%{keyword}%" for keyword in keywords for _ in range(2)])  # 2 conditions per keyword
            query += f" AND ({keyword_conditions})"

        # Apply part category filter if provided
        if part_category:
            query += " AND part_category = %s"
            params.append(part_category)

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Execute the query with the parameters
        cursor.execute(query, tuple(params) if params else None)
        result = cursor.fetchall()

        for row in result:
            ad_latitude = row.get('latitude')
            ad_longitude = row.get('longitude')
            distance = calculate_distance(user_latitude, user_longitude, ad_latitude, ad_longitude) if user_latitude and user_longitude else None

     
            ads.append({
                "ad_id": row['ad_id'],
                "part_name": row['part_name'],
                "price": row['price'],
                "image1": row['image1'],
                "status": row['status'],
                "upload_date": row['upload_date'],
                "latitude": row.get('latitude'),
                "longitude": row.get('longitude'),
                "distance": round(distance, 2) if distance is not None else None,
            })

        # Sort ads by premium status (True first), upload date (latest first), and distance (nearest first)
        ads = sorted(ads, key=lambda x: (
            x["status"] == "Premium", 
            x["upload_date"] if x["upload_date"] else datetime.min,  # Using `datetime.min` correctly
            x["distance"] if x["distance"] is not None else float('inf')  # Handle None in distance
        ), reverse=True)

        # Close the connection
        cursor.close()
        conn.close()

    except Exception as e:
        app.logger.error(f"Error fetching data: {e}")
        return jsonify({"error": "An error occurred while fetching ads."}), 500

    return render_template('shopping_page.html', ads=ads, location=location)






@app.route('/update-payment/<int:part_id>', methods=['POST'])
@login_required
def update_payment(part_id):
    data = request.get_json()
    reference = data.get('reference')

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Update the payment status and status of the part
            cursor.execute("""
                UPDATE shopping 
                SET payment_status = 'Paid', status = 'Premium' 
                WHERE id = %s
            """, (part_id,))
            conn.commit()
            cursor.close()
            app.logger.info(f"Payment updated for part ID {part_id} with reference {reference}.")
            return jsonify({"message": "Payment status updated."}), 200
        except Error as e:
            app.logger.error(f"Error updating payment status: {e}")
            return jsonify({"error": "Error updating payment status."}), 500
        finally:
            conn.close()
    return jsonify({"error": "Database connection error."}), 500


def log_visitor(ad_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ad_statistics (ad_id, event_type, event_date)
        VALUES (%s, 'Visitor', NOW())
    """, (ad_id,))
    conn.commit()
    cursor.close()
    conn.close()




@app.route('/log-contact-reveal/<int:ad_id>', methods=['POST'])
@login_required
def log_contact_reveal(ad_id):
    """
    Logs a contact reveal event for the specified ad.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert a log entry for the contact reveal
        cursor.execute("""
            INSERT INTO ad_statistics (ad_id, event_type, event_date)
            VALUES (%s, 'Phone Reveal', NOW())
        """, (ad_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Contact reveal logged successfully"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500




@app.route('/part-details/<int:ad_id>', methods=['GET', 'POST'])
def part_details(ad_id):
    # Log a visitor for the ad
    log_visitor(ad_id)

    # Get database connection
    conn = get_db_connection()
    if conn is None:
        return "Database connection error", 500

    # Fetch the part details by ad_id
    cursor = conn.cursor(dictionary=True)
    query = """
    SELECT shop_name, part_category, part_name, price, status, upload_date, 
           payment_status, image1, image2, image3, image4, payment_reference, 
           user_id, part_description, seller_contact, Product_Price, ad_id,  
           brand, `condition`
    FROM shopping
    WHERE ad_id = %s
    """
    cursor.execute(query, (ad_id,))
    part = cursor.fetchone()

    # Fetch related ads in the same category (excluding the current ad)
    related_query = """
    SELECT ad_id, part_name, price, image1
    FROM shopping
    WHERE part_category = %s AND ad_id != %s
    LIMIT 4
    """
    cursor.execute(related_query, (part['part_category'], ad_id))
    related_ads = cursor.fetchall()

    # Fetch reviews for this part
    review_query = """
    SELECT reviews.rating, reviews.review_text, reviews.created_at, users.name AS user_name
    FROM reviews
    JOIN users ON reviews.user_id = users.user_id
    WHERE reviews.ad_id = %s
    ORDER BY reviews.created_at DESC
    """
    cursor.execute(review_query, (ad_id,))
    reviews = cursor.fetchall()

    # Handle the form submission
    if request.method == 'POST':
        rating = request.form['rating']
        review_text = request.form['review_text']
        user_id = session.get('user_id', None)  # Get the current user ID from session

        if user_id:
            try:
                # Start the transaction
                cursor.execute("START TRANSACTION")

                # Insert the review into the database
                insert_query = """
                INSERT INTO reviews (ad_id, user_id, rating, review_text)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_query, (ad_id, user_id, rating, review_text))

                # Commit the transaction
                conn.commit()

                # Redirect to the same page to see the newly added review
                return redirect(url_for('part_details', ad_id=ad_id))

            except mysql.connector.Error as err:
                conn.rollback()  # Rollback in case of error
                return f"Error occurred: {err}", 500
        else:
            return "User is not logged in", 403

    # Close the cursor and connection
    cursor.close()
    conn.close()

    # Render the HTML template with part details, related ads, and reviews
    if part:
        return render_template('part_details.html', part=part, related_ads=related_ads, reviews=reviews)
    else:
        return "Part not found", 404





@app.route('/edit-ad/<int:ad_id>', methods=['GET'])
@login_required
def edit_ad(ad_id):
    conn = get_db_connection()
    ad = None
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT ad_id, part_category, part_name, price, image1, image2, image3, image4
                FROM shopping
                WHERE ad_id = %s
            """, (ad_id,))
            ad = cursor.fetchone()
            cursor.close()
        except Error as e:
            app.logger.error(f"Error retrieving ad for editing: {e}")
        finally:
            conn.close()
    
    part_categories = [
        'Engine and Related Parts', 'Fuel System', 'Exhaust System', 'Cooling System', 
        'Electrical System', 'Transmission and Drivetrain', 'Braking System', 'Suspension System',
        'Steering System', 'Interior Components', 'Exterior Body Parts', 'Lighting', 
        'Climate Control', 'Wheels and Tires', 'Safety and Security Systems', 'Glass and Wiper System',
        'Fuel and Emission Control', 'Accessories and Add-ons', 'Miscellaneous and Small Parts',
        'Infotainment and Electronics'
    ]

    return render_template('edit_ad.html', ad=ad, part_categories=part_categories)


@app.route('/delete-ad/<int:ad_id>', methods=['POST'])
@login_required
def delete_ad(ad_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shopping WHERE ad_id = %s", (ad_id,))
        conn.commit()
        app.logger.info(f"Ad {ad_id} deleted successfully.")
    except Error as e:
        app.logger.error(f"Error deleting ad: {e}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('uploaded_ads'))



@app.route('/update-ad/<int:ad_id>', methods=['POST'])
@login_required
def update_ad(ad_id):
    part_category = request.form.get('part_category')
    part_name = request.form.get('part_name')
    price = request.form.get('price')
    images = ['image1', 'image2', 'image3', 'image4']
    image_files = {}

    for img in images:
        file = request.files.get(img)
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_files[img] = filename

    # Update the database with new values
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            update_query = """
                UPDATE shopping
                SET part_category = %s, part_name = %s, price = %s, 
                    image1 = COALESCE(%s, image1),
                    image2 = COALESCE(%s, image2),
                    image3 = COALESCE(%s, image3),
                    image4 = COALESCE(%s, image4)
                WHERE ad_id = %s
            """
            cursor.execute(update_query, (
                part_category, part_name, price,
                image_files.get('image1'), image_files.get('image2'),
                image_files.get('image3'), image_files.get('image4'),
                ad_id
            ))
            conn.commit()
            cursor.close()
        except Error as e:
            app.logger.error(f"Error updating ad: {e}")
        finally:
            conn.close()

    return redirect(url_for('uploaded_ads'))


@app.route('/profile')
@login_required
def profile():
    user_id = session.get('user_id')  # Ensure user is logged in and session contains user_id
    if not user_id:
        return redirect(url_for('login'))

    # Get database connection using the helper function
    conn = get_db_connection()
    
    if conn is None:
        flash('Could not connect to the database. Please try again later.', 'danger')
        return redirect(url_for('login'))

    try:
        # Create a cursor to execute the SQL query
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        # Close the cursor and the connection
        cursor.close()
        conn.close()

        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('login'))

        # Render the profile page with the fetched user data
        return render_template('profile.html', user=user)

    except Exception as e:
        # Log the error and show a flash message
        app.logger.error(f"Error fetching user data: {e}")
        flash('An error occurred while fetching your profile. Please try again.', 'danger')
        return redirect(url_for('login'))


@app.route('/verify-password', methods=['POST'])
@login_required
def verify_password():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Ensure the user is logged in

    current_password = request.form['current_password']
    conn = get_db_connection()

    if conn is None:
        flash('Unable to connect to the database. Please try again later.', 'danger')
        return redirect(url_for('profile'))  # Ensure a valid connection

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT password FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        # Check if the entered password matches the one in the database
        if user and user['password'] == current_password:
            conn.close()
            flash('Password verified successfully!', 'success')  # Optional flash message on success
            return redirect(url_for('edit_profile'))  # Proceed to the edit profile page
        else:
            flash('Incorrect password, please try again.', 'danger')
            conn.close()
            return redirect(url_for('profile'))  # Password mismatch, return to profile page

    except Error as e:
        flash(f"Error occurred while verifying password: {str(e)}", 'danger')
        conn.close()
        return redirect(url_for('profile'))  # Handle any connection errors



@app.route('/edit-profile')
@login_required
def edit_profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Ensure user is logged in

    conn = get_db_connection()

    if conn is None:
        flash('Unable to connect to the database. Please try again later.', 'danger')
        return redirect(url_for('profile'))  # Ensure valid connection

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('login'))  # Redirect to login if user not found

        return render_template('edit_profile.html', user=user)

    except Error as e:
        flash(f"Error occurred while fetching user data: {str(e)}", 'danger')
        conn.close()
        return redirect(url_for('profile'))  # Handle any database connection errors



@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Ensure user is logged in

    new_name = request.form['name']
    new_email = request.form['email']
    new_password = request.form['new_password']

    conn = get_db_connection()

    if conn is None:
        flash('Unable to connect to the database. Please try again later.', 'danger')
        return redirect(url_for('profile'))  # Ensure valid connection

    try:
        cursor = conn.cursor()

        # If new password is provided, update it directly (no hashing)
        if new_password:
            cursor.execute("UPDATE users SET name = %s, email = %s, password = %s WHERE user_id = %s",
                           (new_name, new_email, new_password, user_id))
        else:
            cursor.execute("UPDATE users SET name = %s, email = %s WHERE user_id = %s",
                           (new_name, new_email, user_id))

        conn.commit()  # Commit the changes
        conn.close()  # Close the connection

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))  # Redirect to the profile page after update

    except Error as e:
        flash(f"Error occurred while updating profile: {str(e)}", 'danger')
        conn.close()
        return redirect(url_for('profile'))  # Handle any database connection errors



@app.route('/cost-and-budgeting', methods=['GET'])
@login_required
def cost_and_budgeting():
    # Get the user_id from session
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in."

    # Get the filter parameters from the URL (default to None if not provided)
    license_plate_number = request.args.get('license_plate_number', None)
    year = request.args.get('year', None)

    # Get database connection
    db_connection = get_db_connection()
    if db_connection is None:
        return "Error connecting to the database"

    cursor = db_connection.cursor(dictionary=True)

    # Initialize empty data lists
    maintenance_data = []
    fuel_data = []

    try:
        # Query to get license plate numbers associated with the user
        cursor.execute("""
            SELECT license_plate_number 
            FROM vehicle 
            WHERE user_id = %s
        """, (user_id,))
        license_plate_numbers = cursor.fetchall()

        # Query for maintenance costs, apply filters if provided
        if license_plate_number and year:
            cursor.execute("""
                SELECT 
                    MONTH(log_date) AS month,
                    YEAR(log_date) AS year,
                    SUM(total_cost) AS total_cost
                FROM 
                    maintenance_logs
                JOIN 
                    vehicle ON maintenance_logs.vin = vehicle.vin
                WHERE 
                    vehicle.license_plate_number = %s
                    AND YEAR(log_date) = %s
                GROUP BY 
                    YEAR(log_date), MONTH(log_date)
                ORDER BY 
                    year DESC, month DESC;
            """, (license_plate_number, year))
        else:
            cursor.execute("""
                SELECT 
                    MONTH(log_date) AS month,
                    YEAR(log_date) AS year,
                    SUM(total_cost) AS total_cost
                FROM 
                    maintenance_logs
                GROUP BY 
                    YEAR(log_date), MONTH(log_date)
                ORDER BY 
                    year DESC, month DESC;
            """)
        maintenance_data = cursor.fetchall()

        # Query for fuel costs, apply filters if provided
        if license_plate_number and year:
            cursor.execute("""
                SELECT 
                    MONTH(fuel_date) AS month,
                    YEAR(fuel_date) AS year,
                    SUM(fuel_amount) AS total_fuel_cost
                FROM 
                    fuel_costs
                WHERE 
                    license_plate_number = %s
                    AND YEAR(fuel_date) = %s
                GROUP BY 
                    YEAR(fuel_date), MONTH(fuel_date)
                ORDER BY 
                    year DESC, month DESC;
            """, (license_plate_number, year))
        else:
            cursor.execute("""
                SELECT 
                    MONTH(fuel_date) AS month,
                    YEAR(fuel_date) AS year,
                    SUM(fuel_amount) AS total_fuel_cost
                FROM 
                    fuel_costs
                GROUP BY 
                    YEAR(fuel_date), MONTH(fuel_date)
                ORDER BY 
                    year DESC, month DESC;
            """)
        fuel_data = cursor.fetchall()

    except Error as e:
        app.logger.error(f"Error executing query: {e}")
        return "Error executing queries"

    finally:
        cursor.close()
        db_connection.close()

    return render_template('cost_and_budgeting.html', 
                           maintenance_data=maintenance_data, 
                           fuel_data=fuel_data,
                           license_plate_number=license_plate_number,
                           year=year,
                           license_plate_numbers=license_plate_numbers)





@app.route('/fuel-costs', methods=['GET'])
@login_required
def fuel_costs():
    # Get the filter parameters from the URL
    license_plate_number = request.args.get('license_plate_number')
    year = request.args.get('year')

    if not license_plate_number or not year:
        # Return some error or default data if no parameters are provided
        return "Please provide license plate number and year."

    # Get database connection
    db_connection = get_db_connection()
    if db_connection is None:
        return "Error connecting to the database"

    cursor = db_connection.cursor(dictionary=True)

    try:
        # Query for fuel costs
        cursor.execute("""
            SELECT 
                MONTH(fuel_date) AS month,
                YEAR(fuel_date) AS year,
                SUM(fuel_amount) AS total_fuel_cost
            FROM 
                fuel_costs
            WHERE 
                license_plate_number = %s
                AND YEAR(fuel_date) = %s
            GROUP BY 
                YEAR(fuel_date), MONTH(fuel_date)
            ORDER BY 
                year DESC, month DESC;
        """, (license_plate_number, year))
        fuel_data = cursor.fetchall()

    except Error as e:
        app.logger.error(f"Error executing query: {e}")
        return "Error executing queries"

    finally:
        cursor.close()
        db_connection.close()

    return render_template('fuel_costs.html', fuel_data=fuel_data, license_plate_number=license_plate_number, year=year)




@app.route('/enter-fuel-cost', methods=['GET', 'POST'])
@login_required
def enter_fuel_cost():
    if request.method == 'POST':
        # Retrieve the form data
        license_plate_number = request.form['license_plate_number']
        fuel_amount = request.form['fuel_amount']
        fuel_date = request.form['fuel_date']
        fuel_type = request.form['fuel_type']
        
        # Get the user_id from session (ensure the user is logged in)
        user_id = session.get('user_id')
        if user_id is None:
            return redirect(url_for('login'))  # Redirect to login if no user is logged in

        # Insert data into the fuel_costs table
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fuel_costs (license_plate_number, fuel_amount, fuel_date, fuel_type, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (license_plate_number, fuel_amount, fuel_date, fuel_type, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('success'))  # Redirect to success page after inserting

    # For GET request, fetch vehicle plates from the database
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login'))  # Redirect to login if no user is logged in

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate_number FROM vehicle WHERE user_id = %s", (user_id,))
    license_plate_numbers = cursor.fetchall()  # Returns a list of tuples (e.g., [(plate1,), (plate2,)])
    cursor.close()
    conn.close()

    return render_template('enter_fuel_cost.html', license_plate_numbers=license_plate_numbers)


@app.route('/success')
@login_required
def success():
    return 'Fuel Cost Entered Successfully!'



@app.route('/enter-road-worthy', methods=['GET', 'POST'])
@login_required
def enter_road_worthy():
    if request.method == 'POST':
        # Retrieve the form data
        license_plate_number = request.form['license_plate_number']
        inspection_date = request.form['inspection_date']
        inspection_status = request.form['inspection_status']
        road_worthy_certificate_number = request.form['road_worthy_certificate_number']
        road_worthy_expiry_date = request.form['road_worthy_expiry_date']
        
        # Get the user_id from session (ensure the user is logged in)
        user_id = session.get('user_id')
        if user_id is None:
            return redirect(url_for('login'))  # Redirect to login if no user is logged in

        # Insert data into the road_worthy table
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO road_worthy (license_plate_number, inspection_date, inspection_status, road_worthy_certificate_number, road_worthy_expiry_date, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (license_plate_number, inspection_date, inspection_status, road_worthy_certificate_number, road_worthy_expiry_date, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('success'))  # Redirect to success page after inserting

    # For GET request, fetch vehicle plates from the database
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login'))  # Redirect to login if no user is logged in

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate_number FROM vehicle WHERE user_id = %s", (user_id,))
    license_plate_numbers = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('enter_road_worthy.html', license_plate_numbers=license_plate_numbers)



@app.route('/enter-insurance', methods=['GET', 'POST'])
@login_required
def enter_insurance():
    if request.method == 'POST':
        # Retrieve the form data
        license_plate_number = request.form['license_plate_number']
        insurance_provider = request.form['insurance_provider']
        insurance_policy_number = request.form['insurance_policy_number']
        insurance_amount = request.form['insurance_amount']
        insurance_expiration_date = request.form['insurance_expiration_date']
        payment_status = request.form['payment_status']

        # Get the user_id from session (ensure the user is logged in)
        user_id = session.get('user_id')
        if user_id is None:
            return redirect(url_for('login'))  # Redirect to login if no user is logged in

        # Insert data into the insurance table
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO insurance (license_plate_number, insurance_provider, insurance_policy_number, 
            insurance_amount, insurance_expiration_date, payment_status, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (license_plate_number, insurance_provider, insurance_policy_number, insurance_amount, 
              insurance_expiration_date, payment_status, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('success'))  # Redirect to success page after inserting

    # For GET request, fetch vehicle plates from the database
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('login'))  # Redirect to login if no user is logged in

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_plate_number FROM vehicle WHERE user_id = %s", (user_id,))
    license_plate_numbers = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('enter_insurance.html', license_plate_numbers=license_plate_numbers)


@app.route('/manage-entries')
@login_required
def manage_entries():
    return render_template('manage_entries.html')


# Route to serve the Tow Service Ad Upload Page
@app.route('/tow_service_ad_upload', methods=['GET'])
@login_required
def tow_service_ad_upload():
    return render_template('tow_service_ad_upload.html')

# Set up file upload configuration
UPLOAD_FOLDER = 'static/images/'  # Save images in static/images folder
ALLOWED_EXTENSIONS = {'*'}  # All file extensions allowed

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def save_image(image):
    filename = secure_filename(image.filename)
    filepath = os.path.join('static', 'images', filename)
    image.save(filepath)
    return filename

# Route to upload Free Ad
@app.route('/api/upload_free_ad', methods=['POST'])
@login_required
def upload_free_ad():
    return upload_ad(is_premium=False)

# Route to upload Premium Ad
@app.route('/api/upload_premium_ad', methods=['POST'])
@login_required
def upload_premium_ad():
    return upload_ad(is_premium=True)

# General ad upload function
# General ad upload function
def upload_ad(is_premium):
    try:
        # Retrieve user_id from session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"message": "User not authenticated."}), 403

        # Gather form data
        title = request.form['title']
        description = request.form['description']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        location_detail = request.form['location_detail']
        contact = request.form['contact']

        # Handle image uploads
        image1 = request.files['image1']
        image2 = request.files.get('image2')

        image1_filename = save_image(image1)
        image2_filename = save_image(image2) if image2 else None

        # Establish database connection
        connection = get_db_connection()
        cursor = connection.cursor()

        # Insert ad data including user_id, location_detail, and contact
        query = """
            INSERT INTO towing_ads (title, description, latitude, longitude, is_premium, image1, image2, user_id, location_detail, contact)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (title, description, latitude, longitude, int(is_premium), image1_filename, image2_filename, user_id, location_detail, contact)

        cursor.execute(query, values)
        connection.commit()

        # Cleanup and response
        cursor.close()
        connection.close()
        return jsonify({"message": "Ad uploaded successfully."}), 200

    except Exception as e:
        return jsonify({"message": f"Error: {str(e)}"}), 500



# Route to handle Paystack callback (after successful payment)
@app.route('/api/paystack_callback', methods=['POST'])
@login_required
def paystack_callback():
    try:
        data = request.get_json()
        reference = data.get('reference')

        # Logic to verify the payment with Paystack (using reference)
        # Assuming successful payment, update the ad's is_premium status in the database
        if reference:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE tow_service_ads SET is_premium = TRUE WHERE reference = %s", (reference,))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"message": "Payment successful, ad marked as premium!"})
        else:
            return jsonify({"message": "Payment failed or canceled."}), 400

    except Exception as e:
        return jsonify({"message": f"Error in payment callback: {str(e)}"}), 500




@app.route('/my_ads', methods=['GET'])
def my_ads():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch ads by user ID stored in the session
        user_id = session.get('user_id')  # Retrieve user_id from the session
        query = """
            SELECT ad_id, title, description, latitude, longitude, is_premium, image1
            FROM towing_ads
            WHERE user_id = %s
        """
        cursor.execute(query, (user_id,))
        ads = cursor.fetchall()

        return render_template('my_ads.html', ads=ads)

    except Exception as e:
        return jsonify({"message": f"Error fetching ads: {str(e)}"}), 500
    finally:
        cursor.close()
        connection.close()



@app.route('/delete_towing_ad/<int:ad_id>', methods=['POST'])
def delete_towing_ad(ad_id):
    try:
        # Get the database connection
        connection = get_db_connection()
        cursor = connection.cursor()

        # Retrieve the user_id from session
        user_id = session.get('user_id')  # Assuming the user_id is stored in the session

        # Check if the user is the owner of the ad
        query_check_owner = "SELECT user_id FROM towing_ads WHERE ad_id = %s"
        cursor.execute(query_check_owner, (ad_id,))
        ad_owner = cursor.fetchone()

        if ad_owner and ad_owner[0] == user_id:
            # The user is the owner, proceed with the deletion
            query = "DELETE FROM towing_ads WHERE ad_id = %s"
            cursor.execute(query, (ad_id,))
            connection.commit()

            # Redirect to the ads page after deletion
            return redirect(url_for('my_ads'))
        else:
            # User is not the owner, return an error message
            return jsonify({"message": "You do not have permission to delete this ad."}), 403

    except Exception as e:
        return jsonify({"message": f"Error deleting ad: {str(e)}"}), 500
    finally:
        # Safely close cursor and connection
        cursor.close()
        connection.close()






# Route to edit ad info (This page will display the current info for the ad)
@app.route('/edit_towing_ad_info/<int:ad_id>', methods=['GET'])
def edit_towing_ad_info(ad_id):
    # Check if user_id is in the session
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if user is not authenticated

    try:
        user_id = session['user_id']
        
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch the ad info by ad_id and user_id from session
        query = """
            SELECT ad_id, title, description, latitude, longitude, image1, image2, contact, location_detail
            FROM towing_ads
            WHERE ad_id = %s AND user_id = %s
        """
        cursor.execute(query, (ad_id, user_id))
        ad = cursor.fetchone()

        if not ad:
            return redirect(url_for('my_ads'))  # Redirect if ad is not found

        return render_template('edit_towing_ad.html', ad=ad)

    except Exception as e:
        return jsonify({"message": f"Error fetching ad info: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@app.route('/update_towing_ad_info/<int:ad_id>', methods=['POST'])
def update_towing_ad_info(ad_id):
    connection = None
    cursor = None

    try:
        # Retrieve form data
        title = request.form['title']
        description = request.form['description']
        latitude = request.form['latitude']
        longitude = request.form['longitude']
        contact = request.form['contact']
        location_detail = request.form['location_detail']

        # Handle file uploads
        image1 = request.files.get('image1')
        image2 = request.files.get('image2')
        image1_filename = save_image(image1) if image1 and image1.filename else None
        image2_filename = save_image(image2) if image2 and image2.filename else None

        # Database connection
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch existing image filenames
        query_fetch = "SELECT image1, image2 FROM towing_ads WHERE ad_id = %s"
        cursor.execute(query_fetch, (ad_id,))
        existing_images = cursor.fetchone()
        if not existing_images:
            return jsonify({"message": "Ad not found"}), 404

        # Fallback to existing images if new images are not provided
        if not image1_filename:
            image1_filename = existing_images[0]
        if not image2_filename:
            image2_filename = existing_images[1]

        # Update ad details in the database (excluding is_premium)
        query_update = """
            UPDATE towing_ads
            SET title = %s, description = %s, latitude = %s, longitude = %s,
                image1 = %s, image2 = %s, contact = %s, location_detail = %s
            WHERE ad_id = %s
        """
        cursor.execute(query_update, (title, description, latitude, longitude,
                                      image1_filename, image2_filename, contact, location_detail, ad_id))
        connection.commit()

        return redirect(url_for('my_ads'))

    except Exception as e:
        return jsonify({"message": f"Error updating ad info: {str(e)}"}), 500

    finally:
        # Safely close cursor and connection
        if cursor:
            cursor.close()
        if connection:
            connection.close()







# Route to access the nearby ads page
@app.route('/nearby_ads')
@login_required
def nearby_ads():
    return render_template('nearby_ads.html')


@app.route('/api/submit_review', methods=['POST'])
@login_required
def submit_review():
    data = request.json
    ad_id = data.get('ad_id')
    rating = data.get('rating')
    review_text = data.get('review_text')
    user_id = session.get('user_id')

    if not (ad_id and rating and review_text):
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    connection = get_db_connection()  # Get the connection

    if connection is None:
        return jsonify({'success': False, 'message': 'Database connection failed.'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            INSERT INTO ad_reviews (ad_id, user_id, rating, review_text)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (ad_id, user_id, rating, review_text))
        connection.commit()
        return jsonify({'success': True, 'message': 'Review submitted successfully!'})
    except Exception as e:
        connection.rollback()  # Rollback on error
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        connection.close()  # Ensure the connection is closed after use





@app.route('/api/get_reviews')
def get_reviews():
    ad_id = request.args.get('ad_id')

    if not ad_id:
        return jsonify({'success': False, 'message': 'Ad ID is required.'}), 400

    # Use the get_db_connection function to get the database connection
    db = get_db_connection()
    if not db:
        return jsonify({'success': False, 'message': 'Unable to connect to the database.'}), 500

    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT r.rating, r.review_text, r.created_at, u.name as author
            FROM ad_reviews r
            JOIN users u ON r.user_id = u.user_id
            WHERE r.ad_id = %s
            ORDER BY r.created_at DESC
        """
        cursor.execute(query, (ad_id,))
        reviews = cursor.fetchall()
        print(f"Fetched reviews for ad_id {ad_id}: {reviews}")  # Add this log to see if reviews are fetched

        if reviews:
            return jsonify({'success': True, 'reviews': reviews})
        else:
            return jsonify({'success': True, 'reviews': []})  # Handle case of no reviews
    except Exception as e:
        app.logger.error(f"Error fetching reviews: {str(e)}")  # Log any exception
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if db:
            db.close()  # Ensure the database connection is closed





    


# Route to get ads by location
# Route to get ads by location (or all ads if no location provided)
@app.route('/api/get_ads_by_location')
@login_required
def get_ads_by_location():
    location = request.args.get('location')

    # Check if location is provided, otherwise fetch all ads
    if location:
        # Geocode the location using Geopy
        geolocator = Nominatim(user_agent="ad_search")
        location_data = geolocator.geocode(location, country_codes="GH")

        if location_data is None:
            return jsonify({"error": "Invalid location"}), 400

        # Get latitude and longitude of the input location
        user_latitude = location_data.latitude
        user_longitude = location_data.longitude
    else:
        # Default values for latitude and longitude (can be any value)
        user_latitude = 0.0
        user_longitude = 0.0

    # Fetch ads from the database
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT ad_id, title, description, image1, latitude, longitude, is_premium, created_at, contact, location_detail FROM towing_ads"
        cursor.execute(query)
        result = cursor.fetchall()

        ads = []
        for row in result:
            ad_latitude = row['latitude']
            ad_longitude = row['longitude']
            distance = calculate_distance(user_latitude, user_longitude, ad_latitude, ad_longitude)

            ads.append({
                "ad_id": row['ad_id'],
                "title": row['title'],
                "description": row['description'],
                "image1": row['image1'],  # Ensure this stores only the filename
                "distance": distance,
                "is_premium": row['is_premium'],
                "created_at": row['created_at'],
                "contact": row['contact'],  # Add contact information here
                "location_detail": row['location_detail']  # Add location detail here
            })

        # Sort ads by premium status, creation date, and distance
        ads = sorted(ads, key=lambda x: (x["is_premium"], x["created_at"], x["distance"]), reverse=True)

        return jsonify({"ads": ads})

    except Exception as e:
        app.logger.error(f"Error fetching ads: {e}")
        return jsonify({"error": "An error occurred while fetching ads."}), 500


# Helper function to calculate distance using the Haversine formula
def calculate_distance(lat1, lon1, lat2, lon2):
    # Ensure that latitudes and longitudes are float values
    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)
    
    R = 6371.0  # Radius of the Earth in kilometers

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # Distance in kilometers





@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # General User Data
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        secret_question = request.form['secret_question']
        secret_answer = request.form['secret_answer']

        if role == "Select":
            flash("Please select a valid role.", "danger")
            return redirect(url_for('signup'))

        # Establish DB connection
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            # Insert user into 'users' table
            cursor.execute("""
                INSERT INTO users (name, email, password, role, secret_question, secret_answer)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, email, password, role, secret_question, secret_answer))
            connection.commit()

            # Fetch the new user's user_id
            cursor.execute("SELECT LAST_INSERT_ID() AS user_id")
            user_id = cursor.fetchone()['user_id']

            flash(f"Sign-up successful! Your User ID is: {user_id}. Please save this ID for future logins.", 'success')

            # If the role is 'mechanic', insert additional details into 'mechanic' table
            if role == 'mechanic':
                working_hours = request.form.get('working_hours', '')
                service_locations = request.form.get('service_locations', '')
                skills_certifications = request.form.get('skills_certifications', '')
                latitude = request.form.get('latitude', None)
                longitude = request.form.get('longitude', None)

                # Handle image uploads
                company_image = None
                image_files = []
                for i in range(1, 3):  # Allow up to 2 images
                    image = request.files.get(f'image{i}')
                    if image and image.filename:
                        filename = f"{user_id}_company_image_{i}.jpg"
                        image.save(f"static/images/{filename}")
                        image_files.append(filename)

                # Use the first image as the main company image
                if image_files:
                    company_image = image_files[0]

                # Insert mechanic details into 'mechanic' table
                cursor.execute("""
                    INSERT INTO mechanic (
                        user_id, name, working_hours, service_locations, skills_certifications, 
                        latitude, longitude, company_image
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id, name, working_hours, service_locations, skills_certifications,
                      latitude, longitude, company_image))
                connection.commit()
                flash("Mechanic details saved successfully!", 'success')

            return redirect(url_for('login'))

        except Exception as e:
            app.logger.error(f"Error during sign-up: {e}")
            flash(f'Error during sign-up: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return render_template('signup.html')





# Forgot password route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    secret_question = None  # Initialize to None

    if request.method == 'POST':
        user_id = request.form['user_id']
        secret_answer = request.form.get('secret_answer')
        new_password = request.form.get('new_password')

        # Connect to the database
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            # Retrieve the secret question and answer from the database based on user_id
            cursor.execute("SELECT secret_question, secret_answer FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()

            if user:
                # Store retrieved secret question for display
                secret_question = user[0]

                # If secret answer and new password fields are filled, validate and update password
                if secret_answer and new_password:
                    stored_secret_answer = user[1].lower()
                    provided_secret_answer = secret_answer.lower()

                    if stored_secret_answer == provided_secret_answer:
                        # Update password
                        cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (new_password, user_id))
                        connection.commit()
                        flash('Your password has been updated successfully!', 'success')
                        return redirect(url_for('login'))
                    else:
                        flash('Incorrect secret answer. Please try again.', 'danger')
            else:
                flash('User not found. Please check your user ID.', 'danger')

        except Exception as e:
            app.logger.error(f"Error during password reset: {e}")
            flash('An error occurred. Please try again later.', 'danger')
        finally:
            cursor.close()
            connection.close()

    return render_template('forgot_password.html', secret_question=secret_question)



@app.route('/get_secret_question', methods=['POST'])
def get_secret_question():
    data = request.get_json()
    user_id = data.get('user_id')  # Extract user_id from the JSON request
	

    # Connect to the database
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Fetch the secret question for the given user_id
        cursor.execute("SELECT secret_question FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if user:
            # If the user exists, return the secret question as JSON
            return jsonify({'secret_question': user[0]})
        else:
            # If user is not found, return an empty response
            return jsonify({'error': 'User not found'}), 404

    except Exception as e:
        app.logger.error(f"Error fetching secret question: {e}")
        return jsonify({'error': 'An error occurred'}), 500
    finally:
        cursor.close()
        connection.close()




# Function to get latitude and longitude from a city name (limit to Ghana only)
def get_coordinates(city_name):
    geolocator = Nominatim(user_agent="mechanic_app")
    location = geolocator.geocode(city_name + ", Ghana")  # Add Ghana to ensure the search is limited to Ghana
    if location:
        return (location.latitude, location.longitude)
    return None

@app.route('/mechanic-shops', methods=['GET', 'POST'])
def mechanic_shops():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)  # Use dictionary=True for easier templating

    if request.method == 'POST':
        user_location = request.form.get('location')  # Get location from form submission

        if user_location:  # If a location is provided
            user_coords = get_coordinates(user_location)
            if not user_coords:  # Invalid location entered
                flash("Invalid location, please enter a valid city in Ghana.", "danger")
                return render_template('mechanic_list.html', mechanics=[])  # Empty list to indicate no results

            # Fetch mechanics data, joining the mechanic and services tables
            cursor.execute("""
                SELECT 
                    m.mechanic_id, 
                    m.name, 
                    m.working_hours, 
                    m.service_locations, 
                    m.company_image, 
                    m.latitude, 
                    m.longitude, 
                    m.contact, 
                    GROUP_CONCAT(s.description SEPARATOR ', ') AS service_descriptions 
                FROM mechanic m
                LEFT JOIN services s ON m.mechanic_id = s.mechanic_id
                GROUP BY m.mechanic_id
            """)
            mechanics = cursor.fetchall()

            # Calculate distances and sort by proximity
            mechanic_list = []
            for mech in mechanics:
                shop_coords = (mech["latitude"], mech["longitude"])  # Latitude and Longitude
                distance = geodesic(user_coords, shop_coords).kilometers
                mechanic_list.append({
                    **mech,  # Include all mechanic data
                    'distance': round(distance, 2)  # Add rounded distance
                })
            mechanic_list.sort(key=lambda x: x['distance'])  # Sort by proximity

            return render_template('mechanic_list.html', mechanics=mechanic_list)

    # Default behavior: fetch and display all ads when no location is entered or the page is first loaded
    cursor.execute("""
        SELECT 
            m.mechanic_id, 
            m.name, 
            m.working_hours, 
            m.service_locations, 
            m.company_image, 
            m.contact, 
            GROUP_CONCAT(s.description SEPARATOR ', ') AS service_descriptions 
        FROM mechanic m
        LEFT JOIN services s ON m.mechanic_id = s.mechanic_id
        GROUP BY m.mechanic_id
    """)
    mechanics = cursor.fetchall()

    return render_template('mechanic_list.html', mechanics=mechanics)



@app.route('/log-reveal/<int:ad_id>', methods=['POST'])
def log_phone_number_reveal(ad_id):
    try:
        cursor = db.cursor()
        # Increment the `contact_reveals` stat for the given ad_id
        cursor.execute(
            """
            UPDATE ad_performance_stats 
            SET contact_reveals = contact_reveals + 1 
            WHERE ad_id = %s
            """, 
            (ad_id,)
        )
        db.commit()
        cursor.close()
        return jsonify({"message": "Phone Reveal logged successfully"}), 200
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500


def get_filtered_stats(ad_id, stat_type, start_date=None, end_date=None):
    # Build the base query to fetch stats for a given ad_id and stat_type
    query = f"""
        SELECT created_at, COUNT(*) AS stat_count
        FROM ad_performance_stats
        WHERE ad_id = %s AND stat_type = %s
    """
    
    # Add date range filter if provided
    if start_date and end_date:
        query += " AND created_at BETWEEN %s AND %s"
    
    # Execute the query with the appropriate parameters
    params = [ad_id, stat_type]
    if start_date and end_date:
        params.extend([start_date, end_date])

    cursor = db.cursor(dictionary=True)
    cursor.execute(query, params)
    result = cursor.fetchall()

    # Organize the data for graphing
    stats = {
        "labels": [],
        "values": []
    }
    
    for row in result:
        stats["labels"].append(row['created_at'].strftime('%Y-%m-%d'))  # Format the date as YYYY-MM-DD
        stats["values"].append(row['stat_count'])
    
    return stats




def get_ad_by_id(ad_id):
    try:
        cursor = db.cursor()
        cursor.execute("SELECT title FROM towing_ads WHERE ad_id = %s", (ad_id,))
        ad = cursor.fetchone()
        cursor.close()
        if ad:
            return {"name": ad[0]}
        else:
            raise ValueError(f"Ad with ID {ad_id} not found")
    except Exception as e:
        raise e





@app.route('/ad-performance/<ad_id>', methods=['GET'])
def ad_performance(ad_id):
    connection = get_db_connection()
    if not connection:
        return "Unable to connect to the database", 500

    cursor = connection.cursor(dictionary=True)

    # Get ad information (e.g., name, description) to display on the page
    cursor.execute("SELECT ad_id, title FROM towing_ads WHERE ad_id = %s", (ad_id,))
    ad = cursor.fetchone()

    if not ad:
        cursor.close()
        connection.close()
        return f"Ad with ID {ad_id} not found", 404

    # Get reviews and ratings for the ad
    cursor.execute("SELECT review_text, rating FROM ad_reviews WHERE ad_id = %s", (ad_id,))
    reviews = cursor.fetchall()

    cursor.close()
    connection.close()

    # Pass the ad details and reviews to the template
    return render_template('ad_performance.html', ad_id=ad_id, ad_name=ad['title'], reviews=reviews)






@app.route('/get-performance-stats')
def get_performance_stats():
    # Assuming you pass ad_id, stat_type, start_date, and end_date as query parameters
    ad_id = request.args.get('ad_id')
    stat_type = request.args.get('stat_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Get the database connection
    db = get_db_connection()
    
    if db is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = db.cursor(dictionary=True)
    
    try:
        # Construct the SQL query dynamically based on the filters
        query = """
            SELECT 
                stat_type, 
                COUNT(*) AS stat_count, 
                DATE_FORMAT(created_at, '%Y-%m') AS stat_month
            FROM ad_performance_stats
            WHERE ad_id = %s
        """
        
        # Add optional filters for stat_type and date range
        params = [ad_id]
        if stat_type and stat_type != 'all':
            query += " AND stat_type = %s"
            params.append(stat_type)
        if start_date and end_date:
            query += " AND created_at BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += """
            GROUP BY stat_type, stat_month
            ORDER BY stat_month;
        """
        
        # Execute the query
        cursor.execute(query, tuple(params))
        stats = cursor.fetchall()
        
        # Structure the data to send to the frontend
        result_data = {
            'impressions': 0,
            'visitors': 0,
            'phone_reveals': 0,
            'graph_data': {'labels': [], 'values': []}
        }

        # Collect data for impressions, visitors, and phone_reveals
        for row in stats:
            stat_type = row['stat_type']
            stat_count = row['stat_count']
            stat_month = row['stat_month']
            
            # Aggregate the data for the stats cards
            if stat_type == 'impression':
                result_data['impressions'] += stat_count
            elif stat_type == 'click':
                result_data['visitors'] += stat_count
            elif stat_type == 'contact_reveal':
                result_data['phone_reveals'] += stat_count
            
            # Prepare data for the graph
            result_data['graph_data']['labels'].append(stat_month)
            result_data['graph_data']['values'].append(stat_count)

        # Return the data as a JSON response
        return jsonify(result_data)

    except Error as e:
        app.logger.error(f"Error fetching performance stats: {e}")
        return jsonify({'error': 'Failed to fetch performance stats'}), 500
    
    finally:
        # Always close the cursor and connection
        cursor.close()
        db.close()






@app.route('/ad_details/<int:ad_id>')
def ad_details(ad_id):
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT ad_id, title, description, image1, image2, created_at, contact, location_detail
            FROM towing_ads
            WHERE ad_id = %s
            """,
            (ad_id,)
        )
        ad = cursor.fetchone()
        cursor.close()

        if not ad:
            return "Ad not found", 404

        return render_template("ad_details.html", ad=ad)
    except Exception as e:
        return f"Error: {e}", 500




@app.route('/track_ad_stats', methods=['POST'])
def track_ad_stats():
    try:
        ad_id = request.form["ad_id"]
        stat_type = request.form["stat_type"]

        cursor = db.cursor()
        cursor.execute("SELECT * FROM ad_performance_stats WHERE ad_id = %s", (ad_id,))
        existing_stats = cursor.fetchone()

        if not existing_stats:
            cursor.execute(
                """
                INSERT INTO ad_performance_stats (ad_id, impressions, clicks, contact_reveals)
                VALUES (%s, 0, 0, 0)
                """,
                (ad_id,)
            )
            db.commit()

        if stat_type == "impression":
            cursor.execute(
                "UPDATE ad_performance_stats SET impressions = impressions + 1 WHERE ad_id = %s",
                (ad_id,)
            )
        elif stat_type == "click":
            cursor.execute(
                "UPDATE ad_performance_stats SET clicks = clicks + 1 WHERE ad_id = %s",
                (ad_id,)
            )
        db.commit()
        cursor.close()

        return jsonify({"message": "Stat updated successfully"})
    except mysql.connector.Error as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/track_contact_reveal', methods=['POST'])
@login_required
def track_contact_reveal():
    """
    Logs a contact reveal event for the specified ad.
    """
    ad_id = request.json.get('ad_id')
    if not ad_id:
        return jsonify({"status": "error", "message": "ad_id is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert a log entry for the contact reveal
        cursor.execute("""
            INSERT INTO ad_performance_stats (ad_id, stat_type, created_at)
            VALUES (%s, 'contact_reveal', NOW())
        """, (ad_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Contact reveal tracked successfully"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500







@app.route('/get_ad_stats/<int:ad_id>', methods=['GET'])
def get_ad_stats(ad_id):
    start_date = request.args.get('start_date')  # Optional
    end_date = request.args.get('end_date')      # Optional

    try:
        cursor = db.cursor(dictionary=True)

        # Build the query dynamically
        query = """
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') AS month,
                stat_type,
                COUNT(*) AS count
            FROM ad_performance_stats
            WHERE ad_id = %s
        """
        params = [ad_id]

        if start_date and end_date:
            query += " AND created_at BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += " GROUP BY month, stat_type"
        
        cursor.execute(query, tuple(params))
        stats = cursor.fetchall()
        cursor.close()

        # Format the stats
        data = {
            'impressions': [],
            'clicks': [],
            'contact_reveals': []
        }

        for stat in stats:
            month = stat['month']
            count = stat['count']
            if stat['stat_type'] == 'impression':
                data['impressions'].append({'month': month, 'count': count})
            elif stat['stat_type'] == 'click':
                data['clicks'].append({'month': month, 'count': count})
            elif stat['stat_type'] == 'contact_reveal':
                data['contact_reveals'].append({'month': month, 'count': count})

        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@app.route('/get_ad_performance_stats', methods=['GET'])
def get_ad_performance_stats():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    stat_type = request.args.get('stat_type')

    # Get database connection
    connection = get_db_connection()
    if not connection:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        # Query the database for ad performance stats for the given date range and stat type
        cursor.execute("""
            SELECT * 
            FROM ad_performance_stats 
            WHERE created_at >= %s AND created_at <= %s
        """, (start_date, end_date))

        stats = cursor.fetchall()

        # Collect and prepare the data for the chart
        months = []
        data_points = []
        total_impressions = 0
        total_visitors = 0
        total_phone_reveals = 0

        for stat in stats:
            months.append(stat['created_at'].strftime('%B %Y'))  # Formatting date as month-year
            data_points.append(stat[stat_type])  # Dynamically access the stat type (e.g., impressions, clicks, etc.)
            
            # Aggregate totals for the specific stats
            total_impressions += stat['impressions']
            total_visitors += stat['clicks']
            total_phone_reveals += stat['contact_reveals']

        return jsonify({
            'success': True,
            'stats': {
                'impressions': total_impressions,
                'visitors': total_visitors,
                'phone_reveals': total_phone_reveals,
                'months': months,
                stat_type: data_points
            }
        })

    except Error as e:
        app.logger.error(f"Error retrieving ad performance stats: {e}")
        return jsonify({'message': 'Error retrieving ad performance stats'}), 500
    finally:
        cursor.close()
        connection.close()  # Close the database connection



@app.route('/api/track_impression', methods=['POST'])
def track_impression():
    """
    Logs an impression event for the specified ad.
    """
    ad_id = request.json.get('ad_id')
    if not ad_id:
        return jsonify({"status": "error", "message": "ad_id is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert a log entry for the impression
        cursor.execute("""
            INSERT INTO ad_performance_stats (ad_id, stat_type, created_at)
            VALUES (%s, 'impression', NOW())
        """, (ad_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Impression tracked successfully"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500



@app.route('/api/track_click', methods=['POST'])
@login_required
def track_click():
    """
    Logs a click event for the specified ad.
    """
    ad_id = request.json.get('ad_id')
    if not ad_id:
        return jsonify({"status": "error", "message": "ad_id is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert a log entry for the click event
        cursor.execute("""
            INSERT INTO ad_performance_stats (ad_id, stat_type, created_at)
            VALUES (%s, 'click', NOW())
        """, (ad_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Click tracked successfully"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500


@app.route('/uploaded-ad-performance/<int:ad_id>', methods=['GET', 'POST'])
def uploaded_ad_performance(ad_id):
    connection = get_db_connection()
    if not connection:
        return "Unable to connect to the database", 500

    cursor = connection.cursor(dictionary=True)
    
    # Get ad details (only part_category) from the shopping table using the ad_id
    cursor.execute("""
        SELECT ad_id, part_category
        FROM shopping 
        WHERE ad_id = %s
    """, (ad_id,))
    ad = cursor.fetchone()
    if not ad:
        cursor.close()
        connection.close()
        return f"Ad with ID {ad_id} not found in the shopping table", 404

    # Get filters from the request
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    event_type = request.args.get('event_type', 'all')  # Default to 'all'

    # SQL query to fetch statistics grouped by event type and month
    query = """
        SELECT 
            event_type, 
            COUNT(*) as event_count, 
            DATE_FORMAT(event_date, '%Y-%m') as event_month
        FROM ad_statistics
        WHERE ad_id = %s
    """
    params = [ad_id]

    # Apply date range filters if provided
    if start_date:
        query += " AND event_date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND event_date <= %s"
        params.append(end_date)

    # Apply event type filter if not 'all'
    if event_type != 'all':
        query += " AND event_type = %s"
        params.append(event_type)

    query += " GROUP BY event_type, event_month ORDER BY event_month"

    # Execute the query
    cursor.execute(query, tuple(params))
    stats = cursor.fetchall()

    # Process statistics for cards and graph
    stat_data = {'Impression': 0, 'Visitor': 0, 'Phone Reveal': 0}
    monthly_data = {}

    for row in stats:
        # Count totals for cards
        stat_data[row['event_type']] = stat_data.get(row['event_type'], 0) + row['event_count']

        # Group monthly data for the graph
        monthly_data.setdefault(row['event_type'], []).append({
            'month': row['event_month'],
            'count': row['event_count']
        })

    # Get reviews and ratings for the ad
    cursor.execute("""
        SELECT rating, review_text, created_at
        FROM reviews
        WHERE ad_id = %s
        ORDER BY created_at DESC
    """, (ad_id,))
    reviews = cursor.fetchall()

    cursor.close()
    connection.close()

    # Pass data to the template
    return render_template(
        'uploaded_ad_performance.html',
        ad=ad,
        stats=stat_data,
        monthly_data=monthly_data,
        reviews=reviews,  # Pass reviews to the template
        start_date=start_date,
        end_date=end_date,
        event_type=event_type
    )




@app.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')  # Retrieve user_id from session

    # Get a database connection by calling the function
    db_conn = get_db_connection()

    if not db_conn:
        # Handle database connection failure here (e.g., show an error page)
        return "Failed to connect to the database", 500

    # Create a cursor to execute queries
    cursor = db_conn.cursor()

    # Queries for each card
    queries = {
        "maintenance_due_count": """
            SELECT COUNT(*) FROM maintenance_logs 
            WHERE user_id = %s AND next_scheduled_service <= CURDATE()
        """,
        "total_expense": """
            SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = %s
        """,
        "total_revenue": """
            SELECT COALESCE(SUM(total_price), 0) FROM revenue WHERE user_id = %s
        """,
        "service_revenue": """
            SELECT COALESCE(SUM(service_price), 0) FROM revenue WHERE user_id = %s
        """,
        "part_revenue": """
            SELECT COALESCE(SUM(part_price), 0) FROM revenue WHERE user_id = %s
        """,
        "total_customers": """
            SELECT COUNT(*) FROM customer WHERE user_id = %s
        """,
        "total_services": """
            SELECT COUNT(*) FROM services WHERE user_id = %s
        """,
        "total_vehicles": """
            SELECT COUNT(*) FROM vehicle WHERE user_id = %s
        """,
        "total_employees": """
            SELECT COUNT(*) FROM employees WHERE user_id = %s
        """
    }

    # Execute each query and store results
    stats = {}
    for key, query in queries.items():
        cursor.execute(query, (user_id,))
        stats[key] = cursor.fetchone()[0]

    # Close the cursor
    cursor.close()

    # Pass the stats dictionary to the template
    return render_template('dashboard.html', stats=stats)


if __name__ == "__main__":
    app.run(debug=True)
