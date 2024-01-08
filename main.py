from flask import Flask, request, jsonify, send_file
import pyodbc
import pyttsx3
import tempfile
import os


app = Flask(__name__)

# Replace these with your SQL Server details
db_server = 'agridata.hopto.org,5006'
db_name = 'BEE_AFRIFRUIT_07'
db_user = 'sa'
db_password = '456*_ADATA'

# Increase the timeout for database connections
connection_timeout = 10



##MAIN FUNCTIONS TO GET DATA AND GENERATE TEXT
def process_data_from_database(list_queries):
    # Connection string for SQL Server
    connection_string = f'DRIVER=ODBC Driver 17 for SQL Server;SERVER={db_server};DATABASE={db_name};UID={db_user};PWD={db_password};'

    # Establish a connection to the database
    conn = pyodbc.connect(connection_string, timeout=connection_timeout)

    # Create a cursor from the connection
    cursor = conn.cursor()

    try:
        # Example queries (replace with your own queries)
        queries = list_queries
        

        # Execute the queries
        results = []
        for query in queries:
            cursor.execute(query)
            data = cursor.fetchall()
            results.append(data)

        # Process the data (replace with your own processing logic)
        #processed_data = process_data(results)

        return results

    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

def generate_text_for_list(list,unit):
    text = ''
    for i in list:
        text += str(i[0]) + ' avec ' + str(i[1]) + ' ' + str(unit) + ', '
    return text

def generate_text(result):

    ###GENERATE TEXT FOR TEMPLATES
    effectif = "Vous avez un effectif de " + str(result[0][0][0]) + " ouvriers au total."

    ##operations
    if result[1] != []:
        text_operation = "Les 5 opérations les plus importantes sont les suivantes. "+ generate_text_for_list(result[1],'jours-hommes')
    else:
        text_operation = "Aucune opération n'a été réalisée."

    ##production
    if result[2] != []:
        text_tonnage = "La production par variété est la suivante. " + generate_text_for_list(result[2],'kilogrammes')
    else:
        text_tonnage = "Aucune donnée de production par variété."

    ##observation
    observations_urgentes = result[3][0][0]
    observations_urgentes_phyto = result[4][0][0]

    #TEXT TO GENERATE TEMPLATE
    template = f"""Bonjour, voici les éléments marquants de votre ferme pour la période sélectionnée. {effectif}. {text_operation}. {text_tonnage}. {observations_urgentes} observations urgentes ont été créés dans votre ferme, dont {observations_urgentes_phyto} sont liées à la thématique Phytosanitaire.  """                            

    return template 

