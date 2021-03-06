from pathlib import Path
import uuid
import re
import base64


import pytest
import api as service


@pytest.fixture
def api():
    return service.api


def base64_encode(value):
    return base64.standard_b64encode(value.encode()).decode()


def base64_decode(value):
    return base64.standard_b64decode(value.encode()).decode()


def test_creation_extension_creates_upload_path(api):
    """
    CREATION extension creates upload path.
    """

    resp = request_creation(100, api)

    assert resp.status_code == 201
    assert resp.headers['Tus-Resumable'] == '1.0.0'
    path = Path(resp.headers['Location'])
    assert path.parent == Path('/files')
    assert_uuid_format(path.name)


def test_creation_extension_can_deferred_the_length_of_upload(api):
    """
    CREATION extension can deferred the length of upload.
    """
    headers = {
        'Upload-Defer-Length': '1',
        'Tus-Resumable': '1.0.0'
    }

    resp = api.requests.post(f'/files', headers=headers)

    assert resp.status_code == 201
    assert resp.headers.get('Upload-Length') is None
    assert resp.headers['Tus-Resumable'] == '1.0.0'
    path = Path(resp.headers['Location'])
    assert path.parent == Path('/files')
    assert_uuid_format(path.name)


def test_creation_extension_can_receive_upload_metadata(api):
    """
    CREATION extension can receive upload metadata.
    """
    metadata1 = 'value1'
    metadata2 = 'value2'

    headers = {
        'Upload-Length': '100',
        'Upload-Metadata': f'key1 {base64_encode(metadata1)},key2 {base64_encode(metadata2)}',
        'Tus-Resumable': '1.0.0'
    }

    resp = api.requests.post(f'/files', headers=headers)

    assert resp.status_code == 201

    resource_path = resp.headers['Location']
    assert resource_path.startswith('/files/')

    resp = api.requests.head(resource_path)

    assert resp.status_code == 200
    upload_metadata = resp.headers['Upload-Metadata']
    metadata = upload_metadata.split(',')
    assert base64_decode(metadata[0].split(' ')[1]) == metadata1
    assert base64_decode(metadata[1].split(' ')[1]) == metadata2


def test_creation_extension_can_receive_upload_concat_header(api):
    """
    CREATION extension can receive Upload-Concat header.
    """
    headers = {
        'Upload-Concat': 'partial',
        'Upload-Length': '100',
        'Tus-Resumable': '1.0.0'
    }

    resp = api.requests.post(f'/files', headers=headers)

    assert resp.status_code == 201
    resource_path = resp.headers['Location']

    resp = api.requests.head(resource_path)

    assert resp.status_code == 200
    assert resp.headers['Upload-Concat'] == 'partial'


def test_creation_extension_responses_400_when_invalid_upload_concat_header_received(api):
    """
    CREATION extension responses 400, when ivalid Upload-Concat header received.
    """
    headers = {
        'Upload-Concat': 'hogehoge',
        'Upload-Length': '100',
        'Tus-Resumable': '1.0.0'
    }

    resp = api.requests.post(f'/files', headers=headers)

    assert resp.status_code == 400


def test_creation_extension_ignore_invalid_metadata(api):
    """
    CREATION extension ignore invalid metadata
    """
    metadata1 = 'value1'
    metadata2 = 'value2'

    headers = {
        'Upload-Length': '100',
        'Upload-Metadata': f'key0,key1 {base64_encode(metadata1)},key2 {base64_encode(metadata2)}',
        'Tus-Resumable': '1.0.0'
    }

    resp = api.requests.post(f'/files', headers=headers)

    assert resp.status_code == 201

    resource_path = resp.headers['Location']
    assert resource_path.startswith('/files/')

    resp = api.requests.head(resource_path)

    assert resp.status_code == 200
    upload_metadata = resp.headers['Upload-Metadata']
    metadata = upload_metadata.split(',')
    assert len(metadata) == 2
    assert base64_decode(metadata[0].split(' ')[1]) == metadata1
    assert base64_decode(metadata[1].split(' ')[1]) == metadata2


def test_creation_extension_response_400_when_upload_defer_length_value_is_not_1(api):
    """
    CREATION extension response 400, when Upload-Defer-Length header value is not 1.
    """
    headers = {
        'Upload-Defer-Length': '0',
        'Tus-Resumable': '1.0.0'
    }

    resp = api.requests.post(f'/files', headers=headers)

    assert resp.status_code == 400


def test_creation_extension_response_400_when_upload_length_and_upload_defer_length_are_not_specified(api):
    """
    CREATION extension response 400, when Upload-Length and Upload-Defer-Length header is not specified.
    """
    headers = {
        'Tus-Resumable': '1.0.0'
    }

    resp = api.requests.post(f'/files', headers=headers)

    assert resp.status_code == 400


def test_creation_extension_response_413_when_upload_length_exceeds_max_size(api):
    """
    CREATION extension responses 413, when Upload-Length exceeds Tus-Max-Size.
    """
    resp = request_creation(1024 ** 3 + 1, api)

    assert resp.status_code == 413


