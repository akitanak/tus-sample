from uuid import uuid4


class UploadData:
    __slots__ = [
        "id",
        "upload_offset",
        "upload_length",
        "upload_defer_length",
        "upload_metadata"
    ]

    def __init__(self, upload_length=None, upload_defer_length=None, metadata={}):
        self.id = uuid4()
        self.upload_offset = 0
        self.upload_length = upload_length
        self.upload_defer_length = upload_defer_length
        self.upload_metadata = metadata


class Database:

    def __init__(self):
        self.uploads = {}

    def add_uploads(self, upload_length=None, upload_defer_length=None, metadata={}):
        upload_data = UploadData(upload_length, upload_defer_length, metadata)
        self.uploads[upload_data.id] = upload_data

        return upload_data

    def get_by_id(self, id):
        return self.uploads.get(id)
    
    def set_upload_length(self, id, upload_length):
        data = self.uploads.get(id)
        data.upload_length = upload_length
        data.upload_defer_length = None
