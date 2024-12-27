"""
This is the file responsible for Redash APIs.
"""

import ast
import os
import json
import sys
import requests
from flask import Flask, request, jsonify
from langchain_openai import ChatOpenAI
from langchain.chains import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv
import mysql.connector

load_dotenv()
mydb = mysql.connector.connect(
  host="192.168.1.200",
  user="enterpi",
  password="Enterpi314!",
  database="meta-demo"
)
DB_URI = os.getenv("DB_URI")
OPEN_AI_KEY = os.getenv("OPENAI_API_KEY")
print(DB_URI)
# Set OpenAI API key
os.environ["OPENAI_API_KEY"] = OPEN_AI_KEY

# Connect to MySQL database using db_uri from environment variables
db = SQLDatabase.from_uri(DB_URI)


print("Db connection",db)
if db:
    print("Connected to database")
else:
    print("Not connected")

# Initialize the language model
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# Create SQL query chain with the language model and database connection
chain = create_sql_query_chain(llm, db)
print("This is Chain", chain)
app = Flask(__name__)

@app.route('/', methods=['GET'])
def welcome():
    """Welcome endpoint."""
    return "Welcome to Redash API"

@app.route('/Create_Dashboard', methods=['POST'])
def create_dashboard():
    """Create a new Redash dashboard"""
    try:
        url = "http://192.168.1.64/api/dashboards"
        headers = {
            'Authorization': 'CM0GiRXdmbv5NqqUx3kygAmylkcCtT2xJ1laxNSe',
            'Content-Type': 'application/ecmascript',
            }
        data = request.get_json()
       
        print("Received data:", data)
        
        if not data or 'name' not in data or 'layout' not in data or 'widgets' not in data:
            return jsonify({"error": "Invalid input data"}), 400

        response = requests.post(url, headers=headers, json=data)

        print(response.text)

        if response.status_code == 200:
            return jsonify(response.json()), 200

        try:
            error_message = response.json()
        except ValueError:
            error_message = {"error": "Invalid response from server"}
        return jsonify(error_message), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/qurey', methods=['POST'])
def create_query():
    """Handle queries and create visualizations in Metabase."""
    try:
        data = request.get_json()
        query = data.get("query", "")
        print(query)
        if not query:
            return jsonify({"error": "Query is required"}), 400

        # Assuming 'chain' is defined and 'invoke' method is working as intended
        response = chain.invoke({"question": query})
        result = db.run(response)
        print("result", result)

        mycursor = mydb.cursor()
        mycursor.execute(response)

        # Fetch column names
        column_names = [desc[0] for desc in mycursor.description]

        # Fetch all records
        result = mycursor.fetchall()
        print(result)
        for row in result:
            print("\t".join(map(str, row)))
        print("\t".join(column_names),"columns names")
        url = "http://192.168.1.64/api/queries"
        headers = {
            'Authorization': 'CM0GiRXdmbv5NqqUx3kygAmylkcCtT2xJ1laxNSe',
            'Content-Type': 'application/json',
        }
        payload = {
            "query": response,
            "name": "AI generated Query",
            "data_source_id":  15,
            "schedule": None,
            "options": {
                "parameters": [],
                "visualization_settings": {
                    "type": "line",
                    "series":{
                        "color": "red"
                    }
                }
            }
        }
        
        response1 = requests.post(url, headers=headers, json=payload)
        # print(response1.status_code, response1.text)
        # sys.exit()
        if response1.status_code != 200:
            try:
                error_message = response1.json()
            except ValueError:
                error_message = {"error": "Invalid response from server"}
            return jsonify(error_message), response1.status_code

        response_json = response1.json()
        query_id = response_json.get("id")
        print(f"Card ID: {query_id}")

        if query_id:
            url = "http://192.168.1.64/api/visualizations"
            payload = {
            "description": "Testing",
            "name": "AI",
            "options": {
                # "globalSeriesType": "pie",
                "sortX": True,
                "alignYAxesAtZero": False,
                "coefficient": 1,
                "columnMapping": {
                    column_names[0]: "x",
                    column_names[1]: "y"
                },
                "dateTimeFormat": "DD/MM/YY HH:mm",
                "direction": {
                "type": "counterclockwise"
                },
                "error_y": {
                "type": "data",
                "visible": True
                },
                "legend": {
                "enabled": True,
                "placement": "auto",
                "traceorder": "normal"
                },
                "missingValuesAsZero": True,
                "numberFormat": "0,0[.]00000",
                "percentFormat": "0[.]00%",
                "series": {
                "stacking": None,
                "error_y": {
                    "type": "data",
                    "visible": True
                }
                },
                "seriesOptions": {
                "count": {
                    "color": "#F94D16"
                }
                },
                # "showDataLabels": True,
                "sizemode": "diameter",
                "textFormat": "",
                "valuesOptions": {},
                "xAxis": {
                "type": "_",
                "labels": {
                    "enabled": True
                }
                },
                "yAxis": [   {"type": "linear"}, {"type": "linear","opposite": True}]
            },
            "query_id": query_id,
            "type": "CHART"
            }
            
            response2 = requests.post(url, headers=headers, json=payload)
            # print(response2.status_code, response2.text)
            response_json = response2.json()
            # print(response_json)

            visualization_id = response_json.get("id")
            print(visualization_id,"visualization_id")
            if visualization_id:
                url = "http://192.168.1.64/api/widgets"
                payload = {
                    "dashboard_id": 25,  
                    "visualization_id":visualization_id,  
                    "text": "hello",
                    "options": {
                        "isHidden": False,
                        "parameterMappings": {},
                        "position": {"col": 0, "row": 0, "sizeX": 3, "sizeY": 8}
                    },
                    "width": 1
                }
                response3 = requests.post(url, headers=headers, json=payload)
                # print(response3.text)
                return jsonify({"qurey":response},{"response": response3.text},{"columns":column_names})
            if response2.status_code == 200:
                return jsonify({"response": response2.json()}), 200
            else:
                try:
                    error_message = response2.json()
                except ValueError:
                    error_message = {"error": "Invalid response from server"}
                return jsonify(error_message), response2.status_code
        
        return jsonify({"message": "No ID was generated. Please check the input."})


    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="192.168.1.189", port=8081, debug=True)