def test_head_request_response_upload_offset_when_resource_exists(api):
    """
    HEAD request responses Upload-Offset header, if resource exists.
    """
    resp = request_creation(100, api)
    assert resp.status_code == 201
    resource_path = resp.headers['Location']
    assert resource_path is not None

    resp = api.requests.head(resource_path)

    assert resp.status_code == 200
    assert resp.headers['Upload-Offset'] == '0'
    assert resp.headers['Upload-Length'] == '100'
    assert resp.headers['Tus-Resumable'] == '1.0.0'
    assert resp.headers['Cache-Control'] == 'no-store'


def test_head_request_response_404_when_resource_does_not_exists(api):
    """
    HEAD request responses 404 Not found, if resource does not exists.
    """
    resource_id = str(uuid.uuid4())

    resp = api.requests.head(f'/files/{resource_id}')

    assert resp.status_code == 404
    assert resp.headers['Tus-Resumable'] == '1.0.0'
    assert resp.headers['Cache-Control'] == 'no-store'
    assert resp.headers.get('Upload-Offset') is None


def test_patch_request_apply_received_bytes_at_given_offset(api):
    """
    PATCH request apply received bytes at given offset and response new offset.
    """
    data = b'abcd\nefgh\nijkl\nmnop\n'
    resp = request_creation(len(data), api)
    assert resp.status_code == 201
    resource_path = resp.headers['Location']

    for i in range(0, 4):
        headers = {
            'Content-Type': 'application/offset+octet-stream',
            'Upload-Offset': f'{i * 5}',
            'Tus-Resumable': '1.0.0'
        }
        resp = api.requests.patch(resource_path, headers=headers, data=data[i*5:(i+1)*5])

        assert resp.status_code == 204
        assert resp.headers['Upload-Offset'] == str((i+1) * 5)
        assert resp.headers['Tus-Resumable'] == '1.0.0'
        assert resp.headers['Cache-Control'] == 'no-store'


def test_patch_request_response_400_when_upload_length_exceeded(api):
    """
    PATCH request response 400, when upload length exceeded.
    """
    data = b'abcd\nefgh\nijkl\nmnop\n'
    resp = request_creation(len(data)-1, api)
    assert resp.status_code == 201
    resource_path = resp.headers['Location']

    for i in range(0, 4):
        headers = {
            'Content-Type': 'application/offset+octet-stream',
            'Upload-Offset': f'{i * 5}',
            'Tus-Resumable': '1.0.0'
        }
        resp = api.requests.patch(resource_path, headers=headers, data=data[i*5:(i+1)*5])

        if i < 3:
            assert resp.status_code == 204
            assert resp.headers['Upload-Offset'] == str((i+1) * 5)
            assert resp.headers['Tus-Resumable'] == '1.0.0'
            assert resp.headers['Cache-Control'] == 'no-store'
        else:
            assert resp.status_code == 400


def test_patch_request_response_404_when_resource_does_not_exists(api):
    """
    PATCH request responses 404 when specified resource does not exists.
    """
    data = b'abcd\nefgh\nijkl\nmnop\n'
    resp = request_creation(len(data), api)
    assert resp.status_code == 201

    headers = {
            'Content-Type': 'application/offset+octet-stream',
            'Upload-Offset': '0',
            'Tus-Resumable': '1.0.0'
        }
    resource_path = f'/files/{str(uuid.uuid4())}'
    resp = api.requests.patch(resource_path, headers=headers, data=data[0:5])

    assert resp.status_code == 404


def test_options_request_response_servers_current_configuration_about_tus(api):
    """
    OPTIONS request responses Servers current configuration about Tus.
    """

    resp = api.requests.options('/files')

    assert resp.headers['Tus-Resumable'] == '1.0.0'
    assert resp.headers['Tus-Version'] == '1.0.0'
    assert resp.headers['Tus-Max-Size'] == str(1024 ** 3)
    assert resp.headers['Tus-Extension'] == 'creation,creation-defer-length'


def test_get_request_response_uploaded_file(api):
    """
    GET responses uploaded file.
    """
    data = b'abcd\nefgh\nijkl\nmnop\n'
    resp = request_creation(len(data), api)
    resource_path = resp.headers['Location']

    for i in range(0, 4):
        headers = {
            'Content-Type': 'application/offset+octet-stream',
            'Upload-Offset': f'{i * 5}',
            'Tus-Resumable': '1.0.0'
        }
        resp = api.requests.patch(resource_path, headers=headers, data=data[i*5:(i+1)*5])

    resp = api.requests.get(resource_path)

    assert resp.content == data


def request_creation(upload_length, api):
    headers = {
        'Content-Length': '0',
        'Upload-Length': str(upload_length),
        'Tus-Resumable': '1.0.0'
    }
    return api.requests.post("/files", headers=headers)


def assert_uuid_format(id):
    uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
    assert re.match(uuid_pattern, id, re.ASCII) is not None
