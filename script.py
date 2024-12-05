from flask import Flask, Response, request, jsonify, render_template, g
from flask_cors import CORS
from fatsecret import Fatsecret
from datetime import datetime
import pymysql
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt 


app = Flask(__name__)
CORS(app)  # Allow all cross-origin requests

# Your existing Flask routes and logic...

# FatSecret API setup
fs = Fatsecret(consumer_key='Key',
               consumer_secret='Secret_key')

# Database connection setup


def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(
            host='localhost',
            user='root',
            password='Password',
            database='fitfair'
        )
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    # Render the main HTML page
    return render_template('index.html')

#------------------------------------------------------------------------------------------------------------
@app.route('/search', methods=['POST'])
def search_food():
    try:
        # Extract query from POST request
        data = request.get_json()
        food_query = data.get('food')

        # Search the FatSecret API
        search_results = fs.foods_search(food_query)

        # Return results as JSON
        results = [{'id': food['food_id'], 'name': food['food_name']} for food in search_results]
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    
#------------------------------------------------------------------------------------------------------------
    
@app.route('/add-to-db', methods=['POST'])
def add_to_db():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = {
                'food_id': request.form.get('food_id'),
                'servings': request.form.get('servings')
            }

        food_id = data.get('food_id')
        servings = int(data.get('servings'))

        food_details = fs.food_get(food_id)
        food_name = food_details['food_name']
        serving_data = food_details['servings']['serving']
        if isinstance(serving_data, list):
            serving_data = serving_data[0]

        calories_per_serving = float(serving_data['calories'])
        proteins_per_serving = float(serving_data.get('protein', 0))
        fats_per_serving = float(serving_data.get('fat', 0))
        carbs_per_serving = float(serving_data.get('carbohydrate', 0))

        total_calories = int(calories_per_serving * servings)
        total_proteins = int(proteins_per_serving * servings)
        total_fats = int(fats_per_serving * servings)
        total_carbs = int(carbs_per_serving * servings)

        cursor = get_db().cursor()

        fooditem_query = """
            INSERT INTO fooditem (food_id, food_name, servings, calories, protein, fat, carb)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                calories = VALUES(calories),
                protein = VALUES(protein),
                fat = VALUES(fat),
                carb = VALUES(carb)
        """
        cursor.execute(fooditem_query, (food_id, food_name, servings, calories_per_serving, proteins_per_serving, fats_per_serving, carbs_per_serving))

        dailysum_query = """
            INSERT INTO dailysum (date, dailyCal, dailyPro, dailyCarb, dailyFat)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                dailyCal = dailyCal + VALUES(dailyCal),
                dailyPro = dailyPro + VALUES(dailyPro),
                dailyCarb = dailyCarb + VALUES(dailyCarb),
                dailyFat = dailyFat + VALUES(dailyFat)
        """
        cursor.execute(dailysum_query, (datetime.now().date(), total_calories, total_proteins, total_carbs, total_fats))

        get_db().commit()
        cursor.close()

        return jsonify({'message': 'Food added successfully!'})
    except Exception as e:
        print("Error in /add-to-db:", e)
        return jsonify({'error': str(e)}), 500
    
    
#------------------------------------------------------------------------------------------------------------
@app.route('/update-user', methods=['POST'])
def update_user():
    try:
        data = request.get_json()
        age = int(data.get('age'))
        weight = int(data.get('weight'))
        calgoal = int(data.get('calgoal'))

        cursor = get_db().cursor()
        query = """
            INSERT INTO user (user_id, age, weight, calgoal)
            VALUES (1, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                age = VALUES(age),
                weight = VALUES(weight),
                calgoal = VALUES(calgoal)
        """
        cursor.execute(query, (age, weight, calgoal))
        get_db().commit()
        cursor.close()

        return jsonify({'message': 'User updated successfully!'})
    except Exception as e:
        print("Error in /update-user:", e)
        return jsonify({'error': str(e)}), 500

    
#------------------------------------------------------------------------------------------------------------
@app.route('/remove-user', methods=['POST'])
def remove_user():
    try:
        cursor = get_db().cursor()
        query = "DELETE FROM user WHERE user_id = 1"
        cursor.execute(query)
        get_db().commit()
        cursor.close()

        return jsonify({'message': 'User removed successfully!'})
    except Exception as e:
        print("Error in /remove-user:", e)
        return jsonify({'error': str(e)}), 500

    
