import os
import sys
import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

import scripts.maintenance.r2_manager as r2m

def test_is_sqlite():
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        assert r2m.is_sqlite() is True
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "postgresql://user:pass@host/db"):
        assert r2m.is_sqlite() is False

def test_get_db_path():
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        assert r2m.get_db_path() == "./saa29_local.db"
        
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:////app/data/saa29.db"):
        assert r2m.get_db_path() == "/app/data/saa29.db"
        
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./data.db?timeout=30&cache=shared"):
        assert r2m.get_db_path() == "./data.db"
        
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///app/data/saa29.db"):
        assert r2m.get_db_path() == "/app/data/saa29.db"

@patch("scripts.maintenance.r2_manager.get_s3_client")
def test_backup_db_not_sqlite(mock_get_s3):
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "postgresql://user:pass@host/db"):
        r2m.backup_db()
        mock_get_s3.assert_not_called()

def test_backup_db_file_not_found():
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///nonexistent_file.db"):
        r2m.backup_db()  # should print error and return, not exit

@patch("scripts.maintenance.r2_manager.get_s3_client")
@patch("os.path.exists")
@patch("sqlite3.connect")
@patch("os.remove")
def test_backup_db_success(mock_remove, mock_connect, mock_exists, mock_get_s3):
    mock_exists.side_effect = lambda path: True
    
    mock_s3 = MagicMock()
    mock_get_s3.return_value = mock_s3
    
    mock_conn_src = MagicMock()
    mock_conn_dst = MagicMock()
    mock_connect.side_effect = [mock_conn_src, mock_conn_dst]
    
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        r2m.backup_db()
        
        mock_conn_src.execute.assert_any_call("PRAGMA wal_checkpoint(TRUNCATE);")
        mock_conn_src.backup.assert_called_once_with(mock_conn_dst)
        mock_s3.upload_file.assert_called_once()
        # Verify tmp file removal
        mock_remove.assert_called_once()

@patch("scripts.maintenance.r2_manager.get_s3_client")
@patch("os.path.exists")
@patch("sqlite3.connect")
@patch("os.remove")
def test_backup_db_client_error(mock_remove, mock_connect, mock_exists, mock_get_s3):
    mock_exists.side_effect = lambda path: True
    
    mock_s3 = MagicMock()
    mock_s3.upload_file.side_effect = ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "upload_file")
    mock_get_s3.return_value = mock_s3
    
    mock_conn_src = MagicMock()
    mock_conn_dst = MagicMock()
    mock_connect.side_effect = [mock_conn_src, mock_conn_dst]
    
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        with pytest.raises(SystemExit) as excinfo:
            r2m.backup_db()
        assert excinfo.value.code == 1
        mock_remove.assert_called_once()

@patch("scripts.maintenance.r2_manager.get_s3_client")
def test_restore_db_not_sqlite(mock_get_s3):
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "postgresql://user:pass@host/db"):
        r2m.restore_db()
        mock_get_s3.assert_not_called()

@patch("scripts.maintenance.r2_manager.get_s3_client")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("sqlite3.connect")
@patch("os.replace")
@patch("os.remove")
def test_restore_db_success(mock_remove, mock_replace, mock_connect, mock_makedirs, mock_exists, mock_get_s3):
    mock_exists.return_value = True # Parent directory exists, tmp file doesn't exist initially
    
    mock_s3 = MagicMock()
    mock_get_s3.return_value = mock_s3
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("ok",)
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn
    
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        r2m.restore_db()
        
        mock_s3.head_object.assert_called_once()
        mock_s3.download_file.assert_called_once()
        mock_connect.assert_called_once_with("file:./saa29_local.db.r2tmp?mode=ro", uri=True)
        mock_cursor.execute.assert_any_call("PRAGMA quick_check;")
        mock_replace.assert_called_once_with("./saa29_local.db.r2tmp", "./saa29_local.db")

@patch("scripts.maintenance.r2_manager.get_s3_client")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("sqlite3.connect")
@patch("os.replace")
@patch("os.remove")
def test_restore_db_quick_check_fail(mock_remove, mock_replace, mock_connect, mock_makedirs, mock_exists, mock_get_s3):
    mock_exists.side_effect = lambda path: path.endswith(".r2tmp") # simulate tmp file exists after download
    
    mock_s3 = MagicMock()
    mock_get_s3.return_value = mock_s3
    
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("corrupted",)
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn
    
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        with pytest.raises(SystemExit) as excinfo:
            r2m.restore_db()
        assert excinfo.value.code == 1
        mock_replace.assert_not_called()
        mock_remove.assert_called_with("./saa29_local.db.r2tmp")

@patch("scripts.maintenance.r2_manager.get_s3_client")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("os.remove")
def test_restore_db_404_not_found(mock_remove, mock_makedirs, mock_exists, mock_get_s3):
    mock_exists.side_effect = lambda path: path.endswith(".r2tmp")
    
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "head_object")
    mock_get_s3.return_value = mock_s3
    
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        r2m.restore_db()  # Should not raise SystemExit, just print and return (creating clean local db)
        mock_remove.assert_called_with("./saa29_local.db.r2tmp")

@patch("scripts.maintenance.r2_manager.get_s3_client")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("os.remove")
def test_restore_db_403_critical_error(mock_remove, mock_makedirs, mock_exists, mock_get_s3):
    mock_exists.side_effect = lambda path: path.endswith(".r2tmp")
    
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "head_object")
    mock_get_s3.return_value = mock_s3
    
    with patch("scripts.maintenance.r2_manager.DATABASE_URL", "sqlite+aiosqlite:///./saa29_local.db"):
        with pytest.raises(SystemExit) as excinfo:
            r2m.restore_db()
        assert excinfo.value.code == 1
        mock_remove.assert_called_with("./saa29_local.db.r2tmp")
