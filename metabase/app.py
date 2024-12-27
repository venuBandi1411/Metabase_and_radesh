"""
This is the file responsible for Metabase APIs.
"""

import os
import json
import requests
from flask import Flask, request, jsonify
from langchain_openai import ChatOpenAI
from langchain.chains import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv
import mysql.connector
import psycopg2

# Load environment variables from .env file
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
if db:
    print("Connected to database")
else:
    print("Not connected")

# Initialize the language model
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# Create SQL query chain with the language model and database connection
chain = create_sql_query_chain(llm, db)

app = Flask(__name__)

@app.route('/', methods=['GET'])
def welcome():
    """Welcome endpoint."""
    return "Welcome to Metabase API"

@app.route('/Create_Dashboard', methods=['POST'])
def create_dashboard():
    """Create a new dashboard in Metabase."""
    try:
        url = "http://192.168.1.64:3000/api/dashboard/"
        headers = {
            "Content-Type": "application/json",
            "X-Metabase-Session": "fad9a3b9-85ff-40a4-8062-b04f17dc4cb8"
        }
        data = request.get_json()

        if not data or 'name' not in data or 'description' not in data:
            return jsonify({"error": "Invalid input data"}), 400

        response = requests.post(url, json=data, headers=headers, timeout=10)
        print(response)

        if response.status_code == 200:
            return jsonify(response.json()), 200

        try:
            error_message = response.json()
        except ValueError:
            error_message = {"error": "Invalid response from server"}
        return jsonify(error_message), response.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/query', methods=['POST'])
def query():
    """Handle queries and create visualizations in Metabase."""
    data = request.get_json()
    query = data.get("query", "")

    # graph_type = data.get("graph_type", "bar").lower()
    graph_type="bar"
    
    # col=["id" ,"sales_order"   ,"customer" ,"customer_name" ,"order_date" , "items_count" , "quote_number","created_by","created_date" ,"last_modified_by" , "last_modified_date" ,"quote_id" ,"order_status" , "total_order_valuecustomer_po_number"] 
    if not query:
        return jsonify({"error": "Query is required"}), 400

    # Invoke the chain to get response
    try:
        # prompt = (
        # f" For the follwoing {query} This are the columns {col} that are using in my database"
        # f"by following them in my result use these coloumn names while generating response"
        # )
        response = chain.invoke({"question": query})
        print(response)
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
        print("\t".join(column_names))

        url = "http://192.168.1.64:3000/api/card"

        payload = {
            "name": query,
            "dataset_query": {
                "database": 13,
                "type": "native",
                "native": {
                    "query": response
                }
            },
            "display": graph_type,
            "visualization_settings": {}
        }

        if graph_type == "bar":
            payload["visualization_settings"] = {
                "bar.series_settings": {
                    "series": {
                        "1": {"color": "#33CEFF"},
                        "2": {"color": "#BC33FF"}
                    }
                },
                "graph.metrics": [column_names[0]],
                "graph.dimensions": [column_names[0]]
            }
        elif graph_type == "line":
            payload["visualization_settings"] = {
                "graph.type": "line",
                "graph.colors": ["#33CEFF"],
                "graph.metrics": [column_names[0]],
                "graph.dimensions": [column_names[1]]
            }
        elif graph_type == "pie":
            payload["visualization_settings"] = {
                "pie.labels": {
                    "show_labels": True,
                    "label_field": {"field_ref": {"name": "Created Date"}}
                },
                "graph.metrics": [column_names[0]],
                "graph.dimensions": [column_names[1]],
                "pie.series_settings": {
                    "series": {
                        "1": {"color": "#33CEFF"},
                        "2": {"color": "#BC33FF"}
                    }
                }
            }
        elif graph_type == "area":
            payload["visualization_settings"] = {
                "graph.type": "area",
                "graph.colors": ["#BC33FF"],
                "graph.metrics": [column_names[0]],
                "graph.dimensions": [column_names[1]]
            }
        else:
            payload["visualization_settings"] = {
                "graph.type": "line",
                "graph.colors": ["#33CEFF"],
                "graph.metrics": [column_names[0]],
                "graph.dimensions": [column_names[1]]
            }

        headers = {
            'X-Metabase-Session': 'fad9a3b9-85ff-40a4-8062-b04f17dc4cb8',
            'Content-Type': 'application/json'
        }

        response1 = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        print(response1.status_code, response1.text)

        response_json = response1.json()
        card_id = response_json.get("id")
        print(f"Card ID: {card_id}")
        
        if card_id:
            url = "http://192.168.1.64:3000/api/dashboard/20/cards"

            payload = {
                "cardId": card_id,
                "visualization_settings": {
                    "graph.type": "line",
                    "graph.color": "#33CEFF"
                }
            }

            response2 = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            print(response2.status_code, response2.text)
            return jsonify({"response": response2.text},{"columns":column_names})

        return jsonify({"message": "No ID was generated. Please check the input."})

    except requests.exceptions.RequestException as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="192.168.1.189", port=8080, debug=True)