#------------------------------------------------------------------------------------------------------------

@app.route('/get-user', methods=['GET'])
def get_user():
    try:
        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        query = "SELECT * FROM user WHERE user_id = 1"
        cursor.execute(query)
        user = cursor.fetchone()
        cursor.close()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify(user)
    except Exception as e:
        print("Error in /get-user:", e)
        return jsonify({'error': str(e)}), 500
    

    
    
#------------------------------------------------------------------------------------------------------------
@app.route('/pie-chart', methods=['GET'])
def generate_pie_chart():
    try:
        # Fetch daily totals from the dailysum table
        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        query = "SELECT dailyPro, dailyCarb, dailyFat FROM dailysum WHERE date = %s"
        cursor.execute(query, (datetime.now().date(),))
        result = cursor.fetchone()
        cursor.close()

        # Default values if no record exists
        if not result:
            result = {'dailyPro': 0, 'dailyCarb': 0, 'dailyFat': 0}

        # Prepare data for the pie chart
        labels = ['Proteins', 'Carbs', 'Fats']
        values = [result['dailyPro'], result['dailyCarb'], result['dailyFat']]
        total = sum(values)

        if total == 0:
            # Handle case where totals are zero
            labels = ['No Data']
            values = [1]

        # Create the pie chart
        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Equal aspect ratio to ensure pie is drawn as a circle

        # Save the pie chart to a BytesIO object
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plt.close()

        # Return the image as a response
        return Response(img, mimetype='image/png')
    except Exception as e:
        print("Error generating pie chart:", e)
        return jsonify({'error': str(e)}), 500


    
    
#------------------------------------------------------------------------------------------------------------


@app.route('/daily-totals', methods=['GET'])
def daily_totals():
    try:
        date_today = datetime.now().date()
        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT dailyCal, dailyPro, dailyCarb, dailyFat
            FROM dailysum
            WHERE date = %s
        """
        cursor.execute(query, (date_today,))
        result = cursor.fetchone()
        cursor.close()

        if not result:
            result = {"dailyCal": 0, "dailyPro": 0, "dailyCarb": 0, "dailyFat": 0}

        return jsonify(result)
    except Exception as e:
        print("Error in /daily-totals:", e)
        return jsonify({'error': str(e)}), 500

    
    
#------------------------------------------------------------------------------------------------------------
    

@app.route('/get-food-log', methods=['GET'])
def get_food_log():
    try:
        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT food_id AS foodId, food_name AS foodName, servings, calories, protein, fat, carb
            FROM fooditem
        """
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()

        return jsonify(results)
    except Exception as e:
        print("Error in /get-food-log:", e)
        return jsonify({'error': str(e)}), 500

    
    
#------------------------------------------------------------------------------------------------------------

@app.route('/update-food', methods=['POST'])
def update_food():
    try:
        data = request.get_json()
        food_id = data.get('foodId')
        new_servings = int(data.get('servings'))

        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT servings, calories, protein, fat, carb FROM fooditem WHERE food_id = %s", (food_id,))
        food_details = cursor.fetchone()

        if not food_details:
            return jsonify({'error': 'Food item not found'}), 404

        old_servings = food_details['servings']
        diff_servings = new_servings - old_servings

        # Update fooditem
        cursor.execute(
            "UPDATE fooditem SET servings = %s WHERE food_id = %s",
            (new_servings, food_id)
        )

        # Update dailysum
        cursor.execute(
            """
            UPDATE dailysum
            SET dailyCal = dailyCal + %s,
                dailyPro = dailyPro + %s,
                dailyCarb = dailyCarb + %s,
                dailyFat = dailyFat + %s
            WHERE date = CURDATE()
            """,
            (
                food_details['calories'] * diff_servings,
                food_details['protein'] * diff_servings,
                food_details['carb'] * diff_servings,
                food_details['fat'] * diff_servings,
            )
        )

        get_db().commit()
        cursor.close()

        return jsonify({'message': 'Food updated successfully!'})
    except Exception as e:
        print("Error in /update-food:", e)
        return jsonify({'error': str(e)}), 500

    
    
