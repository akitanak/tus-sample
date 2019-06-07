import pytest

from database import Database


@pytest.fixture
def database():
    return Database()


def test_add_uploads_save_new_upload_data(database):
    upload_length = 100
    metadata = {
        'key1': 'value1',
        'key2': 'value2'
    }

    data = database.add_uploads(upload_length=upload_length, metadata=metadata)

    saved = database.uploads.get(data.id)

    assert saved.upload_offset == 0
    assert saved.upload_length == upload_length
    assert saved.upload_defer_length == None
    assert saved.upload_metadata == metadata


def test_get_by_id_returns_matched_upload_data(database):
    upload_length = 100
    metadata = {
        'key1': 'value1',
        'key2': 'value2'
    }
    
    data = database.add_uploads(upload_length=upload_length, metadata=metadata)

    retrieved = database.get_by_id(data.id)

    assert retrieved.id == data.id
    assert retrieved.upload_length == upload_length
    assert retrieved.upload_offset == 0
    assert retrieved.upload_metadata == metadata


def test_set_upload_length(database):
    upload_length = 100
    metadata = {
        'key1': 'value1',
        'key2': 'value2'
    }
    
    data = database.add_uploads(upload_defer_length=1, metadata=metadata)

    dataset = database.set_upload_length(id=data.id, upload_length=upload_length)

    data = database.get_by_id(id=data.id)

    assert data.upload_length == upload_length
    assert data.upload_defer_length is None
