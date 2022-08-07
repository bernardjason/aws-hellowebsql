import json
from setup_database_connection import conn

def lambda_handler(event, context):
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists Message(
                MessageID int NOT NULL auto_increment,
                user_handle varchar(256) NOT NULL,
                message varchar(256) NOT NULL,
                created_when DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (MessageID)
                )
            """
        )
        conn.commit()

        sql = "INSERT INTO Message (user_handle,message) VALUES (%s, %s)"
        val = ("DBCreateTest", "Bernie The Bolt , database setup complete")
        cur.execute(sql, val)

        conn.commit()

        cur.execute(
            "SELECT MessageId,user_handle,message , CAST(created_when AS char) FROM Message order by MessageId desc")

        myresult = cur.fetchall()
        json_body = {"result": "if data returned db ready to use"}

        row = 1
        for x in myresult:
            json_body.update({f"{row}": str(x)})
            row = row + 1
        return {
            'statusCode': 200,
            'body': json.dumps(json_body)
        }