###API FUNCTION
@app.route('/api', methods=['GET'])
def api_endpoint():
    try:
        # Get the parameters from the request
       # Get JSON data from the request body
        json_data = request.get_json()

        # Extract values from the JSON data
        farm = json_data.get('farm')
        date_debut = json_data.get('date_debut')
        date_fin = json_data.get('date_fin')
        
        # Generate the queries with the parameters
        effectif_aujourdhui = f""" select count(id_personnel) from Presence 
        where date_entree BETWEEN {date_debut} AND {date_fin} and idfermes = {farm}"""
        jourshommes_operation_aujourdhui = f"""SELECT TOP 5 operation, CAST(sum(man_days) as INT) as man_days FROM (

        --subquery to select manadays per operation
        SELECT

            Operation_Ref.OpeRef_Intitule as operation,
            ROUND((Personnel_Pointage.HJ + Personnel_Pointage.HS_NM + Personnel_Pointage.HS_100 + Personnel_Pointage.HS_50 + Personnel_Pointage.HS_25) /  NULLIF(Personnel_Pointage.seuil_horaire,0),0)  AS man_days

            FROM
            Personnel_Pointage
            INNER JOIN Pointage on Personnel_Pointage.IDPointage = Pointage.IDPointage
            INNER JOIN Personnel on personnel.id = Personnel_Pointage.Pers_Id
            INNER JOIN Pointage_ParcelleCulturale ON Pointage_ParcelleCulturale.IDPointage = Pointage.IDPointage
            INNER JOIN ParcelleCulturale on ParcelleCulturale.ID = Pointage_ParcelleCulturale.ParcCul_ID
            INNER JOIN Variete on Variete.ID = ParcelleCulturale.Variete
            INNER JOIN Fermes ON Fermes.IDFermes = Pointage.IDFermes
            INNER JOIN  Parcelle ON Parcelle.ID = ParcelleCulturale.parcelle 
            INNER JOIN Pointage_Operation_REF ON Pointage_Operation_REF.IDPointage = Pointage.IDPointage
            INNER JOIN Operation_REF on Operation_REF.OpeRef_Id = Pointage_Operation_REF.ID_operation_Ref
            WHERE
            Pointage.AFFECTATION = 0
            AND (Pointage.Date between {date_debut} AND {date_fin})
            AND (Pointage.IDFermes in ({farm}))

            GROUP BY Pointage.Date,Personnel.Mat, Pointage.Oper_liste, Personnel_Pointage.HJ,Personnel_Pointage.HS_NM,Personnel_Pointage.HS_100,
            Personnel_Pointage.HS_50,Personnel_Pointage.HS_25,Personnel_Pointage.seuil_horaire, Operation_Ref.OpeRef_Intitule) as t
            
            
            GROUP BY operation
            ORDER BY man_days desc """ 
        production_aujourdhui = f""" 
                select
                temp.Variete as variete,
                SUM(temp.Tonnage) as tonnage
                
                from
                (
                SELECT
                CAST(ROUND(SUM(Exp_Recp_caisse_ParcelleCulturale.Kg_estime * Exp_Recp_caisse_ParcelleCulturale.Qte_caisse),0) as INT) as Tonnage,
                Culture.Culture,
                Variete.Variete
                FROM
                Exp_Recp_caisse_ParcelleCulturale,Parcelle, ParcelleCulturale, Exp_Recp_caisse, Variete, Culture, Fermes
                
                WHERE
                ParcelleCulturale.ID = Exp_Recp_caisse_ParcelleCulturale.ParcelleCulturale
                AND Exp_Recp_caisse.id = Exp_Recp_caisse_ParcelleCulturale.Exp_Recp_caisse
                AND Fermes.IDFermes = ParcelleCulturale.IDFermes
                and Parcelle.ID = ParcelleCulturale.parcelle 
                AND ParcelleCulturale.Variete = Variete.ID
                AND Variete.Culture = Culture.ID
                --AND Exp_Recp_caisse.Client = client.id
                AND ParcelleCulturale.IDFermes in ({farm})
                AND  (Exp_Recp_caisse.DATE BETWEEN {date_debut} AND {date_fin})
                --AND  (Client.Societe NOT LIKE '%PERTE%') /**filtre pour eleminer le client 'PERTE' CHEZ LES DOMAINE*/
                group by Culture.Culture,
                Variete.Variete
            

                ) as temp
                group by  temp.Variete
                order by  tonnage desc
   """
        observations_urgentes_aujourdhui = f"""SELECT count(id) FROM COLAB_observations co where DateCreated BETWEEN {date_debut} AND {date_fin}
        AND importance = 1 and idFerme = '{farm}'"""
        observations_urgentes_phytosanitaires_aujourdhui = f"""SELECT count(id) FROM COLAB_observations co 
        where DateCreated BETWEEN {date_debut} AND {date_fin}
        AND importance = 1
        and idFerme = '{farm}'
        and type = 2"""

        list_queries =  [
            effectif_aujourdhui,
            jourshommes_operation_aujourdhui,
            production_aujourdhui,
            observations_urgentes_aujourdhui,
            observations_urgentes_phytosanitaires_aujourdhui
        ]

        # Get data from the database using the farm parameter
        result = process_data_from_database(list_queries)

        final_text = generate_text(result)

        print(final_text)

        return jsonify({'text': final_text})

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    # Run the Flask app
    app.run(debug=True, threaded=True)
