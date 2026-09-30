"""Same-origin Web + explicit live, replay and synchronous inference APIs."""
from contextlib import asynccontextmanager
import csv
from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from kafka.message_schema import validate_sensor_message
from .runtime import PredictionRuntime
from .replay import ReplayController

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


@dataclass
class Settings:
    bootstrap: str = 'localhost:9092'
    prediction_topic: str = 'tep-predictions'
    monitor_topic: str = 'tep-drift-events'
    sensor_topic: str = 'tep-sensor-data'
    consumer_group: str = 'api-snapshots-v1'
    model_dir: Path = ROOT / 'models/production/v1.0.0'
    store_path: Path = ROOT / 'logs/api-snapshots.sqlite3'
    raw_dir: Path = ROOT / 'data/raw/TEP'
    catalog_path: Path = ROOT / 'data/metadata/trajectory_summary.csv'
    web_dir: Path = ROOT / 'web/dist'
    allowed_origins: tuple = ()

    @classmethod
    def from_env(cls):
        return cls(
            bootstrap=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
            prediction_topic=os.getenv('KAFKA_PREDICTION_TOPIC', 'tep-predictions'),
            monitor_topic=os.getenv('KAFKA_DRIFT_TOPIC', 'tep-drift-events'),
            sensor_topic=os.getenv('KAFKA_SENSOR_TOPIC', 'tep-sensor-data'),
            consumer_group=os.getenv('API_CONSUMER_GROUP', 'api-snapshots-v1'),
            model_dir=Path(os.getenv('MODEL_DIR', str(cls.model_dir))),
            store_path=Path(os.getenv('API_STORE_PATH', str(cls.store_path))),
            raw_dir=Path(os.getenv('DATA_RAW_DIR', str(cls.raw_dir))),
            allowed_origins=tuple(filter(None, os.getenv('API_ALLOWED_ORIGINS', '').split(','))),
        )


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    history: list[dict] = Field(min_length=21, max_length=21)


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    trajectory_key: str = Field(min_length=1, max_length=64)
    interval_seconds: float = Field(default=.1, ge=.01, le=10, allow_inf_nan=False)


def create_app(settings=None, runtime=None, replay=None):
    settings = settings or Settings.from_env()
    runtime = runtime or PredictionRuntime(settings)
    with settings.catalog_path.open(encoding='utf-8-sig', newline='') as stream:
        catalog = list(csv.DictReader(stream))
    replay = replay or ReplayController(settings, catalog)

    @asynccontextmanager
    async def lifespan(_app):
        try:
            runtime.start()
            yield
        finally:
            replay.close()
            runtime.close()

    app = FastAPI(title='TEP Live API', version='1.0.0', lifespan=lifespan)
    app.state.runtime, app.state.replay = runtime, replay
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                       allow_methods=['GET', 'POST'], allow_headers=['Content-Type'],
                       expose_headers=['X-Prediction-Received-At'])

    @app.middleware('http')
    async def protect_write_origin(request: Request, call_next):
        # Private Tailscale development service. No Internet exposure or mock auth.
        origin = request.headers.get('origin')
        own = urlsplit(str(request.url))
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and (
            origin != f'{own.scheme}://{own.netloc}' and origin not in settings.allowed_origins
        ):
            return JSONResponse({'detail': 'Cross-origin writes are not allowed'}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith(('/api/', '/v1/', '/health/')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/health/live')
    def live():
        return {'status': 'live'}

    @app.get('/health/ready')
    def ready():
        return JSONResponse({'status': 'ready' if runtime.ready else 'not_ready',
                             'invalid_messages': runtime.invalid_messages,
                             'reader_failed': runtime.failed}, status_code=200 if runtime.ready else 503)

    @app.get('/api/predictions/latest')
    @app.get('/v1/predictions/latest')
    def latest(response: Response, trajectory_key: str | None = None):
        record = runtime.store.latest('prediction', trajectory_key)
        if record is None:
            raise HTTPException(404, 'No prediction received; replay requires 21 sensor rows')
        response.headers['X-Prediction-Received-At'] = record[1]
        return record[0]

    @app.get('/v1/predictions')
    def predictions():
        return {'items': runtime.store.predictions()}

    @app.get('/v1/monitoring/latest')
    def monitoring(trajectory_key: str | None = None):
        record = runtime.store.latest('monitoring', trajectory_key)
        if record is None:
            raise HTTPException(404, 'No operating-state event received yet')
        return {'event': record[0], 'received_at': record[1], 'meaning': 'operating_state_degradation'}

    @app.post('/v1/predict')
    def predict(body: PredictRequest):
        if runtime.predictor is None:
            raise HTTPException(503, 'Model is not ready')
        try:
            first = body.history[0]
            for index, sensor in enumerate(body.history):
                validate_sensor_message(sensor)
                if sensor['trajectory_key'] != first['trajectory_key'] or (
                    sensor['sequence'] != first['sequence'] + index or
                    abs(sensor['timestamp_hours'] - first['timestamp_hours'] - index * .05) > 1e-6
                ):
                    raise ValueError('History must be one contiguous trajectory')
            return runtime.predict(body.history)
        except (ValueError, TypeError, KeyError) as error:
            raise HTTPException(422, str(error)) from error

    @app.get('/v1/trajectories')
    def trajectories():
        return {'items': [dict(row, raw_available=(settings.raw_dir / (row['case']+'.csv')).is_file())
                          for row in catalog]}

    @app.get('/v1/replay')
    def replay_status():
        state = replay.snapshot()
        record = runtime.store.latest('prediction', state.get('trajectory_key')) if state.get('run_id') else None
        current = bool(record and record[1] >= state.get('started_at', ''))
        state['prediction_timestamp_hours'] = record[0]['timestamp_hours'] if current else None
        sent_time = state.get('last_sent_timestamp_hours')
        state['inference_caught_up'] = state.get('sent', 0) < 21 or bool(
            current and sent_time is not None and record[0]['timestamp_hours'] >= sent_time
        )
        return state

    @app.post('/v1/replay/start', status_code=202)
    def start_replay(body: ReplayRequest):
        if not runtime.ready:
            raise HTTPException(503, 'Kafka reader is not ready')
        state = replay_status()
        if state['status'] in ('completed', 'stopped') and not state['inference_caught_up']:
            raise HTTPException(409, 'Previous replay predictions are still processing')
        try:
            return replay.start(body.trajectory_key, body.interval_seconds)
        except FileNotFoundError as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error

    @app.post('/v1/replay/{action}')
    def control_replay(action: str):
        if action not in ('pause', 'resume', 'stop'):
            raise HTTPException(404, 'Unknown replay action')
        try:
            return replay.command(action)
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error

    if settings.web_dir.is_dir():
        app.mount('/', StaticFiles(directory=settings.web_dir, html=True), name='web')
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_app(), host=os.getenv('API_HOST', '0.0.0.0'), port=int(os.getenv('API_PORT', '8000')))
