import os
from uuid import uuid4
from pathlib import Path

import responder

api = responder.API()

global db
db = {}

TUS_VERSION = '1.0.0'
PATCH_REQ_CONTENT_TYPE = 'application/offset+octet-stream'
UPLOAD_LENGTH = 'Upload-Length'
UPLOAD_OFFSET = 'Upload-Offset'
UPLOAD_DEFER_LENGTH = 'Uplpoad-Defer-Length'
TUS_RESUMABLE = 'Tus-Resumable'
LOCATION = 'Location'
CACHE_CONTROL = 'Cache-Control'
CONTENT_TYPE = 'Content-Type'


@api.route('/files')
class Files:
    
    def on_post(self, req, resp):
        """
        Creation extention.
        create upload resource in the Server.
        """
        id = str(uuid4())
        # get request headers
        upload_length = req.headers.get(UPLOAD_LENGTH)
        db[id] = {
            'upload_length': upload_length,
            'upload_offset': 0
        }

        print(db[id])

        resp.headers[TUS_RESUMABLE] = TUS_VERSION
        resp.headers[LOCATION] = f'/files/{id}'
        resp.status_code = api.status_codes.HTTP_201


    def on_options(self, req, resp):
        """
        Options.
        Options returns Server's current configuration.
        It must contain the Tus-Version header.
        And it may contain the Tus-Extension and Tus-Max-Size headers.
        """
        _set_common_headers(resp)

        resp.headers[TUS_RESUMABLE] = TUS_VERSION
        resp.headers['Tus-Version'] = TUS_VERSION
        resp.headers['Tus-Max-Size'] = str(1024 ** 3)
        resp.headers['Tus-Extension'] = 'creation'

        resp.status_code = api.status_codes.HTTP_200


@api.route('/files/{file_id}')
class File:

    def on_head(self, req, resp, *, file_id):
        """
        Head.
        Head returns current Upload-Offset header.
        If the size of the upload is known, Server must 
        include the Upload-Length header.
        """
        data = db.get(file_id)

        _set_common_headers(resp)

        if data is None:
            resp.status_code = api.status_codes.HTTP_404
            return

        resp.headers[UPLOAD_OFFSET] = str(data['upload_offset'])

        upload_length = data.get('upload_length')
        if upload_length is None:
            resp.headers[UPLOAD_DEFER_LENGTH] = str(1)
        else:
            resp.headers[UPLOAD_LENGTH] = str(upload_length)


    async def on_patch(self, req, resp, *, file_id):
        """
        Patch.
        Patch apply the bytes at the given offset.
        Specified resource is not known, it returns 404.
        """
        data = db.get(file_id)

        _set_common_headers(resp)

        if data is None:
            resp.status_code = api.status_codes.HTTP_404
            return

        # check content-type
        content_type = req.headers.get(CONTENT_TYPE)
        if content_type != PATCH_REQ_CONTENT_TYPE:
            resp.status_code = api.status_codes.HTTP_415
            return

        # check offset
        req_offset = req.headers.get(UPLOAD_OFFSET)
        current_offset = data.get('upload_offset')
        
        if req_offset != str(current_offset):
            resp.status_code = api.status_codes.HTTP_409
            return
        
        resp.status_code = api.status_codes.HTTP_204

        patch_data = await req.content
        received_file = Path('/tmp', file_id)

        mode = 'w+b' if current_offset == 0 else 'a+b'
        with open(received_file, mode) as output:
            output.write(patch_data)
        
        current_offset = os.path.getsize(received_file)
        data['upload_offset'] = current_offset

        resp.headers[UPLOAD_OFFSET] = str(current_offset)
        resp.status_code = api.status_codes.HTTP_204
    
    
def _set_common_headers(resp):
    resp.headers[CACHE_CONTROL] = 'no-store'
    resp.headers[TUS_RESUMABLE] = TUS_VERSION


if __name__ == '__main__':
    api.run(port=5000)