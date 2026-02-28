"""FastAPI dependency injection — shared state from app.state."""

from __future__ import annotations

import sqlite3

from fastapi import Request

from config.settings import Settings
from src.storage.repositories import (
    AlertRepository,
    EVSnapshotRepository,
    PackTypeRepository,
    PullRepository,
    SnapshotRepository,
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(request: Request) -> sqlite3.Connection:
    return request.app.state.conn


def get_pull_repo(request: Request) -> PullRepository:
    return PullRepository(request.app.state.conn)


def get_snapshot_repo(request: Request) -> SnapshotRepository:
    return SnapshotRepository(request.app.state.conn)


def get_ev_repo(request: Request) -> EVSnapshotRepository:
    return EVSnapshotRepository(request.app.state.conn)


def get_alert_repo(request: Request) -> AlertRepository:
    return AlertRepository(request.app.state.conn)


def get_pack_type_repo(request: Request) -> PackTypeRepository:
    return PackTypeRepository(request.app.state.conn)


def get_ws_manager(request: Request):
    return request.app.state.ws_manager