#------------------------------------------------------------------------------------------------------------

@app.route('/delete-food', methods=['POST'])
def delete_food():
    try:
        data = request.get_json()
        food_id = data.get('foodId')

        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT servings, calories, protein, fat, carb FROM fooditem WHERE food_id = %s", (food_id,))
        food_details = cursor.fetchone()

        if not food_details:
            return jsonify({'error': 'Food item not found'}), 404

        # Update dailysum
        cursor.execute(
            """
            UPDATE dailysum
            SET dailyCal = dailyCal - %s,
                dailyPro = dailyPro - %s,
                dailyCarb = dailyCarb - %s,
                dailyFat = dailyFat - %s
            WHERE date = CURDATE()
            """,
            (
                food_details['calories'] * food_details['servings'],
                food_details['protein'] * food_details['servings'],
                food_details['carb'] * food_details['servings'],
                food_details['fat'] * food_details['servings'],
            )
        )

        # Delete fooditem
        cursor.execute("DELETE FROM fooditem WHERE food_id = %s", (food_id,))

        get_db().commit()
        cursor.close()

        return jsonify({'message': 'Food deleted successfully!'})
    except Exception as e:
        print("Error in /delete-food:", e)
        return jsonify({'error': str(e)}), 500

    
#------------------------------------------------------------------------------------------------------------

@app.route('/get-stats', methods=['GET'])
def get_stats():
    try:
        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        query = """
            SELECT date, dailyCal, dailyPro, dailyCarb, dailyFat
            FROM dailysum
            WHERE date >= CURDATE() - INTERVAL 30 DAY
            ORDER BY date ASC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()

        return jsonify(results)
    except Exception as e:
        print("Error in /get-stats:", e)
        return jsonify({'error': str(e)}), 500

    
    
#------------------------------------------------------------------------------------------------------------

@app.route('/calculate-monthly-averages', methods=['POST'])
def calculate_monthly_averages():
    try:
        cursor = get_db().cursor()
        
        # Calculate averages for each month
        for month_id in range(1, 13):
            query = f"""
                UPDATE month
                SET 
                    avgCal = (
                        SELECT AVG(dailyCal)
                        FROM dailysum
                        WHERE MONTH(date) = {month_id}
                    ),
                    avgPro = (
                        SELECT AVG(dailyPro)
                        FROM dailysum
                        WHERE MONTH(date) = {month_id}
                    ),
                    avgCarb = (
                        SELECT AVG(dailyCarb)
                        FROM dailysum
                        WHERE MONTH(date) = {month_id}
                    ),
                    avgFat = (
                        SELECT AVG(dailyFat)
                        FROM dailysum
                        WHERE MONTH(date) = {month_id}
                    )
                WHERE month_id = {month_id};
            """
            cursor.execute(query)
        
        get_db().commit()
        cursor.close()

        return jsonify({'message': 'Monthly averages calculated successfully!'})
    except Exception as e:
        print("Error in /calculate-monthly-averages:", e)
        return jsonify({'error': str(e)}), 500
    

#------------------------------------------------------------------------------------------------------------

@app.route('/get-monthly-averages', methods=['GET'])
def get_monthly_averages():
    try:
        cursor = get_db().cursor(pymysql.cursors.DictCursor)
        query = "SELECT month_name, avgCal, avgPro, avgCarb, avgFat FROM month ORDER BY month_id ASC"
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()

        return jsonify(results)
    except Exception as e:
        print("Error in /get-monthly-averages:", e)
        return jsonify({'error': str(e)}), 500

#------------------------------------------------------------------------------------------------------------

#all the html render routes:


@app.route('/daily-totals-page', methods=['GET'])
def daily_totals_page():
    return render_template('daily_totals.html')

@app.route('/edit-page', methods=['GET'])
def edit_page():
    return render_template('edit.html')

@app.route('/profile-page', methods=['GET'])
def profile_page():
    return render_template('profile.html')

@app.route('/stats-page', methods=['GET'])
def stats_page():
    return render_template('stats.html')

@app.route('/monthly-page', methods=['GET'])
def monthly_page():
    return render_template('monthly.html')





if __name__ == '__main__':
    app.run(debug=True)
