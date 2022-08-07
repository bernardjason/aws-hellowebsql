import json
import os

print('Loading function')
if __name__ == "__main__":
    os.environ['RDSUserSecretId'] = "arn:aws:secretsmanager:eu-west-2:975820831807:secret:helloworld-admin-EYZiMC"

from setup_database_connection import conn


def handler(event, context):
    print(event)
    if event['resource'] == '/reads':
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT user_handle,message , CAST(created_when AS char) as 'when' FROM Message order by MessageId desc")

            myresult = cur.fetchall()
            json_body = {}
            conn.commit()
            row = 1
            for x in myresult:
                json_body.update({f"{row}": x })
                row = row + 1
    elif event['resource'] == '/updates':
        principal = event["requestContext"]["authorizer"]["principalId"];
        with conn.cursor() as cur:
            body = event["body"]
            request = json.loads(body)
            sql = "INSERT INTO Message (user_handle,message) VALUES (%s, %s)"
            val = (principal, request['message'])
            print(val)
            cur.execute(sql, val)
            conn.commit()
            json_body = {'status': 'success', "update": request}
    else:
        json_body = {'what': 'was that', "request": event}

    return {
        "isBase64Encoded": "false",
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
        },

        "body": json.dumps(json_body)
    }


if __name__ == "__main__":
    event = {
        "headers": {
            "authorization": "hello",
        },
        "body": """{
  "resource": "/reads"
}"""
    }
    print(handler(event, None))
