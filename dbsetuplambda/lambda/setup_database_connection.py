import json
import os
import sys

import boto3
import mysql.connector
from botocore.exceptions import ClientError

def get_secret(secret_name):
    region_name = "eu-west-2"
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        print(e)
        raise e
    else:
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
        else:
            print("What? couldnt get secret")
        return json.loads(secret)

os.environ['LIBMYSQL_ENABLE_CLEARTEXT_PLUGIN'] = '1'
credentials = get_secret(os.environ['RDSUserSecretId'])

try:
    print("Try and connect",credentials['host'],credentials['port'])
    conn = mysql.connector.connect(host=credentials['host'], user=credentials['username'],
                                   passwd=credentials['password'],
                                   port=credentials['port'], database=credentials['dbname'], ssl_ca='SSLCERTIFICATE')
    print("Connected")
    cur = conn.cursor()
    cur.execute("""SELECT now()""")
    query_results = cur.fetchall()
    print("Test connection result",query_results)
except Exception as e:
    print("Credentials", credentials)
    print("Database connection failed due to {}".format(e))
    sys.exit(-1)
else:
    conn = conn


