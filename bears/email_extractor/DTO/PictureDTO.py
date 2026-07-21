import datetime
from dataclasses import dataclass
@dataclass
class PictureDTO:
    """

    Data Transfer Object for Picture entity
    
    :param id_picture: The unique identifier of the picture.
    :type id_picture: int
    :param filename: The filename of the picture.
    :type filename: str
    :param image_metadata: The metadata of the picture.
    :type image_metadata: bytes
    :param image_type: The type of image.
    :type image_type: str
    :param device_id: The ID of the camera that took the picture.
    :type device_id: str
    :param parsed_successfully: Whether the picture was parsed successfully.
    :type parsed_successfully: bool
    :param timestamp: The timestamp when the picture was taken.
    :type timestamp: datetime.datetime

    """

    def __init__(self, id_picture: int, filename: str, image_metadata: bytes, image_type: str, device_id: str, parsed_successfully: bool, timestamp: datetime.datetime):
        self.id_picture = id_picture
        self.filename = filename
        self.image_metadata = image_metadata
        self.image_type = image_type
        self.device_id = device_id
        self.parsed_successfully = parsed_successfully
        self.timestamp = timestamp