import os
from celery import Celery
from app import app, db, BatchJob, BatchVideo, Video
from pipeline import run_pipeline
from utils import upload_fileobj_to_s3
import requests
import zipfile
import io

celery = Celery('tasks', broker=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
celery.conf.update(
    result_backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery.task(bind=True)
def generate_video_task(self, topic, character, user_id):
    try:
        video_path, s3_url = run_pipeline(topic, character, user_id=user_id, output_dir=f"outputs/user_{user_id}")
        with app.app_context():
            video = Video(
                user_id=user_id,
                title=f"{topic} - {character}",
                topic=topic,
                character=character,
                s3_url=s3_url
            )
            db.session.add(video)
            db.session.commit()
            return video.id
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery.task(bind=True)
def process_batch_video_task(self, batch_video_id):
    with app.app_context():
        bv = BatchVideo.query.get(batch_video_id)
        if not bv:
            return
        batch = BatchJob.query.get(bv.batch_id)
        try:
            bv.status = 'PROCESSING'
            db.session.commit()
            # Pass the batch's user_id to the pipeline
            s3_url = run_pipeline(bv.topic, bv.character, user_id=batch.user_id, output_dir=f"outputs/user_{batch.user_id}/batch_{batch.id}")
            bv.video_url = s3_url
            bv.status = 'COMPLETED'
            db.session.commit()
            batch.completed += 1
            db.session.commit()
        except Exception as e:
            bv.status = 'FAILED'
            bv.error = str(e)
            db.session.commit()
            batch.failed += 1
            db.session.commit()
        finally:
            # Check if batch done
            if batch.completed + batch.failed == batch.total:
                create_zip_for_batch.delay(batch.id)

@celery.task
def create_zip_for_batch(batch_id):
    with app.app_context():
        batch = BatchJob.query.get(batch_id)
        videos = BatchVideo.query.filter_by(batch_id=batch_id, status='COMPLETED').all()
        if not videos:
            batch.status = 'FAILED'
            db.session.commit()
            return

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for v in videos:
                try:
                    response = requests.get(v.video_url)
                    if response.status_code == 200:
                        filename = f"video_{v.row_index+1}_{v.topic[:20]}_{v.character}.mp4".replace(' ', '_')
                        zip_file.writestr(filename, response.content)
                except Exception as e:
                    print(f"Error downloading {v.id}: {e}")

        zip_buffer.seek(0)
        zip_key = f"users/{batch.user_id}/batches/{batch.id}/videos.zip"
        zip_url = upload_fileobj_to_s3(zip_buffer, 'amharic-fairy-tale-videos', zip_key, content_type='application/zip')
        batch.zip_url = zip_url
        batch.status = 'COMPLETED'
        db.session.commit()
