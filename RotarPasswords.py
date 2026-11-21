import boto3
import os
import pymysql
import secrets
import string
from datetime import datetime, timezone

USUARIOS_A_ROTAR = ["user_dev", "user_test", "user_prod"]

def generar_password_seguro(longitud=16):
    caracteres = string.ascii_letters + string.digits + "!@#$%^&*-_"
    while True:
        password = "".join(secrets.choice(caracteres) for _ in range(longitud))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*-_" for c in password)
        ):
            return password

def lambda_handler(event, context):
    ssm = boto3.client("ssm")

    host = ssm.get_parameter(Name=os.environ["SSM_HOST"],WithDecryption=True)["Parameter"]["Value"]

    admin_user = os.environ["DB_ADMIN_USER"]
    admin_password = ssm.get_parameter(Name=os.environ["SSM_ADMIN_PASSWORD"],WithDecryption=True)["Parameter"]["Value"]

    resultados = []
    connection = None

    try:
        connection = pymysql.connect(host=host,user=admin_user,password=admin_password,connect_timeout=10)

        with connection.cursor() as cursor:
            for usuario in USUARIOS_A_ROTAR:
                nuevo_password = generar_password_seguro(16)
                parametro_ssm = f"/rds_mysql_alumnos/{usuario}/password"

                cursor.execute(f"ALTER USER '{usuario}' IDENTIFIED BY %s;",(nuevo_password,))
                cursor.execute("FLUSH PRIVILEGES;")

                ssm_resp = ssm.put_parameter(Name=parametro_ssm,Value=nuevo_password,Type="SecureString",Overwrite=True)

                resultados.append({
                    "usuario": usuario,
                    "parametro_ssm": parametro_ssm,
                    "nueva_version_ssm": ssm_resp["Version"],
                    "estado": "ROTADO"
                })

        connection.commit()

        respuesta = {
            "statusCode": 200,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "rotaciones": resultados
        }
        print(respuesta)
        return respuesta

    except Exception as e:
        error_msg = {"statusCode": 500, "error": str(e)}
        print(error_msg)
        return error_msg

    finally:
        if connection:
            connection.close()