
import pymysql

def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',       
        password='',  
        db='zoho_order',            
        cursorclass=pymysql.cursors.DictCursor
    )
