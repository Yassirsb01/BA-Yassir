import mysql.connector
from DTO.PictureDTO import PictureDTO

class DBManager:
    """

    Database Manager to handle connections and operations with the MariaDB database.

    :param conn: The connection object to the database.
    :type conn: mysql.connector.MySQLConnection | None
    :param host: The database host.
    :type host: str
    :param user: The database user.
    :type user: str
    :param password: The database password.
    :type password: str
    :param database: The database name.
    :type database: str

    """
    conn : mysql.connector.MySQLConnection | None
    host : str
    user : str
    password : str
    database : str

    def __init__(self, host, user, password, database):
        """

        Initialize the DBManager with connection parameters.

        :param host: The database host.
        :type host: str
        :param user: The database user.
        :type user: str
        :param password: The database password.
        :type password: str
        :param database: The database name.
        :type database: str

        """
        self.conn = None
        self.host = host
        self.user = user
        self.password = password
        self.database = database
    
    def connect(self):
        """

        Establish a connection to the database.

        """
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=3306
            )
        except mysql.connector.Error as error:
            print(f"During the connection, an error occured : {error}")
            return False
        
    def get_all_pictures(self):
        """

        Retrieve all pictures from the database.

        :return: A list of PictureDTO objects representing all pictures in the database.
        :rtype: list[PictureDTO]
        :raises Exception: If the database connection is not established.

        """
        pictures_dto : list[PictureDTO] = []
        if self.conn is None:
            raise Exception("Before getting data, you need to connect to the database.")
        else:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM wildlife_images;")
            results = cursor.fetchall()
            cursor.close()
            for row in results:
                picture_dto = PictureDTO(
                    id_picture=row[0],
                    filename=row[1],
                    image_metadata=row[2],
                    image_type=row[3],
                    device_id=row[4],
                    parsed_successfully=row[5],
                    timestamp=row[6]
                )
                pictures_dto.append(picture_dto)
            return pictures_dto
        
    def get_picture_by_id(self, picture_id):
        """

        Retrieve a picture from the database by its ID.
        
        :param picture_id: The ID of the picture to retrieve.
        :type picture_id: int
        :return: A PictureDTO object representing the picture, or None if not found.
        :rtype: PictureDTO | None
        :raises Exception: If the database connection is not established.

        """
        if self.conn is None:
            raise Exception("Before getting data, you need to connect to the database.")
        else:
            cursor = self.conn.cursor()
            query = "SELECT * FROM wildlife_images WHERE id = %s;"
            cursor.execute(query, (picture_id,))
            result = cursor.fetchone()
            cursor.close()
            return PictureDTO(
                id_picture=result[0],
                filename=result[1],
                image_metadata=result[2],
                image_type=result[3],
                device_id=result[4],
                parsed_successfully=result[5],
                timestamp=result[6]
            ) if result else None
            
    def verify_device_id_exists(self, device_id):
        """

        Verify if a device ID exists in the database.
        
        :param device_id: The device ID to verify.
        :type device_id: str
        :return: True if the device ID exists, False otherwise.
        :rtype: bool
        :raises Exception: If the database connection is not established.

        """
        if self.conn is None:
            raise Exception("Before verifying data, you need to connect to the database.")
        else:
            cursor = self.conn.cursor()
            query = "SELECT COUNT(*) FROM deterrent_devices WHERE id = %s;"
            cursor.execute(query, (device_id,))
            result = cursor.fetchone()
            cursor.close()
            return result[0] > 0
        
    def create_device(self, device_id, lat=0, lng=0):
        """

        Create a new device in the database.
        
        :param device_id: The device ID to create.
        :type device_id: str
        :param lat: The latitude of the device.
        :type lat: float | None
        :param lng: The longitude of the device.
        :type lng: float | None
        :raises Exception: If the database connection is not established.

        """
        if self.conn is None:
            raise Exception("Before inserting data, you need to connect to the database.")
        else:
            cursor = self.conn.cursor()
            query = "INSERT INTO deterrent_devices (id, directory_name, lat, lng) VALUES (%s, %s, %s, %s);"
            values = (device_id, device_id, lat, lng)
            cursor.execute(query, values)
            self.conn.commit()
            cursor.close()
            
    def insert_picture(self, filename, image_metadata, image_type, device_id, parsed_successfully, timestamp):
        """
        Insert a new picture into the database.
        ...
        """
        if self.conn is None:
            raise Exception("Before inserting data, you need to connect to the database.")
        else:
            if(not self.verify_device_id_exists(device_id)):
                self.create_device(device_id)
            cursor = self.conn.cursor()
        
            # NEU: Schreibe in bears_images_unified (unified Tabelle)
            query = """
            INSERT INTO bears_images_unified 
            (device_id, filename, image_bytes, image_type, source, timestamp, parsed_successfully, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
            values = (device_id, filename, image_metadata, image_type, 'email', timestamp, parsed_successfully)
        
            cursor.execute(query, values)
            self.conn.commit()
            cursor.close()
    

    def disconnect(self):
        """

        Disconnect from the database.
        
        """
        if self.conn is not None and self.conn.is_connected():
            self.conn.close()
            self.conn = None

if __name__ == "__main__":
    pass