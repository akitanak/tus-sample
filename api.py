import os
from uuid import UUID
from pathlib import Path

import responder

from database import Database
import headers

cors_params = {
    'allow_origins': '*',
    'allow_methods': ['GET', 'POST', 'HEAD', 'OPTIONS', 'PATCH'],
    'allow_headers': ['*'],
    'expose_headers': [
        headers.TUS_EXTENSION,
        headers.TUS_MAX_SIZE,
        headers.TUS_RESUMABLE,
        headers.TUS_VERSION,
        headers.UPLOAD_DEFER_LENGTH,
        headers.UPLOAD_LENGTH,
        headers.UPLOAD_METADATA,
        headers.UPLOAD_OFFSET
    ]
}
api = responder.API(cors=True, cors_params=cors_params, allowed_hosts=['*'])

global db
db = Database()

CURRENT_TUS_VERSION = '1.0.0'
SUPPORTED_VERSIONS = [
    '1.0.0'
]
ACCEPTABLE_UPLOAD_SIZE = 1024 ** 3
PATCH_REQ_CONTENT_TYPE = 'application/offset+octet-stream'
AVAILABLE_EXTENSION = [
    'creation',
    'creation-defer-length'
]


@api.route('/')
class Default:
    def on_get(self, req, resp):
        url = api.static_url('js/demo.js')
        resp.content = url


@api.route('/files')
class Files:

    def on_post(self, req, resp):
        """
        Creation extension.
        create upload resource in the Server.
        """
        upload_length = req.headers.get(headers.UPLOAD_LENGTH)
        upload_defer_length = req.headers.get(headers.UPLOAD_DEFER_LENGTH)
        upload_metadata = req.headers.get(headers.UPLOAD_METADATA)

        # Upload-Length header or Upload-Defer-Length header must be specified.
        # And Upload-Defer-Length header must be '1' if it was specified.
        if upload_length is None and upload_defer_length != '1':
            resp.status_code = api.status_codes.HTTP_400
            return

        if upload_metadata is not None:
            upload_metadata = dict(
                [tuple(kv.split(' ')) for kv in upload_metadata.split(',') if len(kv.split(' ')) == 2]
            )

        def set_creation_headers(resp, upload_data):
            resp.headers[headers.TUS_RESUMABLE] = CURRENT_TUS_VERSION
            resp.headers[headers.LOCATION] = f'/files/{upload_data.id}'
            resp.status_code = api.status_codes.HTTP_201

        if upload_length is not None:
            if not upload_length.isdecimal():
                resp.status_code = api.status_codes.HTTP_400
                return

            if int(upload_length) <= ACCEPTABLE_UPLOAD_SIZE:
                upload_data = db.add_uploads(upload_length, metadata=upload_metadata)
                set_creation_headers(resp, upload_data)

            else:
                resp.status_code = api.status_codes.HTTP_413

        else:
            upload_data = db.add_uploads(upload_length=None, upload_defer_length='1', metadata=upload_metadata)
            set_creation_headers(resp, upload_data)

    def on_options(self, req, resp):
        """
        Options.
        Options returns Server's current configuration.
        It must contain the Tus-Version header.
        And it may contain the Tus-Extension and Tus-Max-Size headers.
        """
        _set_common_headers(resp)

        resp.headers[headers.TUS_RESUMABLE] = CURRENT_TUS_VERSION
        resp.headers[headers.TUS_VERSION] = ','.join(SUPPORTED_VERSIONS)
        resp.headers[headers.TUS_MAX_SIZE] = str(ACCEPTABLE_UPLOAD_SIZE)
        resp.headers[headers.TUS_EXTENSION] = ','.join(AVAILABLE_EXTENSION)

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
        upload_data = db.get_by_id(UUID(file_id))

        _set_common_headers(resp)

        if upload_data is None:
            resp.status_code = api.status_codes.HTTP_404
            return

        resp.headers[headers.UPLOAD_OFFSET] = str(upload_data.upload_offset)
        if upload_data.upload_metadata is not None:
            resp.headers[headers.UPLOAD_METADATA] = to_metadata_header(upload_data.upload_metadata)

        if upload_data.upload_length is None:
            resp.headers[headers.UPLOAD_DEFER_LENGTH] = str(1)
        else:
            resp.headers[headers.UPLOAD_LENGTH] = str(upload_data.upload_length)

    def on_get(self, req, resp, *, file_id):
        """
        Get.
        Get responses uploaded file.
        """
        upload_data = db.get_by_id(UUID(file_id))

        if upload_data is None:
            resp.status_code = api.status_codes.HTTP_404
            return

        uploaded_file = Path('/tmp', file_id)

        with open(uploaded_file, mode='rb') as f:
            resp.content = f.read()

    async def on_patch(self, req, resp, *, file_id):
        """
        Patch.
        Patch apply the bytes at the given offset.
        Specified resource is not known, it returns 404.
        """
        upload_data = db.get_by_id(UUID(file_id))

        _set_common_headers(resp)

        if upload_data is None:
            resp.status_code = api.status_codes.HTTP_404
            return

        # check content-type
        content_type = req.headers.get(headers.CONTENT_TYPE)
        if content_type != PATCH_REQ_CONTENT_TYPE:
            resp.status_code = api.status_codes.HTTP_415
            return

        # check offset
        req_offset = req.headers.get(headers.UPLOAD_OFFSET)
        current_offset = upload_data.upload_offset

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
        upload_data.upload_offset = current_offset

        resp.headers[headers.UPLOAD_OFFSET] = str(current_offset)
        resp.status_code = api.status_codes.HTTP_204


def _set_common_headers(resp):
    resp.headers[headers.CACHE_CONTROL] = 'no-store'
    resp.headers[headers.TUS_RESUMABLE] = CURRENT_TUS_VERSION


def to_metadata_header(metadata):
    return ','.join([f'{k} {v}' for k, v in metadata.items()])


if __name__ == '__main__':
    api.run(port=5000)
